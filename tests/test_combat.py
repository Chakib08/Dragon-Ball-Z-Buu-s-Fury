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
from movement import resolve_movement_collisions, solid_bodies
from utils.config import Config
from average_stats import use_average_stats


class CombatTests(unittest.TestCase):
    # Characters with both a base and a Super Saiyan sheet downloaded
    TRANSFORMING = ("goku",)
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        use_average_stats(self)
        self.player = Saiyan(100, 100, False, "goku")
        self.player.update()
        self.player.facing = "Right"
        self.player.animation_name = "IDLE Right"
        # Feet 15 map pixels apart: within melee reach
        self.enemy = NPC(120, 100, False, "gohan", 0, [])
        self.place(self.enemy, 15)
        # Punches only: the tests of NPC techniques turn them back on
        self.enemy.next_technique_ms = float("inf")

    def place(self, fighter, gap):
        """Put fighter gap map pixels right of the player (feet to feet)."""
        fighter.position = [self.player.feet.centerx + gap - fighter.rect.width / 2,
                            self.player.position[1] + self.player.rect.height - fighter.rect.height]
        fighter.update()
        with patch("combat.pygame.time.get_ticks", return_value=0):
            self.combat = CombatSystem(self.player, (1200, 1000))

    def hit(self):
        """Damage one auto attack really does to the enemy."""
        return self.combat.PLAYER_ATTACK_DAMAGE * self.enemy.damage_taken

    def test_player_attack_damages_nearby_enemy_once_per_cooldown_and_costs_no_ki(self):
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([self.enemy], [], player_attacking=True)
            self.assertEqual(self.enemy.hp, self.enemy.max_hp - self.hit())
            self.assertEqual(self.player.ki, self.player.max_ki)

            self.combat.update([self.enemy], [], player_attacking=True)
            self.assertEqual(self.enemy.hp, self.enemy.max_hp - self.hit())

    def test_attacks_hit_in_each_facing_direction_and_ignore_enemies_behind(self):
        for direction in ("Up", "Down", "Left", "Right"):
            with self.subTest(direction=direction):
                self.enemy = NPC(0, 0, False, "gohan", 0, [])
                self.player.action = None
                self.player.facing = direction
                origin_x, origin_y = self.player.feet.center
                offset = 16
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
        self.enemy = NPC(100, 100, False, "gohan", 0, [])
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

        self.place(self.enemy, 15)
        reached = 1001 + self.enemy.attack_cooldown_ms
        with patch("combat.pygame.time.get_ticks", return_value=reached):
            self.combat.update([self.enemy], [])
        # Just stepped into reach: the enemy reacts a moment later
        self.assertEqual(self.player.hp, self.player.max_hp)
        with patch("combat.pygame.time.get_ticks", return_value=reached + self.enemy.reaction_ms):
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
            if self.combat.ai.in_attack_range(self.enemy):
                break

        self.assertNotEqual(self.enemy.feet.center, start)
        self.assertFalse(self.enemy.feet.colliderect(wall))
        self.assertTrue(self.combat.ai.in_attack_range(self.enemy))

    def test_attacking_works_with_empty_ki_and_hud_draws(self):
        self.player.ki = 0
        screen = pygame.Surface((1200, 1000))
        with patch("combat.pygame.time.get_ticks", return_value=0):
            self.combat.update([self.enemy], [], player_attacking=True)
        self.combat.draw(screen)

        self.assertLess(self.enemy.hp, self.enemy.max_hp)
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
        for name in ("goku", "gohan", "vegeta", "trunks", "broly"):
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
        for name in self.TRANSFORMING:
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

    def test_super_saiyan_walks_and_runs_faster(self):
        for macro, base in (("Walk Right", self.player.walk_speed), ("Run Right", self.player.run_speed)):
            with self.subTest(move=macro):
                fighter = Saiyan(100, 100, False, "goku")
                start = fighter.position[0]
                fighter.move(macro, 4)
                normal = fighter.position[0] - start
                fighter.transform()
                while fighter.update_action():
                    pass
                start = fighter.position[0]
                fighter.move(macro, 4)
                self.assertEqual(normal, base)
                self.assertAlmostEqual(fighter.position[0] - start, base * fighter.SUPER_SPEED_MULTIPLIER)

    def test_transformation_needs_ki(self):
        self.player.ki = self.player.TRANSFORM_MIN_KI["ssj"] - 1
        self.assertFalse(self.player.transform())
        self.assertIsNone(self.player.action)

    def test_goku_chooses_between_ssj_and_ssj3_and_gohan_has_no_choice(self):
        self.assertEqual(self.player.super_levels, ["ssj", "ssj3"])
        self.assertEqual(self.player.target_level, "ssj")
        self.player.cycle_level(1)
        self.assertEqual(self.player.target_level, "ssj3")
        self.player.cycle_level(1)
        self.assertEqual(self.player.target_level, "ssj")
        self.player.cycle_level(-1)
        self.assertEqual(self.player.target_level, "ssj3")
        gohan = Saiyan(100, 100, False, "gohan")
        self.assertLessEqual(len(gohan.super_levels), 1)

    def test_ssj3_transformation_plays_its_own_aura_then_reverts(self):
        self.player.cycle_level(1)
        self.assertTrue(self.player.transform())
        self.assertEqual(self.player.action["name"], "transform")
        self.assertGreater(self.run_action(self.player), 10)
        self.assertEqual(self.player.form, "ssj3")
        self.assertTrue(self.player.is_super)
        # Pressing transform again at the chosen level goes back to base
        self.assertTrue(self.player.transform())
        self.assertFalse(self.player.is_super)

    def test_switching_from_ssj_to_ssj3_while_transformed(self):
        self.player.transform()
        self.run_action(self.player)
        self.assertEqual(self.player.form, "ssj")
        self.player.cycle_level(1)
        self.assertTrue(self.player.transform())
        self.run_action(self.player)
        self.assertEqual(self.player.form, "ssj3")

    def test_ssj3_needs_more_ki(self):
        self.player.cycle_level(1)
        self.player.ki = self.player.TRANSFORM_MIN_KI["ssj3"] - 1
        self.assertGreater(self.player.ki, self.player.TRANSFORM_MIN_KI["ssj"])
        self.assertFalse(self.player.transform())
        self.assertIsNone(self.player.action)

    def test_ssj3_hits_harder_than_ssj_and_drains_ki_faster(self):
        drained = {}
        for level, multiplier in ((0, self.combat.SUPER_DAMAGE_MULTIPLIER),
                                  (1, self.combat.SUPER_3_DAMAGE_MULTIPLIER)):
            with self.subTest(level=level):
                self.setUp()
                self.player.selected_level = level
                self.player.transform()
                self.run_action(self.player)
                self.player.facing = "Right"
                with patch("combat.pygame.time.get_ticks", return_value=1000):
                    self.combat.update([self.enemy], [], player_attacking=True)
                self.assertAlmostEqual(self.enemy.hp, self.enemy.max_hp - self.hit() * multiplier)
                ki = self.player.ki
                with patch("combat.pygame.time.get_ticks", return_value=11_000):
                    self.combat.update([], [])
                drained[self.player.form] = ki - self.player.ki
        self.assertGreater(self.combat.SUPER_3_DAMAGE_MULTIPLIER, self.combat.SUPER_DAMAGE_MULTIPLIER)
        self.assertGreater(drained["ssj3"], drained["ssj"])

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
        # The drain is slow: about 100 s for a full bar
        with patch("combat.pygame.time.get_ticks", return_value=200_000):
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

    def test_player_and_npc_flinch_on_every_hit(self):
        with patch("character.pygame.time.get_ticks", return_value=1000):
            for fighter in (self.player, self.enemy):
                for _ in range(3):
                    fighter.action = None
                    fighter.take_damage(1)
                    self.assertEqual(fighter.action["name"], "hurt")

    def test_hurt_npc_flinches_instead_of_attacking(self):
        self.enemy.position = [self.player.position[0] + 10, self.player.position[1]]
        self.enemy.update()
        self.enemy.facing = "Left"
        self.enemy.combat_engaged = True
        self.enemy.take_damage(5)
        with patch("combat.pygame.time.get_ticks", return_value=5000):
            self.combat.update([self.enemy], [])
        self.assertEqual(self.player.hp, self.player.max_hp)

    def test_attacks_only_land_when_the_bodies_nearly_touch(self):
        for gap, lands in ((15, True), (22, True), (30, False)):
            with self.subTest(gap=gap):
                enemy = NPC(0, 0, False, "gohan", 0, [])
                enemy.position = [
                    self.player.feet.centerx + gap - enemy.rect.width / 2,
                    self.player.feet.bottom - enemy.rect.height,
                ]
                enemy.update()
                self.player.facing = "Right"
                self.assertEqual(self.combat._is_in_attack_range(enemy), lands)
                enemy.facing = "Left"
                self.assertEqual(self.combat.ai.in_attack_range(enemy), lands)

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

    def tick(self, now, enemies, attacking=False):
        with patch("combat.pygame.time.get_ticks", return_value=now), \
                patch("character.pygame.time.get_ticks", return_value=now), \
                patch("npc.pygame.time.get_ticks", return_value=now):
            self.combat.update(enemies, [], player_attacking=attacking)

    def enemy_in_reach(self):
        self.enemy.position = [self.player.position[0] + 12, self.player.position[1]]
        self.enemy.update()
        self.enemy.facing = "Left"
        self.enemy.combat_engaged = True
        self.enemy.attack_damage = 1

    def test_npc_guards_after_two_quick_hits_then_ripostes(self):
        self.enemy_in_reach()
        now = 1000
        with patch("npc.pygame.time.get_ticks", return_value=now), \
                patch("character.pygame.time.get_ticks", return_value=now):
            self.enemy.take_damage(1, self.player.feet.center)
        with patch("npc.pygame.time.get_ticks", return_value=now + 300), \
                patch("character.pygame.time.get_ticks", return_value=now + 300):
            self.enemy.take_damage(1, self.player.feet.center)
        self.assertTrue(self.enemy.wants_guard)
        # Last attack just now: without the riposte it would have to wait
        self.enemy.last_attack_ms = now + 300
        guarded = False
        now += 300
        while now < 3000 and not guarded:
            now += 17
            self.enemy.knockback = None
            self.tick(now, [self.enemy])
            guarded = self.enemy.blocking
        self.assertTrue(guarded)
        self.assertEqual(self.enemy.animation_name, "Block Left")
        # A hit on the guard: half damage, no new flinch
        before = self.enemy.hp
        with patch("npc.pygame.time.get_ticks", return_value=now), \
                patch("character.pygame.time.get_ticks", return_value=now):
            self.enemy.take_damage(10)
        self.assertAlmostEqual(before - self.enemy.hp, 10 * self.enemy.damage_taken * self.enemy.BLOCK_DAMAGE_TAKEN)
        self.assertIsNone(self.enemy.action)
        # Guard drops after GUARD_MS and the riposte lands at once
        hp = self.player.hp
        guard_end = now + self.enemy.guard_ms
        while now <= guard_end + 17:
            now += 17
            self.enemy.knockback = None
            self.tick(now, [self.enemy])
        self.assertFalse(self.enemy.blocking)
        self.assertLess(self.player.hp, hp)
        self.assertLess(now - self.enemy.last_attack_ms, self.enemy.attack_cooldown_ms)

    def test_a_push_out_of_reach_does_not_restart_the_reaction_time(self):
        self.enemy_in_reach()
        now = 1000
        self.enemy.last_attack_ms = -10000
        self.tick(now, [self.enemy])  # steps into reach: reaction starts
        reach_start = self.enemy.in_reach_since
        # Pushed just out of reach for a moment, then back in
        self.enemy.position[0] += 15
        self.enemy.update()
        self.tick(now + 100, [self.enemy])
        self.enemy.position[0] -= 15
        self.enemy.update()
        self.assertEqual(self.enemy.in_reach_since, reach_start)
        hp = self.player.hp
        self.tick(now + self.enemy.reaction_ms + 1, [self.enemy])
        self.assertLess(self.player.hp, hp)

    def test_npc_turns_to_face_a_player_beside_or_behind_it(self):
        self.enemy_in_reach()
        self.enemy.facing = "Right"  # back turned to the player
        self.enemy.last_attack_ms = -10000
        hp = self.player.hp
        for step in range(30):
            self.tick(1000 + step * 17, [self.enemy])
        self.assertEqual(self.enemy.facing, "Left")
        self.assertLess(self.player.hp, hp)

    def test_fast_attacks_cannot_keep_the_npc_stunned(self):
        """Hit on every frame, the NPC still strikes back when its strike is due."""
        self.enemy.position = [self.player.position[0] + 12, self.player.position[1]]
        self.enemy.update()
        self.enemy.facing = "Left"
        self.enemy.combat_engaged = True
        now = 1000
        struck = False
        for _ in range(120):
            now += 17
            with patch("combat.pygame.time.get_ticks", return_value=now), \
                    patch("character.pygame.time.get_ticks", return_value=now):
                self.enemy.take_damage(0.01)
                self.enemy.knockback = None
                hp = self.player.hp
                self.combat.update([self.enemy], [])
                struck = struck or self.player.hp < hp
        self.assertTrue(struck)

    def saiyan_enemy_next_to_player(self):
        enemy = SaiyanNPC(self.player.position[0] + 10, self.player.position[1], False, "goku", 0, [])
        enemy.update()
        enemy.facing = "Left"
        return enemy

    def test_saiyan_npc_goes_super_saiyan_at_half_health_and_hits_harder(self):
        enemy = self.saiyan_enemy_next_to_player()
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([enemy], [])
            self.assertFalse(enemy.is_super)
            self.assertIsNone(enemy.action)

            enemy.hp = enemy.max_hp * enemy.transform_at_hp
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
        self.assertEqual(hp - self.player.hp, enemy.attack_damage * self.combat.NPC_SUPER_DAMAGE_MULTIPLIER)

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

    def test_super_saiyan_only_npc_starts_transformed_and_stays_that_way(self):
        with self.super_saiyan_only():
            enemy = SaiyanNPC(self.player.position[0] + 10, self.player.position[1], False, "vegeta", 0, [])
        self.place(enemy, 12)
        self.assertTrue(enemy.is_super)
        self.assertFalse(enemy.can_revert)
        self.assertFalse(enemy.transform())
        # Looks like a Super Saiyan, but fights like one only once powered up
        self.assertFalse(enemy.powered_up)
        hp = self.player.hp
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([enemy], [])
        with patch("combat.pygame.time.get_ticks", return_value=1000 + enemy.attack_cooldown_ms):
            self.combat.update([enemy], [])
        self.assertEqual(hp - self.player.hp, enemy.attack_damage)
        enemy.hp = enemy.max_hp * enemy.transform_at_hp
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            for _ in range(50):
                self.combat.update([enemy], [])
        self.assertTrue(enemy.is_super)
        self.assertTrue(enemy.powered_up)
        self.assertIsNone(enemy.action)  # no transformation animation to play
        # Knocked out without knock-out sprites: lies in the hurt pose
        enemy.hp = 0
        with patch("combat.pygame.time.get_ticks", return_value=2000):
            for _ in range(50):
                self.combat.update([enemy], [])
        self.assertTrue(enemy.faint_finished)
        self.assertEqual(len(enemy.faint_frames), 1)

    @staticmethod
    def super_saiyan_only():
        """As if only the Super Saiyan sheets had been downloaded."""
        return patch("animation.SpriteForm.sheet_exists", side_effect=lambda path: not path.endswith("base.json"))

    def test_super_saiyan_only_player_keeps_ki(self):
        with self.super_saiyan_only():
            player = Saiyan(100, 100, False, "vegeta")
        with patch("combat.pygame.time.get_ticks", return_value=0):
            combat = CombatSystem(player, (1200, 1000))
        player.ki = 50
        with patch("combat.pygame.time.get_ticks", return_value=2000):
            combat.update([], [])
        self.assertGreater(player.ki, 50)
        self.assertTrue(player.is_super)

    def test_difficulty_makes_an_enemy_stronger_or_weaker(self):
        normal = NPC(0, 0, False, "gohan", 0, [], difficulty="normal")
        hard = NPC(0, 0, False, "gohan", 0, [], difficulty="hard")
        easy = NPC(0, 0, False, "gohan", 0, [], difficulty="easy")
        # Normal is the enemy as it always was
        self.assertEqual(normal.max_hp, NPC.MAX_HP)
        self.assertEqual(normal.attack_damage, NPC.ATTACK_DAMAGE)
        self.assertEqual(normal.damage_taken, NPC.DAMAGE_TAKEN)
        self.assertEqual(normal.reaction_ms, NPC.REACTION_MS)
        for weaker, stronger in ((easy, normal), (normal, hard)):
            self.assertLess(weaker.max_hp, stronger.max_hp)
            self.assertLess(weaker.attack_damage, stronger.attack_damage)
            self.assertGreater(weaker.damage_taken, stronger.damage_taken)
            self.assertGreater(weaker.reaction_ms, stronger.reaction_ms)
            self.assertGreater(weaker.attack_cooldown_ms, stronger.attack_cooldown_ms)
            self.assertLess(weaker.walk_speed, stronger.walk_speed)
        # The class keeps its own numbers
        self.assertEqual(NPC.WALK_SPEED, normal.walk_speed)

    def test_broly_is_a_hard_enemy_by_default(self):
        broly = SaiyanNPC(0, 0, False, "broly", 0, [])
        gohan = SaiyanNPC(0, 0, False, "gohan", 0, [])
        self.assertEqual(broly.difficulty.name, "hard")
        self.assertEqual(gohan.difficulty.name, "normal")
        self.assertGreater(broly.max_hp, gohan.max_hp)
        self.assertGreater(broly.attack_damage, gohan.attack_damage)
        # Gets angry sooner: powers up with more HP left
        self.assertGreater(broly.transform_at_hp, gohan.transform_at_hp)

    def test_a_big_body_is_reached_where_it_is_touched(self):
        """Broly is twice as wide: fighters touching his body can hit him,
        and he hits them from there too."""
        broly = SaiyanNPC(0, 0, False, "broly", 0, [])
        self.assertEqual(self.combat.body_reach(self.player), 0)
        self.assertGreater(self.combat.body_reach(broly), 0)
        gap = self.combat.ATTACK_RANGE + self.combat.body_reach(broly) - 1
        self.place(broly, gap)
        broly.facing = "Left"
        self.player.facing = "Right"
        self.assertTrue(self.combat._is_in_attack_range(broly))
        self.assertTrue(self.combat.ai.in_attack_range(broly))
        # The same gap is out of reach between two ordinary fighters
        self.place(self.enemy, gap)
        self.assertFalse(self.combat._is_in_attack_range(self.enemy))

    def step(self, fighter, dx, dy=0, others=()):
        """Move fighter by (dx, dy) and resolve the move like the game does."""
        fighter.save_location()
        fighter.position[0] += dx
        fighter.position[1] += dy
        fighter.update()
        resolve_movement_collisions(fighter, [], solid_bodies(others, fighter))

    def test_bodies_are_as_wide_as_the_characters(self):
        widths = {name: Saiyan(0, 0, False, name).body_width for name in ("goku", "gohan", "vegeta", "trunks")}
        self.assertTrue(all(10 <= width <= 20 for width in widths.values()), widths)
        self.assertGreater(Saiyan(0, 0, False, "broly").body_width, 2 * max(widths.values()) - 10)
        body = self.player.body
        self.assertEqual(body.midbottom, self.player.rect.midbottom)

    def test_the_player_cannot_walk_through_an_enemy(self):
        contact = (self.player.body_width + self.enemy.body_width) / 2
        self.place(self.enemy, contact)
        start = list(self.player.position)
        for _ in range(10):
            self.step(self.player, 1, others=[self.enemy])
        self.assertEqual(self.player.position, start)
        # Sideways along the enemy, and away from it, are still free
        self.step(self.player, 0, 5, others=[self.enemy])
        self.step(self.player, -3, others=[self.enemy])
        self.assertEqual(self.player.position, [start[0] - 3, start[1] + 5])

    def test_overlapping_characters_can_move_apart_but_not_closer(self):
        # Gohan's narrow body all inside Goku's wider one: still no way through
        self.place(self.enemy, 4)
        self.assertTrue(self.player.body.colliderect(self.enemy.body))
        start = list(self.player.position)
        self.step(self.player, 2, others=[self.enemy])
        self.assertEqual(self.player.position, start)
        self.step(self.player, -2, others=[self.enemy])
        self.assertEqual(self.player.position[0], start[0] - 2)

    def test_a_knocked_out_enemy_can_be_walked_over(self):
        self.place(self.enemy, 12)
        self.enemy.hp = 0
        self.assertEqual(solid_bodies([self.enemy], self.player), [])

    def test_knockback_stops_at_another_body(self):
        # Pushed left, into a second enemy standing right behind
        behind = NPC(0, 0, False, "vegeta", 0, [])
        self.place(behind, -(self.player.body_width + behind.body_width) / 2 - 1)
        start = list(self.player.position)
        self.player.take_damage(5, (self.player.feet.centerx + 10, self.player.feet.centery))
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            for _ in range(10):
                self.combat.update([behind], [])
        self.assertFalse(self.player.body.colliderect(behind.body))
        # Room for one pixel of the push, no more
        self.assertGreaterEqual(self.player.position[0], start[0] - 1)

    def test_a_chasing_enemy_stops_at_the_players_body(self):
        self.place(self.enemy, 40)
        self.enemy.attack_damage = 0
        self.enemy.reaction_ms = 10 ** 9
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            for _ in range(80):
                self.combat.update([self.enemy], [])
        self.assertFalse(self.player.body.colliderect(self.enemy.body))
        self.assertLessEqual(self.enemy.feet.centerx - self.player.feet.centerx, self.combat.ATTACK_RANGE)

    def test_broly_cannot_transform(self):
        broly = Saiyan(100, 100, False, "broly")
        broly.ki = broly.max_ki
        self.assertEqual(broly.super_levels, [])
        self.assertFalse(broly.transform())
        self.assertFalse(broly.is_super)

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

    def push_until_still(self, character, collisions=()):
        for _ in range(50):
            if not character.update_knockback(list(collisions)):
                break

    def test_a_hit_pushes_the_target_away_from_the_attacker(self):
        for target, source in ((self.enemy, self.player), (self.player, self.enemy)):
            with self.subTest(target=target.character_name):
                target.knockback = None
                start = target.feet.center
                target.take_damage(5, source.feet.center)
                self.push_until_still(target)
                moved_x = target.feet.centerx - start[0]
                away = 1 if start[0] > source.feet.centerx else -1
                self.assertAlmostEqual(moved_x * away, target.KNOCKBACK_DISTANCE, delta=1.5)

    def test_knockback_stops_at_walls(self):
        self.enemy.position = [130, 100]
        self.enemy.update()
        wall = pygame.Rect(self.enemy.feet.right + 3, 0, 20, 400)
        self.enemy.take_damage(5, (self.enemy.feet.centerx - 10, self.enemy.feet.centery))
        self.push_until_still(self.enemy, [wall])
        # Positions are fractional, the collision box is in whole pixels
        self.assertLessEqual(self.enemy.feet.right, wall.left + 1)

    def test_combat_moves_pushed_npcs_and_player(self):
        self.place(self.enemy, 15)
        self.enemy.facing = "Left"
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([self.enemy], [], player_attacking=True)
        start = self.enemy.position[0]
        with patch("combat.pygame.time.get_ticks", return_value=1017):
            self.combat.update([self.enemy], [])
        self.assertGreater(self.enemy.position[0], start)

    def test_guard_takes_70_percent_less_damage_and_still_pushes_back_without_flinch(self):
        self.assertTrue(self.player.start_block())
        self.assertTrue(self.player.blocking)
        before = self.player.hp
        start = self.player.feet.centerx
        self.player.take_damage(10, (self.player.feet.centerx + 10, self.player.feet.centery))
        # 70% less than without guard
        self.assertAlmostEqual(before - self.player.hp, 10 * 0.3)
        self.assertIsNone(self.player.action)
        self.push_until_still(self.player)
        self.assertAlmostEqual(start - self.player.feet.centerx, self.player.KNOCKBACK_DISTANCE, delta=1.5)
        self.assertTrue(self.player.blocking)
        # Guarding costs nothing
        ki = self.player.ki = 50
        with patch("combat.pygame.time.get_ticks", return_value=1000):
            self.combat.update([], [])
        self.assertGreater(self.player.ki, ki)
        self.assertTrue(self.player.blocking)

    def test_hits_only_push_a_little(self):
        self.assertLessEqual(self.player.KNOCKBACK_DISTANCE, 5)

    def test_every_form_has_a_guard_pose(self):
        for name in ("goku", "gohan", "vegeta"):
            fighter = Saiyan(100, 100, False, name)
            for form in fighter.forms:
                fighter.set_form(form)
                for direction in ("Down", "Right", "Left", "Up"):
                    with self.subTest(character=name, form=form, direction=direction):
                        fighter.facing = direction
                        fighter.stop_block()
                        self.assertTrue(fighter.start_block())
                        self.assertEqual(fighter.animation_name, f"Block {direction}")
                        idle = fighter.frame_image(
                            f"IDLE {direction}", flipped=direction == "Left"
                        )
                        self.assertIsNot(fighter.image, idle)
                fighter.stop_block()
                self.assertTrue(fighter.animation_name.startswith("IDLE"))

    def test_npc_health_bar_follows_hp_and_disappears_after_the_faint(self):
        screen = pygame.Surface((200, 200))
        self.enemy.position = [100, 100]
        self.enemy.update()
        combat = self.combat
        bar_y = self.enemy.rect.top - combat.hud.OVERHEAD_BAR_GAP - combat.hud.OVERHEAD_BAR_HEIGHT // 2 - 1
        half = combat.hud.OVERHEAD_BAR_MIN_WIDTH // 2 - 3
        left = (self.enemy.rect.centerx - half, bar_y)
        right = (self.enemy.rect.centerx + half, bar_y)
        red, empty = combat.hud.ENEMY_COLOR, (25, 25, 32)

        combat.draw_npc_bars(screen, [self.enemy], lambda rect: rect)
        self.assertEqual(screen.get_at(left)[:3], red)
        self.assertEqual(screen.get_at(right)[:3], red)

        self.enemy.hp = self.enemy.max_hp / 2
        combat.draw_npc_bars(screen, [self.enemy], lambda rect: rect)
        self.assertEqual(screen.get_at(left)[:3], red)
        self.assertEqual(screen.get_at(right)[:3], empty)

        screen.fill((0, 0, 0))
        self.enemy.faint_finished = True
        combat.draw_npc_bars(screen, [self.enemy], lambda rect: rect)
        self.assertEqual(screen.get_at(left)[:3], (0, 0, 0))

    def test_overhead_bars_are_thin_and_coloured_by_side(self):
        from npc import HEROES
        ally = SaiyanNPC(0, 0, False, "trunks", 0, [], team=HEROES)
        self.combat.update([ally, self.enemy], [])
        screen = pygame.Surface((400, 300))
        for fighter, colour in ((ally, self.combat.hud.ALLY_COLOR), (self.enemy, self.combat.hud.ENEMY_COLOR)):
            fighter.position = [150, 150]
            fighter.update()
            screen.fill((0, 0, 0))
            bars = self.combat.draw_npc_bars(screen, [fighter], lambda rect: rect)
            self.assertEqual(len(bars), 1)
            self.assertLessEqual(bars[0].height, 6)
            self.assertLessEqual(bars[0].width, self.combat.hud.OVERHEAD_BAR_MAX_WIDTH)
            self.assertEqual(screen.get_at(bars[0].center)[:3], colour)

    def test_each_strike_is_one_move_of_the_combo_and_they_cycle(self):
        for name, expected_moves in (("goku", 3), ("gohan", 4), ("vegeta", 4)):
            with self.subTest(character=name):
                fighter = Saiyan(100, 100, False, name)
                fighter.facing = "Right"
                moves = fighter.attack_moves("Right")
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
        right = self.player.attack_moves("Right")[0][0]
        left = self.player.attack_moves("Left")[0][0]
        self.assertIsNot(left, right)
        self.assertEqual(left.get_size(), right.get_size())


if __name__ == "__main__":
    unittest.main()
