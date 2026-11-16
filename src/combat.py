import math
import heapq

import pygame

from animation import AnimationDirection
from character import DIRECTION_VECTORS
from movement import resolve_movement_collisions


class CombatSystem:
    AGGRO_RANGE = 180
    ATTACK_RANGE = 64
    ATTACK_LATERAL_TOLERANCE = 24
    NPC_ATTACK_RANGE = 32
    NPC_ATTACK_LATERAL_TOLERANCE = 20
    PATH_GRID_SIZE = 8
    # One punch or kick per button press, at most one every
    # Character.ATTACK_COOLDOWN_MS (the pace NPCs strike at too)
    PLAYER_ATTACK_DAMAGE = 15
    PLAYER_ATTACK_COST = 3
    KI_REGEN_PER_SECOND = 12
    # Super Saiyan: hits harder, but burns ki instead of regenerating it
    SUPER_DAMAGE_MULTIPLIER = 1.5
    SUPER_KI_DRAIN_PER_SECOND = 5
    # Special technique (energy beam)
    SPECIAL_COST = 30
    SPECIAL_DAMAGE = 70
    SPECIAL_COOLDOWN_MS = 1200
    SPECIAL_RANGE = 220
    SPECIAL_SPEED = 9
    SPECIAL_WIDTH = 10
    SPECIAL_HOLD_TICKS = 30
    SPECIAL_FADE_TICKS = 12
    SPECIAL_COLORS = {"vegeta": (255, 225, 90)}
    SPECIAL_DEFAULT_COLOR = (90, 200, 255)

    def __init__(self, player, screen_size):
        self.player = player
        self.screen_size = screen_size
        self.last_update_ms = pygame.time.get_ticks()
        self.last_player_attack_ms = self.last_update_ms - player.ATTACK_COOLDOWN_MS
        # True when the last update() started a player attack
        self.player_swung = False
        self.last_special_ms = self.last_update_ms - self.SPECIAL_COOLDOWN_MS
        self.beams = []
        self.font = pygame.font.Font(None, 30)
        self.name_font = pygame.font.Font(None, 22)
        # Text is rendered once and reused every frame
        self._labels = {}

    def update(self, npcs, collisions, player_attacking=False):
        now = pygame.time.get_ticks()
        elapsed_seconds = max(0, now - self.last_update_ms) / 1000
        self.last_update_ms = now
        if self.player.is_super:
            self.player.ki = max(
                0, self.player.ki - self.SUPER_KI_DRAIN_PER_SECOND * elapsed_seconds
            )
            if self.player.ki <= 0:
                self.player.revert()
        else:
            self.player.ki = min(
                self.player.max_ki,
                self.player.ki + self.KI_REGEN_PER_SECOND * elapsed_seconds,
            )
        self._update_beams(npcs)

        self.player_swung = False
        player_down = self.player.hp <= 0
        if player_down:
            self.player.faint()
        elif player_attacking:
            self._player_attack(npcs, now)

        for npc in tuple(npcs):
            if npc.hp <= 0:
                npc.is_defeated = True
                npc.combat_engaged = True
                npc.faint()
                continue

            # Flinching or transforming: no chasing or attacking meanwhile
            if npc.update_action():
                continue

            distance = self._distance(self.player.feet.center, npc.feet.center)
            was_engaged = npc.combat_engaged
            npc.combat_engaged = distance <= self.AGGRO_RANGE and not player_down
            if not npc.combat_engaged:
                npc.chase_path = []
                npc.chase_target = None
                npc.chase_stuck_frames = 0
                if was_engaged:
                    # The player got away: go back to the patrol path
                    npc.resume_patrol()
                continue

            npc.update_ai()
            if npc.action is not None:
                continue

            if not was_engaged:
                npc.last_attack_ms = now
                npc.chase_stuck_frames = 0
                npc.chase_path = []
                npc.chase_target = None

            if self._npc_in_attack_range(npc):
                npc.chase_stuck_frames = 0
                npc.chase_path = []
                # One punch or kick at a time, at the same pace as the player
                if now - npc.last_attack_ms >= npc.attack_cooldown_ms:
                    npc.last_attack_ms = now
                    npc.strike()
                    self.player.take_damage(npc.attack_damage * self._damage_multiplier(npc))
                else:
                    npc.face_idle()
            else:
                self._move_toward(npc, self.player.feet.center, collisions)

    def _player_attack(self, npcs, now):
        """Strike once, if the player is free to: plays one punch or kick
        and hits the closest enemy in front, if there is one."""
        player = self.player
        if (
            now - self.last_player_attack_ms < player.ATTACK_COOLDOWN_MS
            or player.action is not None
            or player.ki < self.PLAYER_ATTACK_COST
        ):
            return

        self.last_player_attack_ms = now
        self.player_swung = True
        player.strike()

        targets = [npc for npc in npcs if npc.hp > 0 and self._is_in_attack_range(npc)]
        if not targets:
            return
        target = min(targets, key=lambda npc: self._distance(player.rect.center, npc.rect.center))
        target.take_damage(self.PLAYER_ATTACK_DAMAGE * self._damage_multiplier(player))
        player.ki -= self.PLAYER_ATTACK_COST

    def _damage_multiplier(self, attacker):
        return self.SUPER_DAMAGE_MULTIPLIER if attacker.is_super else 1

    # ---- Special technique -------------------------------------------------
    def start_special(self):
        """Charge, then fire an energy beam in the facing direction.

        Returns True if the technique started (enough ki, not busy, off cooldown).
        """
        player = self.player
        now = pygame.time.get_ticks()
        if (
            player.hp <= 0
            or player.action is not None
            or player.ki < self.SPECIAL_COST
            or now - self.last_special_ms < self.SPECIAL_COOLDOWN_MS
        ):
            return False

        facing = player.facing
        started = player.start_action(
            "special",
            f"Special {facing}",
            clock_speed=player.SPECIAL_CLOCK_SPEED,
            hold_ticks=self.SPECIAL_HOLD_TICKS,
            on_last_frame=lambda: self._fire_beam(facing),
        )
        if not started:
            return False
        player.ki -= self.SPECIAL_COST
        self.last_special_ms = now
        return True

    def _fire_beam(self, facing):
        player = self.player
        direction = DIRECTION_VECTORS[facing]
        # Start at the edge of the body, at chest height for sideways shots
        origin = (
            player.rect.centerx + direction[0] * player.rect.width / 2,
            player.rect.centery + 2 + direction[1] * player.rect.height / 2,
        )
        self.beams.append({
            "origin": origin,
            "direction": direction,
            "length": 0,
            "damage": self.SPECIAL_DAMAGE * self._damage_multiplier(player),
            "color": self.SPECIAL_COLORS.get(player.character_name, self.SPECIAL_DEFAULT_COLOR),
            "stopped": False,
            "fade": self.SPECIAL_FADE_TICKS,
        })

    def _beam_rect(self, beam):
        (x, y), (dx, dy) = beam["origin"], beam["direction"]
        half = self.SPECIAL_WIDTH / 2
        end_x, end_y = x + dx * beam["length"], y + dy * beam["length"]
        left, top = min(x, end_x) - half * abs(dy), min(y, end_y) - half * abs(dx)
        return pygame.Rect(
            round(left),
            round(top),
            max(1, round(abs(end_x - x) + self.SPECIAL_WIDTH * abs(dy))),
            max(1, round(abs(end_y - y) + self.SPECIAL_WIDTH * abs(dx))),
        )

    def _update_beams(self, npcs):
        for beam in tuple(self.beams):
            if beam["stopped"]:
                beam["fade"] -= 1
                if beam["fade"] <= 0:
                    self.beams.remove(beam)
                continue

            beam["length"] = min(self.SPECIAL_RANGE, beam["length"] + self.SPECIAL_SPEED)
            rect = self._beam_rect(beam)
            hit = [npc for npc in npcs if npc.hp > 0 and rect.colliderect(npc.rect)]
            if hit:
                target = min(hit, key=lambda npc: self._distance(beam["origin"], npc.rect.center))
                target.take_damage(beam["damage"])
                # The beam ends on the enemy it hit
                beam["length"] = min(
                    beam["length"], self._distance(beam["origin"], target.rect.center)
                )
                beam["stopped"] = True
            elif beam["length"] >= self.SPECIAL_RANGE:
                beam["stopped"] = True

    def draw_beams(self, screen, to_screen_rect):
        for beam in self.beams:
            rect = pygame.Rect(to_screen_rect(self._beam_rect(beam)))
            alpha = 255 if not beam["stopped"] else round(255 * beam["fade"] / self.SPECIAL_FADE_TICKS)
            horizontal = beam["direction"][0] != 0
            thickness = rect.height if horizontal else rect.width
            # Glowing head at the tip, a little wider than the beam
            head_radius = round(thickness * 0.85)
            pad = head_radius
            layer = pygame.Surface((rect.width + pad * 2, rect.height + pad * 2), pygame.SRCALPHA)
            body = pygame.Rect(pad, pad, rect.width, rect.height)
            core = body.inflate(0, -thickness // 2) if horizontal else body.inflate(-thickness // 2, 0)
            tip = {
                (1, 0): body.midright, (-1, 0): body.midleft,
                (0, 1): body.midbottom, (0, -1): body.midtop,
            }[beam["direction"]]
            pygame.draw.rect(layer, (*beam["color"], 235), body, border_radius=thickness // 2)
            pygame.draw.circle(layer, (*beam["color"], 235), tip, head_radius)
            pygame.draw.rect(layer, (255, 255, 255, 255), core, border_radius=thickness // 4)
            pygame.draw.circle(layer, (255, 255, 255, 255), tip, head_radius // 2)
            layer.set_alpha(alpha)
            screen.blit(layer, (rect.x - pad, rect.y - pad))

    def _player_attack_area(self):
        return self.player.feet.center, self.player.facing

    def _is_in_attack_range(self, npc):
        origin, direction = self._player_attack_area()
        target = npc.feet.center
        forward, lateral = self._forward_lateral(direction, origin, target)
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
        forward, lateral = self._forward_lateral(npc.facing, origin, target)
        tolerance = (
            self.player.feet.width + npc.feet.width
        ) / 2 + self.NPC_ATTACK_LATERAL_TOLERANCE
        return 0 <= forward <= self.NPC_ATTACK_RANGE and abs(lateral) <= tolerance

    @staticmethod
    def _forward_lateral(direction, origin, target):
        """Offset of target from origin, split along and across the facing direction."""
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        if direction == AnimationDirection.UP.value:
            return -dy, dx
        if direction == AnimationDirection.DOWN.value:
            return dy, dx
        if direction == AnimationDirection.LEFT.value:
            return -dx, dy
        return dx, dy

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
    def _distance(first, second):
        return math.hypot(first[0] - second[0], first[1] - second[1])

    def draw(self, screen):
        self._draw_bar(screen, "HP", self.player.hp, self.player.max_hp, (220, 55, 55), 20)
        ki_color = self.SUPER_COLOR if self.player.is_super else (65, 145, 245)
        self._draw_bar(screen, "KI", self.player.ki, self.player.max_ki, ki_color, 58)

    NPC_BAR_MIN_WIDTH = 120
    NPC_BAR_HEIGHT = 14
    NPC_BAR_GAP = 8
    SUPER_COLOR = (245, 205, 60)
    FRAME_COLOR = (235, 235, 235)

    def _label(self, text, font):
        key = (text, font)
        label = self._labels.get(key)
        if label is None:
            label = self._labels[key] = font.render(text, True, (255, 255, 255))
        return label

    def draw_npc_bars(self, screen, npcs, to_screen_rect):
        """Draw a health bar above each NPC.

        to_screen_rect converts a rect in map coordinates to screen coordinates.
        The bar stays (empty) during the knock-out animation, then disappears.
        """
        for npc in npcs:
            if npc.faint_finished:
                continue
            on_screen = pygame.Rect(to_screen_rect(npc.rect))
            width = max(self.NPC_BAR_MIN_WIDTH, on_screen.width)
            bar = pygame.Rect(0, 0, width, self.NPC_BAR_HEIGHT)
            bar.midbottom = (on_screen.centerx, on_screen.top - self.NPC_BAR_GAP)
            fraction = max(0, min(1, npc.hp / npc.max_hp)) if npc.max_hp else 0
            pygame.draw.rect(screen, (35, 35, 42), bar)
            pygame.draw.rect(
                screen,
                (220, 55, 55),
                (bar.x, bar.y, round(bar.width * fraction), bar.height),
            )
            # Gold frame while the NPC is a Super Saiyan
            frame_color = self.SUPER_COLOR if npc.is_super else self.FRAME_COLOR
            pygame.draw.rect(screen, frame_color, bar, 2)
            name = self._label(npc.character_name.capitalize(), self.name_font)
            screen.blit(name, name.get_rect(midbottom=(bar.centerx, bar.top - 2)))

    def _draw_bar(self, screen, label, value, maximum, color, y):
        x = 20
        bar_width = min(260, self.screen_size[0] // 3)
        bar_height = 22
        screen.blit(self._label(label, self.font), (x, y))
        bar_x = x + 42
        bar_y = y + 3
        pygame.draw.rect(screen, (35, 35, 42), (bar_x, bar_y, bar_width, bar_height))
        fraction = max(0, min(1, value / maximum)) if maximum else 0
        pygame.draw.rect(
            screen,
            color,
            (bar_x, bar_y, round(bar_width * fraction), bar_height),
        )
        pygame.draw.rect(screen, self.FRAME_COLOR, (bar_x, bar_y, bar_width, bar_height), 2)
