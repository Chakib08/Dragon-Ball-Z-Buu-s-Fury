"""Walk every map the way the game moves characters (feet against the
collision boxes) and check that every door can be reached from every place
the player appears, and that the void outside the rooms cannot."""
import os
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytmx

from map import Map, map_definitions
from movement import _feet_at, _overlap_area
from pathmanager import PathManager
from saiyan import Saiyan
from utils.config import Config

STEP = 2


def reachable_positions(character, start, collisions, limit=60_000):
    """Every position the character can walk to from start (game rule: a
    move is allowed if it does not increase the overlap with walls), and
    every position it can try to step into (doors trigger on the attempt,
    before the move is pushed back)."""
    start = (round(start[0]), round(start[1]))
    seen = {start}
    tried = set()
    queue = deque([start])
    while queue and len(seen) < limit:
        x, y = queue.popleft()
        here = _overlap_area(_feet_at(character, (x, y)), collisions)
        for dx, dy in ((STEP, 0), (-STEP, 0), (0, STEP), (0, -STEP)):
            nxt = (x + dx, y + dy)
            if nxt in seen:
                continue
            tried.add(nxt)
            if _overlap_area(_feet_at(character, nxt), collisions) <= here:
                seen.add(nxt)
                queue.append(nxt)
    reachable_positions.tried = tried | seen
    return seen


class MapCollisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((100, 100))
        cls.character = Saiyan(0, 0, False, "goku")

    def load(self, name):
        data = pytmx.load_pygame(PathManager.map_path(name))
        collisions = [pygame.Rect(o.x, o.y, o.width, o.height) for o in data.objects if o.type == "collision"]
        return data, collisions

    def spawn_positions(self, name, data):
        """Where the game puts the player when it enters this map."""
        positions = []
        for definition in map_definitions():
            for portal in definition.portals:
                if portal.target_map == name:
                    point = data.get_object_by_name(portal.target_point)
                    positions.append((portal.target_point, (point.x - 10, point.y - 20)))
        if name == "map":
            positions.append(("game start", (159, 289)))
        return positions

    def test_every_door_can_be_reached_from_every_spawn(self):
        definitions = {d.name: d for d in map_definitions()}
        for name, definition in definitions.items():
            data, collisions = self.load(name)
            doors = [(p.src_point, Map.get_rect(data.get_object_by_name(p.src_point))) for p in definition.portals]
            for spawn_name, start in self.spawn_positions(name, data):
                reachable_positions(self.character, start, collisions)
                seen = reachable_positions.tried
                for door, rect in doors:
                    with self.subTest(map=name, spawn=spawn_name, door=door):
                        self.assertTrue(
                            any(_feet_at(self.character, p).colliderect(rect) for p in seen),
                            f"{door} cannot be reached from {spawn_name}",
                        )

    def test_rooms_are_closed(self):
        """From inside a room, its walls and the void around it stay out of reach."""
        for name in ("house", "hall", "kitchen", "chichi_room", "gohan_goten_room"):
            data, collisions = self.load(name)
            for spawn_name, start in self.spawn_positions(name, data):
                seen = reachable_positions(self.character, start, collisions)
                feet = [_feet_at(self.character, p) for p in seen]
                with self.subTest(map=name, spawn=spawn_name):
                    # Never in the top-left corner of the map (void in every room)
                    self.assertFalse(any(f.right < 48 and f.bottom < 96 for f in feet))
                    # Never far outside the map
                    self.assertTrue(all(-8 <= f.x and f.right <= 408 and -8 <= f.y and f.bottom <= 408 for f in feet))

    def test_the_river_cannot_be_crossed_except_on_the_bridge(self):
        data, collisions = self.load("map")
        seen = reachable_positions(self.character, (159, 289), collisions)
        feet = [_feet_at(self.character, p) for p in seen]
        water = pygame.Rect(40, 455, 150, 25)   # middle of the lake, left of the bridge
        river = pygame.Rect(480, 120, 20, 120)  # middle of the river
        self.assertFalse(any(f.colliderect(water) or f.colliderect(river) for f in feet))
        # The bridge itself is walkable all the way across
        self.assertTrue(any(f.colliderect(pygame.Rect(230, 540, 40, 8)) for f in feet))


if __name__ == "__main__":
    unittest.main()
