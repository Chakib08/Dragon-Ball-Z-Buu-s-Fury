"""Connection to the lobby server (see server/lobby_server.py).

Messages are JSON objects, one per line, over TCP: the lobby, and in a
match what must arrive (hits, techniques, knock-outs). Connecting and
reading happen on a background thread so the game never waits on the
network; the game picks up what arrived with poll() once per frame.

During a match the fighters' states (about 30 a second) go over UDP
instead, through the server (start_udp, send_state): a late or lost state
is replaced by the next one anyway, and over TCP a single lost packet holds
back everything after it, which is what makes the opponent stutter. Until
the server answers the first UDP packet (or if UDP is blocked, by a
firewall or a port opened for TCP only) the states keep going over TCP.
"""

import json
import queue
import socket
import threading
import time

CONNECT_TIMEOUT = 4
# The online mode's message format; the server says its own in "welcome"
# and refuses games that speak another (see server/lobby_server.py)
PROTOCOL_VERSION = 1
# Datagrams bigger than this are not ours (a state is about 200 bytes)
MAX_DATAGRAM = 2048
# How often to knock on the server's UDP port until it answers
UDP_PROBE_MS = 250


class NetClient:
    def __init__(self):
        self.status = "offline"  # offline, connecting, connected, error
        self.error = ""
        self._socket = None
        self._send_lock = threading.Lock()
        self._inbox = queue.Queue()
        self._closed = False
        # Number of the current connection: a thread of an older one (closed
        # by a reconnect) must not touch the new one's state
        self._generation = 0
        # The match's UDP channel (see start_udp)
        self._udp = None
        self._udp_server = None
        self._udp_token = None
        self.udp_ready = False
        self._udp_probe_at = 0.0

    @property
    def connected(self):
        return self.status == "connected"

    def connect(self, host, port):
        """Start connecting in the background (check status / poll later)."""
        self.close()
        self._closed = False
        self._generation += 1
        # Messages of the previous connection are no news for this one
        self._inbox = queue.Queue()
        self.status = "connecting"
        self.error = ""
        threading.Thread(target=self._run, args=(host, port, self._generation), daemon=True).start()

    def _current(self, generation):
        return generation == self._generation and not self._closed

    def _run(self, host, port, generation):
        inbox = self._inbox
        try:
            sock = socket.create_connection((host, int(port)), timeout=CONNECT_TIMEOUT)
            sock.settimeout(None)
            # Small messages many times a second: send them right away
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except ConnectionRefusedError:
            self._fail(f"No server on {host}:{port}: is lobby_server.py running on that port?", generation)
            return
        except socket.timeout:
            self._fail(f"No answer from {host}:{port}: wrong address, or a firewall blocks it", generation)
            return
        except (OSError, ValueError) as error:
            self._fail(f"Cannot reach {host}:{port} ({error})", generation)
            return
        if not self._current(generation):
            sock.close()  # closed, or another connection started meanwhile
            return
        self._socket = sock
        self.status = "connected"
        try:
            with sock.makefile("r", encoding="utf-8") as lines:
                for line in lines:
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(message, dict):
                        inbox.put(message)
        except OSError:
            pass
        self._fail("Disconnected from the server", generation)

    def _fail(self, error, generation=None):
        """Report a lost connection; generation: only if it is still the
        current one (an old thread finishing after a reconnect says nothing)."""
        if generation is not None and not self._current(generation):
            return
        self.status = "error"
        self.error = error
        self._socket = None

    def send(self, message):
        sock = self._socket
        if sock is None:
            return False
        data = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            with self._send_lock:
                sock.sendall(data)
        except OSError:
            self._fail("Disconnected from the server")
            return False
        return True

    # ---- UDP (a match's states) ----------------------------------------------------
    def start_udp(self, token, port=None):
        """Send this match's states over UDP, to the server's port (the
        TCP one if None); token tells the server which player it is."""
        self.stop_udp()
        sock = self._socket
        if sock is None:
            return
        try:
            host = sock.getpeername()[0]
            port = int(port) if port else sock.getpeername()[1]
            family = socket.AF_INET6 if ":" in host else socket.AF_INET
            udp = socket.socket(family, socket.SOCK_DGRAM)
            # Bound before reading (Windows cannot read an unbound socket),
            # and a timeout so the reading thread notices stop_udp
            udp.bind(("::" if family == socket.AF_INET6 else "0.0.0.0", 0))
            udp.settimeout(0.5)
        except (OSError, ValueError, TypeError):
            return  # no UDP then: the states stay on TCP
        self._udp, self._udp_server, self._udp_token = udp, (host, port), str(token)
        self.udp_ready = False
        self._udp_probe_at = 0.0
        threading.Thread(target=self._receive_udp, args=(udp, self._inbox), daemon=True).start()
        self._probe_udp()

    def stop_udp(self):
        udp, self._udp = self._udp, None
        self.udp_ready = False
        if udp is not None:
            udp.close()

    def _send_datagram(self, message):
        udp = self._udp
        if udp is None:
            return False
        data = json.dumps({**message, "tok": self._udp_token}, separators=(",", ":")).encode("utf-8")
        try:
            udp.sendto(data, self._udp_server)
            return True
        except OSError:
            return False

    def _probe_udp(self):
        now = time.monotonic()
        if now - self._udp_probe_at >= UDP_PROBE_MS / 1000:
            self._udp_probe_at = now
            self._send_datagram({"t": "udp_hello"})

    def _receive_udp(self, udp, inbox):
        while self._udp is udp:
            try:
                data = udp.recv(MAX_DATAGRAM)
            except (socket.timeout, ConnectionResetError):
                continue  # Windows resets: an earlier packet found the port closed
            except OSError:
                return  # closed (stop_udp)
            try:
                message = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(message, dict):
                continue
            if message.get("t") == "udp_ok":
                self.udp_ready = True
            elif self._udp is udp:
                inbox.put(message)

    def send_state(self, message):
        """A state that the next one replaces: over UDP once it works,
        else over TCP (still knocking on the UDP port meanwhile)."""
        if self.udp_ready and self._send_datagram(message):
            return True
        if self._udp is not None:
            self._probe_udp()
        return self.send(message)

    def poll(self):
        """Every message received since the last call, oldest first."""
        messages = []
        while True:
            try:
                messages.append(self._inbox.get_nowait())
            except queue.Empty:
                return messages

    def close(self):
        self.stop_udp()
        self._closed = True
        sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        self.status = "offline"
