import math
import heapq

import pygame

from animation import AnimationDirection
from constants import C_ATTACK_ANIMATION_COUNT
from movement import resolve_movement_collisions


class CombatSystem:
    AGGRO_RANGE = 180
    ATTACK_RANGE = 64
    ATTACK_LATERAL_TOLERANCE = 24
    NPC_ATTACK_RANGE = 32
    NPC_ATTACK_LATERAL_TOLERANCE = 20
    PATH_GRID_SIZE = 8
    PLAYER_ATTACK_COOLDOWN_MS = 450
    PLAYER_ATTACK_DAMAGE = 20
    PLAYER_ATTACK_COST = 8
    KI_REGEN_PER_SECOND = 12

    def __init__(self, player, screen_size):
        self.player = player
        self.screen_size = screen_size
        self.last_update_ms = pygame.time.get_ticks()
        self.last_player_attack_ms = self.last_update_ms - self.PLAYER_ATTACK_COOLDOWN_MS
        self.font = pygame.font.Font(None, 30)

    def update(self, npcs, collisions, player_attacking=False):
        now = pygame.time.get_ticks()
        elapsed_seconds = max(0, now - self.last_update_ms) / 1000
        self.last_update_ms = now
        self.player.ki = min(
            self.player.max_ki,
            self.player.ki + self.KI_REGEN_PER_SECOND * elapsed_seconds,
        )

        if player_attacking:
            self._player_attack(npcs, now)

        for npc in tuple(npcs):
            if npc.hp <= 0:
                npc.is_defeated = True
                npc.combat_engaged = True
                continue

            distance = self._distance(self.player.feet.center, npc.feet.center)
            was_engaged = npc.combat_engaged
            npc.combat_engaged = distance <= self.AGGRO_RANGE
            if not npc.combat_engaged:
                npc.chase_path = []
                npc.chase_target = None
                npc.chase_stuck_frames = 0
                if was_engaged:
                    # The player got away: go back to the patrol path
                    npc.resume_patrol()
                continue

            if not was_engaged:
                npc.last_attack_ms = now
                npc.chase_stuck_frames = 0
                npc.chase_path = []
                npc.chase_target = None

            if self._npc_in_attack_range(npc):
                npc.chase_stuck_frames = 0
                npc.chase_path = []
                # Keep fighting (animated) even when the player stands still
                npc.attack(f"Attack {npc.facing}", C_ATTACK_ANIMATION_COUNT)
                if now - npc.last_attack_ms >= npc.attack_cooldown_ms:
                    npc.last_attack_ms = now
                    self.player.take_damage(npc.attack_damage)
            else:
                self._move_toward(npc, self.player.feet.center, collisions)

    def _player_attack(self, npcs, now):
        if (
            now - self.last_player_attack_ms < self.PLAYER_ATTACK_COOLDOWN_MS
            or self.player.ki < self.PLAYER_ATTACK_COST
        ):
            return

        targets = [npc for npc in npcs if npc.hp > 0 and self._is_in_attack_range(npc)]
        if not targets:
            return

        target = min(targets, key=lambda npc: self._distance(self.player.rect.center, npc.rect.center))
        target.take_damage(self.PLAYER_ATTACK_DAMAGE)
        self.player.ki -= self.PLAYER_ATTACK_COST
        self.last_player_attack_ms = now

    def _player_attack_area(self):
        direction = getattr(self.player, "facing", self._facing(self.player.animation_name))
        origin = self.player.feet.center
        return origin, direction

    def _is_in_attack_range(self, npc):
        origin, direction = self._player_attack_area()
        target = npc.feet.center
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        if direction == AnimationDirection.UP.value:
            forward, lateral = -dy, dx
        elif direction == AnimationDirection.DOWN.value:
            forward, lateral = dy, dx
        elif direction == AnimationDirection.LEFT.value:
            forward, lateral = -dx, dy
        else:
            forward, lateral = dx, dy
        lateral_tolerance = (
            self.player.feet.width + npc.feet.width
        ) / 2 + self.ATTACK_LATERAL_TOLERANCE
        return 0 <= forward <= self.ATTACK_RANGE and abs(lateral) <= lateral_tolerance

    def _move_toward(self, npc, target, collisions):
        if npc.chase_path:
            target_cell = self._grid_cell(target)
            if self._distance(
                self._cell_to_feet_center(npc, npc.chase_target),
                self._cell_to_feet_center(npc, target_cell),
            ) > self.PATH_GRID_SIZE * 3:
                npc.chase_path = []
                npc.chase_target = None

        if npc.chase_path:
            waypoint = self._cell_to_feet_center(npc, npc.chase_path[0])
            if self._distance(npc.feet.center, waypoint) <= self.PATH_GRID_SIZE:
                npc.chase_path.pop(0)
            if npc.chase_path:
                waypoint = self._cell_to_feet_center(npc, npc.chase_path[0])
                self._step_toward(npc, waypoint, collisions)
                return

        starting_position = tuple(npc.position)
        self._step_toward(npc, target, collisions)
        if self._distance(starting_position, npc.position) < 0.01:
            npc.chase_stuck_frames += 1
        else:
            npc.chase_stuck_frames = 0

        if npc.chase_stuck_frames >= 4:
            npc.chase_path = self._find_path(npc, target, collisions)
            npc.chase_target = self._grid_cell(target)
            npc.chase_stuck_frames = 0
            if npc.chase_path:
                waypoint = self._cell_to_feet_center(npc, npc.chase_path[0])
                self._step_toward(npc, waypoint, collisions)

    def _step_toward(self, npc, target, collisions):
        dx = target[0] - npc.feet.centerx
        dy = target[1] - npc.feet.centery
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return
        direction = (
            AnimationDirection.RIGHT.value if dx >= 0 else AnimationDirection.LEFT.value
        ) if abs(dx) >= abs(dy) else (
            AnimationDirection.DOWN.value if dy >= 0 else AnimationDirection.UP.value
        )
        npc.move(f"Walk {direction}", 4, (dx, dy))
        npc.update()
        resolve_movement_collisions(npc, collisions)

    def _npc_in_attack_range(self, npc):
        origin = npc.feet.center
        target = self.player.feet.center
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        direction = getattr(npc, "facing", AnimationDirection.DOWN.value)
        if direction == AnimationDirection.UP.value:
            forward, lateral = -dy, dx
        elif direction == AnimationDirection.DOWN.value:
            forward, lateral = dy, dx
        elif direction == AnimationDirection.LEFT.value:
            forward, lateral = -dx, dy
        else:
            forward, lateral = dx, dy
        tolerance = (
            self.player.feet.width + npc.feet.width
        ) / 2 + self.NPC_ATTACK_LATERAL_TOLERANCE
        return 0 <= forward <= self.NPC_ATTACK_RANGE and abs(lateral) <= tolerance

    def _find_path(self, npc, target, collisions):
        start = self._grid_cell(npc.feet.center)
        target_cell = self._grid_cell(target)
        bounds = self._path_bounds(npc, target, collisions)
        frontier = [(0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}
        goal = None

        while frontier:
            _, current = heapq.heappop(frontier)
            if self._cell_within_attack_range(npc, current, target):
                goal = current
                break

            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (current[0] + dx, current[1] + dy)
                if not self._cell_in_bounds(neighbor, bounds):
                    continue
                if not self._cell_is_walkable(npc, neighbor, collisions):
                    continue

                new_cost = cost_so_far[current] + 1
                if neighbor in cost_so_far and new_cost >= cost_so_far[neighbor]:
                    continue
                cost_so_far[neighbor] = new_cost
                heuristic = abs(neighbor[0] - target_cell[0]) + abs(neighbor[1] - target_cell[1])
                heapq.heappush(frontier, (new_cost + heuristic, neighbor))
                came_from[neighbor] = current

        if goal is None:
            return []

        path = []
        current = goal
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path

    def _cell_within_attack_range(self, npc, cell, target):
        center = self._cell_to_feet_center(npc, cell)
        dx = target[0] - center[0]
        dy = target[1] - center[1]
        lateral_tolerance = self.NPC_ATTACK_LATERAL_TOLERANCE
        return (
            math.hypot(dx, dy) <= self.NPC_ATTACK_RANGE
            and abs(dx) <= self.NPC_ATTACK_RANGE + lateral_tolerance
            and abs(dy) <= self.NPC_ATTACK_RANGE + lateral_tolerance
        )

    def _cell_is_walkable(self, npc, cell, collisions):
        return not any(
            self._feet_at_position(npc, self._cell_to_position(npc, cell)).colliderect(obstacle)
            for obstacle in collisions
        )

    def _path_bounds(self, npc, target, collisions):
        points_x = [npc.feet.centerx, target[0]]
        points_y = [npc.feet.centery, target[1]]
        for obstacle in collisions:
            points_x.extend((obstacle.left, obstacle.right))
            points_y.extend((obstacle.top, obstacle.bottom))
        grid = self.PATH_GRID_SIZE
        return (
            math.floor(min(points_x) / grid) - 2,
            math.floor(max(points_x) / grid) + 2,
            math.floor(min(points_y) / grid) - 2,
            math.floor(max(points_y) / grid) + 2,
        )

    @staticmethod
    def _grid_cell(point):
        grid = CombatSystem.PATH_GRID_SIZE
        return round(point[0] / grid), round(point[1] / grid)

    def _cell_to_feet_center(self, npc, cell):
        return cell[0] * self.PATH_GRID_SIZE, cell[1] * self.PATH_GRID_SIZE

    def _cell_to_position(self, npc, cell):
        center_x, center_y = self._cell_to_feet_center(npc, cell)
        return (
            center_x - npc.rect.width / 2,
            center_y - npc.rect.height + npc.feet.height / 2,
        )

    def _feet_at_position(self, npc, position):
        x, y = position
        return pygame.Rect(
            x + (npc.rect.width - npc.feet.width) / 2,
            y + npc.rect.height - npc.feet.height,
            npc.feet.width,
            npc.feet.height,
        )

    @staticmethod
    def _cell_in_bounds(cell, bounds):
        min_x, max_x, min_y, max_y = bounds
        return min_x <= cell[0] <= max_x and min_y <= cell[1] <= max_y

    @staticmethod
    def _facing(animation_name):
        for direction in (
            AnimationDirection.UP.value,
            AnimationDirection.DOWN.value,
            AnimationDirection.LEFT.value,
            AnimationDirection.RIGHT.value,
        ):
            if direction in animation_name:
                return direction
        return AnimationDirection.DOWN.value

    @staticmethod
    def _distance(first, second):
        return math.hypot(first[0] - second[0], first[1] - second[1])

    def draw(self, screen):
        self._draw_bar(screen, "HP", self.player.hp, self.player.max_hp, (220, 55, 55), 20)
        self._draw_bar(screen, "KI", self.player.ki, self.player.max_ki, (65, 145, 245), 58)

    def _draw_bar(self, screen, label, value, maximum, color, y):
        x = 20
        bar_width = min(260, self.screen_size[0] // 3)
        bar_height = 22
        label_surface = self.font.render(label, True, (255, 255, 255))
        screen.blit(label_surface, (x, y))
        bar_x = x + 42
        bar_y = y + 3
        pygame.draw.rect(screen, (35, 35, 42), (bar_x, bar_y, bar_width, bar_height))
        fraction = max(0, min(1, value / maximum)) if maximum else 0
        pygame.draw.rect(
            screen,
            color,
            (bar_x, bar_y, round(bar_width * fraction), bar_height),
        )
        pygame.draw.rect(screen, (235, 235, 235), (bar_x, bar_y, bar_width, bar_height), 2)
