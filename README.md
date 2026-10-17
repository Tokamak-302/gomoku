# 五子棋 · 联机版（Python，零依赖）

单端口服务：同一个端口同时提供棋盘页面和 WebSocket 联机，后端只用 Python 标准库，
**不需要安装任何第三方包**。已适配 Render 免费层（自动读取平台注入的 `PORT`，监听 `0.0.0.0`）。

## 文件

| 文件 | 作用 |
|---|---|
| `server.py` | HTTP 页面 + WebSocket 联机服务 + 游戏逻辑（服务端权威） |
| `index.html` | Canvas 棋盘前端，浏览器打开即用 |
| `assets/sounds/` | 落子 / 胜利音效（Kenney CC0 素材，浏览器直接播放 .ogg） |
| `assets/threats.js` | 活三 / 冲四威胁检测（纯函数，前端与单测共用） |
| `test_client.py` | 联机自测客户端，可测本机或线上地址 |
| `requirements.txt` | 空依赖声明（供 Render 构建步骤使用） |
| `render.yaml` | Render Blueprint 配置，可一键按此部署 |
| `README.md` | 本说明 |

## 本机运行

Windows 上 `python` 可能是 Microsoft Store 的占位命令（会静默失败），请用 `py -3`：

```powershell
py -3 gomoku/server.py

# 浏览器打开 http://127.0.0.1:8000
# 再开一个窗口访问同一地址，两个窗口即可联机对弈
```

端口默认 8000，可用环境变量 `PORT` 覆盖（如 `$env:PORT=8080; py -3 gomoku/server.py`）。

## 自动联机自测

```powershell
# 本机（先启动服务器）
py -3 gomoku/test_client.py

# 线上地址（部署完成后，验证公网联通性与完整对局逻辑）
py -3 gomoku/test_client.py --url https://你的应用.onrender.com
```

覆盖：页面可访问、黑白分配、非本回合落子被拒、五连胜负判定与连线、重开换边。

## 音效与连线提示

音效（浏览器直接播放 `.ogg`，拦截自动播放时静默忽略）：

| 场景 | 文件 | 来源 |
|---|---|---|
| 落子 | `assets/sounds/place.ogg` | [Kenney Interface Sounds](https://kenney.nl/assets/interface-sounds)（drop_002） |
| 活三/冲四提示 | `assets/sounds/threat.ogg` | [Kenney Interface Sounds](https://kenney.nl/assets/interface-sounds)（confirmation_002） |
| 胜利 | `assets/sounds/win.ogg` | [Kenney Music Jingles](https://kenney.nl/assets/music-jingles)（jingles_STEEL01，钢鼓风格更欢快） |

两个素材包均为 **CC0 1.0（公有领域）**，可自由商用、无需署名。

棋盘提示（对局进行中）：

- **活三**：蓝色粗虚线连接三颗棋子（连续 3 子、两端空，且一端落子可成"活四"）；
- **冲四**：橙色粗实线连接四颗棋子（任意 5 格窗口内 4 枚同色 + 1 空，含跳四、活四）；
- 连线绘制在棋子上方、带深色衬底，并向两端各延伸半格，便于一眼识别；
- 任意一方落子**新形成**活三或冲四时，播放统一的提示音（threat.ogg）；
- **胜利**：金色粗线连接连成五子的棋子。

说明：跳活三（如 ●●_●）暂不提示；活四按冲四的橙色线条提示。

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
- 免费实例性能较低，但对五子棋完全够用；
- 服务空闲时 WebSocket 消息可让它保持活跃。

部署完成后用 `py -3 test_client.py --url https://你的地址` 做线上验证。

## 游戏规则与协议

- 15×15 棋盘，自由规则（无禁手），黑先，横竖斜任意方向连五即胜；
- 单房间：前两个连接为黑/白，之后为观众；任意一方点「重新开始」即换边重开。

客户端 → 服务端（WebSocket JSON）：

```json
{ "type": "move", "row": 7, "col": 7 }
{ "type": "restart" }
{ "type": "ping" }
```

服务端 → 客户端：`hello`（分到角色）、`state`（完整快照）、`error`、`pong`。
`state` 字段：`board`、`current`、`over`、`winner`、`line`、`lastMove`、`you`、`players`、`connected`。

## 局域网试玩（可选）

本机默认只监听 `127.0.0.1`。想在同一 Wi-Fi 用手机玩，启动时设置 `$env:HOST="0.0.0.0"`，
再访问 `http://<本机局域网 IP>:8000`（Windows 防火墙需允许 Python）。

## 环境备注

- `python` 命令指向 Microsoft Store 占位别名时退出码为 9009，请使用 `py -3`；
- `gomoku/.tmp` 是早期 pip 安装失败残留的、被 Windows 权限锁住的空目录，与本项目代码无关，
  可忽略（`.gitignore` 已排除），需要时用管理员权限删除即可。
