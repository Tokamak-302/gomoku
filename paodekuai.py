#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑得快（二人版，防记牌）规则与联机房间（服务端权威）。

规则要点（牌型与斗地主基本一致）：
- 牌库：去掉大小王，共 52 张；发牌前**随机移除 12 张**（防止记牌），
  剩余 40 张由两名玩家各拿 20 张；
- 先手：若红桃 3 未被移除，由持有者先出；否则随机决定先手；
- 先出完手牌者获胜；
- 牌型：单张、对子、三张、三带一、三带二、顺子（≥5 张，不含 2）、
  连对（≥2 对，不含 2）、飞机（≥2 个连续三张，可带 N 或 2N 张单牌）、炸弹；
- 比较：同牌型同长度比点数（2 最大）；炸弹可压任意非炸弹牌型，炸弹之间比点数；
- 出牌后对手过牌，则由最后出牌者重新领出（自由出牌）；
- 简化：不强制「有管必管」，不支持 4 带 X 与王炸（无王）。

卡牌表示：{"r": 3..15, "s": 0..3}（r=11 J、12 Q、13 K、14 A、15 为 2；s 0=♠ 1=♥ 2=♣ 3=♦）。
"""
import copy
import random
import threading

RANK_NAMES = {
    3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10",
    11: "J", 12: "Q", 13: "K", 14: "A", 15: "2",
}
SUIT_NAMES = {0: "♠", 1: "♥", 2: "♣", 3: "♦"}

HAND_SIZE = 20
REMOVED_CARDS = 12  # 52 - 2 * 20，发牌前随机移除


def log(text):
    print(text, flush=True)


def initial_deck():
    """52 张（不含大小王）：3..A 与 2 各 4 张。"""
    deck = []
    for r in range(3, 16):
        for s in range(4):
            deck.append({"r": r, "s": s})
    return deck


def card_str(card):
    return RANK_NAMES.get(card["r"], "?") + SUIT_NAMES.get(card["s"], "?")


def parse_combo(cards):
    """解析牌型；非法返回 None。"""
    if not cards:
        return None
    counts = {}
    for card in cards:
        counts[card["r"]] = counts.get(card["r"], 0) + 1
    n = len(cards)
    ranks = sorted(counts)
    groups = {}
    for r, c in counts.items():
        groups.setdefault(c, []).append(r)

    if n == 1:
        return {"type": "single", "rank": ranks[0], "length": 1}
    if n == 2 and len(ranks) == 1:
        return {"type": "pair", "rank": ranks[0], "length": 2}
    if n == 3 and len(ranks) == 1:
        return {"type": "triple", "rank": ranks[0], "length": 3}
    if n == 4 and len(ranks) == 1:
        return {"type": "bomb", "rank": ranks[0], "length": 4}
    if n == 4 and len(groups.get(3, [])) == 1 and len(groups.get(1, [])) == 1:
        return {"type": "triple1", "rank": groups[3][0], "length": 4}
    if n == 5 and len(groups.get(3, [])) == 1 and len(groups.get(2, [])) == 1:
        return {"type": "triple2", "rank": groups[3][0], "length": 5}

    # 顺子：>=5 张连续单牌，不含 2
    if (n >= 5 and len(ranks) == n and 15 not in counts
            and ranks[-1] - ranks[0] == n - 1):
        return {"type": "straight", "rank": ranks[-1], "length": n}

    # 连对：>=2 对连续对子，不含 2
    if (n >= 4 and n % 2 == 0 and all(counts[r] == 2 for r in ranks)
            and 15 not in counts and ranks[-1] - ranks[0] == len(ranks) - 1):
        return {"type": "pair_straight", "rank": ranks[-1], "length": n // 2}

    # 飞机：>=2 个连续三张，可带 0 / N / 2N 张单牌
    triple_ranks = sorted(r for r in ranks if counts[r] == 3)
    if len(triple_ranks) >= 2:
        if (15 not in triple_ranks
                and triple_ranks[-1] - triple_ranks[0] == len(triple_ranks) - 1):
            k = len(triple_ranks)
            wings = n - 3 * k
            if wings == 0:
                return {"type": "plane", "rank": triple_ranks[-1], "length": k}
            if wings == k:
                return {"type": "plane1", "rank": triple_ranks[-1], "length": k}
            if wings == 2 * k:
                return {"type": "plane2", "rank": triple_ranks[-1], "length": k}
    return None


def beats(new, old):
    """new 是否压过 old。"""
    if new is None or old is None:
        return False
    if new["type"] == "bomb" and old["type"] != "bomb":
        return True
    if old["type"] == "bomb" and new["type"] != "bomb":
        return False
    if new["type"] != old["type"]:
        return False
    if new["length"] != old["length"]:
        return False
    return new["rank"] > old["rank"]


def broadcast_locked(room):
    for client in room.clients:
        if client.alive:
            client.send(room.state_for(client))
    room.clients[:] = [c for c in room.clients if c.alive]


class PaodekuaiRoom:
    """二人跑得快房间。前两个连接为玩家 1/2，其他人观战。"""

    def __init__(self):
        self.lock = threading.RLock()
        self.clients = []
        self.players = {1: None, 2: None}
        self.restart_votes = {1: False, 2: False}
        self.reset(deal=False)

    def reset(self, deal=False):
        self.hands = {1: [], 2: []}
        self.removed_count = REMOVED_CARDS
        self.turn = None
        self.last_play = None  # {"cards": [...], "by": n, "combo": {...}}
        self.passes = 0
        self.started = False
        self.over = False
        self.winner = None
        self.restart_votes = {1: False, 2: False}
        if deal:
            self.deal()

    def deal(self):
        deck = initial_deck()
        random.shuffle(deck)
        # 随机移除 12 张，防止玩家通过记牌推算对手手牌
        self.removed_count = REMOVED_CARDS
        self.hands = {
            1: deck[0:HAND_SIZE],
            2: deck[HAND_SIZE:HAND_SIZE * 2],
        }
        for color in self.hands:
            self.hands[color].sort(key=lambda c: (c["r"], c["s"]))
        self.started = True
        self.over = False
        self.winner = None
        self.last_play = None
        self.passes = 0
        self.turn = self._first_turn()
        log(f"[跑得快] 发牌完成（随机移除 {REMOVED_CARDS} 张），先手为玩家{self.turn}")

    def start(self):
        self.deal()

    def _first_turn(self):
        for color in (1, 2):
            for card in self.hands[color]:
                if card["r"] == 3 and card["s"] == 1:  # 红桃 3
                    return color
        return random.choice((1, 2))

    def on_join(self):
        if (all(self.players[i] is not None for i in (1, 2))
                and (not self.started or self.over)):
            self.start()

    def on_disconnect(self, conn):
        if self.started and not self.over and conn.color in (1, 2):
            self.over = True
            self.winner = 0
            self.last_play = None
            log(f"[跑得快] 玩家{conn.color}离开，对局中断")

    def state_for(self, conn):
        hand = self.hands[conn.color] if conn.color in (1, 2) else []
        return {
            "type": "state",
            "game": "paodekuai",
            "you": conn.color,
            "hand": copy.deepcopy(hand),
            "counts": {str(i): len(self.hands[i]) for i in (1, 2)},
            "turn": self.turn,
            "lastPlay": self.last_play,
            "started": self.started,
            "over": self.over,
            "winner": self.winner,
            "removedCount": self.removed_count,
            "players": {
                "1": self.players[1] is not None,
                "2": self.players[2] is not None,
            },
            "connected": sum(1 for c in self.players.values() if c is not None),
            "restartVotes": {
                "1": self.restart_votes[1],
                "2": self.restart_votes[2],
            },
        }

    def _next_turn(self, color):
        return 2 if color == 1 else 1

    def _hand_contains(self, color, card):
        return any(c["r"] == card["r"] and c["s"] == card["s"] for c in self.hands[color])

    def handle_play(self, conn, msg):
        if conn.color not in (1, 2):
            conn.send({"type": "error", "message": "观众不能出牌"})
            return
        if not self.started:
            conn.send({"type": "error", "message": "对局还没开始，等待两名玩家到齐"})
            return
        if self.over:
            conn.send({"type": "error", "message": "本局已结束，请重新开始"})
            return
        if conn.color != self.turn:
            conn.send({"type": "error", "message": "还没轮到你出牌"})
            return
        cards = msg.get("cards")
        if not isinstance(cards, list) or not cards:
            conn.send({"type": "error", "message": "请选择要出的牌"})
            return
        normalized = []
        for card in cards:
            if not (isinstance(card, dict)
                    and isinstance(card.get("r"), int)
                    and isinstance(card.get("s"), int)):
                conn.send({"type": "error", "message": "牌数据格式错误"})
                return
            normalized.append({"r": card["r"], "s": card["s"]})
        seen = set()
        for card in normalized:
            key = (card["r"], card["s"])
            if key in seen or not self._hand_contains(conn.color, card):
                conn.send({"type": "error", "message": "手牌中没有这些牌"})
                return
            seen.add(key)

        combo = parse_combo(normalized)
        if combo is None:
            conn.send({"type": "error", "message": "牌型不合法"})
            return
        if self.last_play is not None and not beats(combo, self.last_play["combo"]):
            conn.send({"type": "error", "message": "出的牌压不过上家"})
            return

        for card in normalized:
            self.hands[conn.color].remove(card)
        conn.send({"type": "played", "cards": normalized, "combo": combo})

        if not self.hands[conn.color]:
            self.over = True
            self.winner = conn.color
            self.last_play = {"cards": normalized, "by": conn.color, "combo": combo}
            log(f"[跑得快] 玩家{conn.color}出完手牌，获胜")
            broadcast_locked(self)
            return

        self.last_play = {"cards": normalized, "by": conn.color, "combo": combo}
        self.passes = 0
        self.turn = self._next_turn(conn.color)
        log(f"[跑得快] 玩家{conn.color}出牌 {[card_str(c) for c in normalized]}")
        broadcast_locked(self)

    def handle_pass(self, conn):
        if conn.color not in (1, 2):
            conn.send({"type": "error", "message": "观众不能操作"})
            return
        if not self.started:
            conn.send({"type": "error", "message": "对局还没开始"})
            return
        if self.over:
            conn.send({"type": "error", "message": "本局已结束"})
            return
        if conn.color != self.turn:
            conn.send({"type": "error", "message": "还没轮到你"})
            return
        if self.last_play is None:
            conn.send({"type": "error", "message": "本轮由你领出，不能过牌"})
            return

        self.passes += 1
        if self.passes >= 1:  # 二人局：对手过牌即回合结束
            self.turn = self.last_play["by"]
            self.last_play = None
            self.passes = 0
            log(f"[跑得快] 对手过牌，由玩家{self.turn}重新领出")
        else:
            self.turn = self._next_turn(conn.color)
            log(f"[跑得快] 玩家{conn.color}过牌")
        broadcast_locked(self)

    def handle_restart(self, conn):
        if conn.color not in (1, 2):
            conn.send({"type": "error", "message": "观众不能重新开始"})
            return
        if any(self.players[i] is None for i in (1, 2)):
            conn.send({"type": "error", "message": "需要两名玩家都在线才能重新开始"})
            return
        color = conn.color
        if self.restart_votes[color]:
            self.restart_votes[color] = False
            log(f"[跑得快] 玩家{color}取消了重新开始")
            broadcast_locked(self)
            return
        self.restart_votes[color] = True
        log(f"[跑得快] 玩家{color}请求重新开始")
        if all(self.restart_votes[i] for i in (1, 2)):
            self.reset(deal=True)
            log("[跑得快] 双方确认，重新发牌")
        broadcast_locked(self)
