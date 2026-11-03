#!/usr/bin/env python3
"""
zte_client.py - ZTE Smart Router (ZXSLC Architecture) Automation Client & CLI

Supports ZTE smart router family powered by ZTE in-house chips (ZX279128R etc.)
and ZXSLC web firmware architecture (巡天 AX3000, 巡天青春版 AX1500, 晴天, 问天, E-series, etc.).
"""

import sys
import os
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import requests

DEFAULT_ROUTER_IP = "192.168.31.1"


class ZTERouterClient:
    """Python API Client for ZTE Smart Routers running ZXSLC firmware."""

    def __init__(self, host: str = DEFAULT_ROUTER_IP, password: Optional[str] = None, timeout: int = 6):
        self.host = host.rstrip("/")
        if not self.host.startswith("http://") and not self.host.startswith("https://"):
            self.base_url = f"http://{self.host}"
        else:
            self.base_url = self.host
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session_token = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{self.base_url}/",
            "X-Requested-With": "XMLHttpRequest",
        }

    def login(self, password: Optional[str] = None) -> bool:
        """
        Authenticate with the router using ZTE's dynamic challenge-response protocol.
        Protocol: SHA256(password + dynamic_logintoken)
        """
        pwd = password or self.password
        if not pwd:
            raise ValueError("Password is required for login")

        # Step 1: Fetch session token and dynamic challenge logintoken
        url_token = f"{self.base_url}/?_type=loginsceneData&_tag=login_token_json"
        try:
            r0 = self.session.get(url_token, headers=self.headers, timeout=self.timeout).json()
        except Exception:
            # Fallback to initial_info_json
            url_init = f"{self.base_url}/?_type=hiddenScene&_tag=initial_info_json"
            d_init = self.session.get(url_init, headers=self.headers, timeout=self.timeout).json()
            r0 = {
                "logintoken": d_init.get("data", {}).get("OBJ_GLOBAL_ENV", {}).get("logintoken", ""),
                "_sessionToken": d_init.get("_sessionToken", "")
            }

        logintoken = str(r0.get("logintoken", ""))
        self.session_token = str(r0.get("_sessionToken", ""))
        if not logintoken:
            raise RuntimeError("Failed to obtain logintoken challenge from router")

        # Step 2: Compute SHA256 signature
        pwd_hash = hashlib.sha256((pwd + logintoken).encode("utf-8")).hexdigest()

        # Step 3: Dispatch login POST payload
        url_login = f"{self.base_url}/?_type=loginData&_tag=login_entry"
        payload = {
            "Username": "admin",
            "Password": pwd_hash,
            "action": "login",
            "Frm_Logintoken": "",
            "captchaCode": "",
            "_sessionTOKEN": self.session_token
        }
        headers = dict(self.headers)
        headers["x_xsrf_token"] = self.session_token
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        resp = self.session.post(url_login, data=payload, headers=headers, timeout=self.timeout).json()
        if resp.get("login_need_refresh"):
            if "sess_token" in resp:
                self.session_token = resp["sess_token"]
            self.headers["x_xsrf_token"] = self.session_token
            return True
        else:
            err_msg = resp.get("loginErrMsg") or resp.get("loginErrType") or "Unknown error"
            raise PermissionError(f"Login rejected by router: {err_msg}")

    def _query_xml(self, url: str) -> List[Dict[str, str]]:
        headers = dict(self.headers)
        headers["x_xsrf_token"] = self.session_token
        r = self.session.get(url, headers=headers, timeout=self.timeout)
        r.raise_for_status()

        root = ET.fromstring(r.text)
        items = []
        for inst in root.iter("Instance"):
            names = [el.text for el in inst.findall("ParaName")]
            vals = [el.text for el in inst.findall("ParaValue")]
            items.append(dict(zip(names, vals)))
        return items

    def get_device_info(self) -> Dict[str, Any]:
        """Query router hardware specifications, serial number, and firmware version."""
        items = self._query_xml(f"{self.base_url}/?_type=hiddenData&_tag=vue_dev_info_data")
        info = {}
        for item in items:
            info.update(item)
        uptime_sec = int(info.get("UpTime", 0) or 0)
        days = uptime_sec // 86400
        hours = (uptime_sec % 86400) // 3600
        mins = (uptime_sec % 3600) // 60

        return {
            "model_name": info.get("ModelName", "ZXSLC SR6001"),
            "alias_name": info.get("AliasName", "巡天青春版AX1500"),
            "manufacturer": info.get("ManuFacturer", "ZTE"),
            "serial_number": info.get("SerialNumber", ""),
            "hardware_version": info.get("HardwareVer", "V1.0.0"),
            "software_version": info.get("SoftwareVer", "V1.0.0.3B3.8000"),
            "boot_version": info.get("BootVer", "V1.0.2"),
            "uptime_seconds": uptime_sec,
            "uptime_human": f"{days}天 {hours}小时 {mins}分"
        }

    @staticmethod
    def load_metadata(meta_path: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Load device metadata dictionary (JSON) indexed by MAC and IP."""
        p = Path(meta_path)
        if not p.exists():
            return {}, {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            by_mac = {}
            by_ip = {}
            for dev in data.get("devices", []):
                if "mac" in dev and dev["mac"]:
                    by_mac[dev["mac"].upper()] = dev
                if "ip_hint" in dev and dev["ip_hint"]:
                    by_ip[dev["ip_hint"]] = dev
            return by_mac, by_ip
        except Exception as e:
            print(f"Warning: Failed to load metadata from {meta_path}: {e}", file=sys.stderr)
            return {}, {}

    def get_connected_devices(self, meta_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query all connected and historical LAN/Wi-Fi devices, optionally merging metadata."""
        items = self._query_xml(f"{self.base_url}/?_type=vueData&_tag=localnet_lan_info_lua")
        by_mac, by_ip = {}, {}
        if meta_path:
            by_mac, by_ip = self.load_metadata(meta_path)

        devices = []
        for d in items:
            ip = d.get("IPAddress", "")
            mac = (d.get("MACAddress") or "").upper()
            if not ip and not mac:
                continue
            meta = by_mac.get(mac) or by_ip.get(ip) or {}
            devices.append({
                "ip": ip,
                "mac": mac,
                "hostname": d.get("HostName") or d.get("AliasName") or "未知设备",
                "active": d.get("Active") == "1",
                "port_type": d.get("PortType") or d.get("Port") or "LAN/WLAN",
                "speed": d.get("CurSpeed") or "",
                "alias": meta.get("alias", ""),
                "desc": meta.get("desc", ""),
                "role": meta.get("role", ""),
                "type": meta.get("type", "")
            })
        return devices

    def export_metadata(self, output_path: str):
        """Export current connected devices into a metadata JSON skeleton template."""
        devices = self.get_connected_devices()
        gw = self.base_url.split("://")[-1]
        net_prefix = gw.rsplit(".", 1)[0]
        template = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "version": "1.0",
            "description": "ZTE Smart Router LAN Device Asset Dictionary",
            "network": f"{net_prefix}.0/24",
            "gateway": gw,
            "devices": []
        }
        for d in devices:
            if not d["ip"] or d["ip"] == "0.0.0.0":
                continue
            template["devices"].append({
                "mac": d["mac"],
                "ip_hint": d["ip"],
                "raw_hostname": d["hostname"],
                "alias": d["hostname"],
                "desc": f"设备 {d['hostname']} (接入: {d['port_type']})",
                "role": "终端设备",
                "type": "device"
            })
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"--> 元数据模板已成功导出至: {output_path}")

    def get_wan_status(self) -> Dict[str, Any]:
        """Query WAN link connectivity, IP, DNS, and connection mode."""
        items = self._query_xml(f"{self.base_url}/?_type=vueData&_tag=vue_net_lua")
        wan = items[0] if items else {}
        return {
            "wan_ip": wan.get("IPAddress", ""),
            "gateway": wan.get("DefaultGateway", ""),
            "dns": wan.get("DNSServers", ""),
            "mac": (wan.get("MACAddress") or "").upper(),
            "mode": wan.get("Mode", "DHCP/PPPoE")
        }


def main():
    parser = argparse.ArgumentParser(description="ZTE Smart Router (ZXSLC) Automation CLI")
    parser.add_argument("--host", default=DEFAULT_ROUTER_IP, help="Router IP address (default: 192.168.31.1)")
    parser.add_argument("-p", "--password", help="Admin password for router WebUI (or set ZTE_ROUTER_PASSWORD)")
    parser.add_argument("-i", "--info", action="store_true", help="Print router hardware specifications")
    parser.add_argument("-d", "--devices", action="store_true", help="List connected LAN & Wi-Fi devices")
    parser.add_argument("-w", "--wan", action="store_true", help="Print WAN uplink status")
    parser.add_argument("-a", "--all", action="store_true", help="Show all status (info, devices, wan)")
    parser.add_argument("--meta", help="Path to devices metadata dictionary (JSON) to merge aliases/roles")
    parser.add_argument("--export-meta", help="Export current devices into a metadata JSON template")
    parser.add_argument("--json", action="store_true", help="Output results in structured JSON format")

    args = parser.parse_args()

    if not args.password:
        args.password = os.environ.get("ZTE_ROUTER_PASSWORD")
        if not args.password:
            print("Error: Password must be supplied via -p / --password or ZTE_ROUTER_PASSWORD env var.", file=sys.stderr)
            sys.exit(1)

    # Auto-resolve meta if not explicitly specified
    meta_file = args.meta
    if not meta_file:
        candidate = Path(__file__).resolve().parent.parent / "examples" / "devices_sample.json"
        if candidate.exists():
            meta_file = str(candidate)

    client = ZTERouterClient(host=args.host, password=args.password)
    try:
        client.login()
    except Exception as e:
        print(f"Error authenticating with router: {e}", file=sys.stderr)
        sys.exit(1)

    if args.export_meta:
        client.export_metadata(args.export_meta)
        return

    if not any([args.info, args.devices, args.wan, args.all]):
        args.all = True

    result = {}
    if args.info or args.all:
        result["router_info"] = client.get_device_info()
    if args.devices or args.all:
        result["devices"] = client.get_connected_devices(meta_path=meta_file)
    if args.wan or args.all:
        result["wan_status"] = client.get_wan_status()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Formatted console output
    if "router_info" in result:
        info = result["router_info"]
        print("=" * 70)
        print("  ZTE Smart Router Information")
        print("=" * 70)
        print(f"  ● 设备名称: {info['alias_name']} ({info['model_name']})")
        print(f"  ● 固件版本: {info['software_version']} (Boot: {info['boot_version']})")
        print(f"  ● 硬件版本: {info['hardware_version']}")
        print(f"  ● 序列号:   {info['serial_number']}")
        print(f"  ● 运行时间: {info['uptime_human']}")
        print()

    if "wan_status" in result:
        wan = result["wan_status"]
        print("=" * 70)
        print("  WAN 上行链路状态")
        print("=" * 70)
        print(f"  ● WAN IP:   {wan['wan_ip'] or '已连接/上级分配'}")
        print(f"  ● 默认网关: {wan['gateway']}")
        print(f"  ● DNS 服务: {wan['dns']}")
        print()

    if "devices" in result:
        devs = result["devices"]
        active = [d for d in devs if d["active"] and d["ip"] and d["ip"] != "0.0.0.0"]
        inactive = [d for d in devs if not d["active"] and d["ip"] and d["ip"] != "0.0.0.0"]
        has_meta = any(d.get("alias") or d.get("desc") for d in devs)

        print("=" * 80)
        title = "局域网资产清单 (已融合元数据字典)" if has_meta else "局域网连接设备"
        print(f"  {title} (在线: {len(active)} 台, 历史离线: {len(inactive)} 台)")
        print("=" * 80)

        if has_meta:
            print(f"  {'状态':4} | {'IP 地址':15} | {'MAC 地址':17} | {'别名 / 主机名':16} | {'描述与角色'}")
            print("  " + "-" * 76)
            for d in active:
                name_disp = d['alias'] or d['hostname']
                desc_disp = f"{d['desc']} ({d['role']})" if d['desc'] and d['role'] else (d['desc'] or d['role'] or "-")
                print(f"  🟢   | {d['ip']:15} | {d['mac']:17} | {name_disp:16} | {desc_disp}")
            for d in inactive:
                name_disp = d['alias'] or d['hostname']
                desc_disp = f"{d['desc']} ({d['role']})" if d['desc'] and d['role'] else (d['desc'] or d['role'] or "-")
                print(f"  ⚪   | {d['ip']:15} | {d['mac']:17} | {name_disp:16} | {desc_disp}")
        else:
            print(f"  {'状态':4} | {'IP 地址':15} | {'MAC 地址':17} | {'设备主机名'}")
            print("  " + "-" * 56)
            for d in active:
                print(f"  🟢   | {d['ip']:15} | {d['mac']:17} | {d['hostname']}")
            for d in inactive:
                print(f"  ⚪   | {d['ip']:15} | {d['mac']:17} | {d['hostname']}")
        print()


if __name__ == "__main__":
    main()
