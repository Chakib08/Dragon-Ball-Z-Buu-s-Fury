import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat import CombatSystem
from character import Character
from saiyan import Saiyan
from npc import NPC, SaiyanNPC
from utils.config import Config


class CombatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.player = Saiyan(100, 100, False, "goku")
        self.player.update()
        self.player.facing = "Right"
        self.player.animation_name = "IDLE Right"
        self.enemy = NPC(130, 100, False, "vegeta", 0, [])
        self.enemy.update()
        with patch("combat.pygame.time.get_ticks", return_value=0):
            self.combat = CombatSystem(self.player, (1200, 1000))

    def hit(self):
        """Damage one auto attack really does to the enemy."""
        return self.combat.PLAYER_ATTACK_DAMAGE * self.enemy.damage_taken

    def test_player_attack_damages_nearby_enemy_and_spends_ki_once_per_cooldown(self):
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([self.enemy], [], player_attacking=True)
            self.assertEqual(self.enemy.hp, self.enemy.max_hp - self.hit())
            self.assertEqual(self.player.ki, self.player.max_ki - self.combat.PLAYER_ATTACK_COST)

            self.combat.update([self.enemy], [], player_attacking=True)
            self.assertEqual(self.enemy.hp, self.enemy.max_hp - self.hit())

    def test_attacks_hit_in_each_facing_direction_and_ignore_enemies_behind(self):
        for direction in ("Up", "Down", "Left", "Right"):
            with self.subTest(direction=direction):
                self.enemy = NPC(0, 0, False, "vegeta", 0, [])
                self.player.action = None
                self.player.facing = direction
                origin_x, origin_y = self.player.feet.center
                offset = 42
                if direction == "Up":
                    self.enemy.position = [
                        origin_x - self.enemy.rect.width / 2,
                        origin_y - offset - self.enemy.rect.height + 2,
                    ]
                elif direction == "Down":
                    self.enemy.position = [
                        origin_x - self.enemy.rect.width / 2,
                        origin_y + offset - self.enemy.rect.height + 2,
                    ]
                elif direction == "Left":
                    self.enemy.position = [
                        origin_x - offset - self.enemy.rect.width / 2,
                        origin_y - self.enemy.rect.height + 2,
                    ]
                else:
                    self.enemy.position = [
                        origin_x + offset - self.enemy.rect.width / 2,
                        origin_y - self.enemy.rect.height + 2,
                    ]
                self.enemy.update()
                before = self.enemy.hp
                now = 1000
                self.combat.last_player_attack_ms = now - self.player.ATTACK_COOLDOWN_MS

                with patch("combat.pygame.time.get_ticks", return_value=now):
                    self.combat.update([self.enemy], [], player_attacking=True)

                self.assertEqual(self.enemy.hp, before - self.hit())

        self.player.facing = "Right"
        self.enemy = NPC(100, 100, False, "vegeta", 0, [])
        self.enemy.position = [70, 100]
        self.enemy.update()
        before = self.enemy.hp
        ki_before = self.player.ki
        self.player.action = None
        self.combat.last_player_attack_ms = -self.player.ATTACK_COOLDOWN_MS
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([self.enemy], [], player_attacking=True)
        self.assertEqual(self.enemy.hp, before)
        # Swinging at nothing still plays the attack and uses up the cooldown
        self.assertTrue(self.combat.player_swung)
        self.assertEqual(self.player.action["name"], "attack")
        self.assertEqual(self.player.ki, ki_before)
        self.assertEqual(self.combat.last_player_attack_ms, 1000)

    def test_enemy_chases_and_retaliates_after_attack_cooldown(self):
        self.enemy.position = [180, 100]
        self.enemy.update()
        initial_x = self.enemy.position[0]

        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([self.enemy], [])
        self.assertTrue(self.enemy.combat_engaged)
        self.assertLess(self.enemy.position[0], initial_x)
        self.assertEqual(self.player.hp, self.player.max_hp)

        self.enemy.position = [130, 100]
        self.enemy.update()
        with patch("combat.pygame.time.get_ticks", return_value=1001 + self.enemy.attack_cooldown_ms):
            self.combat.update([self.enemy], [])
        self.assertEqual(self.player.hp, self.player.max_hp - self.enemy.attack_damage)

    def test_enemy_can_move_out_of_collision_overlapping_its_spawn(self):
        self.player.position = [159, 289]
        self.player.update()
        self.enemy.position = [174, 374]
        self.enemy.update()
        obstacle = pygame.Rect(8, 400, 208, 20)
        self.assertTrue(self.enemy.feet.colliderect(obstacle))

        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([self.enemy], [obstacle])

        self.assertLess(self.enemy.position[1], 374)

    def test_enemy_paths_around_a_blocking_wall_to_reach_the_player(self):
        self.player.position = [200, 100]
        self.player.update()
        self.enemy.position = [100, 100]
        self.enemy.update()
        wall = pygame.Rect(145, 80, 10, 60)
        start = self.enemy.feet.center

        for frame in range(300):
            with patch("combat.pygame.time.get_ticks", return_value=frame * 17):
                self.combat.update([self.enemy], [wall])
            if self.combat._npc_in_attack_range(self.enemy):
                break

        self.assertNotEqual(self.enemy.feet.center, start)
        self.assertFalse(self.enemy.feet.colliderect(wall))
        self.assertTrue(self.combat._npc_in_attack_range(self.enemy))

    def test_empty_ki_blocks_attacks_and_hud_draws(self):
        self.player.ki = 0
        screen = pygame.Surface((1200, 1000))
        with patch("combat.pygame.time.get_ticks", return_value=0):
            self.combat.update([self.enemy], [], player_attacking=True)
        self.combat.draw(screen)

        self.assertEqual(self.enemy.hp, self.enemy.max_hp)
        self.assertEqual(self.player.ki, 0)
        self.assertNotEqual(screen.get_at((62, 30))[:3], (0, 0, 0))

    def test_ki_regenerates_over_time(self):
        self.player.ki = 50
        with patch("combat.pygame.time.get_ticks", return_value=2000):
            self.combat.update([], [])

        self.assertAlmostEqual(self.player.ki, 50 + self.combat.KI_REGEN_PER_SECOND * 2)

    def test_defeated_enemy_stays_visible_and_stops_fighting(self):
        self.enemy.hp = self.hit()
        group = pygame.sprite.Group(self.enemy)
        enemies = [self.enemy]

        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update(enemies, [], player_attacking=True)

        self.assertEqual(self.enemy.hp, 0)
        self.assertEqual(enemies, [self.enemy])
        self.assertIn(self.enemy, group)
        self.assertTrue(self.enemy.is_defeated)
        self.assertTrue(self.enemy.combat_engaged)

        self.combat.update(enemies, [])
        self.assertEqual(self.enemy.hp, 0)
        self.assertEqual(self.player.hp, self.player.max_hp)

    def test_defeated_enemy_plays_the_faint_animation_once_and_stays_down(self):
        self.enemy.hp = 0
        standing = self.enemy.image
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            for _ in range(200):
                self.combat.update([self.enemy], [])

        self.assertTrue(self.enemy.faint_finished)
        self.assertEqual(self.enemy.faint_index, len(self.enemy.faint_frames) - 1)
        self.assertIs(self.enemy.image, self.enemy.faint_frames[-1])
        self.assertIsNot(self.enemy.image, standing)
        # Frames are padded so the body lies on the ground, not at head height
        self.assertEqual(self.enemy.image.get_height(), self.enemy.rect.height)

    def test_player_faints_at_zero_hp_and_the_enemy_stops_fighting(self):
        for name in ("goku", "gohan", "goten", "vegeta"):
            with self.subTest(character=name):
                player = Saiyan(100, 100, False, name)
                player.update()
                enemy = NPC(110, 100, False, "vegeta", 0, [])
                enemy.update()
                enemy.facing = "Left"
                with patch("combat.pygame.time.get_ticks", return_value=0):
                    combat = CombatSystem(player, (1200, 1000))
                player.hp = 0
                with patch("combat.pygame.time.get_ticks", return_value=5000):
                    for _ in range(200):
                        combat.update([enemy], [], player_attacking=True)

                self.assertTrue(player.faint_finished)
                self.assertEqual(len(player.faint_frames), 4)
                self.assertIs(player.image, player.faint_frames[-1])
                self.assertFalse(enemy.combat_engaged)
                self.assertEqual(enemy.hp, enemy.max_hp)
                self.assertEqual(player.hp, 0)

    def run_action(self, character, limit=400):
        ticks = 0
        while character.update_action():
            ticks += 1
            self.assertLess(ticks, limit)
        return ticks

    def test_super_saiyan_transformation_plays_then_switches_form_and_toggles_back(self):
        for name in ("goku", "gohan", "goten", "vegeta"):
            with self.subTest(character=name):
                player = Saiyan(100, 100, False, name)
                player.update()
                self.assertFalse(player.is_super)
                self.assertTrue(player.transform())
                self.assertEqual(player.action["name"], "transform")
                self.assertFalse(player.is_super)
                self.assertGreater(self.run_action(player), 10)
                self.assertTrue(player.is_super)
                # Walking still works with the Super Saiyan sprites
                player.move("Walk Right", 4)
                self.assertTrue(player.transform())
                self.assertFalse(player.is_super)

    def test_transformation_needs_ki(self):
        self.player.ki = self.player.TRANSFORM_MIN_KI - 1
        self.assertFalse(self.player.transform())
        self.assertIsNone(self.player.action)

    def test_super_saiyan_hits_harder_takes_less_and_reverts_when_ki_runs_out(self):
        self.player.transform()
        self.run_action(self.player)
        self.player.facing = "Right"
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([self.enemy], [], player_attacking=True)
        self.assertEqual(
            self.enemy.hp,
            self.enemy.max_hp - self.hit() * self.combat.SUPER_DAMAGE_MULTIPLIER,
        )
        ki_after_attack = self.player.ki
        self.player.take_damage(10)
        self.assertEqual(self.player.hp, self.player.max_hp - 5)

        with patch("combat.pygame.time.get_ticks", return_value=2000):
            self.combat.update([], [])
        self.assertLess(self.player.ki, ki_after_attack)
        with patch("combat.pygame.time.get_ticks", return_value=60000):
            self.combat.update([], [])
        self.assertEqual(self.player.ki, 0)
        self.assertFalse(self.player.is_super)

    def test_getting_hit_plays_the_hurt_animation_for_player_and_npc(self):
        for character in (self.player, self.enemy):
            with self.subTest(character=type(character).__name__):
                idle = character.image
                character.take_damage(5)
                self.assertEqual(character.action["name"], "hurt")
                self.assertIsNot(character.image, idle)
                self.run_action(character)
                self.assertIsNone(character.action)

    def test_hurt_npc_flinches_instead_of_attacking(self):
        self.enemy.position = [self.player.position[0] + 10, self.player.position[1]]
        self.enemy.update()
        self.enemy.facing = "Left"
        self.enemy.combat_engaged = True
        self.enemy.take_damage(5)
        with patch("combat.pygame.time.get_ticks", return_value=5000):
            self.combat.update([self.enemy], [])
        self.assertEqual(self.player.hp, self.player.max_hp)

    def test_special_charges_then_fires_a_beam_that_damages_the_enemy_in_front(self):
        self.enemy.position = [self.player.position[0] + 120, self.player.position[1]]
        self.enemy.update()
        with patch("combat.pygame.time.get_ticks", return_value=5000):
            self.assertTrue(self.combat.start_special())
            self.assertEqual(self.player.ki, self.player.max_ki - self.combat.SPECIAL_COST)
            # Busy and on cooldown: a second press does nothing
            self.assertFalse(self.combat.start_special())
            self.assertEqual(self.combat.beams, [])
            for _ in range(200):
                self.player.update_action()
                self.combat.update([self.enemy], [])

        self.assertEqual(self.enemy.hp, self.enemy.max_hp - self.combat.SPECIAL_DAMAGE * self.enemy.damage_taken)
        self.assertEqual(self.combat.beams, [])
        self.assertIsNone(self.player.action)

    def test_special_misses_enemies_that_are_not_in_the_line_of_fire(self):
        self.enemy.position = [self.player.position[0], self.player.position[1] + 120]
        self.enemy.update()
        with patch("combat.pygame.time.get_ticks", return_value=5000):
            self.assertTrue(self.combat.start_special())
            for _ in range(200):
                self.player.update_action()
                self.combat.update([], [])
                self.combat._update_beams([self.enemy])
        self.assertEqual(self.enemy.hp, self.enemy.max_hp)

    def test_special_needs_ki_and_beams_can_be_drawn(self):
        self.player.ki = self.combat.SPECIAL_COST - 1
        with patch("combat.pygame.time.get_ticks", return_value=5000):
            self.assertFalse(self.combat.start_special())
        self.combat._fire_beam("Right")
        self.combat._update_beams([])
        screen = pygame.Surface((400, 400))
        self.combat.draw_beams(screen, lambda rect: rect)
        tip = self.combat._beam_rect(self.combat.beams[0]).midright
        self.assertNotEqual(screen.get_at(tip)[:3], (0, 0, 0))

    def test_player_and_npc_attack_at_the_same_pace(self):
        self.assertEqual(self.player.ATTACK_COOLDOWN_MS, self.enemy.attack_cooldown_ms)
        self.assertEqual(self.player.ATTACK_CLOCK_SPEED, self.enemy.ATTACK_CLOCK_SPEED)
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([self.enemy], [], player_attacking=True)
        self.player.action = None
        with patch("combat.pygame.time.get_ticks", return_value=999 + self.player.ATTACK_COOLDOWN_MS):
            self.combat.update([self.enemy], [], player_attacking=True)
            self.assertFalse(self.combat.player_swung)
        self.assertEqual(self.enemy.hp, self.enemy.max_hp - self.hit())
        with patch("combat.pygame.time.get_ticks", return_value=1000 + self.player.ATTACK_COOLDOWN_MS):
            self.combat.update([self.enemy], [], player_attacking=True)
            self.assertTrue(self.combat.player_swung)
        self.assertEqual(self.enemy.hp, self.enemy.max_hp - 2 * self.hit())

    def test_no_attack_while_busy_with_another_action(self):
        self.player.take_damage(1)
        self.assertEqual(self.player.action["name"], "hurt")
        with patch("combat.pygame.time.get_ticks", return_value=5000):
            self.combat.update([self.enemy], [], player_attacking=True)
        self.assertFalse(self.combat.player_swung)
        self.assertEqual(self.enemy.hp, self.enemy.max_hp)

    def test_npc_is_tough_enough_for_a_long_fight(self):
        hits_to_win = self.enemy.max_hp / self.hit()
        self.assertGreaterEqual(hits_to_win, 15)
        self.assertLess(self.enemy.damage_taken, 1)

    def test_fast_attacks_cannot_keep_the_npc_stunned(self):
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.enemy.take_damage(5)
            self.assertEqual(self.enemy.action["name"], "hurt")
            self.run_action(self.enemy)
        with patch("combat.pygame.time.get_ticks", return_value=1000 + self.player.ATTACK_COOLDOWN_MS):
            self.enemy.take_damage(5)
            self.assertIsNone(self.enemy.action)
        with patch("combat.pygame.time.get_ticks", return_value=1001 + self.enemy.FLINCH_COOLDOWN_MS):
            self.enemy.take_damage(5)
            self.assertEqual(self.enemy.action["name"], "hurt")

    def saiyan_enemy_next_to_player(self):
        enemy = SaiyanNPC(self.player.position[0] + 10, self.player.position[1], False, "vegeta", 0, [])
        enemy.update()
        enemy.facing = "Left"
        return enemy

    def test_saiyan_npc_goes_super_saiyan_at_half_health_and_hits_harder(self):
        enemy = self.saiyan_enemy_next_to_player()
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([enemy], [])
            self.assertFalse(enemy.is_super)
            self.assertIsNone(enemy.action)

            enemy.hp = enemy.max_hp * enemy.TRANSFORM_AT_HP
            enemy.last_flinch_ms = 1000
            self.combat.update([enemy], [])
            self.assertEqual(enemy.action["name"], "transform")
            # Hits do not interrupt the transformation
            enemy.take_damage(5)
            self.assertEqual(enemy.action["name"], "transform")
            for _ in range(300):
                self.combat.update([enemy], [])
                if enemy.is_super:
                    break
        self.assertTrue(enemy.is_super)

        hp = self.player.hp
        with patch("combat.pygame.time.get_ticks", return_value=5000):
            self.combat.update([enemy], [])
            self.combat.update([enemy], [])
        self.assertEqual(hp - self.player.hp, enemy.attack_damage * self.combat.SUPER_DAMAGE_MULTIPLIER)

        # A Super Saiyan NPC is also harder to hurt, and faints in base form
        before = enemy.hp
        enemy.take_damage(10)
        self.assertEqual(before - enemy.hp, 10 * enemy.damage_taken * enemy.SUPER_DAMAGE_TAKEN)
        enemy.hp = 0
        with patch("combat.pygame.time.get_ticks", return_value=6000):
            for _ in range(100):
                self.combat.update([enemy], [])
        self.assertTrue(enemy.faint_finished)
        self.assertFalse(enemy.is_super)

    def test_non_saiyan_npc_never_transforms(self):
        self.enemy.position = [self.player.position[0] + 10, self.player.position[1]]
        self.enemy.update()
        self.enemy.hp = 1
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            for _ in range(50):
                self.combat.update([self.enemy], [])
        self.assertFalse(self.enemy.can_transform)
        self.assertFalse(self.enemy.is_super)
        self.assertFalse(Character(0, 0, "goku").transform())

    def test_npc_health_bar_follows_hp_and_disappears_after_the_faint(self):
        screen = pygame.Surface((200, 200))
        self.enemy.position = [100, 100]
        self.enemy.update()
        bar_y = self.enemy.rect.top - self.combat.NPC_BAR_GAP - self.combat.NPC_BAR_HEIGHT // 2
        left = (self.enemy.rect.centerx - 20, bar_y)
        right = (self.enemy.rect.centerx + 20, bar_y)
        red, empty = (220, 55, 55), (35, 35, 42)

        self.combat.draw_npc_bars(screen, [self.enemy], lambda rect: rect)
        self.assertEqual(screen.get_at(left)[:3], red)
        self.assertEqual(screen.get_at(right)[:3], red)

        self.enemy.hp = self.enemy.max_hp / 2
        self.combat.draw_npc_bars(screen, [self.enemy], lambda rect: rect)
        self.assertEqual(screen.get_at(left)[:3], red)
        self.assertEqual(screen.get_at(right)[:3], empty)

        screen.fill((0, 0, 0))
        self.enemy.faint_finished = True
        self.combat.draw_npc_bars(screen, [self.enemy], lambda rect: rect)
        self.assertEqual(screen.get_at(left)[:3], (0, 0, 0))

    def test_each_strike_is_one_move_of_the_combo_and_they_cycle(self):
        for name, expected_moves in (("goku", 3), ("gohan", 4), ("goten", 4), ("vegeta", 4)):
            with self.subTest(character=name):
                fighter = Saiyan(100, 100, False, name)
                fighter.facing = "Right"
                moves = fighter.get_attack_moves("Right")
                self.assertEqual(len(moves), expected_moves)
                self.assertEqual(sum(len(move) for move in moves), 12)

                played = []
                for _ in range(expected_moves + 1):
                    self.assertTrue(fighter.strike())
                    self.assertEqual(fighter.action["name"], "attack")
                    played.append(fighter.action["frames"])
                    # A single punch or kick is short: well under the cooldown
                    ticks = self.run_action(fighter)
                    self.assertLess(ticks * 1000 / 60, fighter.ATTACK_COOLDOWN_MS)
                self.assertEqual(played[:expected_moves], moves)
                # After the last move the combo starts over
                self.assertEqual(played[expected_moves], moves[0])
                self.assertIsNone(fighter.action)

    def test_left_strikes_are_mirrored(self):
        right = self.player.get_attack_moves("Right")[0][0]
        left = self.player.get_attack_moves("Left")[0][0]
        self.assertIsNot(left, right)
        self.assertEqual(left.get_size(), right.get_size())


if __name__ == "__main__":
    unittest.main()
