import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from map import MapManager
from saiyan import Saiyan
from utils.config import Config


class NpcPatrolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        cls.screen = pygame.display.set_mode((Config.WIDTH, Config.HEIGHT))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.player = Saiyan(159, 289, False, "goku")
        self.maps = MapManager(self.screen, self.player)
        self.npc = self.maps.get_map().npcs[0]
        self.ticks = 0

    def step(self, frames=1, player_walks=False):
        for _ in range(frames):
            self.ticks += 17
            if player_walks:
                self.player.move("Walk Down", 4)
            with patch("combat.pygame.time.get_ticks", return_value=self.ticks):
                self.maps.update(False)
            self.maps.draw()

    def move_player_far_away(self):
        self.player.position = [650, 60]
        self.player.save_location()

    def path_bounds(self):
        xs = [p.x for p in self.npc.points]
        ys = [p.y for p in self.npc.points]
        margin = 40
        return min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin

    def assert_on_patrol_path(self):
        min_x, max_x, min_y, max_y = self.path_bounds()
        x, y = self.npc.position
        self.assertTrue(min_x <= x <= max_x and min_y <= y <= max_y, (x, y))

    def test_npc_patrols_by_itself_when_player_stands_still_far_away(self):
        self.move_player_far_away()
        visited = set()
        for _ in range(1500):
            self.step()
            self.assert_on_patrol_path()
            visited.add(self.npc.current_point)

        self.assertEqual(visited, set(range(len(self.npc.points))))

    def test_npc_patrol_does_not_depend_on_the_player_moving(self):
        self.move_player_far_away()
        self.step(5)
        before = tuple(self.npc.position)
        self.step(30)
        self.assertNotEqual(tuple(self.npc.position), before)

    def test_npc_never_leaves_the_map_when_player_is_far(self):
        self.move_player_far_away()
        for _ in range(3000):
            self.step()
        self.assert_on_patrol_path()
        self.assertIn(self.npc, self.maps.get_group().sprites())

    def test_npc_returns_to_its_path_after_a_chase(self):
        # Player close: the NPC leaves its path to chase him
        self.step(200)
        self.assertTrue(self.npc.combat_engaged)

        # The player flees. The NPC used to run away forever and vanish; it
        # may be off its route (knockback makes chases longer) but walks back
        self.move_player_far_away()
        min_x, max_x, min_y, max_y = self.path_bounds()
        for _ in range(600):
            self.step()
            x, y = self.npc.position
            if min_x <= x <= max_x and min_y <= y <= max_y:
                break
        for _ in range(1400):
            self.step()
            self.assert_on_patrol_path()

        self.assertFalse(self.npc.combat_engaged)
        self.step(600)
        self.assert_on_patrol_path()

    def test_resume_patrol_targets_the_closest_waypoint(self):
        self.npc.position = [
            self.npc.points[2].x + 3,
            self.npc.points[2].y + 3,
        ]
        self.npc.resume_patrol()
        self.assertEqual(self.npc._target_index(), 2)

    def test_npc_keeps_striking_one_move_at_a_time_when_player_is_idle(self):
        self.step(300)
        self.assertTrue(self.npc.combat_engaged)
        moves_before = self.npc.attack_move_index
        hp_before = self.player.hp
        striking = False
        for _ in range(120):
            self.step(1)
            striking = striking or (self.npc.action is not None and self.npc.action["name"] == "attack")
        self.assertTrue(striking)
        # About two seconds: several separate punches and kicks, each a hit
        self.assertGreaterEqual(self.npc.attack_move_index - moves_before, 3)
        self.assertLess(self.player.hp, hp_before)

    def test_maps_are_loaded_on_first_visit_only(self):
        self.assertEqual(list(self.maps.maps), ["map"])
        house = self.maps.load_map("house")
        self.assertIs(self.maps.load_map("house"), house)
        self.assertEqual(set(house.portal_rects), {"exit_house", "enter_hall", "enter_kitchen"})
        self.assertIn(self.player, house.group.sprites())

    def test_world_npc_is_gohan_on_the_map_patrol_route(self):
        self.assertEqual(self.npc.character_name, "gohan")
        self.assertEqual(self.npc.path_name, "vegeta")
        self.assertEqual(len(self.npc.points), 4)
        self.assertTrue(self.npc.can_transform)


if __name__ == "__main__":
    unittest.main()
