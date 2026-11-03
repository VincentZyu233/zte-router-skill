# ZTE Router Skill (`zte-router-skill`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9+-brightgreen.svg)](https://www.python.org/)
[![ZTE: ZXSLC](https://img.shields.io/badge/Architecture-ZXSLC%20Firmware-orange.svg)](references/api_spec.md)

中兴智能路由器（基于中兴自研芯片与 **ZXSLC** 固件架构）自动化运维、资产探测与网络拓扑构建的 Agent Skill 工具库。

> [!WARNING]
> **作者实测机型免责声明 (Works on my machine!)**
>
> <p align="center">
>   <img src="docs/images/works-on-my-machine.png" alt="Works on my machine" width="220" />
> </p>
>
> 本项目**仅证明在作者本人的具体路由器机型与当前固件版本上实测可用**（*“Works on my machine!”* 🤷‍♂️）：
> - **作者实测路由器型号**：**中兴 巡天青春版 AX1500**（内部硬件标识：`ZXSLC SR6001`）
> - **核心 CPU 主控芯片**：中兴自研双核 `ZX279128R`
> - **实测固件软件版本**：`V1.0.0.3B3.8000`（硬件版本：`V1.0.0`）
>
> **不保证其他任何中兴路由器型号或不同固件版本能正常工作！** 厂商随时可能在系统更新或其他机型中调整 WebUI 加密哈希逻辑、修改 `_sessionTOKEN` 校验机制或重构接口字段。除上述明确列出的机型外，其他型号概不承诺兼容性，请使用者自行实测验证。

---

## 🌟 核心特性

- ⚡ **无界面纯自动化**：告别浏览器手动登录，直接通过两阶段动态盐值算法 (`SHA256(Password + dynamic_logintoken)`) 完成身份认证。
- 🔍 **全量资产秒级发现**：直接调取路由器底层 `localnet_lan_info_lua` 终端表，瞬间获取局域网所有设备的**真实系统主机名**、IP、MAC 地址以及接入端口（有线千兆 / 2.4G / 5G Wi-Fi）。
- 📊 **网络拓扑与硬件规格萃取**：精准获取路由器内部型号（如 `ZXSLC SR6001`）、市场型号、CPU 架构、固件版本、连续运行时间与 WAN 上行链路拓扑。
- 🤖 **Agent 原生友好**：内置标准 Antigravity [SKILL.md](SKILL.md) 规范，支持命令行 CLI、Python SDK 以及结构化 JSON 输出，天然适配各类 AI Coding Agent 自动化调用。

---

## 📡 支持与实测机型 (Supported Hardware)

本工具库基于中兴智能路由器统一的 **ZXSLC WebUI 协议栈**，适用于搭载中兴自研芯片（如双核 ZX279128R 等）的系列路由器：

| 系列 | 涵盖型号 | 兼容状态 |
|:---|:---|:---:|
| **中兴巡天系列** | 巡天青春版 AX1500 (`SR6001`) | 🟢 **实机实测通过** |
| **中兴巡天系列** | 巡天 AX3000 / AX3000 Pro | 🟢 理论完全兼容 |
| **中兴晴天系列** | 晴天 AX3000 / 晴天 PoGo | 🟢 理论完全兼容 |
| **中兴问天系列** | AX5400 / AX5400 Pro / BE7200 | 🟢 理论完全兼容 |
| **电信/联通定制版** | E2621 / E2631 / E3630 等 | 🟢 理论完全兼容 |

---

## 🚀 快速上手 (Quickstart)

> [!TIP]
> **先决条件：请先安装 `uv`**
> 本项目全面采用高性能 Python 工具链 [`uv`](https://github.com/astral-sh/uv)。在运行以下命令前，请确保环境中已安装 `uv`：
> ```bash
> # Windows (PowerShell)
> powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
>
> # Linux / macOS
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```

### 1. 依赖安装

使用 `uv pip` 快速安装依赖：
```bash
uv pip install requests
```

### 2. 命令行使用 (CLI)

```bash
# 环境变量传入密码或命令行 -p 传入
export ZTE_ROUTER_PASSWORD="your_password_here"

# 1. 查看路由器硬件信息与连续开机时间
uv run python scripts/zte_client.py --info

# 2. 列出局域网内所有连接的主机终端（在线状态、MAC、真实主机名）
uv run python scripts/zte_client.py --devices

# 3. 输出结构化 JSON 数据供脚本与管道二次解析
uv run python scripts/zte_client.py --all --json
```

---

### 3. Python SDK 集成

```python
from scripts.zte_client import ZTERouterClient

client = ZTERouterClient(host="192.168.31.1", password="your_password")
client.login()

# 获取设备规格
info = client.get_device_info()
print(f"设备型号: {info['alias_name']} ({info['model_name']})")
print(f"运行时间: {info['uptime_human']}")

# 获取局域网终端
devices = client.get_connected_devices()
for dev in devices:
    if dev["active"]:
        print(f"在线设备: {dev['ip']:15} | {dev['mac']:17} | {dev['hostname']}")
```

---

## 📚 目录结构

```text
zte-router-skill/
├── .gitattributes          # 强制配置 Markdown 语言统计识别
├── .gitignore              # Python / OS 临时文件过滤
├── LICENSE                 # MIT 开源许可证
├── README.md               # 仓库详尽技术文档
├── SKILL.md                # Agent Skill 标准规范定义
├── scripts/
│   └── zte_client.py       # Python 客户端类与全功能 CLI 入口
└── references/
    └── api_spec.md         # 逆向梳理的 ZXSLC 固件 API 接口规范
```

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。
