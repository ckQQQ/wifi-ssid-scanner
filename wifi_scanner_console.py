"""Interactive and command-line Windows Wi-Fi scanner (no GUI dependencies)."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import unicodedata

from wifi_native import Network, format_rssi, scan_networks


def safe_text(value: str) -> str:
    """Do not allow a broadcast SSID to inject terminal control sequences."""
    return "".join(f"\\x{ord(c):02X}" if unicodedata.category(c).startswith("C") else c
                   for c in value)


def pad(value: str, width: int) -> str:
    display_width = sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in value)
    return value + " " * max(0, width - display_width)


def show_networks(networks: list[Network], keyword: str = "") -> int:
    query = keyword.strip().casefold()
    matches = [n for n in networks if query in n.name.casefold()]
    print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} | 附近 {len(networks)} 個網路 | 符合 {len(matches)} 個")
    if query:
        print("搜尋關鍵字：" + safe_text(keyword.strip()))
    if not matches:
        print("沒有符合的 SSID。" if query else "未找到 Wi-Fi，請確認 Wi-Fi 已開啟並重新掃描。")
        return 0
    name_width = max(32, *(sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
                             for c in safe_text(n.name)) for n in matches))
    print("-" * (name_width + 46))
    print(pad("序號", 6) + pad("Wi-Fi 名稱 / SSID", name_width + 2)
          + pad("訊號品質", 10) + pad("RSSI", 12) + pad("安全性", 10) + "狀態")
    print("-" * (name_width + 46))
    for i, n in enumerate(matches, 1):
        print(pad(str(i), 6) + pad(safe_text(n.name), name_width + 2)
              + pad(f"{n.quality}%", 10) + pad(format_rssi(n.rssi), 12)
              + pad("已加密" if n.secure else "開放", 10)
              + ("已連線" if n.connected else "未連線"))
    return len(matches)


def scan() -> tuple[list[Network], bool]:
    print("\n正在掃描附近的 Wi-Fi，請稍候…", flush=True)
    try:
        networks, warning = scan_networks()
    except Exception as exc:
        print("掃描失敗：" + safe_text(str(exc)), file=sys.stderr)
        return [], False
    if warning:
        print("提示：" + safe_text(warning), file=sys.stderr)
    return networks, True


def interactive(keyword: str = "") -> int:
    print("=== Wi-Fi 搜尋器 Console ===")
    networks, ok = scan()
    if ok:
        show_networks(networks, keyword)
    while True:
        print("\n1：重新掃描  2：搜尋 SSID  3：顯示全部  0：離開")
        try:
            choice = input("請選擇：").strip()
            if choice == "0":
                return 0
            if choice == "1":
                # Do not retain old results if the new scan fails.
                networks, ok = scan()
                if ok:
                    show_networks(networks, keyword)
            elif choice == "2":
                keyword = input("輸入 SSID 關鍵字（空白顯示全部）：").strip()
                if ok:
                    show_networks(networks, keyword)
                else:
                    print("請先選 1 重新掃描，取得清單後再搜尋。")
            elif choice == "3":
                keyword = ""
                if ok:
                    show_networks(networks)
                else:
                    print("目前沒有有效清單，請選 1 重新掃描。")
            else:
                print("請輸入 0、1、2 或 3。")
        except EOFError:
            return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="掃描附近 Wi-Fi 名稱（SSID）；未帶參數時開啟互動選單。")
    parser.add_argument("--search", metavar="關鍵字", help="依 SSID 關鍵字搜尋，不區分英文大小寫")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="掃描一次並結束，適合命令列或批次檔")
    mode.add_argument("--interactive", action="store_true", help="使用互動選單，可搭配 --search")
    mode.add_argument("--diagnose", type=Path, metavar="檔案", help="將掃描數量及錯誤寫入 JSON，不記錄 SSID")
    args = parser.parse_args(argv)
    if args.diagnose:
        try:
            networks, warning = scan_networks()
            result = {"ok": True, "network_count": len(networks), "warning": warning,
                      "rssi_count": sum(n.rssi is not None for n in networks)}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        try:
            args.diagnose.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            print("無法寫入診斷檔：" + safe_text(str(exc)), file=sys.stderr)
            return 1
        return 0 if result["ok"] else 1
    try:
        if args.interactive or (not args.once and args.search is None):
            return interactive(args.search or "")
        networks, ok = scan()
        if not ok:
            return 1
        show_networks(networks, args.search or "")
        return 0
    except KeyboardInterrupt:
        print("\n已結束。")
        return 130


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
