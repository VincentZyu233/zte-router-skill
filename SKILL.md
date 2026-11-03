---
name: zte-router
description: Autonomous discovery, inspection, and administration for ZTE Smart Routers running the ZXSLC firmware architecture (巡天 AX3000 / 巡天青春版 AX1500 / 晴天 / 问天 / E-series). Use when the user asks to inspect ZTE router status, discover connected LAN/Wi-Fi devices and hostnames, query WAN uplink and gateway topology, test router connectivity, or automate home/office network operations without manual WebUI clicks.
metadata:
  author: Vincent Zyu & gemini-code-assist
  version: "1.0.0"
---

# ZTE Smart Router (ZXSLC Architecture) Skill

`zte-router` is an agent skill for non-interactive discovery, hardware inspection, and device tracking across ZTE smart routers running the `ZXSLC` WebUI stack (powered by ZTE in-house ZX279128 family processors).

> [!WARNING]
> **实机验证与兼容性范围 (Works on my machine!)**
> 本 Skill 仅在作者自用的具体路由器与固件上实测通过：
> - **实测设备**：中兴 巡天青春版 AX1500 (`ZXSLC SR6001`)
> - **实测 CPU**：中兴自研双核 ZX279128R
> - **实测固件**：`V1.0.0.3B3.8000` (硬件版本: `V1.0.0`)
> 
> *不保证其他中兴路由器型号或更新后的固件版本可用。*

---

## 适用于哪些场景 (When to Use)

- **路由器信息探测**：查询中兴路由器实际型号、CPU 芯片、固件版本、连续运行时间。
- **局域网资产盘点**：无需漫长的 ARP/ICMP 探测，直接从路由器内部调取所有已连接设备清单（含精确系统主机名、IP、MAC、有线/Wi-Fi 分频段）。
- **网络拓扑构建**：自动提取 WAN 网关、上行跳数、内网网段，为网络实验、虚拟仿真或路由策略提供实机真实数据支撑。
- **故障排查**：检查设备是否在线、离线历史与链路协商速率。

---

## 认证协议要点 (Authentication Workflow)

1. 请求 `GET /?_type=loginsceneData&_tag=login_token_json` 获取一次性动态挑战盐 `logintoken` 与 `_sessionToken`。
2. 计算加盐哈希：`hash = SHA256(password + logintoken)`。
3. 提交表单 `POST /?_type=loginData&_tag=login_entry`，附带 `_sessionTOKEN` 与头部 `x_xsrf_token`。
4. 获得会话维持 Cookie 与刷新凭证 `sess_token`。

---

## 快速调用命令 (CLI Usage)

> [!TIP]
> 推荐通过 `uv` 工具链直接运行（无需激活外部虚拟环境）：`uv run python ...`。

```bash
# 查看路由器规格与系统运行时间
uv run python scripts/zte_client.py -p "<ROUTER_PASSWORD>" --info

# 导出当前在线与历史设备清单
uv run python scripts/zte_client.py -p "<ROUTER_PASSWORD>" --devices

# 输出结构化 JSON 数据供上层程序或 Agent 管道解析
uv run python scripts/zte_client.py -p "<ROUTER_PASSWORD>" --all --json
```

---

## 模块清单

- `scripts/zte_client.py`: 完整的 Python 客户端类 `ZTERouterClient` 与开箱即用的命令行工具。
- `references/api_spec.md`: 逆向整理的完整 ZXSLC 固件接口文档与 XML 节点字典。
