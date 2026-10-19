/* 前端页面冒烟测试：用 Node + DOM 桩执行各页内联脚本，捕获运行时错误。
 * 用法：node gomoku/frontend_smoke_test.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

const PAGES = ["index.html", "gomoku.html", "xiangqi.html", "paodekuai.html"];

function makeCtx() {
  const grad = { addColorStop: function () {} };
  return {
    createLinearGradient: function () { return grad; },
    createRadialGradient: function () { return grad; },
    fillRect: function () {}, clearRect: function () {}, strokeRect: function () {},
    beginPath: function () {}, closePath: function () {},
    moveTo: function () {}, lineTo: function () {}, bezierCurveTo: function () {},
    arc: function () {}, fill: function () {}, stroke: function () {},
    save: function () {}, restore: function () {}, scale: function () {},
    setLineDash: function () {}, fillText: function () {}, strokeText: function () {},
    measureText: function () { return { width: 10 }; }
  };
}

function makeEl(tag) {
  const el = {
    tag: tag,
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
    addEventListener: function () {},
    appendChild: function () {},
    querySelector: function () { return makeEl("span"); },
    getContext: function () { return makeCtx(); },
    getBoundingClientRect: function () { return { left: 0, top: 0, width: 540, height: 600 }; }
  };
  return el;
}

function runPage(page) {
  const file = path.join(__dirname, page);
  const html = fs.readFileSync(file, "utf8");
  const m = html.match(/<script>\s*"use strict";([\s\S]*?)<\/script>/);
  if (!m) return { ok: false, error: "找不到内联脚本" };
  const code = m[1];

  const elements = {};
  const documentStub = {
    getElementById: function (id) {
      if (!elements[id]) elements[id] = makeEl("div#" + id);
      return elements[id];
    },
    createElement: function (tag) { return makeEl(tag); }
  };
  const sandbox = {
    document: documentStub,
    window: { setTimeout: setTimeout, clearTimeout: clearTimeout, devicePixelRatio: 1 },
    location: { protocol: "http:", host: "127.0.0.1:8000", hostname: "127.0.0.1", port: "8000" },
    Audio: function () {
      return { preload: "", currentTime: 0, play: function () { return { catch: function () {} }; } };
    },
    WebSocket: function () {
      this.readyState = 0;
      this.send = function () {};
      this.close = function () {};
    },
    console: console,
    JSON: JSON,
    Object: Object,
    Math: Math,
    Number: Number,
    String: String,
    Array: Array,
    Set: Set,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    requestAnimationFrame: function (fn) { return setTimeout(fn, 0); }
  };
  sandbox.WebSocket.OPEN = 1;
  sandbox.WebSocket.CLOSED = 3;

  try {
    const vm = require("vm");
    // 模拟浏览器先加载页面引用的外部脚本（五子棋页依赖 assets/threats.js）
    if (page === "gomoku.html") {
      const threats = fs.readFileSync(path.join(__dirname, "assets", "threats.js"), "utf8");
      vm.runInNewContext(threats, sandbox, { filename: "assets/threats.js", timeout: 5000 });
    }
    vm.runInNewContext(code, sandbox, { filename: page, timeout: 5000 });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: String(err && err.message ? err.message : err) };
  }
}

let failed = 0;
for (const page of PAGES) {
  const result = runPage(page);
  if (result.ok) {
    console.log("PASS", page);
  } else {
    failed += 1;
    console.log("FAIL", page, "->", result.error);
  }
}
process.exit(failed ? 1 : 0);
