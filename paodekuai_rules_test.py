#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑得快规则单元测试（纯逻辑，不含网络）。"""
import sys

from paodekuai import PaodekuaiRoom, beats, initial_deck, parse_combo

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


class MockConn:
    def __init__(self, color):
        self.color = color
        self.alive = True
        self.sent = []

    def send(self, obj):
        self.sent.append(obj)


def card(r, s):
    return {"r": r, "s": s}


def last_of(mock, kind):
    for msg in reversed(mock.sent):
        if msg.get("type") == kind:
            return msg
    return None


# 1. 牌库
deck = initial_deck()
check("deck size 48", len(deck) == 48)
check("no spade A", not any(c["r"] == 14 and c["s"] == 0 for c in deck))
check("only spade 2", [c for c in deck if c["r"] == 15] == [card(15, 0)])
check("heart 3 exists", any(c["r"] == 3 and c["s"] == 1 for c in deck))

# 2. 牌型解析
check("single", parse_combo([card(5, 0)]) == {"type": "single", "rank": 5, "length": 1})
check("pair", parse_combo([card(5, 0), card(5, 1)]) == {"type": "pair", "rank": 5, "length": 2})
check("triple", parse_combo([card(5, 0), card(5, 1), card(5, 2)]) == {"type": "triple", "rank": 5, "length": 3})
check("triple1", parse_combo([card(5, 0), card(5, 1), card(5, 2), card(9, 0)]) == {"type": "triple1", "rank": 5, "length": 4})
check("triple2", parse_combo([card(5, 0), card(5, 1), card(5, 2), card(9, 0), card(9, 1)]) == {"type": "triple2", "rank": 5, "length": 5})
check("bomb", parse_combo([card(5, 0), card(5, 1), card(5, 2), card(5, 3)]) == {"type": "bomb", "rank": 5, "length": 4})
check("straight 5", parse_combo([card(3, 0), card(4, 0), card(5, 0), card(6, 0), card(7, 0)]) == {"type": "straight", "rank": 7, "length": 5})
check("straight invalid with 2", parse_combo([card(11, 0), card(12, 0), card(13, 0), card(14, 0), card(15, 0)]) is None)
check("pair_straight", parse_combo([card(3, 0), card(3, 1), card(4, 0), card(4, 1)]) == {"type": "pair_straight", "rank": 4, "length": 2})
check("pair_straight invalid single gap", parse_combo([card(3, 0), card(3, 1), card(5, 0), card(5, 1)]) is None)
check("plane", parse_combo([card(3, 0), card(3, 1), card(3, 2), card(4, 0), card(4, 1), card(4, 2)]) == {"type": "plane", "rank": 4, "length": 2})
check("plane1 wings", parse_combo([card(3, 0), card(3, 1), card(3, 2), card(4, 0), card(4, 1), card(4, 2), card(7, 0), card(8, 0)]) == {"type": "plane1", "rank": 4, "length": 2})
check("plane2 wings", parse_combo([card(3, 0), card(3, 1), card(3, 2), card(4, 0), card(4, 1), card(4, 2), card(7, 0), card(7, 1), card(8, 0), card(8, 1)]) == {"type": "plane2", "rank": 4, "length": 2})
check("invalid random", parse_combo([card(3, 0), card(5, 0)]) is None)

# 3. 比较
s5 = parse_combo([card(3, 0), card(4, 0), card(5, 0), card(6, 0), card(7, 0)])
s6 = parse_combo([card(4, 0), card(5, 0), card(6, 0), card(7, 0), card(8, 0)])
s6b = parse_combo([card(3, 1), card(4, 1), card(5, 1), card(6, 1), card(7, 1)])
check("straight beats lower", beats(s6, s5))
check("straight cannot beat same", not beats(s5, s6b))
check("different length cannot beat", not beats(parse_combo([card(3, 0), card(4, 0), card(5, 0), card(6, 0), card(7, 0), card(8, 0)]), s5))
bomb = parse_combo([card(5, 0), card(5, 1), card(5, 2), card(5, 3)])
check("bomb beats straight", beats(bomb, s5))
check("straight cannot beat bomb", not beats(s5, bomb))
check("bomb beats lower bomb", beats(parse_combo([card(9, 0), card(9, 1), card(9, 2), card(9, 3)]), bomb))

# 4. 房间流程
room = PaodekuaiRoom()
m1, m2, m3 = MockConn(1), MockConn(2), MockConn(3)
room.clients = [m1, m2, m3]
room.players = {1: m1, 2: m2, 3: m3}
room.started = True
room.hands = {
    1: [card(3, 1), card(5, 2), card(5, 3)],   # ♥3, 5♣, 5♦
    2: [card(6, 2), card(8, 2), card(8, 3)],
    3: [card(7, 2), card(9, 2), card(9, 3)],
}
room.turn = room._first_turn()
check("heart 3 holder leads", room.turn == 1)

room.handle_play(m1, {"cards": [card(3, 1)]})
check("single played", last_of(m1, "played") is not None)
check("turn moves to 2", room.turn == 2)
check("hand updated", len(room.hands[1]) == 2)

room.handle_play(m2, {"cards": [card(6, 2)]})
check("6 beats 3", room.turn == 3 and room.last_play["by"] == 2)

room.handle_pass(m3)
room.handle_pass(m1)
check("two passes end round", room.last_play is None and room.turn == 2)
check("passes reset", room.passes == 0)

# 不能过牌（领出时）与非法出牌
room.handle_play(m2, {"cards": []})
check("empty play rejected", last_of(m2, "error") is not None)
room.handle_pass(m2)
check("cannot pass while leading", any(msg.get("message") == "本轮由你领出，不能过牌" for msg in m2.sent if msg.get("type") == "error"))

# 出完手牌获胜
room.hands[1] = [card(5, 2), card(5, 3)]
room.turn = 1
room.last_play = None
room.handle_play(m1, {"cards": [card(5, 2), card(5, 3)]})
check("winner on empty hand", room.over and room.winner == 1)

# 重开投票
room.reset(deal=False)
room.players = {1: m1, 2: m2, 3: m3}
room.clients = [m1, m2, m3]
room.handle_restart(m1)
check("restart vote 1", room.restart_votes[1] is True)
room.handle_restart(m2)
check("restart vote 2", room.restart_votes[1] and room.restart_votes[2] and not room.restart_votes[3])
room.handle_restart(m3)
check("restart deals", room.started and len(room.hands[1]) == 16 and len(room.hands[2]) == 16 and len(room.hands[3]) == 16)

print("-" * 32)
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
