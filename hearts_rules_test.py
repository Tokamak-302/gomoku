#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""红心大战规则 / AI / 房间流程单元测试（纯逻辑，不含网络）。"""
import sys

from hearts import (
    HeartsRoom, ai_choose_pass, ai_choose_play, initial_deck,
    is_queen_spades, trick_points, trick_winner,
)

passed = 0
failed = 0


def check(name, cond, detail=None):
    global passed, failed
    if cond:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name, detail if detail is not None else "")


class MockConn:
    def __init__(self, color):
        self.color = color
        self.alive = True
        self.sent = []

    def send(self, obj):
        self.sent.append(obj)


def C(r, s):
    return {"r": r, "s": s}


# 1. 牌库与基本函数
deck = initial_deck()
check("deck size 52", len(deck) == 52)
check("club 2 exists", C(2, 0) in deck)
check("queen spades helper", is_queen_spades(C(12, 3)) and not is_queen_spades(C(12, 2)))
trick = [{"seat": 0, "card": C(5, 0)}, {"seat": 1, "card": C(11, 0)},
         {"seat": 2, "card": C(3, 1)}, {"seat": 3, "card": C(9, 0)}]
check("trick winner follows lead suit", trick_winner(trick) == 1)
check("trick points hearts/queen", trick_points([
    {"seat": 0, "card": C(2, 2)}, {"seat": 1, "card": C(12, 3)},
    {"seat": 2, "card": C(5, 0)}, {"seat": 3, "card": C(6, 0)}
]) == 14)

# 2. 合法出牌
room = HeartsRoom(delay=0)
m1, m2 = MockConn(1), MockConn(2)
room.clients = []
room.players = {1: m1, 2: m2}
room.start_game()
check("starts hand 1 pass phase", room.phase == "pass" and room.hand_number == 1)
check("pass direction left", room.pass_direction == "left")

# 固定手牌测试合法出牌
room.hands = [
    [C(2, 0), C(5, 0), C(9, 2)],
    [C(3, 0), C(4, 1)],
    [C(6, 0), C(7, 2)],
    [C(8, 0), C(10, 1)],
]
room.trick = []
room.first_trick = True
room.hearts_broken = False
legal = room.legal_plays(0)
check("first leader must play club 2", legal == [C(2, 0)], legal)

room.hands[0] = [C(5, 0), C(9, 2)]
legal = room.legal_plays(0)
check("hearts cannot be led before broken", C(9, 2) not in legal and C(5, 0) in legal)

room.hearts_broken = True
legal = room.legal_plays(0)
check("hearts can be led after broken", C(9, 2) in legal)

# 跟花色
room.first_trick = False
room.trick = [{"seat": 0, "card": C(5, 0)}]
room.turn = 1
legal = room.legal_plays(1)
check("must follow suit", legal == [C(3, 0)])

# 首墩缺门不能出红心/黑桃Q
room.first_trick = True
room.hearts_broken = False
room.trick = [{"seat": 0, "card": C(5, 0)}]
room.turn = 3
room.hands[3] = [C(4, 2), C(12, 3), C(6, 1)]
legal = room.legal_plays(3)
check("first trick void: no hearts/QS", C(6, 1) in legal and C(4, 2) not in legal and C(12, 3) not in legal)
room.turn = 3
room.hands[3] = [C(4, 2), C(12, 3)]
legal = room.legal_plays(3)
check("first trick void: forced hearts/QS allowed", len(legal) == 2)

# 3. AI 基本合法性
room.reset()
room.players = {1: m1, 2: m2}
room.start_game()
for _ in range(5):
    for seat in (0, 2):
        if room.phase == "pass" and not room.pass_ready[seat]:
            room.handle_pass(m1 if seat == 0 else m2, {"cards": room.hands[seat][:3]})
    if room.phase == "play":
        break
check("room reaches play phase after passing", room.phase == "play")

guard = 0
while room.phase == "play" and guard < 300:
    guard += 1
    seat = room.turn
    card = ai_choose_play(room, seat)
    check_card = card in room.legal_plays(seat) if card else False
    if not check_card:
        check("AI returns legal card", False, f"seat {seat} card {card}")
        break
    room._play_card(seat, card)
if guard < 300:
    check("AI returns legal cards every turn", True)
check("hand finished (handNumber moved on)", room.hand_number >= 2 or room.over, room.phase)
check("last hand scores recorded", room.last_hand_scores is not None,
      getattr(room, "last_hand_scores", None))
if room.last_hand_scores:
    total = room.last_hand_scores["NS"] + room.last_hand_scores["EW"]
    check("hand total is 26", total == 26, room.last_hand_scores)

# 4. 换牌方向（左/右/对家）映射
def pass_direction_test(direction, expected_targets):
    r = HeartsRoom(delay=0)
    r.clients = []
    r.players = {1: MockConn(1), 2: MockConn(2)}
    r.pass_direction = direction
    r.phase = "pass"
    # 每手 4 张，方便观察传递
    r.hands = [
        [C(2, 0), C(100, 0)],
        [C(3, 0), C(101, 0)],
        [C(4, 0), C(102, 0)],
        [C(5, 0), C(103, 0)],
    ]
    # 每座换出第 2 张（100+i 标记）
    r.pending_pass = [[r.hands[i][1]] for i in range(4)]
    r.pass_ready = [True, True, True, True]
    r._resolve_pass()
    ok = True
    for seat in range(4):
        tgt = expected_targets[seat]
        if r.hands[tgt].count(C(100 + seat, 0)) != 1:
            ok = False
    return ok

check("pass left mapping", pass_direction_test("left", {s: (s + 1) % 4 for s in range(4)}))
check("pass right mapping", pass_direction_test("right", {s: (s + 3) % 4 for s in range(4)}))
check("pass across mapping", pass_direction_test("across", {s: (s + 2) % 4 for s in range(4)}))

# 5. 计分：全收 / 普通 / 结束
r = HeartsRoom(delay=0)
r.clients = []
r.players = {1: MockConn(1), 2: MockConn(2)}
r.hand_points = [26, 0, 0, 0]
r.scores = {"NS": 10, "EW": 20}
r._end_hand()
check("moon scoring", r.scores == {"NS": 10, "EW": 46}, r.scores)
check("moon recorded", r.last_hand_scores["moon"] == "N")

r2 = HeartsRoom(delay=0)
r2.clients = []
r2.players = {1: MockConn(1), 2: MockConn(2)}
r2.hand_points = [13, 12, 1, 0]
r2.scores = {"NS": 50, "EW": 40}
r2._end_hand()
check("normal scoring", r2.scores == {"NS": 64, "EW": 52}, r2.scores)

r3 = HeartsRoom(delay=0)
r3.clients = []
r3.players = {1: MockConn(1), 2: MockConn(2)}
r3.hand_points = [0, 0, 13, 13]
r3.scores = {"NS": 95, "EW": 80}
r3._end_hand()
check("game over at 100", r3.over and r3.winner == "EW", (r3.scores, r3.winner))

# 6. 重新开始（双方确认）
r4 = HeartsRoom(delay=0)
r4.clients = []
r4.players = {1: m1, 2: m2}
r4.start_game()
r4.handle_restart(m1)
check("restart vote recorded", r4.restart_votes[1] and not r4.restart_votes[2])
r4.handle_restart(m2)
check("restart resets scores", r4.scores == {"NS": 0, "EW": 0} and r4.hand_number == 1,
      (r4.scores, r4.hand_number))

# 7. AI 换牌返回 3 张
hand = [C(r, s) for s in range(4) for r in (2, 14, 12)]  # 含黑桃Q
chosen = ai_choose_pass(hand)
check("AI passes 3 cards", len(chosen) == 3 and all(c in hand for c in chosen))
check("AI passes queen of spades", C(12, 3) in chosen, chosen)

# 8. 单人模式：一名人类 + 三台电脑，个人计分
solo = HeartsRoom(mode="solo", delay=0)
ms = MockConn(1)
solo.clients = []
solo.players = {1: ms}
solo.on_join()
check("solo starts on single join", solo.phase == "pass" and solo.hand_number == 1, solo.phase)
check("solo human seat N", solo.human_seats == (0,))
check("solo AI seats E/S/W", solo.ai_seats == (1, 2, 3))
check("solo 3 AI pass-ready", all(solo.pass_ready[s] for s in (1, 2, 3)))
check("solo human hand 13", len(solo.hands[0]) == 13)

solo.handle_pass(ms, {"cards": solo.hands[0][:3]})
check("solo play phase after human pass", solo.phase == "play", solo.phase)
guard = 0
while solo.phase == "play" and guard < 300:
    guard += 1
    seat = solo.turn
    card = ai_choose_play(solo, seat)
    if card is None:
        break
    solo._play_card(seat, card)
check("solo hand finished", solo.hand_number >= 2 or solo.over, solo.phase)
check("solo last hand per-seat", solo.last_hand_scores is not None and "N" in solo.last_hand_scores,
      solo.last_hand_scores)
if solo.last_hand_scores:
    total = sum(solo.last_hand_scores[n] for n in ("N", "E", "S", "W"))
    check("solo hand total 26", total == 26, solo.last_hand_scores)

# 9. 单人模式计分：全收个人计分 / 结束判定
r5 = HeartsRoom(mode="solo", delay=0)
r5.clients = []
r5.players = {1: MockConn(1)}
r5.hand_points = [0, 0, 0, 26]  # W 全收
r5.scores = {"N": 10, "E": 20, "S": 30, "W": 40}
r5._end_hand()
check("solo moon scoring", r5.scores == {"N": 36, "E": 46, "S": 56, "W": 40}, r5.scores)

r6 = HeartsRoom(mode="solo", delay=0)
r6.clients = []
r6.players = {1: MockConn(1)}
r6.hand_points = [5, 0, 0, 0]
r6.scores = {"N": 95, "E": 80, "S": 60, "W": 50}
r6._end_hand()
check("solo game over", r6.over and r6.winner == "W", (r6.scores, r6.winner))

# 10. 单人模式重新开始（单名玩家确认即可）
r7 = HeartsRoom(mode="solo", delay=0)
r7.clients = []
r7.players = {1: MockConn(1)}
r7.start_game()
r7.handle_restart(MockConn(1))
check("solo restart resets", r7.scores == {"N": 0, "E": 0, "S": 0, "W": 0} and r7.hand_number == 1,
      (r7.scores, r7.hand_number))

print("-" * 32)
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
