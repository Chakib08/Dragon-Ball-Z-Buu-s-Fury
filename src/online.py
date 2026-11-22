"""Online 1v1: the lobby screen, the opponent's fighter and the match.

Each game is the authority on its own fighter: it sends a snapshot of it
(position, frame, health...) about 30 times a second, checks its own punches
and beams against the opponent, and sends a "hit" when one lands. The game
that receives the hit applies it with its own rules (guard, knockback,
Super Saiyan), so both games agree on every health bar.
"""

import math
import random
from collections import deque

import pygame

from character import Character
from combat import CombatSystem
from map import MAX_ALLIES, MapManager
from net import PROTOCOL_VERSION
from npc import HEROES
from saiyan import Saiyan
import settings as user_settings
from taps import tap_position
from utils import timing
import arenas
import epic
import roster
from roster import display_name


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
    """A fighter of the opponent's side (the other player, or one of its
    allies in a team match), drawn from the snapshots its own game sends.
    index: which of that side's fighters (0: the player, 1-3: its allies),
    for the hits sent to its game."""

    # Share of the gap to the latest received position covered each frame
    SMOOTHING = 0.35
    # Further than this (a knockback, a late packet), jump straight there
    SNAP_DISTANCE = 48

    def __init__(self, character_name, player_name, send, index=0):
        super().__init__(0, 0, character_name)
        self.player_name = player_name
        self.index = index
        self._label()
        self._send = send
        self.target_position = None
        self._remote_powered = False
        self.changed = False

    def _label(self):
        name = display_name(self.character_name)
        self.bar_label = f"{self.player_name} ({name})" if self.index == 0 else f"{name} ({self.player_name})"

    def become(self, name):
        target = self.target_position
        super().become(name)
        self.target_position = target
        self._label()

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
        character = state.get("character")
        if isinstance(character, str) and character != self.character_name and roster.installed(character) \
                and character in roster.characters():
            # The other player fused, or Cell absorbed an android
            self.become(character)
            self.changed = True
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
            self.image = self.frame_image(str(frame[0]), bool(frame[1]))

    def follow_snapshot(self):
        """Move smoothly towards the latest received position."""
        if self.target_position is None:
            return
        dx = self.target_position[0] - self.position[0]
        dy = self.target_position[1] - self.position[1]
        if abs(dx) > self.SNAP_DISTANCE or abs(dy) > self.SNAP_DISTANCE:
            self.position = list(self.target_position)
        else:
            share = timing.smoothing(self.SMOOTHING)
            self.position[0] += dx * share
            self.position[1] += dy * share
        self.update()

    def take_damage(self, amount, source=None, push=1.0):
        """A hit landed on the opponent: its own game applies it."""
        self._send({
            "t": "hit",
            "target": self.index,
            "damage": round(float(amount), 2),
            "source": [round(source[0], 2), round(source[1], 2)] if source else None,
            "push": round(float(push), 2),
        })
        return amount


class HitCheck:
    """What a hit from the opponent can be. Its game decides its own hits
    (see the module's docstring), so a modified game could send anything;
    these limits keep it to what that character could really do: no more
    damage than its strongest move fully powered (Super Saiyan 3, fully
    charged), from no farther than its longest reach, no more often than
    hits can land. A fair game never comes near them.

    This stops absurd hits, not subtle cheating: for that the server would
    have to run the fight itself.
    """

    # Room for rounding and for positions that arrive a little late
    DAMAGE_SLACK = 1.25
    REACH_MARGIN = 80
    # Several effects can land in the same second (a punch, a ki blast...)
    MAX_HITS_PER_SECOND = 8

    def __init__(self, attackers):
        """attackers: the opponent's fighters (the player and its allies)."""
        if not isinstance(attackers, (list, tuple)):
            attackers = [attackers]
        self.max_damage = 0
        reaches = []
        for attacker in attackers:
            strongest = max([CombatSystem.PLAYER_ATTACK_DAMAGE, *(t.damage for t in attacker.techniques)])
            self.max_damage = max(self.max_damage, strongest * getattr(attacker, "power", 1.0)
                                  * CombatSystem.SUPER_3_DAMAGE_MULTIPLIER * self.DAMAGE_SLACK)
            reaches.append(CombatSystem.ATTACK_RANGE + CombatSystem.body_reach(attacker) * 2)
            for technique in attacker.techniques:
                stats = technique.stats
                reaches.append(stats.get("range") or stats.get("reach") or stats.get("radius") or 0)
        self.max_reach = max(reaches) + self.REACH_MARGIN
        # Each of its fighters can land hits
        self.max_hits_per_second = self.MAX_HITS_PER_SECOND * len(attackers)
        self.recent_ms = deque()
        self.refused = 0

    def allows(self, damage, source, target, now):
        """Whether a hit of damage, coming from source (a point, or None),
        can land on a fighter standing at target."""
        while self.recent_ms and now - self.recent_ms[0] >= 1000:
            self.recent_ms.popleft()
        plausible = (
            damage <= self.max_damage
            and (source is None or math.dist(source, target) <= self.max_reach)
            and len(self.recent_ms) < self.max_hits_per_second
        )
        if plausible:
            self.recent_ms.append(now)
        else:
            self.refused += 1
        return plausible


class OnlineMatch:
    """An online match on the world map against a player from the lobby:
    1v1, or in a team match each player with the allies it chose (up to 3,
    their AI run by its own game). Knocking out the other player wins."""

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

        # An Epic Fight: the fight says who plays whom (the host the heroes,
        # the other player the boss), whatever they had picked
        fight = epic.by_id(start.get("epic")) if isinstance(start.get("epic"), str) else None
        if fight is not None and not epic.playable(fight):
            fight = None
        self.epic = fight
        if fight is not None:
            my_character, my_form, epic_allies = fight.side(slot)
            their_character, their_form, epic_their_allies = fight.side(1 - slot)
        else:
            my_character, my_form = game.menu.selected_character, None
        x, y, facing = self.SPAWNS[slot]
        self.player = Saiyan(x, y, False, my_character)
        # Online share of each hit (kept if the player becomes someone else)
        self.player.base_damage_taken = self.DAMAGE_TAKEN
        self.player.damage_taken = self.DAMAGE_TAKEN / self.player.stats.defense
        self.player.facing = facing
        self.player.face_idle()
        names = game.menu.character_names
        character = opponent.get("character", "goku")
        if character not in names:
            character = "goku"
        opponent_name = str(opponent.get("name", "Opponent"))
        self.mode = "team" if start.get("mode") == "team" or fight is not None else "1v1"
        if fight is not None:
            character = their_character
            my_allies, their_allies = epic_allies, epic_their_allies
        elif self.mode == "team":
            my_allies = [name for name in game.menu.selected_allies if name in names][:MAX_ALLIES]
            their_allies = opponent.get("allies") if isinstance(opponent.get("allies"), list) else []
            their_allies = [name for name in their_allies if name in names][:MAX_ALLIES]
        else:
            my_allies, their_allies = [], []
        self.opponent = RemoteFighter(character, opponent_name, net.send)
        if fight is not None:
            epic.start_in_form(self.player, my_form)
            epic.start_in_form(self.opponent, their_form)
        # The other side: its player first, then its allies (their index in
        # the hits and states)
        self.opponents = [self.opponent] + [
            RemoteFighter(name, opponent_name, net.send, index=index)
            for index, name in enumerate(their_allies, start=1)
        ]
        ox, oy, ofacing = self.SPAWNS[1 - slot]
        for fighter, (dx, dy) in zip(self.opponents, ((0, 0), *MapManager.ALLY_SPOTS)):
            fighter.place(ox + dx, oy + dy, ofacing)
        self.hit_check = HitCheck(self.opponents)
        # The states go over UDP when the server offers it (see net.py);
        # numbered, so one arriving late never moves the opponent back
        udp = start.get("udp")
        if isinstance(udp, dict) and udp.get("token"):
            net.start_udp(udp["token"], udp.get("port"))
        self.state_seq = 0
        self.last_state_seq = -1

        game.character = self.player
        # The room's arena (its host chose it), if this game has it too
        arena = fight.arena if fight is not None else start.get("map")
        self.arena = arena if isinstance(arena, str) and arena in arenas.available() else arenas.DEFAULT
        game.map_manager = MapManager(game.screen, self.player, versus=True, opponents=self.opponents,
                                      allies=my_allies, arena_name=self.arena)
        if self.arena != arenas.DEFAULT:
            self._place_on_arena(game.map_manager.get_map(), slot)
        game.map_manager.combat.on_technique = self._send_technique
        # This side: the player, then its allies (run by this game's AI)
        self.allies = [npc for npc in game.map_manager.get_map().npcs if npc.team == HEROES]
        self.fighters = [self.player, *self.allies]
        self.result = None
        self.result_since = None
        self.last_sent_ms = -self.SEND_INTERVAL_MS
        self.resize(game.resolution)

    def _place_on_arena(self, game_map, slot):
        """On an arena, the two players start on its spawn points (the
        host on spawn_world, facing each other)."""
        try:
            spots = [game_map.get_object("spawn_world"), game_map.get_object("spawn_rival")]
        except (KeyError, ValueError):
            return
        mine, theirs = (spots[0], spots[1]) if slot == 0 else (spots[1], spots[0])
        facing = "Right" if mine.x <= theirs.x else "Left"
        other_facing = "Left" if facing == "Right" else "Right"
        player = self.player
        player.position = [mine.x - player.rect.width / 2, mine.y - player.rect.height]
        player.facing = facing
        player.face_idle()
        player.update()
        player.save_location()
        for index, fighter in enumerate(self.opponents):
            dx, dy = ((0, 0), *MapManager.ALLY_SPOTS)[index]
            fighter.place(theirs.x - fighter.rect.width / 2 + dx, theirs.y - fighter.rect.height + dy, other_facing)

    def resize(self, resolution):
        self.banner_font = pygame.font.Font(None, max(48, resolution[1] // 7))
        self.info_font = pygame.font.Font(None, max(22, resolution[1] // 28))

    def _send_technique(self, user, technique_id, direction, origin, power=None):
        """Show the opponent the technique the player or an ally just
        released (with its own sprites)."""
        if user not in self.fighters:
            return
        message = {"t": "tech", "id": technique_id, "dir": direction, "origin": origin,
                   "by": self.fighters.index(user)}
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
                seq = message.get("seq")
                if isinstance(seq, int):
                    if seq <= self.last_state_seq:
                        continue  # an older state, overtaken by a newer one
                    self.last_state_seq = seq
                self.opponent.apply_snapshot(message)
                allies = message.get("allies")
                for fighter, state in zip(self.opponents[1:], allies if isinstance(allies, list) else []):
                    if isinstance(state, dict):
                        fighter.apply_snapshot(state)
                if any(getattr(fighter, "changed", False) for fighter in self.opponents):
                    # Someone else now: what its hits can be changes too
                    for fighter in self.opponents:
                        fighter.changed = False
                    self.hit_check = HitCheck(self.opponents)
            elif kind == "hit" and self.result is None and self.player.hp > 0:
                target = message.get("target", 0)
                if not isinstance(target, int) or not 0 <= target < len(self.fighters):
                    continue
                fighter = self.fighters[target]
                if fighter.hp <= 0:
                    continue
                source = message.get("source")
                try:
                    damage = max(0.0, _number(message.get("damage", 0), 0.0))
                    source = (_number(source[0]), _number(source[1])) if source else None
                    push = min(5.0, max(0.0, _number(message.get("push", 1.0), 1.0)))
                except (TypeError, IndexError, KeyError):
                    continue
                if source is not None and None in source:
                    source = None
                if self.hit_check.allows(damage, source, fighter.feet.center, pygame.time.get_ticks()):
                    fighter.take_damage(damage, source, push)
            elif kind == "tech":
                try:
                    origin = (_number(message["origin"][0]), _number(message["origin"][1]))
                    if None in origin:
                        continue
                    power = message.get("power")
                    power = None if power is None else max(0.0, min(1.0, _number(power, 1.0)))
                    by = message.get("by", 0)
                    user = self.opponents[by] if isinstance(by, int) and 0 <= by < len(self.opponents) \
                        else self.opponent
                    combat.show_opponent_technique(user, str(message["id"]), str(message["dir"]), origin, power)
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
            self.state_seq += 1
            state = {"t": "state", "seq": self.state_seq, **self.player.snapshot()}
            if self.allies:
                state["allies"] = [ally.snapshot() for ally in self.allies]
            self.net.send_state(state)
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
            f"{display_name(self.player.character_name)} (you)  vs  {self.opponent.bar_label}",
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
    """Connect to the server, list the rooms, create one (1v1, or team: each
    player with the allies it chose) or join one."""

    BACKGROUND = (12, 14, 24)
    PANEL = (25, 30, 45)
    BUTTON = (60, 110, 190)
    BUTTON_ALT = (90, 95, 110)
    ROOM = (40, 48, 70)
    TEXT = (255, 255, 255)
    DIM = (180, 185, 200)
    ACCENT = (255, 220, 90)
    MAX_ROOMS_SHOWN = 5

    def __init__(self, net, screen_size, character, background=None, name=None, allies=(), arena=None,
                 epic=None):
        self.net = net
        # An Epic Fight to play online (epic.Fight): the rooms this player
        # opens are for it (the host plays the heroes, the other player the boss)
        self.epic = epic
        self.screen_size = screen_size
        self.character = character
        self.allies = list(allies)[:MAX_ALLIES]
        # Where the rooms this player creates fight
        self.arena = arena or arenas.DEFAULT
        self.background = background
        self.settings = user_settings.load()
        self.name = (name or "").strip() or f"{display_name(character)} {random.randint(100, 999)}"
        self.rooms = []
        self.room_id = None  # our room while waiting in it
        self.room_mode = "1v1"
        self.server_version = None  # said by the server when we connect
        self.notice = ""
        self.editing = None  # text being typed for the server address
        self.buttons = {}
        self.room_buttons = []
        self._said_hello = False
        self.resize(screen_size, background)
        self.connect()

    def resize(self, screen_size, background=None):
        """Lay the lobby out for this screen size (background: the menu
        artwork made for it)."""
        self.screen_size = screen_size
        self.background = background
        height = screen_size[1]
        self.title_font = pygame.font.Font(None, max(40, height // 12))
        self.font = pygame.font.Font(None, max(24, height // 22))
        self.small_font = pygame.font.Font(None, max(20, height // 30))

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
                version = message.get("version", PROTOCOL_VERSION)
                if version != PROTOCOL_VERSION:
                    # Another version of the game: matches could not work
                    self.notice = (f"This server is for version {version} of the online mode "
                                   f"(this game: {PROTOCOL_VERSION}): update the game or the server")
                    self.net.close()
                    continue
                self._said_hello = True
                self.server_version = message.get("server_version")
                self.net.send({"t": "hello", "name": self.name, "character": self.character,
                               "allies": self.allies, "version": PROTOCOL_VERSION})
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
    def create_room(self, mode="1v1"):
        """mode: "1v1", or "team" (each player with its allies)."""
        if self.net.connected and self.room_id is None:
            if self.epic is not None:
                # Both sides bring the fight's teams
                mode = "team"
                self.net.send({"t": "create", "mode": mode, "map": self.epic.arena, "epic": self.epic.id})
            else:
                self.net.send({"t": "create", "mode": mode, "map": self.arena})
            self.room_mode = mode

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
                self.create_room("1v1")
            elif event.key == pygame.K_t:
                self.create_room("team")
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
            self.create_room("1v1")
        elif name == "create_team":
            self.create_room("team")
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
    def team_label(self):
        """The player's character, and its allies (used in team matches)."""
        team = display_name(self.character)
        if self.allies:
            team += " + " + ", ".join(display_name(name) for name in self.allies)
        return team

    @staticmethod
    def room_label(room):
        fight = epic.by_id(room.get("epic")) if isinstance(room.get("epic"), str) else None
        if fight is not None:
            # Joining it: playing the boss's side
            return (f"Epic: {fight.title} - {room.get('host', '?')} plays the heroes, "
                    f"you play {display_name(fight.boss)}")
        label = LobbyScreen._room_players(room)
        arena = room.get("map")
        if isinstance(arena, str) and arena != arenas.DEFAULT:
            label += f" - {arenas.name(arena)}"
        return label

    @staticmethod
    def _room_players(room):
        host = str(room.get("host", "?"))
        character = display_name(str(room.get("character", "?")))
        if room.get("mode") == "team":
            allies = room.get("allies") if isinstance(room.get("allies"), list) else []
            team = " + ".join([character, *(display_name(str(name)) for name in allies)])
            return f"Team: {host} ({team})"
        return f"1v1: {host} ({character})"

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
        title = self.title_font.render("ONLINE", True, self.ACCENT)
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
            "connected": (f"Connected as {self.name} ({self.team_label()})"
                          + (f"  -  server v{self.server_version}" if self.server_version else ""),
                          (140, 230, 140)),
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
            mode = "team match" if self.room_mode == "team" else "1v1"
            text = self.font.render(f"Room {self.room_id} ({mode}): waiting for an opponent...", True, self.TEXT)
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
                label = f"{index + 1}. {self.room_label(room)}  -  Join"
                text = self.font.render(label, True, self.TEXT)
                screen.blit(text, text.get_rect(midleft=(rect.left + line / 2, rect.centery)))
                self.room_buttons.append((room.get("id"), rect))
                y += row_height + line * 0.3

        quarter = (panel.width - line * 5) / 4
        left = panel.left + line
        connected = self.net.connected
        colour = self.BUTTON if connected else self.BUTTON_ALT
        self._button(screen, "create", pygame.Rect(left, bottom_y, quarter, button_height),
                     "New 1v1" if connected else "-", colour)
        self._button(screen, "create_team", pygame.Rect(left + quarter + line, bottom_y, quarter, button_height),
                     "New team" if connected else "-", colour)
        retry = self.net.status == "error"
        self._button(screen, "refresh", pygame.Rect(left + (quarter + line) * 2, bottom_y, quarter, button_height),
                     "Retry" if retry else "Refresh", self.BUTTON_ALT)
        self._button(screen, "back", pygame.Rect(left + (quarter + line) * 3, bottom_y, quarter, button_height),
                     "Back", self.BUTTON_ALT)
