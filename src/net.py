"""Connection to the lobby server (see server/lobby_server.py).

Messages are JSON objects, one per line, over TCP. Connecting and reading
happen on a background thread so the game never waits on the network; the
game picks up what arrived with poll() once per frame.
"""

import json
import queue
import socket
import threading

CONNECT_TIMEOUT = 4


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

    def poll(self):
        """Every message received since the last call, oldest first."""
        messages = []
        while True:
            try:
                messages.append(self._inbox.get_nowait())
            except queue.Empty:
                return messages

    def close(self):
        self._closed = True
        sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        self.status = "offline"
