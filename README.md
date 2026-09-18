# Creeper

基于 Python 与 Selenium 的可配置网页采集工具。支持单机采集，也支持由服务器统一分配任务、多个子节点执行并回传结果。

> 1.1.0 提供 `creeper-client`、`creeper-server` 两个应用包；共享依赖 `yunying-creeper-core` 自动安装。以下 PyPI 安装命令适用于版本发布成功之后。尚未发布时，可使用本文的源码安装或本地 wheel 安装方式。

## 功能

- **任务调度**：每个 YAML 站点配置对应一个任务，服务器将其分配给一个空闲节点，每个节点同时处理一个分布式任务。
- **持久队列**：任务状态、执行次数与结果保存到服务器 SQLite；服务器重启后恢复未完成任务。
- **断线恢复**：任务未完成时节点断开，任务重新入队；默认最多分配三次，避免无限重试。
- **结果回传**：节点保留本地结果，同时回传服务器；服务器在同一事务中写入内容并完成任务，拒绝重复或错误归属的结果。
- **采集控制**：浏览器隔离、有界并发、显式等待、有限重试、代理列表、前置点击/输入/滚动操作。
- **字段提取**：XPath、class、tag、CSS、相对子 XPath、target/rel 属性过滤、文本与属性值提取。
- **结果控制台**：中文页面、搜索、分页、统计、JSON API，自带页面资源，无需 Node.js。
- **存储**：默认 SQLite；单机/节点可选 MySQL。服务器队列与控制台使用 SQLite。

## 环境要求

- Python **3.10 或更高版本**，Windows、Linux 或 macOS。
- **子节点**安装 Chrome/Chromium；服务器不需要安装浏览器。
- Selenium Manager 在首次采集时查找或下载匹配的 ChromeDriver，首次启动可能需要数分钟和网络访问。离线环境请事先配置匹配的 `chromedriver` 到 `PATH`。
- 子节点需要能够访问服务器 TCP 端口，默认 `11451`。连接由子节点主动发起，服务器通过同一连接下发任务，子节点不需要开放入站端口。

## 快速开始：服务器与子节点

### 1. 安装并启动服务器

建议使用独立虚拟环境及工作目录：

```bash
python -m pip install creeper-server
creeper-server init
creeper-server --host 127.0.0.1 --port 11451
```

`init` 创建 `config.yaml` 和 `config/example.yaml` 示例任务，不覆盖已有配置。默认只监听本机，适用于同机测试。将示例 YAML 改为实际需要采集的站点后再部署。

跨机器部署时，在服务器和所有节点设置同一个 `CREEPER_TOKEN`，服务器绑定可访问的网卡地址：

```powershell
# Windows PowerShell：两端设置相同的随机令牌
$env:CREEPER_TOKEN = "替换为自行生成的随机令牌"
creeper-server --host 0.0.0.0 --port 11451
```

```bash
# Linux/macOS
export CREEPER_TOKEN='替换为自行生成的随机令牌'
creeper-server --host 0.0.0.0 --port 11451
```

令牌可用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成。非本机监听强制要求令牌。该协议为明文 TCP，跨不可信网络时通过 VPN/SSH 隧道传输；不要直接作为公网服务开放。

### 2. 安装并启动子节点

在另一台机器或另一个工作目录中执行：

```bash
python -m pip install creeper-client
creeper-client --server SERVER_IP --port 11451
```

跨机器时先设置与服务器一致的 `CREEPER_TOKEN`。无需下载仓库，也无需在节点复制站点 YAML。客户端会主动连接、保持心跳、接收任务、启动浏览器采集，并把结果回传服务器。增加节点只需在其他机器重复安装和启动客户端。

客户端连接连续失败/中断累计三次后退出，返回非零退出码，便于通过 systemd、容器或服务管理器重启。认证失败立即退出。断线后的旧任务会先被取消和清理，再建立新的任务会话。

### 3. 分配与重复执行任务

服务器从 `config/` 加载 YAML 任务。也可指定目录和数据库：

```bash
creeper-server --tasks-dir ./tasks --database ./data/server.sqlite3
```

服务器每 **5 秒**扫描任务目录，新建或修改配置会形成新任务并分配给空闲节点。未变更且已经执行过的配置不会在重启时自动重复。需要全部重新执行时使用：

```bash
creeper-server --repeat
```

每个启动时的站点配置会创建一次新任务；后续扫描不会再次重复该批任务。删除 YAML 不会删除已入队任务或历史数据。

任务状态：`pending` → `running` → `completed` / `partial-failure` / `failed`。节点断线时 `running` 回到 `pending`，达到三次分配后标记失败。采集字段失败会记录错误并结束该任务，不会无休止重跑整个任务。由于断线重派可能再次访问页面，执行语义为 **至少一次**；同一任务的中心结果只接受一次提交。

一个队列数据库只能由一个调度服务器使用，不支持多个服务器共享数据库进行高可用调度。

### 4. 查看服务器结果

在服务器工作目录另开终端：

```bash
creeper-server dashboard
```

打开 [http://127.0.0.1:5000](http://127.0.0.1:5000)。如使用自定义数据库，两条命令应指定相同文件：

```bash
creeper-server dashboard --database ./data/server.sqlite3 --port 5000
```

控制台只读取数据库，没有公开的任务写入接口。默认监听本机；内置 Flask 服务用于本地查看，不包含多用户登录或生产级 Web 部署配置。

| API | 用途 |
| --- | --- |
| `GET /api/stats` | 内容数量、来源数量、最近采集时间 |
| `GET /api/results?limit=25&offset=0&q=关键词` | 内容/URL/栏目文字搜索及分页；limit 范围 1–200 |
| `GET /api/tasks` | 各任务状态的数量；单机数据库返回空对象 |

新安装且未创建配置文件时，服务器数据库为 `data/server.sqlite3`，客户端数据库为 `data/client.sqlite3`。使用 `--config` 或工作目录的 `config.yaml` 后，以配置中的 `database-path` 为准。日志输出到启动目录下的 `data/creeper.log`，每份最多约 5 MB，保留三份轮转日志。

## 源码安装与本地 wheel 安装

```bash
git clone https://github.com/YunyingTech/Creeper.git
cd Creeper
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py --validate
.\.venv\Scripts\creeper-server.exe --tasks-dir ServerConfig
```

Linux/macOS：

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python main.py --validate
creeper-server --tasks-dir ServerConfig
```

依赖文件以 editable 方式安装三个本地包，保留原来的 `python main.py --mode single|server|client|dashboard` 入口。源码仓库的 `config.yaml` 显式使用 `data/creeper.sqlite3`；独立部署时请使用不同工作目录，避免节点和服务器共用同一结果文件。

如果已经下载 Release 的 wheel 文件，将三个 wheel 放到同一目录，再分别安装所需应用：

```bash
python -m pip install --find-links ./dist creeper-client==1.1.0
# 在服务器环境中执行：
python -m pip install --find-links ./dist creeper-server==1.1.0
```

不需要手动安装共享 core 包，pip 会自动处理。普通第三方依赖仍需要访问包源，完全离线部署时应另外准备依赖 wheel。

## 单机采集与完全本地演示

```bash
creeper-client --single --config-dir config --output data/results.json
```

单机模式最多同时运行 `max_thread` 个站点任务，每个站点拥有独立浏览器。`delay` 是同一站点集合之间及失败重试之间的等待秒数，不是全局请求限速器。成功结果写入数据库；某些任务失败时仍导出成功结果，并返回退出码 `1`。

仓库自带本地测试页面，不必依赖新闻站点当前的页面结构：

```bash
# 终端一，在仓库根目录
python -m http.server 8000 --bind 127.0.0.1 --directory examples/site

# 终端二
creeper-client --single --config-dir examples/sites --output data/example.json
```

分布式演示可将服务器 `--tasks-dir` 设置为 `examples/sites`。示例地址是 `127.0.0.1:8000`，因此服务器、节点和示例页面应在同一台机器；跨机器测试时将 YAML URL 改成节点可访问的 HTTP 地址。

## 站点 YAML

```yaml
name: 本地新闻
url: http://127.0.0.1:8000
pre:
  - id: 1
    type: input
    xpath: "//*[@id='keyword']"
    text: Creeper
  - id: 2
    type: click
    xpath: "//*[@id='reveal']"
collections:
  - name: 新闻文本
    xpath: "//*[@id='news']"
    type: tag
    child: a
  - name: 标题属性
    xpath: "//*[@id='news']//a/@title"
  - name: 可见交互内容
    xpath: "//*[@id='delayed']"
```

`url` 只允许 HTTP/HTTPS；省略协议时补为 HTTPS。`collections` 必须是非空列表，每项必须包含 `name` 和 `xpath`。

| `type` | 作用 | `child` 示例 |
| --- | --- | --- |
| 省略或 `text` | 读取所有 XPath 匹配元素的可见文本 | 不需要 |
| `class` | 在匹配元素内按单一 class 名查找后代 | `headline` |
| `tag` | 按标签查找后代 | `a` |
| `css` | 使用 CSS 选择器查找后代 | `a.headline` |
| `xpath` | 使用相对子 XPath 查找后代 | `.//li/a` |
| `target` | 过滤匹配元素及后代的 target 属性 | `_blank` |
| `rel` | 过滤匹配元素及后代的 rel 属性单词 | `noreferrer` |

`attribute: href` 可改为读取属性值。兼容终结在 `/@title` 或 `//@title` 的旧 XPath 写法。各集合去掉空白文本并按原始顺序去重；不同集合或不同任务之间不进行全局文本去重。找不到有效内容时按配置重试，最终记录失败。

前置操作按 `id` 升序执行：

| `pre.type` | 字段 | 作用 |
| --- | --- | --- |
| `wait` | `seconds`，默认 1 | 等待指定秒数 |
| `click` | `xpath` | 等待可点击后点击 |
| `input` | `xpath`、`text` | 清空输入框后填入文字 |
| `scroll` | `pixels`，默认 600 | 向下滚动指定像素 |

原项目中的数字前置操作只有空分支，没有定义含义，本版本明确拒绝数字类型。配置不会执行任意 Python 或任意 JavaScript；滚动使用固定脚本。

`config/` 和 `ServerConfig/` 中保留了上游新闻网站示例。**配置校验通过只代表格式有效，不保证第三方站点的旧 XPath 仍然有效**，应根据当前页面更新。请遵循目标网站的访问政策及适用规则；本工具不会自动解析 robots.txt。

## 应用配置

可通过 `--config /path/to/config.yaml` 指定配置，省略时读取工作目录中的 `config.yaml`，若不存在则采用内置默认值。YAML 中的相对路径始终相对于该配置文件；CLI 路径参数相对于当前工作目录。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `max_thread` | `2` | 单机最大同时运行的站点浏览器数 |
| `delay` | `1` | 集合间隔及重试间隔，秒 |
| `timeout` | `15` | 元素/内容显式等待，秒 |
| `page-load-timeout` | `45` | 页面加载超时，秒 |
| `max-retries` | `3` | 每个集合总尝试次数 |
| `headless` | `true` | 使用无头 Chrome |
| `config-dir` | `config` | 单机站点目录 |
| `server-config-dir` | `ServerConfig`（初始化生成配置时为 `config`） | 服务器任务目录 |
| `database-backend` | `sqlite` | 节点/单机后端，可选 `mysql` |
| `database-path` | 见上文各运行方式 | SQLite 文件 |
| `mysql-config` | `database.yaml` | 可选 MySQL 配置 |
| `server-ip` / `server-port` | `127.0.0.1` / `11451` | 客户端连接目标 |
| `listen-host` / `listen-port` | `127.0.0.1` / `11451` | 服务器监听地址 |
| `max_connection` | `16` | 最大同时连接数，含未认证连接 |
| `auth-token` | 空字符串 | 可被 `CREEPER_TOKEN` 环境变量覆盖 |
| `dashboard-host` / `dashboard-port` | `127.0.0.1` / `5000` | 结果控制台监听地址 |
| `IP-pool` | `false` | 使用代理池 |
| `IP-pool-list` | `[]` | 代理文本文件列表 |

`auto-start` 与 `received-config-dir` 保留用于旧接口兼容；新版服务器默认主动调度，节点接收完整任务对象，无需配置文件广播。消息上限为 **4 MiB**；超限任务结果保留在节点本地，中心任务记录失败。应将特别大的采集任务拆分成多个站点配置。

代理列表每行一个地址，如 `http://127.0.0.1:7890` 或 `socks5://127.0.0.1:1080`。空行和 `#` 注释被忽略，省略协议时按 HTTP 处理。代理在创建浏览器时配置；不包含代理存活探测、自动封禁切换或验证码处理。

### 可选 MySQL

```bash
python -m pip install 'yunying-creeper-core[mysql]==1.1.0'
```

将节点或单机的 `database-backend` 设为 `mysql`，提供 `mysql-config` 指向的 YAML：

```yaml
mysql:
  host: 127.0.0.1
  port: 3306
  username: creeper
  password: ""
  database: creeper
```

支持 `CREEPER_MYSQL_HOST`、`CREEPER_MYSQL_PORT`、`CREEPER_MYSQL_USER`、`CREEPER_MYSQL_PASSWORD`、`CREEPER_MYSQL_DATABASE` 环境变量覆盖。需先创建数据库并授予写入/建表权限，程序自动创建 `raw_data` 表，内容保存为 JSON 数组。遗留 `creeper_log` / `creeper_config` 辅助写入方法需要调用方已有相应表，不在主采集流程中使用。

服务器任务与中心结果仍保存在 `database-path` 指定的 SQLite 中。MySQL 服务集成需在使用者环境验证；默认测试不连接外部数据库。上游曾提交的远程数据库账号已从当前配置移除；若该账号仍有效，应由维护者撤销或轮换，Git 历史不会因此自动清除。

## 测试与构建

```bash
python -m pip install -r requirements-dev.txt build twine
python -m pytest -q
ruff check .
ruff format --check .
python scripts/build_release.py
```

默认测试不访问外部网站，也不启动 Chrome。覆盖配置、SQLite 迁移和并发写入、浏览器隔离及重试、协议分包、文件路径校验、认证、任务租约与恢复、节点到中心数据库的完整流程、控制台 API 和 CLI。

真实 Chrome 测试仅访问本机测试页面：

```powershell
$env:CREEPER_BROWSER_TESTS = "1"
python -m pytest tests/test_browser_integration.py -q
```

```bash
CREEPER_BROWSER_TESTS=1 python -m pytest tests/test_browser_integration.py -q
```

测试会验证全部提取类型、前置操作、控制台搜索和移动端布局，截图写入 `data/screenshots/`。独立 wheel 安装验证及 PyPI/GitHub Release 流程见 [发布文档](docs/PUBLISHING.md)。

## 项目结构

```text
packages/
  core/       # 配置、浏览器采集、SQLite/MySQL、协议、日志
  client/     # creeper-client CLI、节点连接、任务执行
  server/     # creeper-server CLI、持久队列、调度、控制台及静态资源
config/       # 保留的上游单机站点配置
ServerConfig/ # 保留的上游服务器站点配置
examples/     # 本地 HTML 页面与配套 YAML
tests/        # 单元、协议、分布式、可选浏览器集成测试
scripts/      # 构建与独立安装验证脚本
docs/         # 发布说明与发布操作
main.py       # 源码环境兼容入口
```

顶层 `Creeper/`、`Utils/`、`Logger/`、`Dashboard/` 保留旧导入路径，实际实现位于 `packages/`。上游提交的根目录 `db.sqlite3`、`creeper.log` 不再作为默认运行文件，也不会被打进 Python 包。

## 常见问题

- **找不到 `creeper-client` / `creeper-server` 命令**：确认使用了正确虚拟环境，或运行 `python -m creeper_client.cli` / `python -m creeper_server.cli`。
- **NoSuchDriverException / 无法启动 Chrome**：确认 Chrome 已安装、驱动与浏览器版本匹配，Selenium Manager 可联网；服务器端不需要启动浏览器。
- **连接被拒绝**：检查服务器是否启动、IP/端口、监听地址以及两台机器之间的网络连通性。
- **认证失败**：检查两端 `CREEPER_TOKEN` 是否一致，环境变量会覆盖 YAML 中的 token。
- **没有任务执行**：检查 `/api/tasks`；相同配置若已完成不会自动再次执行，使用 `--repeat` 创建新一轮任务。
- **单个站点失败**：查看日志和配置的选择器；动态加载内容可以增加 `timeout` 或添加明确的前置操作。
- **控制台为空**：确认控制台与服务器指向同一 SQLite 文件；单机采集或节点本地数据库需要显式指定 `--database`。
- **停止速度较慢**：Ctrl+C 会停止新任务并清理已启动浏览器；正在执行的浏览器调用需要等待超时或返回，首次驱动下载也可能较慢。

退出码：`0` 表示正常完成，`1` 表示运行/采集失败，`2` 表示命令行参数错误，`130` 表示 Ctrl+C 中断。

## 许可证

遵循原项目 [GNU GPL v3](LICENSE)。
