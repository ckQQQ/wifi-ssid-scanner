"""Verify the built Console EXE without printing or storing SSIDs."""
import json
from pathlib import Path
import subprocess

from wifi_native import scan_networks
from wifi_scanner_console import safe_text

root = Path(__file__).resolve().parent
exe = root / "dist" / "WiFiScannerConsoleRSSI.exe"
report = {}


def run(*args, input_text=None):
    result = subprocess.run([str(exe), *args], input=input_text, capture_output=True,
                            encoding="utf-8", errors="replace", timeout=45, cwd=root)
    assert result.returncode == 0, f"Executable exit code: {result.returncode}"
    return result.stdout


output = run("--help")
assert "--search" in output and "--once" in output
report["help"] = True

diagnostic = root / "verification" / "console-exe-scan.json"
diagnostic.parent.mkdir(exist_ok=True)
run("--diagnose", str(diagnostic))
summary = json.loads(diagnostic.read_text(encoding="utf-8"))
assert summary["ok"]
assert summary["rssi_count"] > 0
report["scan"] = summary

output = run("--once")
assert "附近" in output and "RSSI" in output and "dBm" in output
report["once"] = True

networks, _ = scan_networks()
named = [n for n in networks if n.raw_ssid]
assert named, "No broadcast SSIDs available for search verification"
keyword = named[0].name
output = run("--search", keyword.swapcase())
assert "搜尋關鍵字" in output and safe_text(keyword) in output
report["search_real_ssid"] = True

output = run(input_text="2\n" + keyword + "\n3\n0\n")
assert "請選擇" in output and "搜尋關鍵字" in output
report["interactive_search_show_all_exit"] = True

path = root / "verification" / "console-exe-checks.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
