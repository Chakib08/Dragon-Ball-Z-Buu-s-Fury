from dataclasses import dataclass
from typing import List
import pygame, pytmx, pyscroll

from pathmanager import PathManager

@dataclass
class Portal:
    src_map: str        # Map where the character is located
    src_point: str      # Point where the character location will be changed when he enter in collision witht this point
    target_map: str     # Map where the chacter is going to spawn after a collision with the refering point
    target_point: str   # Point where the charcter is going to spawn after being in the target map

@dataclass
class Map:
    name: str                       # Name of the map
    collisions: List[pygame.Rect]   # Lits of collisions
    group: pyscroll.PyscrollGroup   # The group of objects (ex: character)
    tmx_data: pytmx.TiledMap        # TMX Map data 
    portals: List[Portal]           # List of portals
    

class MapManager:
    def __init__(self, screen, character, default_map="map") -> None:
        self.maps = dict()
        self.current_map = default_map
        self.screen = screen
        self.character = character
        
        self.register_map(default_map, portals=[Portal("map", "enter_house", "house", "spawn_house")])
        self.register_map("house", portals=[Portal("house", "exit_house", "map", "spawn_world")])
        
    def position_character(self, name):
        pos = self.get_object(name)
        self.character.position[0] = pos.x - 10
        self.character.position[1] = pos.y - 20
        self.character.save_location()
        
    def register_map(self, name, portals=[]):
        # Load tmx utils to handle the game's map
        pathManager = PathManager()
        tmx_map = pathManager.map_path(name)
        tmx_data = pytmx.load_pygame(tmx_map)
        map_data = pyscroll.data.TiledMapData(tmx_data)
        map_layer = pyscroll.orthographic.BufferedRenderer(map_data, self.screen.get_size())
        map_layer.zoom = 3

        collisions = []

        for obj in tmx_data.objects:
            if obj.type == "collision":
                collisions.append(pygame.Rect(
                    obj.x, obj.y, obj.width, obj.height))

        # Draw layers groups
        group = pyscroll.PyscrollGroup(map_layer=map_layer, default_layer=1)

        # Add your layers here (like characters etc.)
        group.add(self.character)
    
        self.maps[name] = Map(name, collisions, group, tmx_data, portals)
    
    def check_collisions(self):
        # Handle Portals
        for portal in self.get_map().portals:
            if portal.src_map == self.current_map:
                # The object defined in the tmx map representing the collision to enter 
                point = self.get_object(portal.src_point)
                # The rectangle of the previous point
                rect = self.get_rect(point)
                if self.character.feet.colliderect(rect):
                    portal_cpy = portal
                    self.current_map = portal.target_map
                    self.position_character(portal_cpy.target_point)
        # Handle collisions
        for sprite in self.get_group().sprites():
            if sprite.feet.collidelist(self.get_collisions()) > -1:
                sprite.move_back()      
        
    def get_map(self): return self.maps[self.current_map]
    
    def get_group(self): return self.get_map().group
    
    def get_collisions(self): return self.get_map().collisions
    
    def get_object(self, name): return self.get_map().tmx_data.get_object_by_name(name)
    
    def get_rect(self, object): return pygame.Rect(object.x, object.y, object.width, object.height)
    
    def draw(self):
        self.get_group().draw(self.screen)
        self.get_group().center(self.character.rect.center)
        
    def update(self):
        self.get_group().update()
        self.check_collisions()
