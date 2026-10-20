#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""红心大战（四人）规则、AI 与联机房间（服务端权威）。

座位（顺时针）：N(0) → E(1) → S(2) → W(3)。支持两种模式：
- duo（双人组队）：N / S 为两名人类（颜色 1 / 2），E / W 为电脑；
  N+S「蓝队」对 E+W「红队」，按队累计得分，先到 100 分结束，分低者胜；
- solo（单人）：仅 N 为人类（颜色 1），E / S / W 为电脑；个人计分，先到 100 分结束，分最低者胜。

规则：每手 13 张；换牌方向按局循环：左 → 右 → 对家 → 不换；
红心每张 1 分，黑桃 Q 13 分；一家收齐 26 分「全收」：该家 0 分，其他人各 +26；
首墩必须领出 ♣2，且首墩不能出红心或黑桃 Q；红心未「破」之前不能主动领出红心；
必须跟花色，没有该花色时可出任意牌（受首墩限制）。

卡牌表示 {"r": 2..14, "s": 0..3}：r 11=J 12=Q 13=K 14=A；s 0=♣ 1=♦ 2=♥ 3=♠。
"""
import copy
import random
import threading
import time

SEAT_NAMES = ["N", "E", "S", "W"]
TEAM_OF = {0: "NS", 1: "EW", 2: "NS", 3: "EW"}
PASS_DIRECTIONS = ["left", "right", "across", "keep"]
RANK_NAMES = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10",
    11: "J", 12: "Q", 13: "K", 14: "A",
}
SUIT_NAMES = {0: "♣", 1: "♦", 2: "♥", 3: "♠"}


def log(text):
    print(text, flush=True)


def card_str(card):
    return RANK_NAMES.get(card["r"], "?") + SUIT_NAMES.get(card["s"], "?")


def is_queen_spades(card):
    return card["s"] == 3 and card["r"] == 12


def initial_deck():
    deck = []
    for s in range(4):
        for r in range(2, 15):
            deck.append({"r": r, "s": s})
    return deck


def trick_winner(trick):
    """trick: [{"seat": i, "card": c}, ...]；返回赢家座位。"""
    led = trick[0]["card"]["s"]
    best_seat = None
    best_rank = -1
    for play in trick:
        card = play["card"]
        if card["s"] == led and card["r"] > best_rank:
            best_rank = card["r"]
            best_seat = play["seat"]
    return best_seat


def trick_points(trick):
    pts = 0
    for play in trick:
        card = play["card"]
        if card["s"] == 2:
            pts += 1
        elif is_queen_spades(card):
            pts += 13
    return pts


def seat_of_color(color):
    if color == 1:
        return 0
    if color == 2:
        return 2
    return None


def broadcast_locked(room):
    for client in room.clients:
        if client.alive:
            client.send(room.state_for(client))
    room.clients[:] = [c for c in room.clients if c.alive]


# ---------------------------------------------------------------------------
# 电脑 AI（目标：与 Windows 自带红心大战 AI 相当或略强）
# ---------------------------------------------------------------------------
def ai_choose_pass(hand):
    """换牌：把最危险的 3 张换走（黑桃 Q 权重最高，其次大牌/红心）。"""
    def danger(card):
        score = card["r"]
        if is_queen_spades(card):
            score += 20
        if card["s"] == 2:
            score += 1
        return score

    return sorted(hand, key=danger, reverse=True)[:3]


def same_team(room, a, b):
    """duo 模式下 N/S、E/W 为队友；solo 模式下所有人都是对手。"""
    if getattr(room, "mode", "duo") != "duo":
        return False
    return TEAM_OF[a] == TEAM_OF[b]


def ai_choose_play(room, seat):
    """返回要出的牌（调用方保证轮次与合法性）。"""
    legal = room.legal_plays(seat)
    if not legal:
        return None
    hand = room.hands[seat]
    trick = room.trick

    if trick:
        led = trick[0]["card"]["s"]
        points = sum(1 for play in trick if play["card"]["s"] == 2)
        if any(is_queen_spades(play["card"]) for play in trick):
            points += 13

        def winner_after(extra):
            plays = list(trick)
            if extra is not None:
                plays.append({"seat": extra[0], "card": extra[1]})
            led = plays[0]["card"]["s"]
            best = None
            best_rank = -1
            for play in plays:
                c = play["card"]
                if c["s"] == led and c["r"] > best_rank:
                    best_rank = c["r"]
                    best = play["seat"]
            return best

        follow = [c for c in legal if c["s"] == led]
        if follow:
            options = [(c, winner_after((seat, c))) for c in follow]

            def rank_option(item):
                card, winner = item
                if winner != seat:
                    return (0, -card["r"])  # 不赢：顺便把大牌垫掉
                if points > 0:
                    return (2, card["r"])   # 会吃到分：尽量避免
                return (1, card["r"])       # 无分可赢：用小牌赢

            options.sort(key=rank_option)
            return options[0][0]

        # 该花色已缺，无法赢下这墩
        winner = winner_after(None)
        opponent_wins = not same_team(room, winner, seat)

        def card_points(card):
            p = 1 if card["s"] == 2 else 0
            if is_queen_spades(card):
                p += 13
            return p

        if opponent_wins:
            return max(legal, key=lambda c: (card_points(c), c["r"]))
        return min(legal, key=lambda c: (card_points(c), -c["r"]))

    # 领出
    if room.first_trick:
        for card in legal:
            if card["r"] == 2 and card["s"] == 0:
                return card
    non_hearts = [c for c in legal if c["s"] != 2]
    pool = non_hearts or legal
    suit_counts = {}
    for card in hand:
        suit_counts[card["s"]] = suit_counts.get(card["s"], 0) + 1
    return min(pool, key=lambda c: (suit_counts.get(c["s"], 0), c["r"]))


# ---------------------------------------------------------------------------
# 房间
# ---------------------------------------------------------------------------
class HeartsRoom:
    """四人红心大战房间：duo = 双人组队；solo = 单人 vs 三台电脑。"""

    def __init__(self, mode="duo", delay=0.25):
        self.lock = threading.RLock()
        self.clients = []
        self.mode = mode
        self.human_colors = (1,) if mode == "solo" else (1, 2)
        self.human_seats = (0,) if mode == "solo" else (0, 2)
        self.ai_seats = tuple(s for s in (1, 2, 3) if s not in self.human_seats)
        self.players = {c: None for c in self.human_colors}
        self.delay = delay
        self.reset()

    # ---------------- 生命周期 ----------------
    def reset(self):
        self.hands = [[], [], [], []]
        if self.mode == "solo":
            self.scores = {name: 0 for name in ("N", "E", "S", "W")}
        else:
            self.scores = {"NS": 0, "EW": 0}
        self.hand_number = 0
        self.phase = "idle"          # idle / pass / play / over
        self.pass_direction = "left"
        self.pass_ready = [False, False, False, False]
        self.pending_pass = [None, None, None, None]
        self.trick = []
        self.last_trick = []
        self.turn = 0
        self.hearts_broken = False
        self.first_trick = True
        self.hand_points = [0, 0, 0, 0]
        self.last_hand_scores = None
        self.over = False
        self.winner = None
        self.restart_votes = {c: False for c in self.human_colors}

    def on_join(self):
        if all(self.players[c] is not None for c in self.human_colors) and self.phase == "idle":
            self.start_game()

    def on_disconnect(self, conn):
        # 有人中途离开：当前对局作废，房间回到等待状态
        if self.phase in ("pass", "play"):
            log("[红心] 有玩家离开，对局作废，等待重新开始")
            self.reset()

    def start_game(self):
        if self.mode == "solo":
            self.scores = {name: 0 for name in ("N", "E", "S", "W")}
        else:
            self.scores = {"NS": 0, "EW": 0}
        self.hand_number = 0
        self.over = False
        self.winner = None
        self.last_hand_scores = None
        self.restart_votes = {c: False for c in self.human_colors}
        self.next_hand()

    # ---------------- 发牌 / 换牌 ----------------
    def next_hand(self):
        self.hand_number += 1
        self.pass_direction = PASS_DIRECTIONS[(self.hand_number - 1) % 4]
        deck = initial_deck()
        random.shuffle(deck)
        self.hands = [deck[i * 13:(i + 1) * 13] for i in range(4)]
        for seat in range(4):
            self.hands[seat].sort(key=lambda c: (c["s"], c["r"]))
        self.hand_points = [0, 0, 0, 0]
        self.trick = []
        self.last_trick = []
        self.hearts_broken = False
        self.first_trick = True
        self.pass_ready = [False, False, False, False]
        self.pending_pass = [None, None, None, None]
        if self.pass_direction == "keep":
            self.phase = "play"
            self.turn = self._leader_seat()
            log(f"[红心] 第 {self.hand_number} 手：不换牌，开始出牌")
        else:
            self.phase = "pass"
            for seat in self.ai_seats:
                self.pending_pass[seat] = ai_choose_pass(self.hands[seat])
                self.pass_ready[seat] = True
            log(f"[红心] 第 {self.hand_number} 手：换牌方向 {self.pass_direction}")

    def _leader_seat(self):
        for seat in range(4):
            for card in self.hands[seat]:
                if card["r"] == 2 and card["s"] == 0:
                    return seat
        return 0

    def _resolve_pass(self):
        direction = self.pass_direction
        if direction == "left":
            targets = {s: (s + 1) % 4 for s in range(4)}
        elif direction == "right":
            targets = {s: (s + 3) % 4 for s in range(4)}
        else:
            targets = {s: (s + 2) % 4 for s in range(4)}
        new_hands = [list(self.hands[s]) for s in range(4)]
        outgoing = {}
        for seat in range(4):
            chosen = self.pending_pass[seat] or []
            outgoing[seat] = chosen
            for card in chosen:
                new_hands[seat].remove({"r": card["r"], "s": card["s"]})
        for seat in range(4):
            for card in outgoing[seat]:
                new_hands[targets[seat]].append(card)
        for seat in range(4):
            new_hands[seat].sort(key=lambda c: (c["s"], c["r"]))
            self.hands[seat] = new_hands[seat]
        self.phase = "play"
        self.pending_pass = [None, None, None, None]
        self.pass_ready = [False, False, False, False]
        self.trick = []
        self.hearts_broken = False
        self.first_trick = True
        self.turn = self._leader_seat()
        log("[红心] 换牌完成，开始出牌（♣2 持有者领出）")

    # ---------------- 出牌合法性 ----------------
    def legal_plays(self, seat):
        hand = self.hands[seat]
        if not hand:
            return []
        if not self.trick:
            if self.first_trick:
                twos = [c for c in hand if c["r"] == 2 and c["s"] == 0]
                if twos:
                    return twos
            if not self.hearts_broken:
                non_hearts = [c for c in hand if c["s"] != 2]
                if non_hearts:
                    return non_hearts
            return list(hand)
        led = self.trick[0]["card"]["s"]
        follow = [c for c in hand if c["s"] == led]
        if follow:
            return follow
        if self.first_trick:
            safe = [c for c in hand
                    if c["s"] != 2 and not is_queen_spades(c)]
            if safe:
                return safe
        return list(hand)

    # ---------------- 出牌 ----------------
    def handle_play(self, conn, msg):
        seat = seat_of_color(conn.color)
        if seat is None:
            conn.send({"type": "error", "message": "观众不能出牌"})
            return
        if self.over:
            conn.send({"type": "error", "message": "本局已结束"})
            return
        if self.phase != "play":
            conn.send({"type": "error", "message": "现在还不能出牌"})
            return
        if seat != self.turn:
            conn.send({"type": "error", "message": "还没轮到你出牌"})
            return
        card = msg.get("card")
        if not (isinstance(card, dict) and isinstance(card.get("r"), int)
                and isinstance(card.get("s"), int)):
            conn.send({"type": "error", "message": "牌数据格式错误"})
            return
        card = {"r": card["r"], "s": card["s"]}
        if card not in self.hands[seat]:
            conn.send({"type": "error", "message": "手牌中没有这张牌"})
            return
        if card not in self.legal_plays(seat):
            conn.send({"type": "error", "message": "这张牌现在不能出"})
            return
        self._play_card(seat, card)
        broadcast_locked(self)
        self._advance_ai()

    def handle_pass(self, conn, msg):
        seat = seat_of_color(conn.color)
        if seat is None:
            conn.send({"type": "error", "message": "观众不能换牌"})
            return
        if self.phase != "pass":
            conn.send({"type": "error", "message": "现在不是换牌阶段"})
            return
        if self.pass_ready[seat]:
            conn.send({"type": "error", "message": "你已经换过牌了"})
            return
        cards = msg.get("cards")
        if not isinstance(cards, list) or len(cards) != 3:
            conn.send({"type": "error", "message": "请选择 3 张牌"})
            return
        normalized = []
        for card in cards:
            if not (isinstance(card, dict) and isinstance(card.get("r"), int)
                    and isinstance(card.get("s"), int)):
                conn.send({"type": "error", "message": "牌数据格式错误"})
                return
            normalized.append({"r": card["r"], "s": card["s"]})
        if len({(c["r"], c["s"]) for c in normalized}) != 3:
            conn.send({"type": "error", "message": "不能重复选择同一张牌"})
            return
        for card in normalized:
            if card not in self.hands[seat]:
                conn.send({"type": "error", "message": "手牌中没有这些牌"})
                return
        self.pending_pass[seat] = normalized
        self.pass_ready[seat] = True
        log(f"[红心] 玩家{SEAT_NAMES[seat]} 已选择换牌")
        if all(self.pass_ready[s] for s in self.human_seats):
            self._resolve_pass()
        broadcast_locked(self)
        self._advance_ai()

    def handle_restart(self, conn):
        if conn.color not in self.human_colors:
            conn.send({"type": "error", "message": "观众不能重新开始"})
            return
        if any(self.players[c] is None for c in self.human_colors):
            conn.send({"type": "error", "message": "需要玩家都在线"})
            return
        color = conn.color
        if self.restart_votes[color]:
            self.restart_votes[color] = False
            log("[红心] 取消重新开始")
            broadcast_locked(self)
            return
        self.restart_votes[color] = True
        log("[红心] 请求重新开始")
        if all(self.restart_votes[c] for c in self.human_colors):
            self.start_game()
            log("[红心] 全员确认，新对局开始")
        broadcast_locked(self)
        self._advance_ai()

    # ---------------- 内部流程 ----------------
    def _play_card(self, seat, card):
        self.hands[seat].remove({"r": card["r"], "s": card["s"]})
        self.trick.append({"seat": seat, "card": card})
        if card["s"] == 2:
            self.hearts_broken = True
        if len(self.trick) == 4:
            winner = trick_winner(self.trick)
            self.hand_points[winner] += trick_points(self.trick)
            self.last_trick = list(self.trick)
            self.trick = []
            self.turn = winner
            self.first_trick = False
            if all(not hand for hand in self.hands):
                self._end_hand()
        else:
            self.turn = (seat + 1) % 4

    def _end_hand(self):
        moon = next((s for s in range(4) if self.hand_points[s] == 26), None)
        if self.mode == "solo":
            hand_scores = {}
            for seat in range(4):
                name = SEAT_NAMES[seat]
                if moon is not None:
                    hand_scores[name] = 0 if seat == moon else 26
                else:
                    hand_scores[name] = self.hand_points[seat]
                self.scores[name] += hand_scores[name]
            self.last_hand_scores = dict(hand_scores)
            self.last_hand_scores["moon"] = SEAT_NAMES[moon] if moon is not None else None
            log("[红心] 第 %d 手结束（单人）：%s" % (self.hand_number, hand_scores))
            if max(self.scores.values()) >= 100:
                self.over = True
                self.phase = "over"
                low = min(self.scores.values())
                winners = [name for name, val in self.scores.items() if val == low]
                self.winner = winners[0] if len(winners) == 1 else None
                log(f"[红心] 对局结束：{self.scores}，胜者 {self.winner}")
            else:
                self.next_hand()
            return

        ns_points = self.hand_points[0] + self.hand_points[2]
        ew_points = self.hand_points[1] + self.hand_points[3]
        if moon is not None:
            if TEAM_OF[moon] == "NS":
                ns_points, ew_points = 0, 26
            else:
                ns_points, ew_points = 26, 0
        self.scores["NS"] += ns_points
        self.scores["EW"] += ew_points
        self.last_hand_scores = {
            "NS": ns_points,
            "EW": ew_points,
            "moon": SEAT_NAMES[moon] if moon is not None else None,
        }
        log(f"[红心] 第 {self.hand_number} 手结束：蓝队 +{ns_points}，红队 +{ew_points}")
        if max(self.scores.values()) >= 100:
            self.over = True
            self.phase = "over"
            if self.scores["NS"] < self.scores["EW"]:
                self.winner = "NS"
            elif self.scores["EW"] < self.scores["NS"]:
                self.winner = "EW"
            else:
                self.winner = None
            log(f"[红心] 对局结束：{self.scores}")
        else:
            self.next_hand()

    def _advance_ai(self):
        while self.phase == "play" and not self.over and self.turn in self.ai_seats:
            if self.delay:
                time.sleep(self.delay)
            card = ai_choose_play(self, self.turn)
            if card is None:
                break
            seat = self.turn
            self._play_card(seat, card)
            log(f"[红心] 电脑{SEAT_NAMES[seat]}出牌 {card_str(card)}")
            broadcast_locked(self)

    # ---------------- 状态快照 ----------------
    def state_for(self, conn):
        seat = seat_of_color(conn.color)
        hand = copy.deepcopy(self.hands[seat]) if seat is not None else []
        legal = []
        if self.phase == "play" and seat is not None and seat == self.turn:
            legal = copy.deepcopy(self.legal_plays(seat))
        return {
            "type": "state",
            "game": "hearts",
            "mode": self.mode,
            "you": seat,
            "seatName": SEAT_NAMES[seat] if seat is not None else None,
            "phase": self.phase,
            "handNumber": self.hand_number,
            "passDirection": self.pass_direction,
            "passReady": {str(i): self.pass_ready[i] for i in range(4)},
            "hand": hand,
            "counts": {str(i): len(self.hands[i]) for i in range(4)},
            "trick": self.trick,
            "legal": legal,
            "turn": self.turn,
            "heartsBroken": self.hearts_broken,
            "firstTrick": self.first_trick,
            "scores": self.scores,
            "handPoints": {str(i): self.hand_points[i] for i in range(4)},
            "lastHandScores": self.last_hand_scores,
            "over": self.over,
            "winner": self.winner,
            "players": {
                "N": self.players.get(1) is not None,
                "S": self.players.get(2) is not None,
            },
            "connected": sum(1 for c in self.players.values() if c is not None),
            "restartVotes": {str(c): self.restart_votes[c] for c in self.human_colors},
        }
