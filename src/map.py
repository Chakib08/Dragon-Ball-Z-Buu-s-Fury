import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pygame
import pyscroll
import pytmx

from combat import CombatSystem
from effects import EFFECT_LAYER
from movement import resolve_movement_collisions, solid_bodies
from difficulty import enemy_profile
from npc import HEROES, NPC, SaiyanNPC
from pathmanager import PathManager
from utils.config import Config
from utils import timing


class CharacterGroup(pyscroll.PyscrollGroup):
    """PyscrollGroup that lets a sprite shift its image (see image_offset),
    and draws the characters in depth order.

    Animation frames have different sizes; drawing them all from the top-left
    of the rect would make the character jump around.
    """

    def depth_layer(self, sprite):
        """The sprite's layer, plus a tiny fraction growing with how low it
        stands: pyscroll sorts by layer first (then by x), so within a
        layer the one lower on the screen, nearer to the viewer, is drawn
        last, in front. The fraction stays far below 1, so the order with the
        map's own tile layers does not change."""
        return self.get_layer_of_sprite(sprite) + max(0, sprite.rect.bottom) / 1_000_000

    def draw(self, surface):
        ox, oy = self._map_layer.get_center_offset()
        view_rect = self.view
        new_surfaces = []
        for sprite in self.sprites():
            if not sprite.rect.colliderect(view_rect):
                continue
            dx, dy = sprite.image_offset() if hasattr(sprite, "image_offset") else (0, 0)
            new_rect = sprite.rect.move(ox + dx, oy + dy)
            new_surfaces.append((sprite.image, new_rect, self.depth_layer(sprite)))
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
    # The .tmx file (Graphics/maps/<file>.tmx), when not the map's name: the
    # world map can be another arena (Config "arena", tools/png_to_map.py)
    file: Optional[str] = None


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


DEFAULT_ENEMY = "gohan"
# Most fighters a side can have: up to 4 against 4 (the player and 3
# allies against 4 enemies), 8 on the field
MAX_ENEMIES = 4
MAX_ALLIES = 3
ALLY_LINES = ["I've got your back!", "Let's beat them together!"]


def _world_npcs(enemies=(DEFAULT_ENEMY,), allies=()):
    """The fighters of the world map: the enemies, with the strength and
    lines Config/enemies.json gives them, walking the route the map calls
    "vegeta_path" (each from another of its points), and the player's allies
    (MapManager places them next to the player)."""
    npcs = []
    for index, name in enumerate(enemies[:MAX_ENEMIES]):
        profile = enemy_profile(name)
        dialog = profile.dialog or ["Let's fight!"]
        enemy = SaiyanNPC(99, 345, False, name, 4, dialog, path_name="vegeta", difficulty=profile.difficulty)
        enemy.current_point = index % 4
        npcs.append(enemy)
    for name in allies[:MAX_ALLIES]:
        npcs.append(SaiyanNPC(0, 0, False, name, 0, ALLY_LINES, team=HEROES))
    return npcs


def _has_object(tmx_data, name):
    try:
        tmx_data.get_object_by_name(name)
        return True
    except (KeyError, ValueError):
        return False


def _map_exists(name):
    try:
        return os.path.exists(PathManager.map_path(name))
    except ValueError:
        return False


def arena():
    """The map arcade fights happen on: "map" (Goku's home), or a map made
    with tools/png_to_map.py, named in Config/config.json ("arena")."""
    name = Config.get_config_value("arena", default_value="map") or "map"
    try:
        return name if os.path.exists(PathManager.map_path(name)) else "map"
    except ValueError:
        return "map"


def map_definitions(enemies=(DEFAULT_ENEMY,), allies=(), world_file=None):
    world = PathManager.soundtrack(WORLD_MUSIC)
    home = PathManager.soundtrack(HOME_MUSIC)
    return [
        MapDefinition("map", world, [Portal("map", "enter_house", "house", "spawn_house")],
                      lambda: _world_npcs(enemies, allies), file=world_file),
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

    def __init__(self, screen, character, default_map="map", versus=False, opponents=(),
                 enemies=(DEFAULT_ENEMY,), allies=(), arena_name=None) -> None:
        """versus: an online match on this map, without enemies or doors, the
        opponents (the remote player and its allies) drawn alongside the
        player. enemies: the characters the player fights on the world map;
        allies: the ones who fight on his side (online too)."""
        self.screen = screen
        self.character = character
        self.versus = versus
        self.opponents = list(opponents)
        self.combat = CombatSystem(character, screen.get_size())
        self.enemies = tuple(enemies)
        self.allies = tuple(allies)
        # The arena chosen on the map screen, else Config's (online: the
        # room's, else Goku's home)
        if arena_name and _map_exists(arena_name):
            self.world_file = arena_name
        else:
            self.world_file = "map" if versus else arena()
        self.definitions = {definition.name: definition
                            for definition in map_definitions(self.enemies, self.allies, self.world_file)}
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
        tmx_data = pytmx.load_pygame(PathManager.map_path(definition.file or name))
        map_layer = pyscroll.orthographic.BufferedRenderer(
            pyscroll.data.TiledMapData(tmx_data), self.screen.get_size()
        )
        map_layer.zoom = self.zoom_for(self.screen.get_size())

        collisions = [
            pygame.Rect(obj.x, obj.y, obj.width, obj.height)
            for obj in tmx_data.objects
            if obj.type == "collision"
        ]
        if name == "map" and definition.file not in (None, "map") and _has_object(tmx_data, "spawn_world"):
            # Another arena: the player starts on its spawn point
            spawn = tmx_data.get_object_by_name("spawn_world")
            self.character.position = [spawn.x - self.character.rect.width / 2,
                                       spawn.y - self.character.rect.height]
            self.character.update()
            self.character.save_location()
        if self.versus:
            npcs = _world_npcs((), self.allies)  # the player's allies only
        else:
            npcs = definition.make_npcs() if definition.make_npcs else []
        portals = [] if self.versus else definition.portals
        # A map without a door's spot (a new arena) has no such door
        portals = [portal for portal in portals if _has_object(tmx_data, portal.src_point)]
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
        enemies = [npc for npc in npcs if npc.team != HEROES]
        self._free_spawns(enemies, collisions)
        self._place_allies([npc for npc in npcs if npc.team == HEROES], collisions, enemies)
        self.maps[name] = game_map
        return game_map

    # Nudges tried, nearest first, when a spawn point is not free ground
    SPAWN_NUDGES = sorted(((dx, dy) for dx in range(-32, 33, 4) for dy in range(-32, 33, 4)),
                          key=lambda offset: offset[0] ** 2 + offset[1] ** 2)

    def _free_spawns(self, fighters, collisions):
        """Fighters standing in a wall (some of the map's patrol points are on
        the cliff edge) or in someone else move to the nearest free ground."""
        taken = [self.character.body]
        for fighter in fighters:
            start = list(fighter.position)
            for dx, dy in self.SPAWN_NUDGES:
                fighter.position = [start[0] + dx, start[1] + dy]
                fighter.update()
                if fighter.feet.collidelist(collisions) == -1 and fighter.body.collidelist(taken) == -1:
                    break
            else:
                fighter.position = start
                fighter.update()
            fighter.save_location()
            taken.append(fighter.body)

    # Where allies appear, around the player's feet
    ALLY_SPOTS = ((-26, 8), (26, 8), (0, 22), (-26, -12), (26, -12), (0, -24))

    def _place_allies(self, allies, collisions, others=()):
        """Next to the player, on free ground (no wall, nobody else: the
        player, the other allies and others, the enemies already placed)."""
        self.character.update()  # its rect follows its position from now on
        taken = [self.character.body, *(other.body for other in others)]
        for ally in allies:
            for dx, dy in self.ALLY_SPOTS:
                feet_x = self.character.feet.centerx + dx
                feet_bottom = self.character.feet.bottom + dy
                ally.position = [feet_x - ally.rect.width / 2, feet_bottom - ally.rect.height]
                ally.update()
                if ally.feet.collidelist(collisions) == -1 and ally.body.collidelist(taken) == -1:
                    break
            ally.save_location()
            taken.append(ally.body)

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

        # Walls stop the feet; the enemies' and online opponents' bodies
        # stop the player's body
        others = solid_bodies([*game_map.npcs, *self.opponents], self.character)
        resolve_movement_collisions(self.character, game_map.collisions, others)

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
        # Technique effects are sprites: zoomed and drawn with the characters
        for effect in self.combat.new_effects:
            game_map.group.add(effect, layer=EFFECT_LAYER)
        self.combat.new_effects.clear()
        for loaded in self.maps.values():  # finished effects, on any map
            for effect in loaded.group.get_sprites_from_layer(EFFECT_LAYER):
                if getattr(effect, "done", False):
                    loaded.group.remove(effect)

        self.current_music = game_map.music
        self.isMusicChanged = self.current_music != previous_music

        for npc in game_map.npcs:
            npc.save_location()
            npc.move_npc()
            # Patrolling does not walk into the player (or another NPC); the
            # route itself keeps clear of the walls
            resolve_movement_collisions(npc, [], solid_bodies([self.character, *game_map.npcs], npc))

    def draw(self):
        group = self.get_group()
        group.draw(self.screen)
        # Drawn before re-centering so the overlays match the frame just rendered
        to_screen_rect = group._map_layer.translate_rect
        self.combat.draw_npc_bars(self.screen, [*self.get_map().npcs, *self.opponents], to_screen_rect)
        self.combat.draw_charge(self.screen, to_screen_rect)
        group.center(self.character.rect.center)
        if self.transitioning:
            self.black_screen.set_alpha(int(self.transition_alpha))
            self.screen.blit(self.black_screen, (0, 0))

    def black_transition(self):
        if self.transitioning_in:
            self.transition_alpha += self.FADE_SPEED * timing.ticks()
            if self.transition_alpha >= 255:
                self.transition_alpha = 255
                self.transitioning_in = False
                self.combat.clear_effects()
                self.load_map(self.new_map)
                self.current_map = self.new_map
                self.position_character(self.new_position)
        else:
            self.transition_alpha -= self.FADE_SPEED * timing.ticks()
            if self.transition_alpha <= 0:
                self.transition_alpha = 0
                self.transitioning = False
                self.input_enabled = True
