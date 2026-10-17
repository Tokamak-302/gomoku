#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""五子棋 · 联机版（纯标准库，零依赖；单端口同时提供页面与 WebSocket）

本机运行:
    py -3 server.py
浏览器打开 http://127.0.0.1:8000，再开一个窗口即可联机对弈。

部署到 Render / Railway 等平台时:
    - 平台会注入环境变量 PORT，程序自动监听 0.0.0.0:$PORT；
    - 也可用环境变量 HOST 显式指定监听地址。
"""
import base64
import hashlib
import json
import os
import socket
import socketserver
import struct
import sys
import threading
from pathlib import Path

BOARD_SIZE = 15
STATIC_DIR = Path(__file__).resolve().parent
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

PORT = int(os.environ.get("PORT", "8000"))
# 本地默认只监听回环地址；检测到平台注入的 PORT 时监听所有网卡。
HOST = os.environ.get("HOST") or ("0.0.0.0" if "PORT" in os.environ else "127.0.0.1")

COLOR_NAMES = {1: "黑棋", 2: "白棋", 0: "观众"}


def _fix_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(text):
    print(text, flush=True)


# ---------------------------------------------------------------------------
# 游戏逻辑
# ---------------------------------------------------------------------------
def check_win(board, row, col, color):
    """返回构成五连（或更长）的坐标列表；未获胜返回空列表。"""
    directions = ((1, 0), (0, 1), (1, 1), (1, -1))
    for dr, dc in directions:
        cells = [(row, col)]
        r, c = row - dr, col - dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == color:
            cells.insert(0, (r, c))
            r -= dr
            c -= dc
        r, c = row + dr, col + dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == color:
            cells.append((r, c))
            r += dr
            c += dc
        if len(cells) >= 5:
            return [[cr, cc] for cr, cc in cells]
    return []


class PlayerConn:
    """一条客户端连接。"""

    def __init__(self, sock, addr, room):
        self.sock = sock
        self.addr = addr
        self.room = room
        self.color = 0  # 0=观众, 1=黑, 2=白
        self.send_lock = threading.Lock()
        self.alive = True

    def send(self, obj):
        if not self.alive:
            return
        try:
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            with self.send_lock:
                self.sock.sendall(encode_frame(0x1, data))
        except OSError:
            self.alive = False


class Room:
    """单房间游戏状态。所有读写都在 self.lock 内完成。"""

    def __init__(self):
        self.lock = threading.RLock()
        self.clients = []                  # 所有在线 WebSocket 连接（含观众）
        self.players = {1: None, 2: None}  # 黑 / 白
        self.board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.current = 1
        self.over = False
        self.winner = None
        self.line = []
        self.last_move = None

    def reset(self, swap=False):
        if swap and self.players[1] is not None and self.players[2] is not None:
            p1, p2 = self.players[1], self.players[2]
            self.players[1], self.players[2] = p2, p1
            p1.color, p2.color = 2, 1
        self.board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.current = 1
        self.over = False
        self.winner = None
        self.line = []
        self.last_move = None

    def state_for(self, conn):
        return {
            "type": "state",
            "board": self.board,
            "current": self.current,
            "over": self.over,
            "winner": self.winner,
            "line": self.line,
            "lastMove": self.last_move,
            "you": conn.color,
            "players": {
                "black": self.players[1] is not None,
                "white": self.players[2] is not None,
            },
            "connected": len([c for c in self.clients if c.alive]),
        }


ROOM = Room()


def broadcast_locked(room):
    """给所有在线连接推送完整状态（调用方需持有 room.lock）。"""
    for client in room.clients:
        if client.alive:
            client.send(room.state_for(client))
    room.clients[:] = [c for c in room.clients if c.alive]


# ---------------------------------------------------------------------------
# WebSocket 帧编码 / 解码
# ---------------------------------------------------------------------------
def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("连接已断开")
        data += chunk
    return bytes(data)


def read_frame(sock):
    b1, b2 = recv_exact(sock, 2)
    fin = bool(b1 & 0x80)
    if b1 & 0x70:
        raise ConnectionError("不支持 RSV 扩展")
    opcode = b1 & 0x0F
    masked = bool(b2 & 0x80)
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack(">H", recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", recv_exact(sock, 8))[0]
    if length > 4 * 1024 * 1024:
        raise ConnectionError("帧过大")
    if not masked:
        raise ConnectionError("客户端帧必须带掩码")
    mask = recv_exact(sock, 4)
    payload = bytearray(recv_exact(sock, length))
    for i in range(length):
        payload[i] ^= mask[i & 3]
    return opcode, fin, bytes(payload)


def encode_frame(opcode, payload):
    header = bytearray([0x80 | opcode])
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n <= 0xFFFF:
        header.append(126)
        header += struct.pack(">H", n)
    else:
        header.append(127)
        header += struct.pack(">Q", n)
    return bytes(header) + payload


def read_until(sock, sep):
    buf = bytearray()
    while sep not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("连接在读取请求头时关闭")
        buf += chunk
        if len(buf) > 64 * 1024:
            raise ConnectionError("请求头过大")
    return bytes(buf)


def send_http_status(sock, status):
    body = (status + "\n").encode("utf-8")
    sock.sendall((
        "HTTP/1.1 %s\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n\r\n" % (status, len(body))
    ).encode("latin-1") + body)


# ---------------------------------------------------------------------------
# HTTP 静态页面（与 WebSocket 共用同一端口）
# ---------------------------------------------------------------------------
def serve_http_request(sock, method, path, headers):
    clean = path.split("?", 1)[0].split("#", 1)[0]
    rel = clean.lstrip("/")
    if rel in ("", "index.html"):
        rel = "index.html"
    target = STATIC_DIR / rel
    allowed = rel == "index.html" and target.is_file()

    if not allowed:
        send_http_status(sock, "404 Not Found")
        return

    data = target.read_bytes()
    mime = MIME_TYPES.get(target.suffix.lower(), "application/octet-stream")
    head = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: %s\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "Cache-Control: no-store\r\n\r\n" % (mime, len(data))
    )
    sock.sendall(head.encode("latin-1"))
    if method != "HEAD":
        sock.sendall(data)


# ---------------------------------------------------------------------------
# 业务消息处理
# ---------------------------------------------------------------------------
def handle_move(conn, msg):
    room = conn.room
    if conn.color == 0:
        conn.send({"type": "error", "message": "观众不能落子"})
        return
    if room.over:
        conn.send({"type": "error", "message": "本局已结束，请点「重新开始」"})
        return
    if conn.color != room.current:
        conn.send({"type": "error", "message": "还没轮到你"})
        return
    row = msg.get("row")
    col = msg.get("col")
    if (not isinstance(row, int)) or (not isinstance(col, int)) \
            or not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
        conn.send({"type": "error", "message": "坐标不合法"})
        return
    if room.board[row][col] != 0:
        conn.send({"type": "error", "message": "这个交叉点已经有棋子了"})
        return

    room.board[row][col] = conn.color
    room.last_move = [row, col]
    line = check_win(room.board, row, col, conn.color)
    if line:
        room.over = True
        room.winner = conn.color
        room.line = line
        log(f"[胜负] {COLOR_NAMES[conn.color]}连五获胜 {line}")
    elif all(room.board[r][c] != 0 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)):
        room.over = True
        room.winner = 0
        room.line = []
        log("[胜负] 棋盘已满，平局")
    else:
        room.current = 2 if room.current == 1 else 1
        log(f"[落子] {COLOR_NAMES[conn.color]} -> ({row + 1}, {col + 1})")
    broadcast_locked(room)


def handle_restart(conn):
    room = conn.room
    if conn.color == 0:
        conn.send({"type": "error", "message": "只有玩家可以重新开始"})
        return
    if room.players[1] is None or room.players[2] is None:
        conn.send({"type": "error", "message": "需要两名玩家都在线才能重新开始"})
        return
    room.reset(swap=True)
    log("[重开] 新对局开始，双方交换黑白")
    broadcast_locked(room)


def handle_message(conn, text):
    try:
        msg = json.loads(text)
    except json.JSONDecodeError:
        conn.send({"type": "error", "message": "消息不是合法 JSON"})
        return
    if not isinstance(msg, dict):
        conn.send({"type": "error", "message": "消息格式错误"})
        return
    mtype = msg.get("type")
    room = conn.room
    with room.lock:
        if mtype == "move":
            handle_move(conn, msg)
        elif mtype == "restart":
            handle_restart(conn)
        elif mtype == "ping":
            conn.send({"type": "pong"})
        else:
            conn.send({"type": "error", "message": "未知消息类型: %s" % mtype})


# ---------------------------------------------------------------------------
# WebSocket 帧循环与连接生命周期（握手 + 帧循环）
# ---------------------------------------------------------------------------
def frame_loop(sock, conn):
    frag_op = None
    frag = bytearray()
    while conn.alive:
        opcode, fin, payload = read_frame(sock)
        if opcode == 0x8:  # close
            try:
                with conn.send_lock:
                    sock.sendall(encode_frame(0x8, b""))
            except OSError:
                pass
            return
        if opcode == 0x9:  # ping
            with conn.send_lock:
                sock.sendall(encode_frame(0xA, payload))
            continue
        if opcode == 0xA:  # pong
            continue
        if opcode in (0x1, 0x2, 0x0):
            if opcode == 0x0:
                if frag_op is None:
                    raise ConnectionError("非法分片")
                frag += payload
            else:
                frag_op = opcode
                frag = bytearray(payload)
            if fin:
                if frag_op == 0x1:
                    try:
                        text = frag.decode("utf-8")
                    except UnicodeDecodeError:
                        conn.send({"type": "error", "message": "文本不是合法 UTF-8"})
                    else:
                        handle_message(conn, text)
                frag_op = None
                frag = bytearray()
            continue
        raise ConnectionError("不支持的帧类型: %d" % opcode)


def handle_connection(sock, addr, room):
    """单端口分发：带 Upgrade 头的走 WebSocket，其余按 HTTP 页面处理。"""
    conn = PlayerConn(sock, addr, room)
    registered = False
    try:
        sock.settimeout(10)
        raw = read_until(sock, b"\r\n\r\n")
        sock.settimeout(None)

        lines = raw.split(b"\r\n")
        request_line = lines[0].decode("latin-1", "replace")
        method, _, rest = request_line.partition(" ")
        method = method.upper()
        path = rest.split(" ", 1)[0] if " " in rest else rest

        headers = {}
        for line in lines[1:]:
            if b":" not in line:
                continue
            key, _, value = line.partition(b":")
            headers[key.strip().lower().decode("latin-1")] = value.strip().decode("latin-1")

        if headers.get("upgrade", "").lower() == "websocket":
            ws_key = headers.get("sec-websocket-key", "")
            if not ws_key:
                send_http_status(sock, "400 Bad Request")
                return
            accept = base64.b64encode(
                hashlib.sha1((ws_key + WS_GUID).encode()).digest()
            ).decode()
            sock.sendall((
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Accept: %s\r\n\r\n" % accept
            ).encode("latin-1"))

            with room.lock:
                room.clients.append(conn)
                if room.players[1] is None:
                    conn.color = 1
                    room.players[1] = conn
                elif room.players[2] is None:
                    conn.color = 2
                    room.players[2] = conn
                else:
                    conn.color = 0  # 观众
                registered = True
                log(f"[+] 连接 {addr[0]} 身份={COLOR_NAMES[conn.color]}")
                conn.send({"type": "hello", "color": conn.color})
                broadcast_locked(room)

            frame_loop(sock, conn)
        else:
            serve_http_request(sock, method, path, headers)
    except (ConnectionError, OSError):
        pass
    finally:
        conn.alive = False
        if registered:
            with room.lock:
                if conn in room.clients:
                    room.clients.remove(conn)
                if room.players.get(1) is conn:
                    room.players[1] = None
                if room.players.get(2) is conn:
                    room.players[2] = None
                if conn.color:
                    log(f"[-] 离开 {addr[0]} 身份={COLOR_NAMES[conn.color]}")
                broadcast_locked(room)
        try:
            sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 服务器
# ---------------------------------------------------------------------------
class WSServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class WSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        handle_connection(self.request, self.client_address, ROOM)


def main():
    _fix_stdout()
    try:
        server = WSServer((HOST, PORT), WSHandler)
    except OSError as exc:
        log(f"[X] 端口 {PORT} 无法绑定：{exc}")
        return 1

    shown = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    log("=" * 52)
    log(" 五子棋 · 联机服务已启动（单端口：页面 + WebSocket）")
    log(f" 本机访问 : http://{shown}:{PORT}")
    log(" 部署平台 : 自动使用环境变量 PORT / HOST")
    log(" 停止     : 按 Ctrl+C")
    log("=" * 52)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("\n[·] 服务已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
