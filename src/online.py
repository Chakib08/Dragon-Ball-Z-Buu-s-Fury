"""Online 1v1: the lobby screen, the opponent's fighter and the match.

Each game is the authority on its own fighter: it sends a snapshot of it
(position, frame, health...) about 30 times a second, checks its own punches
and beams against the opponent, and sends a "hit" when one lands. The game
that receives the hit applies it with its own rules (guard, knockback,
Super Saiyan), so both games agree on every health bar.
"""

import math
import random

import pygame

from character import Character
from map import MapManager
from saiyan import Saiyan
import settings as user_settings
from taps import tap_position


def _number(value, default=None):
    """value as a finite float, else default: JSON from the network may hold
    NaN or Infinity, which would crash the drawing (health bars, positions)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _tap_position(event, screen_size):
    """Where a tap or click happened, or None (a touch counts once, see taps.py)."""
    return tap_position(event, screen_size)


class RemoteFighter(Character):
    """The opponent, drawn from the snapshots its own game sends."""

    # Share of the gap to the latest received position covered each frame
    SMOOTHING = 0.35
    # Further than this (a knockback, a late packet), jump straight there
    SNAP_DISTANCE = 48

    def __init__(self, character_name, player_name, send):
        super().__init__(0, 0, character_name)
        self.player_name = player_name
        self.bar_label = f"{player_name} ({character_name.capitalize()})"
        self._send = send
        self.target_position = None
        self._remote_powered = False

    @property
    def powered_up(self):
        return self._remote_powered

    def place(self, x, y, facing):
        self.position = [x, y]
        self.target_position = [x, y]
        self.facing = facing
        self.face_idle()
        self.update()

    def apply_snapshot(self, state):
        x, y = _number(state.get("x")), _number(state.get("y"))
        if x is None or y is None:
            return
        if self.target_position is None:
            self.position = [x, y]
        self.target_position = [x, y]
        self.facing = state.get("facing", self.facing)
        form = state.get("form")
        if form in self.forms:
            self.set_form(form)
        self.max_hp = max(1.0, _number(state.get("max_hp"), self.max_hp))
        self.hp = min(self.max_hp, max(0.0, _number(state.get("hp"), self.hp)))
        self.ki = max(0.0, _number(state.get("ki"), self.ki))
        self.blocking = bool(state.get("blocking", False))
        self._remote_powered = bool(state.get("powered", False))

        if "faint" in state:
            if not self.faint_frames:
                self.faint_frames = self._load_faint_frames()
            if self.faint_frames:
                self.faint_index = min(max(0, int(_number(state["faint"], 0))), len(self.faint_frames) - 1)
                self.image = self.faint_frames[self.faint_index]
                self.faint_finished = self.faint_index == len(self.faint_frames) - 1
            return
        self.faint_frames = None
        self.faint_finished = False
        frame = state.get("frame")
        if isinstance(frame, list) and len(frame) == 2 and self.has_animation(str(frame[0])):
            self.image = self.get_image_by_animation_name(str(frame[0]), bool(frame[1]))

    def follow_snapshot(self):
        """Move smoothly towards the latest received position."""
        if self.target_position is None:
            return
        dx = self.target_position[0] - self.position[0]
        dy = self.target_position[1] - self.position[1]
        if abs(dx) > self.SNAP_DISTANCE or abs(dy) > self.SNAP_DISTANCE:
            self.position = list(self.target_position)
        else:
            self.position[0] += dx * self.SMOOTHING
            self.position[1] += dy * self.SMOOTHING
        self.update()

    def take_damage(self, amount, source=None, push=1.0):
        """A hit landed on the opponent: its own game applies it."""
        self._send({
            "t": "hit",
            "damage": round(float(amount), 2),
            "source": [round(source[0], 2), round(source[1], 2)] if source else None,
            "push": round(float(push), 2),
        })
        return amount


class OnlineMatch:
    """A 1v1 on the world map against a player from the lobby."""

    SEND_INTERVAL_MS = 33
    RESULT_MS = 3500
    # Share of each hit that gets through online, so a match lasts (players
    # have no NPC toughness and both hit at full pace)
    DAMAGE_TAKEN = 0.4
    # Feet positions on the path in front of the house, facing each other
    SPAWNS = ((139, 289, "Right"), (199, 289, "Left"))
    RESULTS = {
        "win": "YOU WIN!",
        "lose": "YOU LOSE",
        "left": "Your opponent left",
        "disconnected": "Connection lost",
    }

    def __init__(self, game, net, start):
        self.game = game
        self.net = net
        slot = 1 if start.get("slot") == 1 else 0
        opponent = start.get("opponent") or {}

        x, y, facing = self.SPAWNS[slot]
        self.player = Saiyan(x, y, False, game.menu.selected_character)
        self.player.damage_taken = self.DAMAGE_TAKEN
        self.player.facing = facing
        self.player.face_idle()
        character = opponent.get("character", "goku")
        if character not in game.menu.character_names:
            character = "goku"
        self.opponent = RemoteFighter(character, str(opponent.get("name", "Opponent")), net.send)
        ox, oy, ofacing = self.SPAWNS[1 - slot]
        self.opponent.place(ox, oy, ofacing)

        game.character = self.player
        game.map_manager = MapManager(game.screen, self.player, versus=True, opponents=[self.opponent])
        game.map_manager.combat.on_technique = self._send_technique
        self.result = None
        self.result_since = None
        self.last_sent_ms = -self.SEND_INTERVAL_MS
        self._fonts(game.resolution)

    def _fonts(self, resolution):
        self.banner_font = pygame.font.Font(None, max(48, resolution[1] // 7))
        self.info_font = pygame.font.Font(None, max(22, resolution[1] // 28))

    def _send_technique(self, technique_id, direction, origin, power=None):
        """Show the opponent the technique just released (its own sprites)."""
        message = {"t": "tech", "id": technique_id, "dir": direction, "origin": origin}
        if power is not None:
            message["power"] = round(power, 3)
        self.net.send(message)

    def _finish(self, result):
        if self.result is None:
            self.result = result
            self.result_since = pygame.time.get_ticks()

    def handle_messages(self, messages):
        combat = self.game.map_manager.combat
        for message in messages:
            kind = message.get("t")
            if kind == "state":
                self.opponent.apply_snapshot(message)
            elif kind == "hit" and self.result is None and self.player.hp > 0:
                source = message.get("source")
                try:
                    damage = max(0.0, _number(message.get("damage", 0), 0.0))
                    source = (_number(source[0]), _number(source[1])) if source else None
                    push = min(5.0, max(0.0, _number(message.get("push", 1.0), 1.0)))
                except (TypeError, IndexError, KeyError):
                    continue
                if source is not None and None in source:
                    source = None
                self.player.take_damage(damage, source, push)
            elif kind == "tech":
                try:
                    origin = (_number(message["origin"][0]), _number(message["origin"][1]))
                    if None in origin:
                        continue
                    power = message.get("power")
                    power = None if power is None else max(0.0, min(1.0, _number(power, 1.0)))
                    combat.show_opponent_technique(self.opponent, str(message["id"]),
                                                   str(message["dir"]), origin, power)
                except (KeyError, TypeError, ValueError, IndexError):
                    pass
            elif kind == "ko":
                # Its last state may not have arrived yet
                self.opponent.hp = 0
                self._finish("win")
            elif kind == "opponent_left":
                self._finish("left")
        if self.net.status == "error":
            self._finish("disconnected")

    def after_frame(self):
        now = pygame.time.get_ticks()
        if now - self.last_sent_ms >= self.SEND_INTERVAL_MS:
            self.last_sent_ms = now
            self.net.send({"t": "state", **self.player.snapshot()})
        if self.player.hp <= 0 and self.result is None:
            self.net.send({"t": "ko"})
            self._finish("lose")

    @property
    def finished(self):
        return (
            self.result is not None
            and pygame.time.get_ticks() - self.result_since >= self.RESULT_MS
        )

    def draw(self, screen):
        width, height = screen.get_size()
        names = self.info_font.render(
            f"{self.player.character_name.capitalize()} (you)  vs  {self.opponent.bar_label}",
            True, (255, 255, 255),
        )
        screen.blit(names, names.get_rect(midtop=(width / 2, 8)))
        if self.result is None:
            return
        shade = pygame.Surface((width, height // 4), pygame.SRCALPHA)
        shade.fill((10, 12, 20, 170))
        screen.blit(shade, (0, height * 3 // 8))
        color = (255, 220, 90) if self.result == "win" else (240, 240, 240)
        text = self.banner_font.render(self.RESULTS[self.result], True, color)
        screen.blit(text, text.get_rect(center=(width / 2, height / 2)))


class LobbyScreen:
    """Connect to the server, list the rooms, create or join one."""

    BACKGROUND = (12, 14, 24)
    PANEL = (25, 30, 45)
    BUTTON = (60, 110, 190)
    BUTTON_ALT = (90, 95, 110)
    ROOM = (40, 48, 70)
    TEXT = (255, 255, 255)
    DIM = (180, 185, 200)
    ACCENT = (255, 220, 90)
    MAX_ROOMS_SHOWN = 5

    def __init__(self, net, screen_size, character, background=None):
        self.net = net
        self.screen_size = screen_size
        self.character = character
        self.background = background
        self.settings = user_settings.load()
        self.name = f"{character.capitalize()} {random.randint(100, 999)}"
        self.rooms = []
        self.room_id = None  # our room while waiting in it
        self.notice = ""
        self.editing = None  # text being typed for the server address
        self.buttons = {}
        self.room_buttons = []
        self._said_hello = False
        height = screen_size[1]
        self.title_font = pygame.font.Font(None, max(40, height // 12))
        self.font = pygame.font.Font(None, max(24, height // 22))
        self.small_font = pygame.font.Font(None, max(20, height // 30))
        self.connect()

    # ---- Connection -------------------------------------------------------------
    @property
    def address(self):
        return f"{self.settings['server_host']}:{self.settings['server_port']}"

    def connect(self):
        self._said_hello = False
        self.rooms = []
        self.room_id = None
        self.net.connect(self.settings["server_host"], self.settings["server_port"])

    def after_match(self):
        """Back from a match: still connected, show the rooms again."""
        self.room_id = None
        self.notice = ""
        self.net.send({"t": "list"})

    def _handle_messages(self):
        for message in self.net.poll():
            kind = message.get("t")
            if kind == "welcome" and not self._said_hello:
                self._said_hello = True
                self.net.send({"t": "hello", "name": self.name, "character": self.character})
            elif kind == "rooms":
                self.rooms = [room for room in message.get("rooms", []) if isinstance(room, dict)]
            elif kind == "waiting":
                self.room_id = message.get("room")
                self.notice = ""
            elif kind == "error":
                self.notice = str(message.get("message", ""))
            elif kind == "start":
                return message
        return None

    # ---- Actions --------------------------------------------------------------------
    def create_room(self):
        if self.net.connected and self.room_id is None:
            self.net.send({"t": "create"})

    def join_room(self, room_id):
        if self.net.connected and self.room_id is None:
            self.net.send({"t": "join", "room": room_id})

    def cancel_waiting(self):
        if self.room_id is not None:
            self.net.send({"t": "leave"})
            self.room_id = None
            self.net.send({"t": "list"})

    def start_editing(self):
        self.editing = self.address
        pygame.key.start_text_input()  # shows the keyboard on Android

    def finish_editing(self, keep):
        text, self.editing = self.editing, None
        pygame.key.stop_text_input()
        if not keep:
            return
        address = user_settings.parse_address(text)
        if address is None:
            self.notice = "Address must look like 192.168.1.20:5050"
            return
        self.settings["server_host"], self.settings["server_port"] = address
        user_settings.save(self.settings)
        self.notice = ""
        self.connect()

    def update(self, events):
        """Handle this frame. Returns "back", a "start" message, or None."""
        start = self._handle_messages()
        if start is not None:
            return start
        for event in events:
            action = self._handle_event(event)
            if action is not None:
                return action
        return None

    def _handle_event(self, event):
        if self.editing is not None:
            if event.type == pygame.TEXTINPUT:
                self.editing += event.text
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    self.editing = self.editing[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.finish_editing(keep=True)
                elif event.key == pygame.K_ESCAPE:
                    self.finish_editing(keep=False)
            position = _tap_position(event, self.screen_size)
            if position is not None:
                if self.buttons.get("save", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
                    self.finish_editing(keep=True)
                elif self.buttons.get("cancel_edit", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
                    self.finish_editing(keep=False)
            return None

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_AC_BACK):
                if self.room_id is not None:
                    self.cancel_waiting()
                    return None
                return "back"
            if event.key == pygame.K_c:
                self.create_room()
            elif event.key == pygame.K_r:
                if self.net.status == "error":
                    self.connect()
                else:
                    self.net.send({"t": "list"})
            elif event.key == pygame.K_e:
                self.start_editing()
            elif pygame.K_1 <= event.key <= pygame.K_9:
                index = event.key - pygame.K_1
                if index < len(self.rooms):
                    self.join_room(self.rooms[index].get("id"))
            return None

        position = _tap_position(event, self.screen_size)
        if position is None:
            return None
        for name, rect in self.buttons.items():
            if rect.collidepoint(position):
                return self._press(name)
        for room_id, rect in self.room_buttons:
            if rect.collidepoint(position):
                self.join_room(room_id)
        return None

    def _press(self, name):
        if name == "back":
            return "back"
        if name == "create":
            self.create_room()
        elif name == "cancel":
            self.cancel_waiting()
        elif name == "refresh":
            if self.net.status == "error":
                self.connect()
            else:
                self.net.send({"t": "list"})
        elif name == "server":
            self.start_editing()
        return None

    # ---- Drawing --------------------------------------------------------------------
    def _button(self, screen, name, rect, label, color):
        pygame.draw.rect(screen, color, rect, border_radius=10)
        pygame.draw.rect(screen, (235, 235, 235), rect, 2, border_radius=10)
        text = self.font.render(label, True, self.TEXT)
        screen.blit(text, text.get_rect(center=rect.center))
        self.buttons[name] = rect

    def draw(self, screen):
        width, height = self.screen_size
        if self.background is not None:
            screen.blit(self.background, (0, 0))
        else:
            screen.fill(self.BACKGROUND)
        panel = pygame.Rect(0, 0, min(width - 32, max(560, width * 0.6)), height - 32)
        panel.center = (width / 2, height / 2)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill((*self.PANEL, 225))
        screen.blit(shade, panel.topleft)
        pygame.draw.rect(screen, (235, 235, 235), panel, 2, border_radius=12)
        self.buttons = {}
        self.room_buttons = []

        line = self.font.get_linesize()
        y = panel.top + line * 0.5
        title = self.title_font.render("ONLINE 1V1", True, self.ACCENT)
        screen.blit(title, title.get_rect(midtop=(panel.centerx, y)))
        y += title.get_height() + line * 0.4

        # Server address (tap to change)
        server_rect = pygame.Rect(panel.left + line, y, panel.width - line * 2, line * 1.6)
        if self.editing is not None:
            pygame.draw.rect(screen, (250, 250, 250), server_rect, border_radius=8)
            text = self.font.render(f"Server: {self.editing}|", True, (20, 20, 30))
            screen.blit(text, text.get_rect(midleft=(server_rect.left + line / 2, server_rect.centery)))
        else:
            self._button(screen, "server", server_rect, f"Server: {self.address}  (change)", self.ROOM)
        y = server_rect.bottom + line * 0.4

        status = {
            "connecting": ("Connecting...", self.DIM),
            "connected": (f"Connected as {self.name}", (140, 230, 140)),
            "error": (self.net.error or "Not connected", (255, 140, 120)),
            "offline": ("Not connected", self.DIM),
        }[self.net.status]
        text = self.small_font.render(status[0], True, status[1])
        screen.blit(text, text.get_rect(midtop=(panel.centerx, y)))
        y += text.get_height() + line * 0.3
        if self.notice:
            text = self.small_font.render(self.notice, True, (255, 180, 120))
            screen.blit(text, text.get_rect(midtop=(panel.centerx, y)))
            y += text.get_height() + line * 0.3

        bottom_y = panel.bottom - line * 2.2
        button_height = line * 1.6
        if self.editing is not None:
            half = (panel.width - line * 3) / 2
            self._button(screen, "save", pygame.Rect(panel.left + line, bottom_y, half, button_height),
                         "Save", self.BUTTON)
            self._button(screen, "cancel_edit",
                         pygame.Rect(panel.left + line * 2 + half, bottom_y, half, button_height),
                         "Cancel", self.BUTTON_ALT)
            return

        if self.room_id is not None:
            text = self.font.render(f"Room {self.room_id}: waiting for an opponent...", True, self.TEXT)
            screen.blit(text, text.get_rect(midtop=(panel.centerx, y + line)))
            rect = pygame.Rect(0, 0, panel.width / 2, button_height)
            rect.midtop = (panel.centerx, bottom_y)
            self._button(screen, "cancel", rect, "Cancel", self.BUTTON_ALT)
            return

        # Rooms waiting for an opponent (tap to join)
        if self.net.connected:
            label = "Rooms (tap to join):" if self.rooms else "No rooms yet: create one!"
            text = self.small_font.render(label, True, self.DIM)
            screen.blit(text, (panel.left + line, y))
            y += text.get_height() + line * 0.3
            row_height = line * 1.5
            for index, room in enumerate(self.rooms[: self.MAX_ROOMS_SHOWN]):
                if y + row_height > bottom_y - line * 0.3:
                    break
                rect = pygame.Rect(panel.left + line, y, panel.width - line * 2, row_height)
                pygame.draw.rect(screen, self.ROOM, rect, border_radius=8)
                label = (f"{index + 1}. Room {room.get('id')}: {room.get('host', '?')} "
                         f"({str(room.get('character', '?')).capitalize()})  -  Join")
                text = self.font.render(label, True, self.TEXT)
                screen.blit(text, text.get_rect(midleft=(rect.left + line / 2, rect.centery)))
                self.room_buttons.append((room.get("id"), rect))
                y += row_height + line * 0.3

        third = (panel.width - line * 4) / 3
        left = panel.left + line
        create_label = "Create room" if self.net.connected else "-"
        self._button(screen, "create", pygame.Rect(left, bottom_y, third, button_height), create_label,
                     self.BUTTON if self.net.connected else self.BUTTON_ALT)
        retry = self.net.status == "error"
        self._button(screen, "refresh", pygame.Rect(left + third + line, bottom_y, third, button_height),
                     "Retry" if retry else "Refresh", self.BUTTON_ALT)
        self._button(screen, "back", pygame.Rect(left + (third + line) * 2, bottom_y, third, button_height),
                     "Back", self.BUTTON_ALT)
