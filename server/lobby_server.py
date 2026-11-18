#!/usr/bin/env python3
"""Lobby server for online 1v1 matches.

Players connect over TCP and exchange JSON messages, one per line. In the
lobby they see the rooms waiting for an opponent, create one or join one.
When a room has two players the match starts, and from then on the server
relays the match messages (fighter state, hits, beams, knock-out) from one
player to the other. Each game is the authority on its own fighter, so the
server does not simulate anything.

Usage:
    python3 server/lobby_server.py [--host 0.0.0.0] [--port 5050]

Client -> server
    {"t": "hello", "name": str, "character": str}
    {"t": "list"}                       ask for the room list
    {"t": "create"}                     open a room and wait in it
    {"t": "join", "room": int}          join a waiting room
    {"t": "leave"}                      leave the room (cancel or quit a match)
    {"t": "state" | "hit" | "beam" | "ko", ...}   relayed to the opponent

Server -> client
    {"t": "welcome", "id": int}
    {"t": "rooms", "rooms": [{"id", "host", "character"}]}
    {"t": "waiting", "room": int}       room created, waiting for an opponent
    {"t": "start", "room": int, "slot": 0 | 1,
     "opponent": {"name", "character"}}
    {"t": "opponent_left"}
    {"t": "error", "message": str}
    relayed messages, unchanged
"""

import argparse
import asyncio
import itertools
import json
import logging

PROTOCOL_VERSION = 1
DEFAULT_PORT = 5050
# Messages forwarded as they are from one player of a match to the other
RELAYED = {"state", "hit", "beam", "ko"}
MAX_LINE = 64 * 1024
NAME_LENGTH = 24

log = logging.getLogger("lobby")


class Player:
    def __init__(self, player_id, writer):
        self.id = player_id
        self.writer = writer
        self.name = f"Player {player_id}"
        self.character = "goku"
        self.room = None

    def send(self, message):
        if self.writer.is_closing():
            return
        self.writer.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")


class Room:
    def __init__(self, room_id, host):
        self.id = room_id
        self.players = [host]

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
        self._room_ids = itertools.count(1)

    # ---- Connection --------------------------------------------------------------
    async def handle(self, reader, writer):
        player = Player(next(self._player_ids), writer)
        self.players[player.id] = player
        peer = writer.get_extra_info("peername")
        log.info("player %s connected from %s", player.id, peer)
        try:
            player.send({"t": "welcome", "id": player.id, "version": PROTOCOL_VERSION})
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
                if isinstance(message, dict):
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
            player.send(self.room_list())
        elif kind == "list":
            player.send(self.room_list())
        elif kind == "create":
            self.create_room(player)
        elif kind == "join":
            self.join_room(player, message.get("room"))
        elif kind == "leave":
            self.leave_room(player)
        elif kind in RELAYED and player.room is not None:
            opponent = player.room.other(player)
            if opponent is not None:
                opponent.send(message)

    def room_list(self):
        return {
            "t": "rooms",
            "rooms": [
                {"id": room.id, "host": room.players[0].name, "character": room.players[0].character}
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

    def create_room(self, player):
        self.leave_room(player)
        room = Room(next(self._room_ids), player)
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
            member.send({
                "t": "start",
                "room": room.id,
                "slot": slot,
                "opponent": {"name": opponent.name, "character": opponent.character},
            })
        log.info("room %s: %s vs %s", room.id, host.name, player.name)
        self.broadcast_rooms()

    def leave_room(self, player):
        room = player.room
        if room is None:
            return
        player.room = None
        room.players.remove(player)
        for member in room.players:
            member.room = None
            member.send({"t": "opponent_left"})
        self.rooms.pop(room.id, None)
        self.broadcast_rooms()


async def serve(host, port, ready=None):
    lobby = LobbyServer()
    server = await asyncio.start_server(lobby.handle, host, port, limit=MAX_LINE)
    log.info("lobby listening on %s", ", ".join(str(s.getsockname()) for s in server.sockets))
    if ready is not None:
        ready(server)
    async with server:
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Lobby server for online 1v1 matches")
    parser.add_argument("--host", default="0.0.0.0", help="address to listen on (default: all)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default {DEFAULT_PORT})")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        asyncio.run(serve(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
