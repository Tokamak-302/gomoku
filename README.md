# 五子棋 · 本机联机验证版（Python，零依赖）

用于在部署到公网之前，先在本机把「浏览器棋盘 + WebSocket 联机 + 服务端权威规则」跑通。
后端只用 Python 标准库，**不需要安装任何第三方包**。

## 文件

| 文件 | 作用 |
|---|---|
| `server.py` | HTTP 静态服务（8000）+ WebSocket 联机服务（8765）+ 游戏逻辑 |
| `index.html` | Canvas 棋盘前端，浏览器打开即用 |
| `test_client.py` | 联机自测客户端，验证协议与胜负判定 |
| `README.md` | 本说明 |

## 运行

Windows 上 `python` 可能是 Microsoft Store 的占位命令（会静默失败），请用 `py -3`：

```powershell
# 1. 启动服务器（在项目所在的任意目录执行均可）
py -3 gomoku/server.py

# 2. 浏览器打开
#    http://localhost:8000
#    再开一个窗口访问同一地址，两个窗口即可联机对弈

# 3. 想跑自动联机自测（另开一个终端，服务器保持运行）
py -3 gomoku/test_client.py
```

> 若提示端口被占用，先关掉占用进程；端口常量在 `server.py` 顶部（`HTTP_PORT` / `WS_PORT`）。

## 游戏规则（验证版）

- 15×15 棋盘，自由规则（无禁手），**黑先**，横竖斜任意方向连五即胜。
- 单房间：前两个连接分别为黑棋、白棋，之后的连接是观众。
- 服务器权威：轮次、落子合法性、胜负全在服务端判定；客户端只负责显示和发消息。
- 任意一方点「重新开始」即重开一局，并交换黑白。

## 消息协议（JSON over WebSocket）

客户端 → 服务端：

```json
{ "type": "move", "row": 7, "col": 7 }
{ "type": "restart" }
{ "type": "ping" }
```

服务端 → 客户端：

- `hello`：`{ "type": "hello", "color": 1 }`（1 黑 / 2 白 / 0 观众）
- `state`：完整对局快照
  `{ "type": "state", "board": [[...15 行...]], "current": 1, "over": false,
     "winner": null, "line": [], "lastMove": [7,7], "you": 1,
     "players": { "black": true, "white": false }, "connected": 2 }`
- `error`：`{ "type": "error", "message": "还没轮到你" }`
- `pong`：心跳回应

## 本机验证通过项

`test_client.py` 已覆盖：

1. HTTP 棋盘页面可访问；
2. 两个客户端连接、黑/白颜色分配；
3. 非本回合落子被服务端拒绝；
4. 五连胜利判定（含获胜连线坐标）；
5. 「重新开始」清空棋盘并交换黑白。

## 局域网试玩（可选）

把 `server.py` 顶部的 `HOST = "127.0.0.1"` 改成 `"0.0.0.0"`，重启服务器，
然后让同一 Wi-Fi 下的手机/电脑访问 `http://<本机局域网 IP>:8000`。
Windows 防火墙可能弹窗，需允许 Python 通过。

## 下一步（公网联机）

本版本验证通过后，部署公网只需两步：

1. 把 `server.py` 放到支持 WebSocket 的平台（Render / Railway / 云服务器），得到 `wss://...` 地址；
2. 修改 `index.html` 里的 `wsUrl()`，将 `:8765` 换成线上地址；页面本身部署到静态托管（Vercel / Netlify）。

> 说明：早期 pip 安装 `websockets` 失败，`.tmp` 目录里留有一些被 Windows 权限锁住的空目录，
> 与本项目代码无关，可以忽略；如需清理，用管理员权限删除 `gomoku/.tmp` 即可。
