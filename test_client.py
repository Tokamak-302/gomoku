#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""五子棋联机自测（纯标准库，零依赖）。

本机测试（需先启动 server.py）:
    py -3 test_client.py

线上地址验证（Render / Railway 部署完成后）:
    py -3 test_client.py --url https://你的应用.onrender.com

测试内容:
    1. HTTP 棋盘页面可访问
    2. 两个客户端连接、黑白颜色分配
    3. 非本回合落子被拒绝
    4. 轮流落子后五连胜利判定（含获胜连线）
    5. 「重新开始」清空棋盘并交换黑白
"""
import argparse
import base64
import json
import os
import socket
import ssl
import struct
import sys
import urllib.parse
import urllib.request

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

HOST = DEFAULT_HOST
PORT = DEFAULT_PORT
TIMEOUT = 5
TLS = False
BASE_URL = "http://%s:%d/" % (DEFAULT_HOST, DEFAULT_PORT)


def _fix_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class WSClient:
    def __init__(self):
        self.timeout = TIMEOUT
        raw = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
        try:
            raw.settimeout(TIMEOUT)
            if TLS:
                context = ssl.create_default_context()
                raw = context.wrap_socket(raw, server_hostname=HOST)
                raw.settimeout(TIMEOUT)
            self.sock = raw
            key = base64.b64encode(os.urandom(16)).decode()
            request = (
                "GET / HTTP/1.1\r\n"
                "Host: %s:%d\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Key: %s\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ) % (HOST, PORT, key)
            self.sock.sendall(request.encode("latin-1"))
            self.buf = bytearray()
            head = self._read_until(b"\r\n\r\n")
            status = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            assert " 101 " in status, "WebSocket 握手失败: %s" % status
            self.buf = bytearray(head.split(b"\r\n\r\n", 1)[1])
        except Exception:
            try:
                raw.close()
            except OSError:
                pass
            raise

    def _read_until(self, sep):
        while sep not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("连接被关闭")
            self.buf += chunk
        idx = self.buf.index(sep) + len(sep)
        head = bytes(self.buf[:idx])
        self.buf = bytearray(self.buf[idx:])
        return head

    def _recv_exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("连接被关闭")
            self.buf += chunk
        data = bytes(self.buf[:n])
        self.buf = bytearray(self.buf[n:])
        return data

    def _send_frame(self, opcode, data, mask=True):
        header = bytearray([0x80 | opcode])
        n = len(data)
        if n < 126:
            header.append((0x80 if mask else 0) | n)
        elif n <= 0xFFFF:
            header.append((0x80 if mask else 0) | 126)
            header += struct.pack(">H", n)
        else:
            header.append((0x80 if mask else 0) | 127)
            header += struct.pack(">Q", n)
        if mask:
            key = os.urandom(4)
            header += key
            data = bytes(b ^ key[i & 3] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + data)

    def send(self, obj):
        self._send_frame(0x1, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def recv(self):
        self.sock.settimeout(self.timeout)
        while True:
            b1 = self._recv_exact(1)[0]
            b2 = self._recv_exact(1)[0]
            opcode = b1 & 0x0F
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8))[0]
            payload = self._recv_exact(length)
            if opcode == 0x8:
                raise ConnectionError("服务器关闭了连接")
            if opcode == 0x9:  # ping -> pong
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            return json.loads(payload.decode("utf-8"))

    def close(self):
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def expect(client, msg_type):
    msg = client.recv()
    assert msg.get("type") == msg_type, "期望收到 %s，实际收到: %r" % (msg_type, msg)
    return msg


def expect_error(client, keyword):
    msg = expect(client, "error")
    assert keyword in msg.get("message", ""), "错误信息不含「%s」: %r" % (keyword, msg)
    return msg


def test_http_page():
    with urllib.request.urlopen(BASE_URL, timeout=TIMEOUT) as resp:
        html = resp.read().decode("utf-8")
        assert resp.status == 200, "HTTP 状态码异常: %r" % resp.status
    assert "五子棋" in html, "页面内容不是五子棋页面"
    print("[1/6] HTTP 页面可访问          PASS")


def test_join_and_colors():
    p1 = WSClient()
    hello1 = expect(p1, "hello")
    assert hello1["color"] == 1, "第一个玩家应为黑棋: %r" % hello1
    st1 = expect(p1, "state")
    assert st1["players"] == {"black": True, "white": False}, st1["players"]
    assert st1["you"] == 1 and st1["current"] == 1

    p2 = WSClient()
    hello2 = expect(p2, "hello")
    assert hello2["color"] == 2, "第二个玩家应为白棋: %r" % hello2
    st2 = expect(p2, "state")
    st1 = expect(p1, "state")
    assert st1["players"] == {"black": True, "white": True}
    assert st2["you"] == 2 and st1["you"] == 1
    assert sum(sum(row) for row in st1["board"]) == 0, "开局棋盘应为空"
    print("[2/6] 双客户端连接、黑白分配    PASS")
    return p1, p2


def test_out_of_turn(p2):
    p2.send({"type": "move", "row": 7, "col": 7})  # 白棋抢先落子
    expect_error(p2, "轮")
    print("[3/6] 非本回合落子被拒绝        PASS")


def test_win(p1, p2):
    # 黑棋在第 0 行连五，白棋在第 1 行陪跑
    for i in range(4):
        p1.send({"type": "move", "row": 0, "col": i})
        s1 = expect(p1, "state")
        expect(p2, "state")
        assert s1["board"][0][i] == 1, "黑棋落子未生效"
        assert s1["lastMove"] == [0, i], "lastMove 异常: %r" % s1["lastMove"]
        assert s1["current"] == 2, "落子后应轮到白棋"

        p2.send({"type": "move", "row": 1, "col": i})
        s1 = expect(p1, "state")
        expect(p2, "state")
        assert s1["board"][1][i] == 2, "白棋落子未生效"
        assert s1["current"] == 1, "落子后应轮到黑棋"

    p1.send({"type": "move", "row": 0, "col": 4})  # 黑棋第五子
    s1 = expect(p1, "state")
    expect(p2, "state")
    assert s1["board"][0][4] == 1
    assert s1["over"] is True, "五连后应判定对局结束"
    assert s1["winner"] == 1, "黑棋应获胜: %r" % s1["winner"]
    assert len(s1["line"]) >= 5, "获胜连线应包含至少 5 个点"
    cells = {(r, c) for r, c in s1["line"]}
    for i in range(5):
        assert (0, i) in cells, "获胜连线缺少 (0, %d)" % i
    print("[4/6] 五连胜利判定与连线        PASS")


def test_undo(p1, p2):
    # 悔棋：撤销黑棋刚才的获胜落子 (0,4)，恢复上一手白棋 (1,3)
    p1.send({"type": "undo"})
    ev1 = expect(p1, "undo")
    ev2 = expect(p2, "undo")
    assert ev1["color"] == 1, "悔棋事件应记录被撤销的一方: %r" % ev1
    assert ev2["color"] == 1
    s1 = expect(p1, "state")
    expect(p2, "state")
    assert s1["board"][0][4] == 0, "悔棋应移除最后一枚棋子"
    assert s1["over"] is False and s1["winner"] is None, "悔棋后对局应恢复进行中"
    assert s1["current"] == 1, "悔棋后应重新轮到黑棋"
    assert s1["lastMove"] == [1, 3], "悔棋后最后一步应回退到白棋 (1,3): %r" % s1["lastMove"]

    # 重新落子恢复胜局，便于后续重新开始测试
    p1.send({"type": "move", "row": 0, "col": 4})
    s1 = expect(p1, "state")
    expect(p2, "state")
    assert s1["over"] is True and s1["winner"] == 1, "重新落子后应再次判定黑棋获胜"
    print("[5/6] 悔棋与恢复                 PASS")


def test_restart(p1, p2):
    p1.send({"type": "restart"})
    s1 = expect(p1, "state")
    s2 = expect(p2, "state")
    for s in (s1, s2):
        assert all(all(v == 0 for v in row) for row in s["board"]), "重开后棋盘应为空"
        assert s["over"] is False and s["current"] == 1 and s["lastMove"] is None
    assert s1["you"] == 2 and s2["you"] == 1, "重开后黑白应交换"
    print("[6/6] 重新开始与换边            PASS")


def main():
    global HOST, PORT, TIMEOUT, TLS, BASE_URL
    _fix_stdout()
    parser = argparse.ArgumentParser(description="五子棋联机自测")
    parser.add_argument("--url", help="线上地址，如 https://gomoku.onrender.com；省略则测本机")
    args = parser.parse_args()

    if args.url:
        url = args.url if "://" in args.url else "https://" + args.url
        parsed = urllib.parse.urlparse(url)
        HOST = parsed.hostname
        TLS = parsed.scheme == "https"
        PORT = parsed.port or (443 if TLS else 80)
        TIMEOUT = 90
        BASE_URL = url.rstrip("/") + "/"
        print("测试目标: %s（首次访问可能触发平台冷启动，请耐心等待）" % url)
    else:
        print("测试目标: 本机 %s" % BASE_URL)

    print("五子棋联机自测（本机测试请先启动 server.py）")
    print("-" * 44)
    try:
        test_http_page()
        p1, p2 = test_join_and_colors()
        test_out_of_turn(p2)
        test_win(p1, p2)
        test_undo(p1, p2)
        test_restart(p1, p2)
        p1.close()
        p2.close()
    except AssertionError as exc:
        print("\n[FAIL] %s" % exc)
        return 1
    except (OSError, ConnectionError) as exc:
        print("\n[FAIL] 无法连接目标（服务未启动或地址不可达）: %s" % exc)
        return 1
    print("-" * 44)
    print("全部通过 ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
