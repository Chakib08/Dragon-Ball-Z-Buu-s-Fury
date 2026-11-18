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

    @property
    def connected(self):
        return self.status == "connected"

    def connect(self, host, port):
        """Start connecting in the background (check status / poll later)."""
        self.close()
        self._closed = False
        self.status = "connecting"
        self.error = ""
        threading.Thread(target=self._run, args=(host, port), daemon=True).start()

    def _run(self, host, port):
        try:
            sock = socket.create_connection((host, int(port)), timeout=CONNECT_TIMEOUT)
            sock.settimeout(None)
            # Small messages many times a second: send them right away
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except ConnectionRefusedError:
            self._fail(f"No server on {host}:{port}: is lobby_server.py running on that port?")
            return
        except socket.timeout:
            self._fail(f"No answer from {host}:{port}: wrong address, or a firewall blocks it")
            return
        except (OSError, ValueError) as error:
            self._fail(f"Cannot reach {host}:{port} ({error})")
            return
        if self._closed:
            sock.close()
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
                        self._inbox.put(message)
        except OSError:
            pass
        if not self._closed:
            self._fail("Disconnected from the server")

    def _fail(self, error):
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
