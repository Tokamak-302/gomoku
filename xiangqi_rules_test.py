#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中国象棋规则单元测试（纯逻辑，不含网络）。"""
import sys

from xiangqi import (
    BOARD_COLS, BOARD_ROWS,
    in_check, initial_board, has_legal_moves, legal_moves, pseudo_moves,
)

RED, BLACK = 1, 2
passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


def empty_board():
    return [[None] * BOARD_COLS for _ in range(BOARD_ROWS)]


def board_with_kings():
    """空棋盘 + 双方将帅（不同列，互不干扰）。"""
    b = empty_board()
    b[9][3] = "K"   # 红帅
    b[0][5] = "k"   # 黑将
    return b


# 1. 初始局面：红兵
board = initial_board()
check("initial red pawn legal", legal_moves(board, 6, 0) == [(5, 0)])

# 2. 初始局面：红马两个走法
moves = set(legal_moves(board, 9, 1))
check("initial red horse two moves", moves == {(7, 0), (7, 2)})

# 3. 蹩马腿
b = board_with_kings()
b[5][4] = "N"
b[5][5] = "P"   # 马腿（右）
moves = set(legal_moves(b, 5, 4))
check("horse leg blocked", (4, 6) not in moves and (6, 6) not in moves)
check("horse other direction open", (3, 5) in moves)

# 4. 炮：隔一子吃子、不可越过隔子平移
b = board_with_kings()
b[5][0] = "C"
b[5][2] = "P"   # 炮架（己方）
b[5][4] = "p"   # 黑卒
moves = set(legal_moves(b, 5, 0))
check("cannon moves before screen", (5, 1) in moves)
check("cannon cannot pass screen without capture", (5, 3) not in moves)
check("cannon captures over screen", (5, 4) in moves)

# 5. 飞将（照面）约束：车横向移开会让将帅照面 → 不合法
b = empty_board()
b[9][4] = "K"
b[0][4] = "k"
b[5][4] = "R"
moves = set(legal_moves(b, 5, 4))
check("flying-general illegal move", (5, 3) not in moves)
check("rook can move along file", (4, 4) in moves)

# 6. 将军检测
b = board_with_kings()
b[0][4] = "k"   # 黑将
b[2][4] = "R"   # 红车直线攻击
check("check detection", in_check(b, False) is True)
check("check detection false side", in_check(b, True) is False)

# 7. 将死：黑将无路可走
b = empty_board()
b[0][4] = "k"   # 黑将
b[9][4] = "K"   # 红帅（被 (1,4) 的车隔开，不照面）
b[0][0] = "R"
b[0][8] = "R"
b[1][4] = "R"
b[1][0] = "R"
check("checkmate no legal moves", has_legal_moves(b, False) is False)

# 8. 被将军但仍有解 → 有合法走法
b = empty_board()
b[0][4] = "k"   # 黑将
b[9][3] = "K"   # 红帅
b[0][3] = "R"   # 红车贴脸将军
check("checked but escapable has moves", has_legal_moves(b, False) is True)

print("-" * 32)
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
