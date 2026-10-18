# 棋类对战 · 联机版（五子棋 + 中国象棋，Python，零依赖）

单端口服务：同一个端口同时提供页面和 WebSocket 联机，后端只用 Python 标准库，
**不需要安装任何第三方包**。打开开始界面选择「五子棋」或「中国象棋」，两个窗口即可联机对弈。
已适配 Render 免费层（自动读取平台注入的 `PORT`，监听 `0.0.0.0`）。

## 文件

| 文件 | 作用 |
|---|---|
| `server.py` | HTTP 页面 + WebSocket 联机服务 + 五子棋逻辑 + 多游戏房间路由（服务端权威） |
| `index.html` | 开始界面（大厅）：显示已连接玩家、选择玩法；双方选择相同玩法后进入对局 |
| `gomoku.html` | 五子棋对局页（Canvas 棋盘、威胁提示、音效、悔棋虚影） |
| `xiangqi.html` | 中国象棋对局页（Canvas 棋盘、合法落点高亮、悔棋、双方确认重开） |
| `xiangqi.py` | 中国象棋规则与房间（走子/将军/将死判定，服务端权威） |
| `assets/sounds/` | 落子 / 胜利音效（Kenney CC0）与自制的威胁提示音 `threat.wav` |
| `assets/threats.js` | 五子棋活三 / 冲四威胁检测（纯函数，前端与单测共用） |
| `test_client.py` | 联机自测客户端（五子棋 + 中国象棋），可测本机或线上地址 |
| `xiangqi_rules_test.py` | 中国象棋规则单元测试（马腿、炮架、飞将、将死等） |
| `requirements.txt` | 空依赖声明（供 Render 构建步骤使用） |
| `render.yaml` | Render Blueprint 配置，可一键按此部署 |
| `README.md` | 本说明 |

## 本机运行

Windows 上 `python` 可能是 Microsoft Store 的占位命令（会静默失败），请用 `py -3`：

```powershell
py -3 gomoku/server.py

# 浏览器打开 http://127.0.0.1:8000
# 在开始界面选择「五子棋」或「中国象棋」；再开一个窗口访问同一地址即可联机对弈
```

端口默认 8000，可用环境变量 `PORT` 覆盖（如 `$env:PORT=8080; py -3 gomoku/server.py`）。

## 自动测试

```powershell
# 联机自测（先启动服务器；本机）
py -3 gomoku/test_client.py

# 线上地址（部署完成后，验证公网联通性与完整对局逻辑）
py -3 gomoku/test_client.py --url https://你的应用.onrender.com

# 中国象棋规则单测（不需要服务器）
py -3 gomoku/xiangqi_rules_test.py
```

联机自测覆盖：开始界面与两个游戏页可访问、五子棋黑白分配/非法落子/五连/悔棋虚影/双方确认重开、
中国象棋加入分色/合法走法查询/走子/悔棋仅限自己/双方确认重开换边、大厅选玩法与开局流程。

## 进入对局流程（大厅）

1. 两名玩家各打开一个窗口访问本站，开始界面显示「已连接玩家：n/2」；
2. 一方选择玩法后，另一方界面提示「另一位玩家想玩五子棋 / 中国象棋」（自己选择的卡片显示黄色实线框，对方选择的卡片显示黄色虚线框）；
3. **双方选择同一种玩法后**，两人自动进入对应游戏界面；若选择不同则提示统一玩法；
4. 游戏中点击「← 选择玩法」返回大厅后，仍在游戏中的另一方会看到「另一位玩家已离开五子棋 / 象棋」。

## 音效

（浏览器直接播放 `.ogg`，拦截自动播放时静默忽略）

| 场景 | 文件 | 来源 |
|---|---|---|
| 落子 | `assets/sounds/place.ogg` | [Kenney Interface Sounds](https://kenney.nl/assets/interface-sounds)（drop_002） |
| 活三/冲四提示（仅五子棋） | `assets/sounds/threat.wav` | 本项目自制合成音（A5→D6 两声清脆铃铛，模仿"钓鱼上钩"的提示感，零版权风险） |
| 将军提示（仅象棋） | `assets/sounds/check.wav` | 本项目自制合成音（A6→E6→C6 三音下行，短促警示感，零版权风险） |
| 胜利 | `assets/sounds/win.ogg` | [Kenney Music Jingles](https://kenney.nl/assets/music-jingles)（jingles_STEEL01，钢鼓风格更欢快；仅获胜方播放） |

两个 Kenney 素材包均为 **CC0 1.0（公有领域）**，可自由商用、无需署名；`threat.wav` 为本项目合成的原创音效。
中国象棋使用落子音、胜利音与将军提示音（`check.wav`，无威胁提示）。

> 版权说明：《星露谷》的「上钩了」音效属于游戏版权素材，不能直接提取并放入公开仓库/线上站点使用。
> 若你想本地自用替换，可把获得授权的音频命名为 `threat.wav` 替换即可。

## 五子棋

- 15×15 棋盘，自由规则（无禁手），黑先，横竖斜任意方向连五即胜；
- 单房间：前两个连接为黑/白，之后为观众；
- 活三 / 冲四连线提示（蓝色粗虚线 / 橙色粗实线，绘制在棋子上方并向两端外延半格），
  新形成威胁时播放提示音并弹出「🎣 上钩了！」文字动画；
- 重新开始：需**双方都点击确认**后才重开并交换黑白；先点击的一方等待对方确认（再点一次可取消）；
- 悔棋：只能撤销**自己**刚下的一手；被悔掉的棋子位置以虚影标记，直到下一手落下。

## 中国象棋

- 9×10 棋盘，红方先行；将死对方（或对方无任何合法走法）即胜；
- 服务端校验全部规则：马（蹩马腿）、象/相（塞象眼、不过河）、炮（必须隔一子吃子）、
  兵/卒（过河后可横走、不可后退）、士/仕与将/帅（九宫限制）、将帅不可照面（飞将）；
- 操作：点击己方棋子（棋子会向上浮起突出显示）→ 服务端返回合法落点（绿点＝走子，红圈＝可吃）→ 点击目标位置落子；
  鼠标悬停在合法落点上时提示点放大，并标出下一步可能反吃该位置的敌方棋子（橙色虚线环）；
- 视角：**黑方玩家自动翻转棋盘**，使黑方棋子始终在下方；红方与观众默认红方在下；
- 选择马 / 象时，用紫色虚线环标出正在「硌马腿」/「蹩象眼」的挡子；
- 任何一方被将军时，播放提示音并弹出「⚔️ 将军了！」文字动画，状态栏同步提示；
- 悔棋：只能悔自己刚下的一手（恢复被吃的棋子与轮次）；重新开始：双方确认后交换红黑。

## 联机协议

WebSocket 建立后，客户端需先发送「加入游戏」消息，再发送对局消息：

```json
{ "type": "join", "game": "lobby" }
{ "type": "join", "game": "gomoku" }
{ "type": "join", "game": "xiangqi" }
```

**大厅（开始界面）**：

```json
{ "type": "select", "game": "gomoku" }
{ "type": "select", "game": "xiangqi" }
```

`select` 再次发送相同玩法 = 取消选择。服务端 → 客户端：`lobby_state`（`connected` 人数、`selections` 双方选择、`players` 是否在线）、
`start`（`game`，双方选择相同玩法后下发，客户端据此跳转到游戏页）。

**五子棋**：

```json
{ "type": "move", "row": 7, "col": 7 }
{ "type": "restart" }
{ "type": "undo" }
{ "type": "ping" }
```

**中国象棋**：

```json
{ "type": "move", "from": [6, 0], "to": [5, 0] }
{ "type": "legal", "from": [9, 1] }
{ "type": "restart" }
{ "type": "undo" }
{ "type": "ping" }
```

服务端 → 客户端：

- `hello`：`{ "type": "hello", "color": 1|2|0, "game": "gomoku"|"xiangqi" }`
- `state`：完整状态快照
  - 五子棋字段：`board`（15×15 数字）、`current`、`over`、`winner`、`line`、`lastMove`、`you`、
    `players`（black/white）、`connected`、`restartVotes`、`undoGhost`、`canUndo`
  - 象棋字段：`board`（10×9 棋子编码/空）、`turn`、`over`、`winner`、`lastMove`（`{from,to}` 或 null）、`inCheck`（轮到走棋的一方是否被将军）、
    `you`、`players`（red/black）、`connected`、`restartVotes`、`canUndo`
- `legal`（仅象棋，仅发给请求者）：`{ "type": "legal", "from": [r,c], "moves": [[r,c], ...], "captures": {"r,c": "敌方棋子编码"}, "captureBy": {"r,c": [[er,ec], ...]} }`；
  `captures` 标出可吃子的目标位置，`captureBy` 表示走子到该位置后、下一步可能反吃的敌方棋子
- `undo`：撤销事件（`color` 为被撤销的一方；五子棋附带 `row`/`col`，象棋附带 `from`/`to`）
- `error`、`pong`

棋子编码：红方大写 `R N B A K C P`，黑方小写 `r n b a k c p`，空位为 `null`。

## 部署到 Render 免费层

前置：仓库根目录包含 `server.py`、`index.html`、`requirements.txt`、`render.yaml`。

**方式一（推荐，一键）**：Render 控制台 → **New +** → **Blueprint** → 选择本仓库 →
Render 读取 `render.yaml`，按免费计划创建 Web Service。

**方式二（手动）**：Render 控制台 → **New +** → **Web Service** → 选择仓库，配置：

| 配置项 | 值 |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python server.py` |
| Health Check Path | `/` |
| Instance Type | Free |

无需手动设置端口：Render 注入 `PORT`，程序自动监听 `0.0.0.0:$PORT`。

免费层注意：

- 空闲约 15 分钟会休眠，再次访问需 30–60 秒冷启动（页面右上角会显示连接状态）；
- 免费实例性能较低，但棋类对局完全够用；
- 服务空闲时 WebSocket 消息可让它保持活跃。

部署完成后用 `py -3 test_client.py --url https://你的地址` 做线上验证。

## 局域网试玩（可选）

本机默认只监听 `127.0.0.1`。想在同一 Wi-Fi 用手机玩，启动时设置 `$env:HOST="0.0.0.0"`，
再访问 `http://<本机局域网 IP>:8000`（Windows 防火墙需允许 Python）。

## 环境备注

- `python` 命令指向 Microsoft Store 占位别名时退出码为 9009，请使用 `py -3`；
- `gomoku/.tmp` 是早期 pip 安装失败残留的、被 Windows 权限锁住的空目录，与本项目代码无关，
  可忽略（`.gitignore` 已排除），需要时用管理员权限删除即可。
