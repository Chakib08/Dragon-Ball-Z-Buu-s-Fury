"""Teams (allies and several enemies), NPC techniques, the end of a fight
(retry / main menu), and the fixes for big characters (Broly)."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat import CombatSystem
from effects import Projectile
from game import Game
from map import MAX_ALLIES, MAX_ENEMIES, CharacterGroup, MapManager
from menu import Menu, State
from movement import resolve_movement_collisions, solid_bodies
from npc import ENEMIES, HEROES, NPC, SaiyanNPC
from quit_prompt import QuitPrompt
from saiyan import Saiyan
from utils.config import Config
from average_stats import use_average_stats


def key_down(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code)


class Clock:
    """pygame.time.get_ticks under the tests' control, in every module."""

    def __init__(self, test, now=10_000):
        self.now = now
        patcher = patch("pygame.time.get_ticks", side_effect=lambda: self.now)
        patcher.start()
        test.addCleanup(patcher.stop)


class TeamFightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def setUp(self):
        use_average_stats(self)
        self.clock = Clock(self)
        self.player = Saiyan(100, 100, False, "goku")
        self.player.update()
        self.combat = CombatSystem(self.player, (1200, 540))

    def fighter(self, name, team, gap, dy=0):
        """An NPC whose feet are gap px right of the player's (dy below)."""
        npc = SaiyanNPC(0, 0, False, name, 0, [], team=team)
        npc.position = [self.player.feet.centerx + gap - npc.rect.width / 2,
                        self.player.rect.bottom + dy - npc.rect.height]
        npc.update()
        npc.save_location()
        npc.next_technique_ms = float("inf")  # punches only, unless a test says
        return npc

    def run_frames(self, npcs, frames, attacking=False):
        for _ in range(frames):
            self.clock.now += 17
            self.player.update_action()
            self.combat.update(npcs, [], player_attacking=attacking)

    # ---- Allies ---------------------------------------------------------------------
    def test_an_ally_fights_the_enemy_and_never_the_player(self):
        enemy = self.fighter("vegeta", ENEMIES, 120)
        enemy.attack_damage = 0
        ally = self.fighter("gohan", HEROES, 70)
        self.run_frames([ally, enemy], 400)
        self.assertIs(ally.target, enemy)
        self.assertLess(enemy.hp, enemy.max_hp)
        self.assertEqual(self.player.hp, self.player.max_hp)

    def test_an_enemy_attacks_the_closest_hero(self):
        enemy = self.fighter("vegeta", ENEMIES, 60)
        ally = self.fighter("gohan", HEROES, 85)  # closer to the enemy than the player
        ally.attack_damage = 0
        self.run_frames([ally, enemy], 200)
        self.assertIs(enemy.target, ally)
        self.assertLess(ally.hp, ally.max_hp)

    def test_an_ally_with_nobody_to_fight_follows_the_player(self):
        ally = self.fighter("trunks", HEROES, 150)
        self.run_frames([ally], 300)
        distance = abs(ally.feet.centerx - self.player.feet.centerx)
        self.assertLessEqual(distance, CombatSystem.FOLLOW_DISTANCE + 2)
        self.assertIsNone(ally.target)

    def test_the_players_punches_and_techniques_skip_allies(self):
        ally = self.fighter("gohan", HEROES, 15)
        self.player.facing = "Right"
        self.run_frames([ally], 1, attacking=True)
        self.assertTrue(self.combat.player_swung)
        self.assertEqual(ally.hp, ally.max_hp)
        self.assertNotIn(ally, self.combat._targets)

    def test_allies_are_as_strong_as_a_normal_enemy(self):
        ally = SaiyanNPC(0, 0, False, "gohan", 0, [], team=HEROES)
        enemy = SaiyanNPC(0, 0, False, "gohan", 0, [], difficulty="normal")
        self.assertEqual(ally.difficulty.name, "ally")
        for stat in ("max_hp", "attack_damage", "damage_taken", "REACTION_MS", "attack_cooldown_ms",
                     "WALK_SPEED", "technique_damage", "technique_every_ms", "TRANSFORM_AT_HP"):
            with self.subTest(stat=stat):
                self.assertEqual(getattr(ally, stat), getattr(enemy, stat))

    # ---- Several enemies --------------------------------------------------------------
    def test_several_enemies_all_fight_and_all_can_be_hit(self):
        first = self.fighter("gohan", ENEMIES, 18)
        second = self.fighter("vegeta", ENEMIES, -18)
        for enemy in (first, second):
            enemy.attack_damage = 1
        self.run_frames([first, second], 120)
        self.assertIs(first.target, self.player)
        self.assertIs(second.target, self.player)
        self.assertLess(self.player.hp, self.player.max_hp)
        for facing, enemy in (("Right", first), ("Left", second)):
            self.player.facing = facing
            self.combat.last_player_attack_ms = -10 ** 6
            self.player.action = None
            self.combat._player_attack(self.combat._targets, self.clock.now)
            self.assertLess(enemy.hp, enemy.max_hp)

    # ---- NPC techniques ------------------------------------------------------------------
    def test_an_enemy_uses_a_technique_on_a_player_in_line(self):
        enemy = self.fighter("vegeta", ENEMIES, 90)
        enemy.attack_damage = 0
        enemy.combat_engaged = True  # already fighting: its next try is due
        enemy.next_technique_ms = 0
        ki = enemy.ki
        with patch("combat.random.choice", side_effect=lambda options: options[0]):
            self.run_frames([enemy], 1)
        self.assertIsNotNone(enemy.action)
        self.assertEqual(enemy.action["name"], "special")
        self.assertEqual(enemy.facing, "Left")
        self.assertLess(enemy.ki, ki)
        self.run_frames([enemy], 120)
        self.assertLess(self.player.hp, self.player.max_hp)

    def test_an_enemys_technique_never_hurts_another_enemy(self):
        enemy = self.fighter("vegeta", ENEMIES, 90)
        friend = self.fighter("gohan", ENEMIES, 45)  # standing in the way
        friend.next_technique_ms = float("inf")
        friend.attack_damage = enemy.attack_damage = 0
        self.player.hp = self.player.max_hp
        technique = next(t for t in enemy.techniques if t.kind == "projectile")
        self.combat.update([enemy, friend], [])
        self.assertTrue(self.combat.use_technique(enemy, technique, self.player))
        self.run_frames([enemy, friend], 150)
        self.assertEqual(friend.hp, friend.max_hp)
        self.assertLess(self.player.hp, self.player.max_hp)

    def test_an_npc_technique_does_only_a_share_of_its_damage(self):
        enemy = self.fighter("vegeta", ENEMIES, 90)
        technique = next(t for t in enemy.techniques if t.kind == "projectile")
        effect = self.combat._release_by(enemy, technique, "Left")
        self.assertIsInstance(effect, Projectile)
        self.assertEqual(effect.team, ENEMIES)
        self.assertAlmostEqual(effect.damage, technique.damage * enemy.technique_damage)
        player_effect = self.combat._release_by(self.player, technique if technique in self.player.techniques
                                                else self.player.techniques[0], "Right")
        self.assertEqual(player_effect.team, HEROES)

    def test_techniques_are_only_tried_when_they_can_reach(self):
        enemy = self.fighter("vegeta", ENEMIES, 90, dy=40)  # not in line
        blast = next(t for t in enemy.techniques if t.kind == "projectile")
        self.assertFalse(self.combat._technique_fits(enemy, blast, self.player))
        enemy = self.fighter("vegeta", ENEMIES, 90)
        self.assertTrue(self.combat._technique_fits(enemy, blast, self.player))
        gohan = self.fighter("gohan", ENEMIES, 25)
        burst = next(t for t in gohan.techniques if t.kind == "burst")
        self.assertTrue(self.combat._technique_fits(gohan, burst, self.player))
        far = self.fighter("gohan", ENEMIES, 150)
        self.assertFalse(self.combat._technique_fits(far, burst, self.player))

    def test_an_enemy_can_use_instant_transmission(self):
        goku = self.fighter("goku", ENEMIES, 130, dy=30)
        goku.attack_damage = 0
        teleport = next(t for t in goku.techniques if t.kind == "teleport")
        self.combat.update([goku], [])
        self.assertTrue(self.combat.use_technique(goku, teleport, self.player))
        self.run_frames([goku], 80)
        distance = abs(goku.feet.centerx - self.player.feet.centerx) + abs(goku.feet.centery - self.player.feet.centery)
        self.assertLess(distance, 60)
        self.assertLess(self.player.hp, self.player.max_hp)

    def test_a_new_fight_waits_a_moment_before_the_first_technique(self):
        enemy = self.fighter("vegeta", ENEMIES, 90)
        enemy.next_technique_ms = 0
        self.run_frames([enemy], 1)
        self.assertIsNone(enemy.action)
        self.assertGreater(enemy.next_technique_ms, self.clock.now)

    def test_harder_enemies_try_techniques_more_often(self):
        easy = SaiyanNPC(0, 0, False, "gohan", 0, [], difficulty="easy")
        hard = SaiyanNPC(0, 0, False, "gohan", 0, [], difficulty="hard")
        self.assertGreater(easy.technique_every_ms, hard.technique_every_ms)
        self.assertLess(easy.technique_damage, hard.technique_damage)


class BigCharacterTests(unittest.TestCase):
    """Broly's sprite is twice the size of the others."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def test_spawn_points_put_every_characters_feet_on_the_same_spot(self):
        point = pygame.Rect(174, 374, 1, 1)
        feet = []
        for name in ("gohan", "goku", "broly"):
            npc = NPC(0, 0, False, name, 0, [])
            npc.points = [point]
            npc.teleport_spawn()
            feet.append((npc.feet.centerx, npc.feet.bottom))
        self.assertTrue(all(abs(x - feet[0][0]) <= 1 and y == feet[0][1] for x, y in feet), feet)

    def test_broly_reaches_the_player_on_the_world_map(self):
        clock = Clock(self)
        game = Game((1200, 540), "test", fullscreen=False)
        game.select_character("goku", ("broly",))
        player = game.character
        broly = game.map_manager.get_map().npcs[0]
        broly.attack_damage = 0
        broly.next_technique_ms = float("inf")
        for _ in range(60 * 12):
            clock.now += 17
            game.play_frame([], False)
        distance = ((player.feet.centerx - broly.feet.centerx) ** 2
                    + (player.feet.centery - broly.feet.centery) ** 2) ** 0.5
        self.assertLess(distance, CombatSystem.ATTACK_RANGE + CombatSystem.body_reach(broly) + 10)

    def test_feet_are_capped_so_big_characters_fit_through_passages(self):
        broly = Saiyan(0, 0, False, "broly")
        self.assertLessEqual(broly.feet.width, broly.MAX_FEET_WIDTH)
        self.assertGreater(broly.body_depth, Saiyan(0, 0, False, "goku").body_depth)

    def test_nobody_walks_into_broly_from_any_side(self):
        broly = SaiyanNPC(0, 0, False, "broly", 0, [])
        broly.position = [200, 200]
        broly.update()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            with self.subTest(direction=(dx, dy)):
                goku = Saiyan(0, 0, False, "goku")
                goku.position = [broly.rect.centerx - goku.rect.width / 2 - dx * 60,
                                 broly.rect.bottom - goku.rect.height - dy * 60]
                goku.update()
                for _ in range(80):
                    goku.save_location()
                    goku.position[0] += dx
                    goku.position[1] += dy
                    goku.update()
                    resolve_movement_collisions(goku, [], solid_bodies([broly], goku))
                self.assertFalse(goku.body.colliderect(broly.body))
                # And it did not get past him either
                if dx:
                    self.assertEqual(goku.feet.centerx < broly.feet.centerx, dx > 0)
                else:
                    self.assertEqual(goku.feet.bottom < broly.feet.bottom, dy > 0)

    def test_characters_are_drawn_front_to_back(self):
        group = CharacterGroup.__new__(CharacterGroup)
        group.get_layer_of_sprite = lambda sprite: 1
        behind, front = Saiyan(0, 0, False, "goku"), Saiyan(0, 0, False, "broly")
        behind.position, front.position = [100, 100], [80, 90]
        behind.update()
        front.update()
        self.assertGreater(front.rect.bottom, behind.rect.bottom)
        self.assertGreater(group.depth_layer(front), group.depth_layer(behind))
        self.assertLess(group.depth_layer(front), 2)  # stays under the next layer

    def test_ssj_kamehameha_charges_in_the_plain_pose(self):
        """The SSJ sheet draws a big ki ball in some pose frames; charging
        holds only the frame without it (the game draws its own ball)."""
        goku = Saiyan(0, 0, False, "goku")
        goku.set_form("ssj")
        kamehameha = next(t for t in goku.techniques if t.id == "kamehameha")
        sprites = kamehameha.form_for(goku)
        for direction in ("Right", "Left", "Down", "Up"):
            with self.subTest(direction=direction):
                frames = goku.frames(kamehameha.pose_macro(direction))
                charging = frames[:sprites.fire_frame(direction)]
                self.assertEqual(len(charging), 1)
        pose = sprites.data["pose"]["Right"]
        self.assertEqual(pose[0], [32, 1117, 20, 29])
        # The frames with the ball ([135, 1117], [172, 1117], [206, 1117]) are gone
        self.assertFalse(any(box[0] in (135, 172, 206) for box in pose))


class WorldTeamsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    def setUp(self):
        self.clock = Clock(self)
        self.screen = pygame.display.set_mode((1200, 540))

    def test_enemies_spread_on_the_route_and_allies_stand_by_the_player(self):
        player = Saiyan(159, 289, False, "goku")
        manager = MapManager(self.screen, player, enemies=("broly", "vegeta", "gohan"),
                             allies=("gohan", "trunks"))
        npcs = manager.get_map().npcs
        enemies = [npc for npc in npcs if npc.team == ENEMIES]
        allies = [npc for npc in npcs if npc.team == HEROES]
        self.assertEqual([e.character_name for e in enemies], ["broly", "vegeta", "gohan"])
        self.assertEqual(len({(e.feet.centerx, e.feet.centery) for e in enemies}), 3)
        self.assertEqual([a.character_name for a in allies], ["gohan", "trunks"])
        for ally in allies:
            distance = abs(ally.feet.centerx - player.feet.centerx) + abs(ally.feet.centery - player.feet.centery)
            self.assertLess(distance, 60)
            self.assertEqual(ally.feet.collidelist(manager.get_collisions()), -1)
            self.assertFalse(ally.body.colliderect(player.body))
        self.assertFalse(allies[0].body.colliderect(allies[1].body))

    def test_four_against_four_fits_on_the_map(self):
        player = Saiyan(159, 289, False, "vegeta")
        manager = MapManager(self.screen, player, enemies=("goku", "gohan", "trunks", "broly"),
                             allies=("goku", "gohan", "trunks"))
        npcs = manager.get_map().npcs
        enemies = [npc for npc in npcs if npc.team == ENEMIES]
        allies = [npc for npc in npcs if npc.team == HEROES]
        self.assertEqual((len(allies) + 1, len(enemies)), (4, 4))
        everyone = [player, *npcs]
        # Nobody starts inside a wall or inside someone else
        for fighter in everyone:
            self.assertEqual(fighter.feet.collidelist(manager.get_collisions()), -1, fighter.character_name)
        for index, fighter in enumerate(everyone):
            for other in everyone[index + 1:]:
                self.assertFalse(fighter.body.colliderect(other.body),
                                 (fighter.character_name, fighter.team, other.character_name, other.team))

    def test_crowded_health_bars_do_not_cover_each_other(self):
        player = Saiyan(159, 289, False, "goku")
        manager = MapManager(self.screen, player, enemies=("goku", "gohan", "trunks", "broly"),
                             allies=("vegeta", "gohan", "trunks"))
        npcs = manager.get_map().npcs
        for index, npc in enumerate(npcs):  # all in one spot
            npc.position = [200 + index * 3, 300]
            npc.update()
        bars = manager.combat.draw_npc_bars(self.screen, npcs, lambda rect: rect)
        self.assertEqual(len(bars), len(npcs))
        for index, bar in enumerate(bars):
            self.assertEqual(bar.collidelist(bars[index + 1:]), -1)

    def test_team_panels_list_allies_left_and_enemies_right(self):
        player = Saiyan(159, 289, False, "goku")
        manager = MapManager(self.screen, player, enemies=("goku", "gohan", "trunks", "broly"),
                             allies=("vegeta", "gohan", "trunks"))
        combat = manager.combat
        combat.update(manager.get_map().npcs, manager.get_collisions())
        self.assertEqual([a.character_name for a in combat.allies], ["vegeta", "gohan", "trunks"])
        self.assertEqual([e.character_name for e in combat.enemies], ["goku", "gohan", "trunks", "broly"])
        rows = combat.draw_team_panels(self.screen)
        width = self.screen.get_width()
        ally_rows, enemy_rows = rows[:3], rows[3:]
        self.assertTrue(all(row.right < width / 3 for row in ally_rows))
        self.assertTrue(all(row.left > width * 2 / 3 for row in enemy_rows))
        # Under the player's bars and the quit button, above the touch controls
        quit_bottom = QuitPrompt(self.screen.get_size()).button_center[1] + 22
        self.assertTrue(all(row.top > quit_bottom for row in enemy_rows))
        self.assertTrue(all(row.top >= combat.ALLY_PANEL_TOP for row in ally_rows))
        self.assertTrue(all(row.bottom < self.screen.get_height() / 2 for row in rows))
        for index, row in enumerate(rows):
            self.assertEqual(row.collidelist(rows[index + 1:]), -1)

    def test_a_knocked_out_fighter_stays_listed_greyed_out(self):
        player = Saiyan(159, 289, False, "goku")
        manager = MapManager(self.screen, player, enemies=("broly",), allies=("gohan",))
        combat = manager.combat
        combat.update(manager.get_map().npcs, manager.get_collisions())
        broly = combat.enemies[0]
        rendered = []
        real = combat._label
        combat._label = lambda text, font, color=(255, 255, 255): rendered.append((text, color)) or real(text, font, color)
        combat.draw_team_panels(self.screen)
        self.assertIn(("Broly", (235, 80, 70)), rendered)  # Hard: red
        broly.hp = 0
        rendered.clear()
        combat.draw_team_panels(self.screen)
        self.assertIn(("Broly KO", combat.KO_COLOR), rendered)

    def test_team_sizes_are_capped(self):
        player = Saiyan(159, 289, False, "goku")
        manager = MapManager(self.screen, player, enemies=("goku",) * 5, allies=("gohan",) * 5)
        npcs = manager.get_map().npcs
        self.assertEqual(sum(npc.team == ENEMIES for npc in npcs), MAX_ENEMIES)
        self.assertEqual(sum(npc.team == HEROES for npc in npcs), MAX_ALLIES)


class EndOfFightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    def setUp(self):
        self.clock = Clock(self)
        self.game = Game((1200, 540), "test", fullscreen=False)
        self.game.menu = Menu((1200, 540))
        self.game.menu.selected_character = "vegeta"
        self.game.menu.selected_allies = ["trunks"]
        self.game.menu.selected_enemies = ["gohan", "broly"]
        self.game.start_story()
        self.game.scene = "story"

    def frames(self, count, events=()):
        for _ in range(count):
            self.clock.now += 17
            self.game.frame(list(events), False)

    def enemies(self):
        return [npc for npc in self.game.map_manager.get_map().npcs if npc.team == ENEMIES]

    def test_the_chosen_team_is_on_the_map(self):
        self.assertEqual(self.game.character.character_name, "vegeta")
        npcs = self.game.map_manager.get_map().npcs
        self.assertEqual(sorted((n.character_name, n.team) for n in npcs),
                         [("broly", ENEMIES), ("gohan", ENEMIES), ("trunks", HEROES)])

    def test_losing_offers_retry_with_the_same_team(self):
        self.game.character.hp = 0
        self.frames(60)
        self.assertIsNotNone(self.game.result)
        self.assertFalse(self.game.result.victory)
        old_player = self.game.character
        self.frames(1, [key_down(pygame.K_RETURN)])
        self.assertIsNone(self.game.result)
        self.assertEqual(self.game.scene, "story")
        self.assertIsNot(self.game.character, old_player)
        self.assertEqual(self.game.character.hp, self.game.character.max_hp)
        self.assertEqual(sorted(e.character_name for e in self.enemies()), ["broly", "gohan"])

    def test_the_fight_is_frozen_behind_the_result(self):
        self.game.character.hp = 0
        self.frames(60)
        positions = [list(npc.position) for npc in self.game.map_manager.get_map().npcs]
        self.frames(30)
        self.assertEqual(positions, [list(npc.position) for npc in self.game.map_manager.get_map().npcs])

    def test_winning_offers_to_play_again_or_go_to_the_menu(self):
        for enemy in self.enemies():
            enemy.hp = 0
        self.frames(90)
        self.assertIsNotNone(self.game.result)
        self.assertTrue(self.game.result.victory)
        self.assertEqual(self.game.result.retry_label, "Play again")
        self.frames(1, [key_down(pygame.K_m)])
        self.assertEqual(self.game.scene, "menu")
        self.assertEqual(self.game.menu.state, State.START)
        self.assertIsNone(self.game.result)

    def test_result_buttons_work_by_touch(self):
        self.game.character.hp = 0
        self.frames(60)
        rect = self.game.result.menu_rect
        tap = pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=rect.centerx / 1200, y=rect.centery / 540)
        self.frames(1, [tap])
        self.assertEqual(self.game.scene, "menu")

    def test_no_result_while_the_fight_goes_on(self):
        self.frames(30)
        self.assertIsNone(self.game.result)
        self.assertIsNone(self.game.story_outcome())


class QuitPromptMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_while_playing_the_prompt_offers_the_main_menu(self):
        prompt = QuitPrompt((1200, 540))
        prompt.process([key_down(pygame.K_ESCAPE)], menu_available=True)
        self.assertTrue(prompt.is_open)
        prompt.draw(pygame.Surface((1200, 540)))
        prompt.process([key_down(pygame.K_m)], menu_available=True)
        self.assertTrue(prompt.to_menu)
        self.assertFalse(prompt.is_open)
        self.assertFalse(prompt.confirmed)

    def test_main_menu_button_by_touch_and_buttons_do_not_overlap(self):
        prompt = QuitPrompt((1200, 540))
        prompt.process([key_down(pygame.K_ESCAPE)], menu_available=True)
        rects = (prompt.yes_rect, prompt.menu_rect, prompt.no_rect)
        self.assertEqual(sum(a.colliderect(b) for a in rects for b in rects if a is not b), 0)
        x, y = prompt.menu_rect.center
        prompt.process([pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=x / 1200, y=y / 540)],
                       menu_available=True)
        self.assertTrue(prompt.to_menu)

    def test_in_the_main_menu_there_is_no_menu_button(self):
        prompt = QuitPrompt((1200, 540))
        prompt.process([key_down(pygame.K_ESCAPE)], menu_available=False)
        prompt.process([key_down(pygame.K_m)], menu_available=False)
        self.assertFalse(prompt.to_menu)
        self.assertTrue(prompt.is_open)

    def test_the_game_goes_back_to_the_menu_from_a_fight(self):
        with patch("pygame.time.get_ticks", return_value=10_000):
            Config.init()
            game = Game((1200, 540), "test", fullscreen=False)
            game.menu = Menu((1200, 540))
            game.start_story()
            game.scene = "story"
            game.quit_prompt.process([key_down(pygame.K_ESCAPE)], menu_available=True)
            game.quit_prompt.process([key_down(pygame.K_m)], menu_available=True)
            self.assertTrue(game.quit_prompt.to_menu)
            # What the main loop does with it
            game.quit_prompt.to_menu = False
            game.back_to_menu()
        self.assertEqual(game.scene, "menu")
        self.assertTrue(game.isRunning)


if __name__ == "__main__":
    unittest.main()
