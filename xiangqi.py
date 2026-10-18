#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中国象棋规则与联机房间（服务端权威，纯标准库）。

坐标：r 0..9（0 为黑方底线，9 为红方底线），c 0..8。
红方 = 1（先手），黑方 = 2。
棋子编码：红方大写 R N B A K C P；黑方小写 r n b a k c p；空位 None。

本模块由 server.py 导入使用；房间接口与服务端广播约定一致：
- 属性：lock / clients / players{1,2} / restart_votes{1,2}
- state_for(conn) 返回完整状态快照
- handle_move / handle_legal / handle_restart / handle_undo
"""
import copy
import threading

BOARD_ROWS = 10
BOARD_COLS = 9
RED = 1
BLACK = 2

PIECE_NAMES = {
    "R": "车", "N": "马", "B": "相", "A": "仕", "K": "帅", "C": "炮", "P": "兵",
    "r": "车", "n": "马", "b": "象", "a": "士", "k": "将", "c": "炮", "p": "卒",
}

INITIAL = [
    ["r", "n", "b", "a", "k", "a", "b", "n", "r"],
    [None] * 9,
    [None, "c", None, None, None, None, None, "c", None],
    ["p", None, "p", None, "p", None, "p", None, "p"],
    [None] * 9,
    [None] * 9,
    ["P", None, "P", None, "P", None, "P", None, "P"],
    [None, "C", None, None, None, None, None, "C", None],
    [None] * 9,
    ["R", "N", "B", "A", "K", "A", "B", "N", "R"],
]


def log(text):
    print(text, flush=True)


def initial_board():
    return copy.deepcopy(INITIAL)


def in_board(r, c):
    return 0 <= r < BOARD_ROWS and 0 <= c < BOARD_COLS


def in_palace(r, c, red):
    if not (3 <= c <= 5):
        return False
    return (7 <= r <= 9) if red else (0 <= r <= 2)


def color_of(piece):
    return RED if piece.isupper() else BLACK


def find_king(board, red):
    target = "K" if red else "k"
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            if board[r][c] == target:
                return (r, c)
    return None


def kings_face(board):
    """双方将帅在同一列且中间无子（飞将/照面）。"""
    rk = find_king(board, True)
    bk = find_king(board, False)
    if rk is None or bk is None or rk[1] != bk[1]:
        return False
    lo, hi = sorted((rk[0], bk[0]))
    for rr in range(lo + 1, hi):
        if board[rr][rk[1]] is not None:
            return False
    return True


def pseudo_moves(board, r, c):
    """不考虑将军/照面的走法。"""
    piece = board[r][c]
    if piece is None:
        return []
    red = piece.isupper()
    kind = piece.upper()
    moves = []

    def add_target(rr, cc):
        if not in_board(rr, cc):
            return
        q = board[rr][cc]
        if q is None:
            moves.append((rr, cc))
        elif q.isupper() != red:
            moves.append((rr, cc))

    if kind == "K":
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if in_palace(rr, cc, red):
                add_target(rr, cc)
    elif kind == "A":
        for dr, dc in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            rr, cc = r + dr, c + dc
            if in_palace(rr, cc, red):
                add_target(rr, cc)
    elif kind == "B":
        for dr, dc in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
            rr, cc = r + dr, c + dc
            if not in_board(rr, cc):
                continue
            if red and rr < 5:
                continue
            if (not red) and rr > 4:
                continue
            eye_r, eye_c = r + dr // 2, c + dc // 2
            if board[eye_r][eye_c] is None:
                add_target(rr, cc)
    elif kind == "N":
        for dr, dc in ((2, 1), (2, -1), (-2, 1), (-2, -1),
                       (1, 2), (1, -2), (-1, 2), (-1, -2)):
            rr, cc = r + dr, c + dc
            if not in_board(rr, cc):
                continue
            if abs(dr) == 2:
                leg_r, leg_c = r + dr // 2, c
            else:
                leg_r, leg_c = r, c + dc // 2
            if board[leg_r][leg_c] is None:
                add_target(rr, cc)
    elif kind == "R":
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            while in_board(rr, cc):
                q = board[rr][cc]
                if q is None:
                    moves.append((rr, cc))
                else:
                    if q.isupper() != red:
                        moves.append((rr, cc))
                    break
                rr += dr
                cc += dc
    elif kind == "C":
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            jumped = False
            while in_board(rr, cc):
                q = board[rr][cc]
                if not jumped:
                    if q is None:
                        moves.append((rr, cc))
                    else:
                        jumped = True
                else:
                    if q is not None:
                        if q.isupper() != red:
                            moves.append((rr, cc))
                        break
                rr += dr
                cc += dc
    elif kind == "P":
        forward = -1 if red else 1
        add_target(r + forward, c)
        crossed = (r <= 4) if red else (r >= 5)
        if crossed:
            add_target(r, c - 1)
            add_target(r, c + 1)
    return moves


def _apply(board, fr, fc, tr, tc):
    b = copy.deepcopy(board)
    b[tr][tc] = b[fr][fc]
    b[fr][fc] = None
    return b


def in_check(board, red):
    """red 方是否被将军（含将帅照面）。"""
    king = find_king(board, red)
    if king is None:
        return True
    if kings_face(board):
        return True
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            p = board[r][c]
            if p is not None and p.isupper() != red:
                if king in pseudo_moves(board, r, c):
                    return True
    return False


def move_keeps_king_safe(board, fr, fc, tr, tc):
    new_board = _apply(board, fr, fc, tr, tc)
    red = board[fr][fc].isupper()
    if kings_face(new_board):
        return False
    return not in_check(new_board, red)


def legal_moves(board, r, c):
    piece = board[r][c]
    if piece is None:
        return []
    return [(tr, tc) for (tr, tc) in pseudo_moves(board, r, c)
            if move_keeps_king_safe(board, r, c, tr, tc)]


def has_legal_moves(board, red):
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            p = board[r][c]
            if p is not None and p.isupper() == red:
                if legal_moves(board, r, c):
                    return True
    return False


def broadcast_locked(room):
    """给房间内所有在线连接推送状态（调用方需持有 room.lock）。"""
    for client in room.clients:
        if client.alive:
            client.send(room.state_for(client))
    room.clients[:] = [c for c in room.clients if c.alive]


class XiangqiRoom:
    """中国象棋单房间状态。"""

    def __init__(self):
        self.lock = threading.RLock()
        self.clients = []
        self.players = {1: None, 2: None}  # 1=红 2=黑
        self.reset(swap=False)

    def reset(self, swap=False):
        if swap and self.players[1] is not None and self.players[2] is not None:
            p1, p2 = self.players[1], self.players[2]
            self.players[1], self.players[2] = p2, p1
            p1.color, p2.color = 2, 1
        self.board = initial_board()
        self.turn = RED
        self.over = False
        self.winner = None
        self.history = []  # [{"from":[r,c],"to":[r,c],"piece","captured","color"}]
        self.last_move = None  # {"from":[r,c],"to":[r,c]}
        self.restart_votes = {1: False, 2: False}

    def state_for(self, conn):
        return {
            "type": "state",
            "game": "xiangqi",
            "board": self.board,
            "turn": self.turn,
            "over": self.over,
            "winner": self.winner,
            "lastMove": self.last_move,
            "you": conn.color,
            "players": {
                "red": self.players[1] is not None,
                "black": self.players[2] is not None,
            },
            "connected": len([c for c in self.clients if c.alive]),
            "restartVotes": {
                "red": self.restart_votes[1],
                "black": self.restart_votes[2],
            },
            "canUndo": bool(
                conn.color in (1, 2)
                and self.history
                and self.history[-1]["color"] == conn.color
            ),
        }

    def handle_move(self, conn, msg):
        if conn.color == 0:
            conn.send({"type": "error", "message": "观众不能落子"})
            return
        if self.over:
            conn.send({"type": "error", "message": "本局已结束，请重新开始"})
            return
        if conn.color != self.turn:
            conn.send({"type": "error", "message": "还没轮到你"})
            return
        frm = msg.get("from")
        to = msg.get("to")
        if not (isinstance(frm, list) and len(frm) == 2
                and isinstance(to, list) and len(to) == 2):
            conn.send({"type": "error", "message": "坐标格式错误"})
            return
        fr, fc = frm
        tr, tc = to
        if not (isinstance(fr, int) and isinstance(fc, int)
                and isinstance(tr, int) and isinstance(tc, int)
                and in_board(fr, fc) and in_board(tr, tc)):
            conn.send({"type": "error", "message": "坐标不合法"})
            return
        piece = self.board[fr][fc]
        if piece is None:
            conn.send({"type": "error", "message": "起点没有棋子"})
            return
        if color_of(piece) != conn.color:
            conn.send({"type": "error", "message": "不能移动对方的棋子"})
            return
        if (tr, tc) not in legal_moves(self.board, fr, fc):
            conn.send({"type": "error", "message": "这步棋不合法"})
            return

        captured = self.board[tr][tc]
        self.board[tr][tc] = piece
        self.board[fr][fc] = None
        self.history.append({
            "from": [fr, fc], "to": [tr, tc],
            "piece": piece, "captured": captured, "color": conn.color,
        })
        self.last_move = {"from": [fr, fc], "to": [tr, tc]}
        self.turn = BLACK if conn.color == RED else RED

        opponent_red = (conn.color == BLACK)
        if find_king(self.board, opponent_red) is None \
                or not has_legal_moves(self.board, opponent_red):
            self.over = True
            self.winner = conn.color
            log(f"[胜负] {'红方' if conn.color == RED else '黑方'}获胜（将死/困毙）")
        else:
            log(f"[落子] {PIECE_NAMES.get(piece, '?')} {fr},{fc} -> {tr},{tc}")
        broadcast_locked(self)

    def handle_legal(self, conn, msg):
        if conn.color == 0:
            conn.send({"type": "error", "message": "观众不能操作"})
            return
        frm = msg.get("from")
        valid = (isinstance(frm, list) and len(frm) == 2
                 and isinstance(frm[0], int) and isinstance(frm[1], int)
                 and in_board(frm[0], frm[1]))
        if not valid:
            conn.send({"type": "legal", "from": None, "moves": []})
            return
        fr, fc = frm
        piece = self.board[fr][fc]
        if piece is None or color_of(piece) != conn.color:
            conn.send({"type": "legal", "from": [fr, fc], "moves": []})
            return
        conn.send({
            "type": "legal",
            "from": [fr, fc],
            "moves": [[r, c] for r, c in legal_moves(self.board, fr, fc)],
        })

    def handle_restart(self, conn):
        if conn.color == 0:
            conn.send({"type": "error", "message": "只有玩家可以重新开始"})
            return
        if self.players[1] is None or self.players[2] is None:
            conn.send({"type": "error", "message": "需要两名玩家都在线才能重新开始"})
            return
        color = conn.color
        if self.restart_votes[color]:
            self.restart_votes[color] = False
            log("[重开] 取消了重新开始请求")
            broadcast_locked(self)
            return
        self.restart_votes[color] = True
        log("[重开] 请求重新开始")
        if self.restart_votes[1] and self.restart_votes[2]:
            self.reset(swap=True)
            log("[重开] 双方已确认，新对局开始，双方交换红黑")
        broadcast_locked(self)

    def handle_undo(self, conn):
        if conn.color == 0:
            conn.send({"type": "error", "message": "观众不能悔棋"})
            return
        if self.players[1] is None or self.players[2] is None:
            conn.send({"type": "error", "message": "需要两名玩家都在线才能悔棋"})
            return
        if not self.history:
            conn.send({"type": "error", "message": "还没有可以悔的棋子"})
            return
        if self.history[-1]["color"] != conn.color:
            conn.send({"type": "error", "message": "只能悔自己下过的棋"})
            return

        entry = self.history.pop()
        fr, fc = entry["from"]
        tr, tc = entry["to"]
        self.board[fr][fc] = entry["piece"]
        self.board[tr][tc] = entry["captured"]
        self.turn = entry["color"]
        self.over = False
        self.winner = None
        self.last_move = None
        if self.history:
            prev = self.history[-1]
            self.last_move = {"from": prev["from"], "to": prev["to"]}

        log(f"[悔棋] 撤销 {PIECE_NAMES.get(entry['piece'], '?')} "
            f"{fr},{fc} -> {tr},{tc}")
        for client in self.clients:
            if client.alive:
                client.send({
                    "type": "undo",
                    "color": entry["color"],
                    "from": entry["from"],
                    "to": entry["to"],
                })
        broadcast_locked(self)
