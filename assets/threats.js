/* 五子棋威胁检测：活三 / 冲四（纯函数，浏览器与 Node 均可使用）。
 *
 * 返回 [{ type: "three" | "four", cells: [[r, c], ...] }, ...]
 *
 * 判定规则（简化版，用于连线提示）：
 * - 活三：恰好连续 3 子、两端为空，且在其中一端落子能形成"活四"；
 *   连续的"跳活三"（如 ●●_●）暂不识别。
 * - 冲四：任意连续 5 格窗口内恰好有 4 枚同色棋子 + 1 个空位
 *   （覆盖：连续四、跳四 ●_●●●、活四），去重后返回这些棋子坐标。
 * - 已经连成 5 子以上的线段不会出现在对局中（游戏已结束），调用方可跳过本检测。
 */
(function (root) {
  "use strict";

  var DIRS = [[1, 0], [0, 1], [1, 1], [1, -1]];

  function findThreats(board, size) {
    var S = size || board.length;
    var found = [];
    var seen = {};

    function add(type, cells) {
      var key = type + ":" + cells.map(function (p) { return p[0] + "," + p[1]; }).join("|");
      if (seen[key]) return;
      seen[key] = true;
      found.push({ type: type, cells: cells });
    }

    function emptyAt(r, c) {
      return r >= 0 && r < S && c >= 0 && c < S && board[r][c] === 0;
    }

    var r, c, i, k, dr, dc, rr, cc, v, cells;

    // 1) 活三：连续 3 子，两端为空，且一端落子后能成活四
    for (r = 0; r < S; r++) {
      for (c = 0; c < S; c++) {
        v = board[r][c];
        if (!v) continue;
        for (i = 0; i < DIRS.length; i++) {
          dr = DIRS[i][0];
          dc = DIRS[i][1];
          // 只从连续段的起点开始处理（前一格若是同色则跳过）
          var pr = r - dr, pc = c - dc;
          if (pr >= 0 && pr < S && pc >= 0 && pc < S && board[pr][pc] === v) {
            continue;
          }
          cells = [[r, c]];
          rr = r + dr;
          cc = c + dc;
          while (rr >= 0 && rr < S && cc >= 0 && cc < S && board[rr][cc] === v) {
            cells.push([rr, cc]);
            rr += dr;
            cc += dc;
          }
          if (cells.length !== 3) continue;

          var Lr = r - dr, Lc = c - dc;          // 左端外一格
          var Rr = rr, Rc = cc;                  // 右端外一格
          var L0r = r - 2 * dr, L0c = c - 2 * dc; // 左端外两格
          var R0r = rr + dr, R0c = cc + dc;       // 右端外两格

          var openL = emptyAt(Lr, Lc);
          var openR = emptyAt(Rr, Rc);
          // 左端落子成四后，两端为 L0 和 R；右端落子成四后，两端为 L 和 R0
          var canOpenFour = (openL && openR) && (emptyAt(L0r, L0c) || emptyAt(R0r, R0c));
          if (canOpenFour) add("three", cells);
        }
      }
    }

    // 2) 冲四：任意 5 格窗口 = 4 枚同色 + 1 空
    for (r = 0; r < S; r++) {
      for (c = 0; c < S; c++) {
        for (i = 0; i < DIRS.length; i++) {
          dr = DIRS[i][0];
          dc = DIRS[i][1];
          var er = r + dr * 4;
          var ec = c + dc * 4;
          if (er < 0 || er >= S || ec < 0 || ec >= S) continue;

          var color = 0;
          var stones = 0;
          var empty = 0;
          var ok = true;
          for (k = 0; k < 5; k++) {
            v = board[r + dr * k][c + dc * k];
            if (v === 0) {
              empty++;
            } else if (color === 0 || v === color) {
              color = v;
              stones++;
            } else {
              ok = false;
              break;
            }
          }
          if (!ok || stones !== 4 || empty !== 1) continue;

          cells = [];
          for (k = 0; k < 5; k++) {
            rr = r + dr * k;
            cc = c + dc * k;
            if (board[rr][cc] !== 0) cells.push([rr, cc]);
          }
          add("four", cells);
        }
      }
    }

    return found;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { findThreats: findThreats };
  }
  root.findThreats = findThreats;
})(typeof globalThis !== "undefined" ? globalThis : this);
