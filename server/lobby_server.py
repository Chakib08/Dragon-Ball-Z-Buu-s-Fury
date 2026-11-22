#!/usr/bin/env python3
"""Lobby server for online 1v1 matches.

Players connect over TCP and exchange JSON messages, one per line. In the
lobby they see the rooms waiting for an opponent, create one or join one.
When a room has two players the match starts, and from then on the server
relays the match messages (fighter state, hits, beams, knock-out) from one
player to the other: the fighters' states over UDP (on the same port
number: the game sends them there once its "udp_hello" got an answer, and
over TCP before that, or if UDP is blocked), the rest over TCP, which never
loses a hit or a knock-out. Each game is the authority on its own fighter, so the
server does not simulate anything (each game checks that the hits it
receives are possible, see src/online.py HitCheck). A client sending far
more messages than a game does has the excess dropped.

Usage:
    python3 server/lobby_server.py [--host 0.0.0.0] [--port 5050]
    python3 server/lobby_server.py --version

Open the port for TCP and UDP (a box's port forwarding, a firewall).

Client -> server
    {"t": "hello", "name": str, "character": str, "version": int,
     "allies": [str]}                   up to 3, for team matches
                                        a game of another version gets an
                                        error and may not create or join
    {"t": "list"}                       ask for the room list
    {"t": "create", "mode": "1v1" | "team", "map": str, "epic": str}
                                        open a room and wait in it, on that
                                        arena (in a team match each player
                                        brings its allies); "epic": an Epic
                                        Fight's id (a team match: the host
                                        plays the heroes, the other the boss)
    {"t": "join", "room": int}          join a waiting room
    {"t": "leave"}                      leave the room (cancel or quit a match)
    {"t": "state" | "hit" | "tech" | "ko", ...}   relayed to the opponent

Client -> server, UDP (the token of its "start" message in "tok")
    {"t": "udp_hello", "tok": str}      answered by {"t": "udp_ok"}
    {"t": "state", "tok": str, ...}     relayed to the opponent (over UDP if
                                        it said udp_hello too, else TCP)

Server -> client
    {"t": "welcome", "id": int, "version": int, "server_version": str}
    {"t": "rooms", "rooms": [{"id", "host", "character", "mode", "allies", "map", "epic"}]}
    {"t": "waiting", "room": int}       room created, waiting for an opponent
    {"t": "start", "room": int, "slot": 0 | 1, "mode": "1v1" | "team", "map": str, "epic": str,
     "opponent": {"name", "character", "allies"},   (allies: team matches)
     "udp": {"token": str, "port": int}}   (no "udp" if UDP is not open)
    {"t": "opponent_left"}
    {"t": "error", "message": str}
    relayed messages, unchanged
"""

import argparse
import asyncio
import itertools
import json
import logging
import secrets
import time

# The server's own version: the game's it ships with (src/version.py; a
# test keeps them in step). The release page has this file for each version
SERVER_VERSION = "1.0.6"
# 2: names, team matches (allies in the states, hits for any fighter)
# 3: the room's arena ("map")
# 4: Epic Fights ("epic": the fight a room is for)
PROTOCOL_VERSION = 4
DEFAULT_PORT = 5050
# Messages forwarded as they are from one player of a match to the other
RELAYED = {"state", "hit", "tech", "ko"}
MAX_LINE = 64 * 1024
# A client that stops reading (frozen app, dead link not noticed yet) while
# its opponent keeps playing: past this much unsent data it is dropped,
# instead of the server keeping its messages forever
MAX_PENDING_BYTES = 256 * 1024
NAME_LENGTH = 24
MAX_ALLIES = 3
MODES = ("1v1", "team")
# A game sends about 30 states a second plus a few hits and techniques: a
# client sending far more is flooding, and what it sends over this pace
# (with room for bursts) is dropped
MESSAGES_PER_SECOND = 90
MESSAGE_BURST = 180
# A state is about 200 bytes: anything much bigger is not from the game
MAX_DATAGRAM = 2048

log = logging.getLogger("lobby")


class Player:
    def __init__(self, player_id, writer):
        self.id = player_id
        self.writer = writer
        self.name = f"Player {player_id}"
        self.character = "goku"
        self.allies = []
        self.room = None
        # Games that speak another version may not play (see "hello")
        self.compatible = True
        # In a match: the token its UDP packets carry, and where they come
        # from once one arrived (its address as the internet box shows it)
        self.udp_token = None
        self.udp_address = None
        self.allowance = MESSAGE_BURST
        self.allowance_at = time.monotonic()
        self.dropped = 0

    def take_message(self):
        """Whether one more message fits the rate limit (a token bucket)."""
        now = time.monotonic()
        self.allowance = min(MESSAGE_BURST, self.allowance + (now - self.allowance_at) * MESSAGES_PER_SECOND)
        self.allowance_at = now
        if self.allowance < 1:
            self.dropped += 1
            return False
        self.allowance -= 1
        return True

    def send(self, message):
        if self.writer.is_closing():
            return
        if self.writer.transport.get_write_buffer_size() > MAX_PENDING_BYTES:
            log.info("player %s does not read its messages: dropped", self.id)
            self.writer.close()  # its handler then ends and leaves the room
            return
        self.writer.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")


class Room:
    def __init__(self, room_id, host, mode="1v1", arena="map", epic=None):
        self.id = room_id
        self.players = [host]
        self.mode = mode if mode in MODES else "1v1"
        # An arena id: letters, digits and _ only (the games look it up)
        arena = str(arena or "map")[:40]
        self.map = arena if arena.replace("_", "").isalnum() else "map"
        # An Epic Fight's id (the games know who plays whom), same rules
        epic = str(epic)[:40] if epic else None
        self.epic = epic if epic and epic.replace("_", "").isalnum() else None
        if self.epic is not None:
            self.mode = "team"

    @property
    def waiting(self):
        return len(self.players) == 1

    def other(self, player):
        for candidate in self.players:
            if candidate is not player:
                return candidate
        return None


class LobbyServer:
    def __init__(self):
        self.players = {}
        self.rooms = {}
        self._player_ids = itertools.count(1)
        # UDP: the open socket (None: states stay on TCP), its port and the
        # players of running matches by token
        self.udp = None
        self.udp_port = None
        self.udp_tokens = {}
        self._room_ids = itertools.count(1)

    # ---- Connection --------------------------------------------------------------
    async def handle(self, reader, writer):
        player = Player(next(self._player_ids), writer)
        self.players[player.id] = player
        peer = writer.get_extra_info("peername")
        log.info("player %s connected from %s", player.id, peer)
        try:
            player.send({"t": "welcome", "id": player.id, "version": PROTOCOL_VERSION,
                         "server_version": SERVER_VERSION})
            while True:
                try:
                    line = await reader.readline()
                except (asyncio.LimitOverrunError, ValueError):
                    break  # absurdly long line: drop the client
                if not line:
                    break
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict) and player.take_message():
                    self.dispatch(player, message)
                await writer.drain()
        except ConnectionError:
            pass
        finally:
            self.leave_room(player)
            del self.players[player.id]
            writer.close()
            log.info("player %s disconnected", player.id)

    # ---- Messages ----------------------------------------------------------------
    def dispatch(self, player, message):
        kind = message.get("t")
        if kind == "hello":
            player.name = str(message.get("name") or player.name)[:NAME_LENGTH]
            player.character = str(message.get("character") or player.character)[:NAME_LENGTH]
            allies = message.get("allies")
            player.allies = [str(name)[:NAME_LENGTH] for name in allies[:MAX_ALLIES]] \
                if isinstance(allies, list) else []
            # Games from before the handshake say nothing: they speak 1
            version = message.get("version", 1)
            player.compatible = version == PROTOCOL_VERSION
            if not player.compatible:
                player.send({"t": "error", "message": f"This server runs version {PROTOCOL_VERSION} of the "
                                                      f"online mode, your game {version}: update it"})
            player.send(self.room_list())
        elif kind in ("create", "join") and not player.compatible:
            player.send({"t": "error", "message": "Update the game to play on this server"})
        elif kind == "list":
            player.send(self.room_list())
        elif kind == "create":
            self.create_room(player, message.get("mode"), message.get("map"), message.get("epic"))
        elif kind == "join":
            self.join_room(player, message.get("room"))
        elif kind == "leave":
            self.leave_room(player)
        elif kind in RELAYED and player.room is not None:
            self.relay(player, message)

    def relay(self, player, message):
        """To player's opponent; a state over UDP when it can take one."""
        opponent = player.room.other(player) if player.room is not None else None
        if opponent is None:
            return
        if message.get("t") == "state" and self.udp is not None and opponent.udp_address is not None:
            data = json.dumps(message, separators=(",", ":")).encode()
            self.udp.sendto(data, opponent.udp_address)
        else:
            opponent.send(message)

    # ---- UDP ---------------------------------------------------------------------
    def datagram(self, data, address):
        """A UDP packet: a match's player saying hello, or its state."""
        if len(data) > MAX_DATAGRAM:
            return
        try:
            message = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(message, dict):
            return
        player = self.udp_tokens.get(message.pop("tok", None))
        if player is None or not player.take_message():
            return  # not from a running match (or too much of it)
        player.udp_address = address
        kind = message.get("t")
        if kind == "udp_hello":
            self.udp.sendto(b'{"t":"udp_ok"}', address)
        elif kind == "state":
            self.relay(player, message)

    def _end_udp(self, player):
        self.udp_tokens.pop(player.udp_token, None)
        player.udp_token = player.udp_address = None

    def room_list(self):
        return {
            "t": "rooms",
            "rooms": [
                {"id": room.id, "host": room.players[0].name, "character": room.players[0].character,
                 "mode": room.mode, "allies": room.players[0].allies if room.mode == "team" else [],
                 "map": room.map, **({"epic": room.epic} if room.epic else {})}
                for room in self.rooms.values()
                if room.waiting
            ],
        }

    def broadcast_rooms(self):
        """Players in the lobby (not in a room) see the list change live."""
        rooms = self.room_list()
        for player in self.players.values():
            if player.room is None:
                player.send(rooms)

    def create_room(self, player, mode=None, arena=None, epic=None):
        self.leave_room(player)
        room = Room(next(self._room_ids), player, mode, arena, epic)
        self.rooms[room.id] = room
        player.room = room
        player.send({"t": "waiting", "room": room.id})
        log.info("player %s created room %s", player.id, room.id)
        self.broadcast_rooms()

    def join_room(self, player, room_id):
        room = self.rooms.get(room_id)
        if room is None or not room.waiting or player.room is room:
            player.send({"t": "error", "message": "This room is no longer available"})
            player.send(self.room_list())
            return
        self.leave_room(player)
        host = room.players[0]
        room.players.append(player)
        player.room = room
        for slot, member in enumerate(room.players):
            opponent = room.other(member)
            start = {
                "t": "start",
                "room": room.id,
                "slot": slot,
                "mode": room.mode,
                "map": room.map,
                "opponent": {"name": opponent.name, "character": opponent.character,
                             "allies": opponent.allies if room.mode == "team" else []},
            }
            if room.epic:
                start["epic"] = room.epic  # slot 0 plays the heroes, slot 1 the boss
            if self.udp is not None:
                self._end_udp(member)
                member.udp_token = secrets.token_hex(8)
                self.udp_tokens[member.udp_token] = member
                start["udp"] = {"token": member.udp_token, "port": self.udp_port}
            member.send(start)
        log.info("room %s: %s vs %s", room.id, host.name, player.name)
        self.broadcast_rooms()

    def leave_room(self, player):
        room = player.room
        if room is None:
            return
        player.room = None
        room.players.remove(player)
        self._end_udp(player)
        for member in room.players:
            member.room = None
            self._end_udp(member)
            member.send({"t": "opponent_left"})
        self.rooms.pop(room.id, None)
        self.broadcast_rooms()


class UdpRelay(asyncio.DatagramProtocol):
    def __init__(self, lobby):
        self.lobby = lobby

    def datagram_received(self, data, address):
        self.lobby.datagram(data, address)

    def error_received(self, error):
        pass  # a packet to a player who left (ICMP unreachable): ignored


async def serve(host, port, ready=None):
    lobby = LobbyServer()
    server = await asyncio.start_server(lobby.handle, host, port, limit=MAX_LINE)
    log.info("lobby server v%s (online protocol %s) listening on %s", SERVER_VERSION, PROTOCOL_VERSION,
             ", ".join(str(s.getsockname()) for s in server.sockets))
    # The same port number for UDP (the one TCP got, when port is 0)
    udp_port = server.sockets[0].getsockname()[1]
    try:
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: UdpRelay(lobby), local_addr=(host, udp_port))
        lobby.udp, lobby.udp_port = transport, udp_port
        log.info("fighters' states over UDP on port %s", udp_port)
    except OSError as error:
        log.warning("no UDP on port %s (%s): states go over TCP", udp_port, error)
    if ready is not None:
        ready(server)
    async with server:
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Lobby server for online 1v1 matches")
    parser.add_argument("--host", default="0.0.0.0", help="address to listen on (default: all)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default {DEFAULT_PORT})")
    parser.add_argument("--version", action="version",
                        version=f"lobby server {SERVER_VERSION} (online protocol {PROTOCOL_VERSION})")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        asyncio.run(serve(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
