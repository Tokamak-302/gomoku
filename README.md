# 棋类对战 · 联机版（五子棋 + 中国象棋 + 跑得快 + 红心大战，Python，零依赖）

单端口服务：同一个端口同时提供页面和 WebSocket 联机，后端只用 Python 标准库，
**不需要安装任何第三方包**。打开开始界面选择「五子棋」「中国象棋」「跑得快」「红心大战」或
「红心大战 · 单人」，两人组局后自动进入对局（红心大战为两名人类 N/S 组队 vs 两名电脑 E/W；
单人红心为 1 名人类 + 3 台电脑，个人计分，用于测试 AI 强度）。
已适配 Render 免费层（自动读取平台注入的 `PORT`，监听 `0.0.0.0`）。

## 文件

| 文件 | 作用 |
|---|---|
| `server.py` | HTTP 页面 + WebSocket 联机服务 + 五子棋逻辑 + 多游戏房间路由（服务端权威） |
| `index.html` | 开始界面（大厅）：最多 2 名玩家（显示 n/2）、选择玩法；按所需人数组局后进入对局 |
| `gomoku.html` | 五子棋对局页（Canvas 棋盘、威胁提示、音效、悔棋虚影） |
| `xiangqi.html` | 中国象棋对局页（Canvas 棋盘、合法落点高亮、悔棋、双方确认重开） |
| `xiangqi.py` | 中国象棋规则与房间（走子/将军/将死判定，服务端权威） |
| `paodekuai.html` | 跑得快对局页（手牌选牌、出牌/过牌、两家牌数、音效） |
| `paodekuai.py` | 跑得快规则与房间（52 张随机移除 12 张、每人 20 张，服务端权威） |
| `hearts.html` | 红心大战对局页（四人座位、换牌、收墩、比分；双人组队与单人共用，`?solo=1` 为单人） |
| `hearts.py` | 红心大战规则、电脑 AI 与房间（52 张、四人；duo 组队计分 / solo 个人计分） |
| `assets/sounds/` | 落子 / 胜利音效（Kenney CC0）与自制的提示音（threat.wav、check.wav） |
| `assets/threats.js` | 五子棋活三 / 冲四威胁检测（纯函数，前端与单测共用） |
| `test_client.py` | 联机自测客户端（五子棋 + 象棋 + 跑得快 + 红心大战），可测本机或线上地址 |
| `xiangqi_rules_test.py` | 中国象棋规则单元测试（马腿、炮架、飞将、将死等） |
| `paodekuai_rules_test.py` | 跑得快规则单元测试（牌型、比较、出牌/过牌、发牌、重开） |
| `hearts_rules_test.py` | 红心大战规则 / AI / 房间单元测试（换牌、收墩、全收、组队计分、单人计分） |
| `requirements.txt` | 空依赖声明（供 Render 构建步骤使用） |
| `render.yaml` | Render Blueprint 配置，可一键按此部署 |
| `README.md` | 本说明 |

## 本机运行

Windows 上 `python` 可能是 Microsoft Store 的占位命令（会静默失败），请用 `py -3`：

```powershell
py -3 gomoku/server.py

# 浏览器打开 http://127.0.0.1:8000
# 在开始界面选择玩法（对局玩法均为 2 人；单人红心大战选中即开局）；多开窗口访问同一地址即可联机
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

# 跑得快规则单测（不需要服务器）
py -3 gomoku/paodekuai_rules_test.py

# 红心大战规则 / AI 单测（不需要服务器）
py -3 gomoku/hearts_rules_test.py

# 前端页面冒烟测试（用 DOM 桩执行各页脚本，捕获运行时错误）
node gomoku/frontend_smoke_test.js

# 象棋前端交互回归（模拟点击选马/走子，覆盖翻转视角与马腿挡子）
node gomoku/xiangqi_interact_test.js
```

联机自测覆盖：开始界面与四个游戏页可访问、五子棋黑白分配/非法落子/五连/悔棋虚影/双方确认重开、
中国象棋加入分色/合法走法查询/走子/悔棋仅限自己/双方确认重开换边、
跑得快两人到齐发牌（每人 20 张、随机移除 12 张）/出牌与过牌流转/非当前玩家被拒/双方确认重新发牌、
红心大战换牌、出牌与电脑自动接管、非当前玩家被拒、整手结算；
单人红心大战经大厅选中即开局、1 人 + 3 电脑换牌/出牌/电脑自动接管；大厅最多 2 人（第三名连接为观众，不能选玩法）、选玩法与开局流程、
断线重连（同一 client_id 接管原座位而不是变成观众）。

## 断线重连与心跳

- 每个浏览器标签页在 `sessionStorage` 里生成一个 `client_id`，`join` 时随消息发送；
- 网络波动导致 WebSocket 断开后，页面会自动重连，并用同一 `client_id` **接管原来的座位**，棋局/牌局状态保留，不会变成观众；
- 客户端每 10 秒发送一次应用层 ping，超过 25 秒收不到服务器任何消息会主动断开并重连；
- 服务端每 15 秒发送一次 WebSocket ping（浏览器自动回 pong），45 秒无响应则判定死连接、断开并释放座位，避免僵尸连接占座；
- 断开连接的收尾只释放「仍然属于自己的座位」，已被新连接接管的座位不会被误清。

## 进入对局流程（大厅）

1. 玩家打开窗口访问本站，开始界面显示「已连接玩家：n/2」；**大厅最多 2 名玩家**，第三名及以后连接为观众（不能选择玩法）；
2. 一方选择玩法后，其他玩家界面提示「另一位玩家想玩五子棋 / 中国象棋 / 跑得快 / 红心大战」（自己选择的卡片显示黄色实线框，对方选择的卡片显示黄色虚线框）；
3. 对局玩法为 **2 人**：两名玩家都选择了同一种玩法后自动进入对应游戏界面；单人红心（所需 1 人）选中即开局；选择不同则提示统一玩法；
4. 游戏中点击「← 选择玩法」返回大厅后，仍在游戏中的玩家会看到「另一位玩家已离开五子棋 / 象棋 / 跑得快 / 红心大战」。

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
跑得快使用落子音与胜利音。
红心大战使用落子音与胜利音。

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

## 跑得快（二人版 · 防记牌）

牌型与斗地主基本一致：

- 牌库：去掉大小王，共 **52 张**；发牌前**随机移除 12 张**（防止玩家记牌推算对手手牌），
  剩余 40 张由两名玩家各拿 **20 张**；
- 先手：红桃 3 未被移除时由持有者先出，否则随机决定先手；
- **先出完手牌者获胜**；
- 牌型：单张、对子、三张、三带一、三带二、顺子（≥5 张，不含 2）、连对（≥2 对，不含 2）、
  飞机（≥2 个连续三张，可带 N 或 2N 张单牌）、炸弹；
- 比较：同牌型同长度比点数（2 最大）；炸弹可压任意非炸弹牌型，炸弹之间比点数；
- 出牌后对手过牌，则由最后出牌者重新领出；
- 操作：点击手牌选牌（再点取消）→ 点「出牌」；选择「过牌」放弃本轮；双方确认后重新发牌；
- 简化：不强制「有管必管」，不支持 4 带 X 与王炸（无王）。

## 红心大战（四人 · 双人组队 / 单人 vs 电脑）

座位顺时针 N → E → S → W，两种模式共用同一套牌局引擎：

- **双人组队**（「红心大战」）：N / S 为两名人类（队友，蓝队），E / W 为电脑（红队）；
- **单人**（「红心大战 · 单人」）：仅 N 为人类，E / S / W 为电脑；**个人计分**，先到 100 分结束、分最低者胜，用于测试 AI 强度；
- 52 张牌，每人 13 张；换牌方向按手数循环：左 → 右 → 对家 → 不换（每手人类选 3 张，电脑 AI 自动选）；
- 必须跟花色，没有该花色时可出任意牌；首墩必须领出 ♣2，且首墩不能出红心或黑桃 Q；
- 红心未「破」前不能主动领出红心（跟牌时可以出，即破）；
- 红心每张 1 分、黑桃 Q 13 分，一手共 26 分；一家收齐 26 分「全收」：该家本手 0 分，其他人各 +26；
- 双人组队按队累计得分（N+S 一队、E+W 一队）；单人按个人累计得分；先到 100 分结束；
- 电脑 AI：换牌优先换走黑桃 Q 与大牌；出牌尽量不赢带分墩、缺门时把危险牌垫给对手、
  领出优先短花色小牌；双人模式下会区分队友/对手，单人模式下所有人都是对手；
  整体与 Windows 自带红心大战 AI 相当或略强；
- 操作：换牌阶段选 3 张点「换牌」；出牌阶段点击高亮（可出）的牌再点「出牌」；对局结束后可再来一局。

## 联机协议

WebSocket 建立后，客户端需先发送「加入游戏」消息，再发送对局消息：

```json
{ "type": "join", "game": "lobby", "client_id": "c-abc123" }
{ "type": "join", "game": "gomoku", "client_id": "c-abc123" }
{ "type": "join", "game": "xiangqi" }
{ "type": "join", "game": "paodekuai" }
{ "type": "join", "game": "hearts" }
{ "type": "join", "game": "hearts_solo" }
```

`client_id` 可选：带相同值的重连会接管该房间中原连接占用的座位（断线重连）；不带则按普通新连接分配座位。

**大厅（开始界面）**：

```json
{ "type": "select", "game": "gomoku" }
{ "type": "select", "game": "xiangqi" }
{ "type": "select", "game": "paodekuai" }
{ "type": "select", "game": "hearts" }
{ "type": "select", "game": "hearts_solo" }
```

`select` 再次发送相同玩法 = 取消选择。服务端 → 客户端：`lobby_state`（`connected` 人数、`needs` 各玩法所需人数、`selections` 选择、`players` 是否在线）、
`start`（`game`，所需人数选择相同玩法后下发，客户端据此跳转到游戏页；`hearts_solo` 所需 1 人，选中即开局）、`notice`（额外玩家提示）。

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

**跑得快**：

```json
{ "type": "play", "cards": [{"r": 5, "s": 0}, {"r": 5, "s": 1}] }
{ "type": "pass" }
{ "type": "restart" }
{ "type": "ping" }
```

牌编码：`r` 3..15（14=A，15=2），`s` 0=♠ 1=♥ 2=♣ 3=♦。

**红心大战**：

```json
{ "type": "pass", "cards": [{"r": 2, "s": 0}, {"r": 12, "s": 3}, {"r": 14, "s": 1}] }
{ "type": "play", "card": {"r": 5, "s": 2} }
{ "type": "restart" }
{ "type": "ping" }
```

牌编码：`r` 2..14（11=J，12=Q，13=K，14=A），`s` 0=♣ 1=♦ 2=♥ 3=♠。

服务端 → 客户端：

- `hello`：`{ "type": "hello", "color": 1|2|3|0, "game": "gomoku"|"xiangqi"|"paodekuai"|"hearts"|"hearts_solo" }`
- `state`：完整状态快照
  - 五子棋字段：`board`（15×15 数字）、`current`、`over`、`winner`、`line`、`lastMove`、`you`、
    `players`（black/white）、`connected`、`restartVotes`、`undoGhost`、`canUndo`
  - 象棋字段：`board`（10×9 棋子编码/空）、`turn`、`over`、`winner`、`lastMove`（`{from,to}` 或 null）、`inCheck`（轮到走棋的一方是否被将军）、
    `you`、`players`（red/black）、`connected`、`restartVotes`、`canUndo`
  - 跑得快字段：`hand`（自己的手牌）、`counts`（两家牌数）、`turn`、`lastPlay`（`{cards,by,combo}` 或 null）、`started`、
    `over`、`winner`（1/2，0 为中断）、`removedCount`（本局随机移除张数）、`you`、`players`、`connected`、`restartVotes`
  - 红心大战字段：`mode`（duo 双人组队 / solo 单人）、`you`（座位 0=N/2=S，观众为 null）、`phase`（idle/pass/play/over）、`hand`（自己手牌）、`counts`（四家张数）、
    `trick`（本墩 `{seat,card}` 列表）、`turn`、`legal`（轮到自己的可出牌）、`heartsBroken`、`firstTrick`、
    `passDirection`（left/right/across/keep）、`passReady`、`scores`（duo: NS/EW；solo: N/E/S/W）、`handPoints`、`lastHandScores`、
    `over`、`winner`（duo: NS/EW；solo: 座位名 N/E/S/W）、`players`（N/S 是否在线）、`connected`、`restartVotes`
- `legal`（仅象棋，仅发给请求者）：`{ "type": "legal", "from": [r,c], "moves": [[r,c], ...], "captures": {"r,c": "敌方棋子编码"}, "captureBy": {"r,c": [[er,ec], ...]} }`；
  `captures` 标出可吃子的目标位置，`captureBy` 表示走子到该位置后、下一步可能反吃的敌方棋子
- `undo`：撤销事件（`color` 为被撤销的一方；五子棋附带 `row`/`col`，象棋附带 `from`/`to`）
- `played`（跑得快）：出牌成功回执（`cards` 与 `combo`）
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
