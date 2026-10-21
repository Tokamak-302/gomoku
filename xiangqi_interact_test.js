/* 象棋前端交互回归测试：用 Node + DOM 桩执行 xiangqi.html 的内联脚本，
 * 模拟「点击选子 → 服务端返回合法落点 → 点击落点走子」的完整交互。
 *
 * 覆盖：红方 / 黑方翻转视角 / 马腿被挡 / 马或象的目标格上有棋子 / 全方向被挡。
 * 用法：node gomoku/xiangqi_interact_test.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const testFile = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(__dirname, "xiangqi.html");
const html = fs.readFileSync(testFile, "utf8");
const m = html.match(/<script>\s*"use strict";([\s\S]*?)<\/script>/);
if (!m) {
  console.log("找不到内联脚本");
  process.exit(1);
}
const code = m[1];

const sent = [];
const handlers = {};

function makeCtx() {
  const grad = { addColorStop: function () {} };
  const noop = function () {};
  return new Proxy({}, {
    get: function (target, key) {
      if (key === "createLinearGradient" || key === "createRadialGradient") {
        return function () { return grad; };
      }
      if (key === "measureText") return function () { return { width: 10 }; };
      return noop;
    },
    set: function () { return true; }
  });
}

function makeEl(id) {
  return {
    id: id,
    className: "",
    innerHTML: "",
    textContent: "",
    width: 640,
    height: 640,
    dataset: {},
    style: {},
    classList: {
      toggle: function () {}, add: function () {}, remove: function () {},
      contains: function () { return false; }
    },
    addEventListener: function (name, fn) { handlers[id + ":" + name] = fn; },
    appendChild: function () {},
    querySelector: function () { return makeEl("span"); },
    getContext: function () { return makeCtx(); },
    getBoundingClientRect: function () { return { left: 0, top: 0, width: 540, height: 600 }; }
  };
}

const elements = {};
function getEl(id) {
  if (!elements[id]) elements[id] = makeEl(id);
  return elements[id];
}

let wsInstance = null;
function FakeWebSocket() {
  wsInstance = this;
  this.readyState = 1;
  this.onopen = null;
  this.onmessage = null;
  this.onclose = null;
  this.onerror = null;
  this.send = function (data) { sent.push(JSON.parse(data)); };
  this.close = function () {};
}
FakeWebSocket.OPEN = 1;
FakeWebSocket.CLOSED = 3;

const sandbox = {
  document: {
    getElementById: getEl,
    createElement: function (tag) { return makeEl(tag); }
  },
  window: { setTimeout: setTimeout, clearTimeout: clearTimeout, devicePixelRatio: 1 },
  location: { protocol: "http:", host: "127.0.0.1:8000", hostname: "127.0.0.1", port: "8000" },
  Audio: function () {
    return { preload: "", currentTime: 0, play: function () { return { catch: function () {} }; } };
  },
  WebSocket: FakeWebSocket,
  console: console,
  JSON: JSON, Object: Object, Math: Math, Number: Number, String: String,
  Array: Array, Set: Set, setTimeout: setTimeout, clearTimeout: clearTimeout,
  setInterval: setInterval, clearInterval: clearInterval
};

vm.runInNewContext(code + "\n;globalThis.__sel = function(){ return selected; };", sandbox, { filename: "xiangqi.html", timeout: 5000 });
wsInstance.onopen();

let failures = 0;
function check(name, cond, detail) {
  if (cond) {
    console.log("PASS", name);
  } else {
    failures += 1;
    console.log("FAIL", name, detail === undefined ? "" : detail);
  }
}

function click(dispR, dispC) {
  const fn = handlers["board:click"];
  if (!fn) throw new Error("找不到 board 的 click 监听");
  fn({ clientX: 30 + 60 * dispC, clientY: 30 + 60 * dispR });
}

function makeBoard(placements) {
  const b = Array.from({ length: 10 }, () => Array(9).fill(null));
  for (const p of placements) b[p[0]][p[1]] = p[2];
  return b;
}

function feedState(board, you, turn) {
  wsInstance.onmessage({
    data: JSON.stringify({
      type: "state", game: "xiangqi", board: board, turn: turn, over: false,
      winner: null, lastMove: null, inCheck: false, you: you,
      players: { red: true, black: true }, connected: 2,
      restartVotes: { red: false, black: false }, canUndo: false
    })
  });
}

// 1. 红方：马腿被挡 → 仍可选中并走子
sent.length = 0;
feedState(makeBoard([[9, 4, "K"], [0, 4, "k"], [5, 5, "N"], [4, 5, "p"], [5, 6, "P"]]), 1, 1);
click(5, 5);
check("红方：点击蹩马腿的马会请求合法落点", sent.some(function (msg) {
  return msg.type === "legal" && msg.from[0] === 5 && msg.from[1] === 5;
}));
wsInstance.onmessage({ data: JSON.stringify({
  type: "legal", from: [5, 5], moves: [[4, 3], [6, 3], [7, 4], [7, 6]],
  captures: {}, captureBy: {}
}) });
sent.length = 0;
click(4, 3);
check("红方：点击合法落点会走子", sent.some(function (msg) {
  return msg.type === "move" && msg.from[0] === 5 && msg.from[1] === 5
    && msg.to[0] === 4 && msg.to[1] === 3;
}));

// 2. 回归：马的目标格上有棋子（此前 t.isupper() 抛异常导致无法选马）
sent.length = 0;
feedState(makeBoard([[9, 4, "K"], [0, 4, "k"], [5, 5, "N"], [4, 6, "p"], [3, 4, "p"], [6, 4, "P"]]), 1, 1);
click(5, 5);
check("红方：目标格有棋子时仍能选中马（isupper 回归）", sent.some(function (msg) {
  return msg.type === "legal" && msg.from[0] === 5;
}));

// 3. 回归：象的目标格上有棋子
sent.length = 0;
feedState(makeBoard([[9, 4, "K"], [0, 4, "k"], [9, 2, "B"], [7, 0, "p"]]), 1, 1);
click(9, 2);
check("红方：目标格有棋子时仍能选中象（isupper 回归）", sent.some(function (msg) {
  return msg.type === "legal" && msg.from[0] === 9 && msg.from[1] === 2;
}));

// 4. 黑方翻转视角：点击黑马 → 合法落点 → 走子
sent.length = 0;
feedState(makeBoard([[0, 4, "k"], [9, 4, "K"], [3, 2, "n"], [2, 2, "p"]]), 2, 2);
click(9 - 3, 8 - 2);  // 逻辑(3,2) 显示为 (6,6)
check("黑方翻转视角：点击黑马会请求合法落点", sent.some(function (msg) {
  return msg.type === "legal" && msg.from[0] === 3 && msg.from[1] === 2;
}));
wsInstance.onmessage({ data: JSON.stringify({
  type: "legal", from: [3, 2], moves: [[1, 3], [1, 1]], captures: {}, captureBy: {}
}) });
sent.length = 0;
click(9 - 1, 8 - 3);  // 逻辑(1,3) 显示为 (8,5)
check("黑方翻转视角：点击合法落点会走子", sent.some(function (msg) {
  return msg.type === "move" && msg.to[0] === 1 && msg.to[1] === 3;
}));

// 5. 全部方向被挡的马（8 个目标格都被占）→ 仍可选中
sent.length = 0;
feedState(makeBoard([
  [9, 4, "K"], [0, 4, "k"], [5, 5, "N"],
  [4, 5, "p"], [6, 5, "P"], [5, 4, "p"], [5, 6, "P"],
  [3, 4, "p"], [3, 6, "p"], [7, 4, "P"], [7, 6, "P"]
]), 1, 1);
click(5, 5);
check("全方向被挡的马仍能选中", sent.some(function (msg) {
  return msg.type === "legal" && msg.from[0] === 5;
}));

// 6. 没有任何合法走法的棋子也应允许选中（选中状态保留）
sent.length = 0;
feedState(makeBoard([[9, 4, "K"], [0, 4, "k"], [9, 2, "B"], [7, 0, "P"], [7, 4, "P"]]), 1, 1);
click(9, 2);
check("无合法走法的象也能选中（发出 legal）", sent.some(function (msg) {
  return msg.type === "legal" && msg.from[0] === 9 && msg.from[1] === 2;
}));
wsInstance.onmessage({ data: JSON.stringify({
  type: "legal", from: [9, 2], moves: [], captures: {}, captureBy: {}
}) });
check("无合法走法时选中状态保留", !!(sandbox.__sel && sandbox.__sel()));
const statusText = sandbox.document.getElementById("status").textContent;
check("无合法走法时状态栏给出提示", statusText.indexOf("没有可走的位置") >= 0, statusText);

console.log("-".repeat(32));
console.log(failures === 0 ? "全部通过 ✔" : failures + " 项失败");
process.exit(failures ? 1 : 0);
