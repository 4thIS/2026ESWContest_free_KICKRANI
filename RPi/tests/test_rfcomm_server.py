"""④ RFCOMM 서버 — 줄단위 JSON, 명령 라우팅, ACK/ERROR, STATUS 송신, 끊김 훅.

실제 소켓 코드 경로를 그대로 쓰되 전송만 TCP 루프백으로 대체(RFCOMM은 Pi에서만).
"""
import json
import socket
import time

import pytest

from pi.comm.files import FileManager
from pi.comm.rfcomm_server import RfcommServer


def _tcp_listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    return s


class Client:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.f = self.s.makefile("rw", encoding="utf-8", newline="\n")

    def send(self, obj):
        self.f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.f.flush()

    def raw(self, text):
        self.f.write(text)
        self.f.flush()

    def recv(self):
        line = self.f.readline()
        assert line, "connection closed"
        return json.loads(line)

    def close(self):
        self.f.close()          # makefile 참조 해제 없이는 소켓이 실제로 안 닫힌다
        self.s.close()


@pytest.fixture
def server(tmp_path):
    lst = _tcp_listener()
    port = lst.getsockname()[1]
    srv = RfcommServer(listener=lst, files=FileManager(tmp_path))
    yield srv, port, tmp_path
    srv.stop()


def _wait(pred, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_control_command_dispatched_and_acked(server):
    srv, port, _ = server
    got = []
    srv.on_command(lambda c: got.append(c) or True)
    srv.start()
    c = Client(port)
    c.send({"cmd": "SET_MODE", "mode": "COLLECT"})
    assert c.recv() == {"type": "ACK", "cmd": "SET_MODE", "ok": True}
    assert got == [{"cmd": "SET_MODE", "mode": "collect"}]
    c.close()


def test_rejected_control_command_returns_error(server):
    srv, port, _ = server
    srv.on_command(lambda c: False)
    srv.start()
    c = Client(port)
    c.send({"cmd": "START"})
    r = c.recv()
    assert r["type"] == "ERROR" and r["cmd"] == "START"
    c.close()


def test_bad_json_returns_error_and_keeps_connection(server):
    srv, port, _ = server
    srv.on_command(lambda c: True)
    srv.start()
    c = Client(port)
    c.raw("garbage\n")
    assert c.recv()["type"] == "ERROR"
    c.send({"cmd": "STOP"})
    assert c.recv()["type"] == "ACK"
    c.close()


def test_file_commands_handled_locally(server):
    srv, port, d = server
    (d / "run_1.csv").write_text("x")
    srv.on_command(lambda c: pytest.fail("파일 명령은 controller로 가면 안 됨"))
    srv.start()
    c = Client(port)
    c.send({"cmd": "LIST_FILES"})
    assert c.recv() == {"type": "FILES", "files": ["run_1.csv"]}
    c.send({"cmd": "RENAME", "old": "run_1.csv", "new": "run_1_아스팔트_건조.csv"})
    assert c.recv() == {"type": "ACK", "cmd": "RENAME", "ok": True}
    c.send({"cmd": "MEMO", "file": "run_1_아스팔트_건조.csv", "memo": "hi"})
    assert c.recv() == {"type": "ACK", "cmd": "MEMO", "ok": True}
    c.send({"cmd": "RENAME", "old": "ghost.csv", "new": "a.csv"})
    assert c.recv()["type"] == "ERROR"
    c.close()


def test_send_telemetry_emits_status_line(server):
    srv, port, _ = server
    srv.on_command(lambda c: True)
    srv.start()
    c = Client(port)
    assert _wait(lambda: srv.connected)
    srv.send_telemetry({"speed": 0.4, "road": "gravel", "distance": 1.5, "vibration": 0.1})
    assert c.recv() == {"type": "STATUS", "speed": 0.4, "distance": 1.5, "vibration": 0.1, "roadType": "비포장"}
    c.close()


def test_send_telemetry_without_client_is_noop(server):
    srv, port, _ = server
    srv.on_command(lambda c: True)
    srv.start()
    srv.send_telemetry({"speed": 0.0})     # 예외 없음


def test_disconnect_invokes_hook_and_accepts_next_client(server):
    srv, port, _ = server
    dropped = []
    srv.on_command(lambda c: True)
    srv.on_disconnect(lambda: dropped.append(1))
    srv.start()
    c = Client(port)
    assert _wait(lambda: srv.connected)
    c.close()
    assert _wait(lambda: dropped == [1])
    assert _wait(lambda: not srv.connected)
    c2 = Client(port)
    c2.send({"cmd": "STOP"})
    assert c2.recv()["type"] == "ACK"
    c2.close()
