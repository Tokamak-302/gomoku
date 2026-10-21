/* 临时本地 CONNECT 代理：把 github.com:443 隧道到一组可达 IP 中的第一个可用者。
 * 仅本次推送使用，不改系统 hosts / git 配置。
 * 用法：node _push_proxy.js 140.82.112.3 140.82.114.3 ...
 */
"use strict";
const net = require("net");

const IPS = process.argv.slice(2);
const PORT = 18080;

const server = net.createServer(function (client) {
  client.on("error", function () { /* 忽略 */ });
  client.once("data", function (chunk) {
    const head = chunk.toString("latin1");
    if (!head.startsWith("CONNECT")) {
      client.end("HTTP/1.1 400 Bad Request\r\n\r\n");
      return;
    }
    let connected = false;

    function tryNext(index) {
      if (connected) return;
      if (index >= IPS.length) {
        client.destroy();
        return;
      }
      const ip = IPS[index];
      const upstream = net.connect(443, ip, function () {
        connected = true;
        client.write("HTTP/1.1 200 Connection Established\r\n\r\n");
        upstream.pipe(client);
        client.pipe(upstream);
      });
      upstream.setTimeout(6000, function () {
        upstream.destroy();
        tryNext(index + 1);
      });
      upstream.on("error", function () {
        upstream.destroy();
        tryNext(index + 1);
      });
    }

    tryNext(0);
  });
});

server.listen(PORT, "127.0.0.1", function () {
  console.log("proxy listening on 127.0.0.1:" + PORT + " -> " + IPS.join(", "));
});
