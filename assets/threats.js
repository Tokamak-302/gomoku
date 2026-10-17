/* 五子棋威胁检测：活三 / 冲四（纯函数，浏览器与 Node 均可使用）。
 *
 * 返回 [{ type: "three" | "four", cells: [[r, c], ...] }, ...]
 *
 * 判定规则（简化版，用于连线提示）：
 * - 活三：连续 3 子两端为空且能在其中一端落子形成"活四"；
 *   另有跳活三：4 格窗口内 3 子同色 + 1 个中间空位（如 ●●_●、●_●●），
 *   补上空位后成四连，且两侧外端为空；
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

    // 1.5) 跳活三：4 格窗口内 3 子同色 + 1 个中间空位（●●_● / ●_●●），
    //      补上空位后形成四连，且窗口两端外侧为空（能成活四）
    for (r = 0; r < S; r++) {
      for (c = 0; c < S; c++) {
        for (i = 0; i < DIRS.length; i++) {
          dr = DIRS[i][0];
          dc = DIRS[i][1];
          var er3 = r + dr * 3;
          var ec3 = c + dc * 3;
          if (er3 < 0 || er3 >= S || ec3 < 0 || ec3 >= S) continue;

          var color3 = 0;
          var stones3 = [];
          var emptyIdx = -1;
          var ok3 = true;
          for (k = 0; k < 4; k++) {
            v = board[r + dr * k][c + dc * k];
            if (v === 0) {
              if (emptyIdx !== -1) {
                ok3 = false;
                break;
              }
              emptyIdx = k;
            } else if (color3 === 0 || v === color3) {
              color3 = v;
              stones3.push([r + dr * k, c + dc * k]);
            } else {
              ok3 = false;
              break;
            }
          }
          if (!ok3 || stones3.length !== 3) continue;
          // 空位必须位于窗口中间（索引 1 或 2），两端各有一颗子
          if (emptyIdx !== 1 && emptyIdx !== 2) continue;
          // 补上空位后成四连子，需要两端外侧都为空才算活三
          if (emptyAt(r - dr, c - dc) && emptyAt(r + dr * 4, c + dc * 4)) {
            add("three", stones3);
          }
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
