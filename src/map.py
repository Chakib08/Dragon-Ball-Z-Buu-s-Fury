from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pygame
import pyscroll
import pytmx

from combat import CombatSystem
from movement import resolve_movement_collisions
from npc import NPC, SaiyanNPC
from pathmanager import PathManager


class CharacterGroup(pyscroll.PyscrollGroup):
    """PyscrollGroup that lets a sprite shift its image (see image_offset).

    Animation frames have different sizes; drawing them all from the top-left
    of the rect would make the character jump around.
    """

    def draw(self, surface):
        ox, oy = self._map_layer.get_center_offset()
        view_rect = self.view
        new_surfaces = []
        for sprite in self.sprites():
            if not sprite.rect.colliderect(view_rect):
                continue
            dx, dy = sprite.image_offset() if hasattr(sprite, "image_offset") else (0, 0)
            new_rect = sprite.rect.move(ox + dx, oy + dy)
            new_surfaces.append((sprite.image, new_rect, self.get_layer_of_sprite(sprite)))
            self.spritedict[sprite] = new_rect
        self.lostsprites = []
        return self._map_layer.draw(surface, surface.get_rect(), new_surfaces)


@dataclass
class Portal:
    src_map: str        # Map the portal is on
    src_point: str      # Map object the character has to step on
    target_map: str     # Map the character is sent to
    target_point: str   # Map object the character appears on


@dataclass
class MapDefinition:
    """What a map is made of. The map itself is only loaded on first visit."""
    name: str
    music: str
    portals: List[Portal] = field(default_factory=list)
    # Called on first visit, so NPCs of unvisited maps cost nothing
    make_npcs: Optional[Callable[[], List[NPC]]] = None


@dataclass
class Map:
    name: str
    collisions: List[pygame.Rect]
    group: pyscroll.PyscrollGroup
    tmx_data: pytmx.TiledMap
    portals: List[Portal]
    npcs: List[NPC]
    music: str
    portal_rects: Dict[str, pygame.Rect] = field(default_factory=dict)

    def get_object(self, name):
        return self.tmx_data.get_object_by_name(name)

    @staticmethod
    def get_rect(map_object):
        return pygame.Rect(map_object.x, map_object.y, map_object.width, map_object.height)


HOME_MUSIC = "DBZ-Buus-Fury-Soundtrack-Gokus-Home"
WORLD_MUSIC = "legacy-of-goku-II/The Legacy Of Goku 2 OST - The Imperfect Cell"


def _world_npcs():
    # Gohan walks the route the map calls "vegeta_path"
    return [
        SaiyanNPC(
            99, 345, False, "gohan", 4,
            ["Hey! Let's see how strong you've become!", "I won't hold back this time!"],
            path_name="vegeta",
        )
    ]


def map_definitions():
    world = PathManager.soundtrack(WORLD_MUSIC)
    home = PathManager.soundtrack(HOME_MUSIC)
    return [
        MapDefinition("map", world, [Portal("map", "enter_house", "house", "spawn_house")], _world_npcs),
        MapDefinition("house", home, [
            Portal("house", "exit_house", "map", "spawn_world"),
            Portal("house", "enter_hall", "hall", "spawn_from_house_to_hall"),
            Portal("house", "enter_kitchen", "kitchen", "spawn_kitchen"),
        ]),
        MapDefinition("hall", home, [
            Portal("hall", "exit_hall", "house", "spawn_from_hall_to_house"),
            Portal("hall", "gohan_goten_room_enter", "gohan_goten_room", "spawn_gohan_goten_room"),
            Portal("hall", "enter_chichi_room", "chichi_room", "spawn_chichi_room"),
        ]),
        MapDefinition("gohan_goten_room", home, [
            Portal("gohan_goten_room", "exit_gohan_goten_room", "hall", "spawn_from_room_to_hall"),
        ]),
        MapDefinition("chichi_room", home, [
            Portal("chichi_room", "exit_chichi_room", "hall", "spawn_from_room_to_hall"),
        ]),
        MapDefinition("kitchen", home, [
            Portal("kitchen", "exit_kitchen", "house", "spawn_from_kitchen_to_house"),
        ]),
    ]


class MapManager:
    # Map pixels visible from top to bottom of the screen
    VISIBLE_MAP_HEIGHT = 250
    # Alpha added per frame while fading to/from black between maps
    FADE_SPEED = 10

    def __init__(self, screen, character, default_map="map", versus=False, opponents=()) -> None:
        """versus: an online match on this map, without NPCs or doors, the
        opponents (remote players) drawn alongside the player."""
        self.screen = screen
        self.character = character
        self.versus = versus
        self.opponents = list(opponents)
        self.combat = CombatSystem(character, screen.get_size())
        self.definitions = {definition.name: definition for definition in map_definitions()}
        self.maps = {}

        # Fade to black between two maps
        self.input_enabled = True
        self.transitioning = False
        self.transitioning_in = True
        self.transition_alpha = 0
        self.new_map = None
        self.new_position = None
        self.black_screen = pygame.Surface(screen.get_size())
        self.black_screen.fill((0, 0, 0))

        self.current_map = default_map
        self.load_map(default_map)
        self.current_music = self.get_map().music
        self.isMusicChanged = False

    def set_screen(self, screen):
        """Draw to a new display surface (after switching full screen)."""
        self.screen = screen
        size = screen.get_size()
        for game_map in self.maps.values():
            layer = game_map.group._map_layer
            layer.zoom = self.zoom_for(size)
            layer.set_size(size)
        self.combat.screen_size = size
        self.black_screen = pygame.Surface(size)
        self.black_screen.fill((0, 0, 0))

    @classmethod
    def zoom_for(cls, screen_size):
        # Whole numbers keep the pixel art sharp
        return max(2, round(screen_size[1] / cls.VISIBLE_MAP_HEIGHT))

    # ---- Loading ----------------------------------------------------------------
    def load_map(self, name):
        """Load a map the first time it is needed (each one holds a
        screen-sized render buffer, so unvisited maps stay unloaded)."""
        if name in self.maps:
            return self.maps[name]

        definition = self.definitions[name]
        tmx_data = pytmx.load_pygame(PathManager.map_path(name))
        map_layer = pyscroll.orthographic.BufferedRenderer(
            pyscroll.data.TiledMapData(tmx_data), self.screen.get_size()
        )
        map_layer.zoom = self.zoom_for(self.screen.get_size())

        collisions = [
            pygame.Rect(obj.x, obj.y, obj.width, obj.height)
            for obj in tmx_data.objects
            if obj.type == "collision"
        ]
        npcs = definition.make_npcs() if definition.make_npcs and not self.versus else []
        portals = [] if self.versus else definition.portals
        group = CharacterGroup(map_layer=map_layer, default_layer=1)
        group.add(self.character, *npcs, *self.opponents)

        game_map = Map(name, collisions, group, tmx_data, portals, npcs, definition.music)
        # Looked up once here instead of on every frame
        game_map.portal_rects = {
            portal.src_point: game_map.get_rect(game_map.get_object(portal.src_point))
            for portal in portals
        }
        for npc in npcs:
            npc.load_points(game_map)
            npc.teleport_spawn()
        self.maps[name] = game_map
        return game_map

    # ---- Accessors --------------------------------------------------------------
    def get_map(self):
        return self.maps[self.current_map]

    def get_group(self):
        return self.get_map().group

    def get_collisions(self):
        return self.get_map().collisions

    def get_object(self, name):
        return self.get_map().get_object(name)

    def position_character(self, name):
        point = self.get_object(name)
        self.character.position[0] = point.x - 10
        self.character.position[1] = point.y - 20
        self.character.save_location()

    # ---- Collisions -------------------------------------------------------------
    def check_collisions(self):
        if self.transitioning:
            return
        game_map = self.get_map()
        for portal in game_map.portals:
            if self.character.feet.colliderect(game_map.portal_rects[portal.src_point]):
                self.transitioning = True
                self.transitioning_in = True
                self.new_map = portal.target_map
                self.new_position = portal.target_point
                self.transition_alpha = 0
                self.input_enabled = False
                break

        resolve_movement_collisions(self.character, game_map.collisions)

        # NPCs stand still while touching the player, so he can talk to them
        for sprite in game_map.group.sprites():
            if isinstance(sprite, NPC):
                sprite.speed = 0 if sprite.feet.colliderect(self.character.rect) else 1

    def check_npc_collisions(self, dialogBox):
        for npc in self.get_map().npcs:
            if npc.feet.colliderect(self.character.rect):
                dialogBox.open(npc.dialog_texts)

    # ---- Frame ------------------------------------------------------------------
    def update(self, player_attacking=False):
        previous_music = self.current_music
        if self.transitioning:
            self.black_transition()
        game_map = self.get_map()
        game_map.group.update()
        self.check_collisions()
        for opponent in self.opponents:
            opponent.follow_snapshot()
        self.combat.update(game_map.npcs, game_map.collisions, player_attacking, self.opponents)

        self.current_music = game_map.music
        self.isMusicChanged = self.current_music != previous_music

        for npc in game_map.npcs:
            npc.move_npc()

    def draw(self):
        group = self.get_group()
        group.draw(self.screen)
        # Drawn before re-centering so the overlays match the frame just rendered
        to_screen_rect = group._map_layer.translate_rect
        self.combat.draw_beams(self.screen, to_screen_rect)
        self.combat.draw_npc_bars(self.screen, [*self.get_map().npcs, *self.opponents], to_screen_rect)
        group.center(self.character.rect.center)
        if self.transitioning:
            self.black_screen.set_alpha(self.transition_alpha)
            self.screen.blit(self.black_screen, (0, 0))

    def black_transition(self):
        if self.transitioning_in:
            self.transition_alpha += self.FADE_SPEED
            if self.transition_alpha >= 255:
                self.transition_alpha = 255
                self.transitioning_in = False
                self.load_map(self.new_map)
                self.current_map = self.new_map
                self.position_character(self.new_position)
        else:
            self.transition_alpha -= self.FADE_SPEED
            if self.transition_alpha <= 0:
                self.transition_alpha = 0
                self.transitioning = False
                self.input_enabled = True
