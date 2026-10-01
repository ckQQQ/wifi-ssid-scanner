"""Windows Wi-Fi SSID scanner. Uses only Python's standard library."""
from __future__ import annotations

import argparse
import ctypes as C
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk


from wifi_native import Network, format_rssi, merge_networks, scan_networks


class WifiApp:
    def __init__(self, root: tk.Tk, auto_scan: bool = True):
        self.root = root
        self.networks: list[Network] = []
        self.visible: dict[str, Network] = {}
        self.results = queue.Queue()
        self.busy = False
        root.title("Wi-Fi 搜尋器")
        root.geometry("900x540")
        root.minsize(780, 440)
        root.configure(bg="#18212f")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Treeview", font=("Microsoft JhengHei UI", 11), rowheight=40,
                        background="#ffffff", fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Microsoft JhengHei UI", 10, "bold"))
        style.configure("TButton", font=("Microsoft JhengHei UI", 10), padding=(12, 7))
        shell = tk.Frame(root, bg="#18212f", padx=24, pady=20)
        shell.pack(fill="both", expand=True)
        tk.Label(shell, text="附近的 Wi-Fi", fg="white", bg="#18212f",
                 font=("Microsoft JhengHei UI", 23, "bold")).pack(anchor="w")
        tk.Label(shell, text="搜尋無線網路名稱（SSID） · 已連線優先，依訊號排序",
                 fg="#bbc9dc", bg="#18212f", font=("Microsoft JhengHei UI", 10)).pack(anchor="w", pady=(4, 18))
        toolbar = tk.Frame(shell, bg="#18212f")
        toolbar.pack(fill="x", pady=(0, 14))
        self.query = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.query, font=("Microsoft JhengHei UI", 12))
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.query.trace_add("write", lambda *_: self.render())
        self.scan_button = ttk.Button(toolbar, text="重新掃描", command=self.start_scan)
        self.scan_button.pack(side="left", padx=(10, 0))
        ttk.Button(toolbar, text="清除搜尋", command=lambda: self.query.set("")).pack(side="left", padx=(8, 0))
        table_frame = tk.Frame(shell)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=("ssid", "signal", "rssi", "security", "state"),
                                  show="headings", selectmode="browse")
        for key, title, width in [("ssid", "Wi-Fi 名稱 / SSID", 320), ("signal", "訊號品質", 95),
                                   ("rssi", "RSSI", 110),
                                   ("security", "安全性", 100), ("state", "狀態", 100)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=70, anchor="w" if key == "ssid" else "center")
        self.table.tag_configure("connected", foreground="#007b67", background="#e2f5ef")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.bind("<Double-1>", lambda _: self.copy_ssid())
        self.table.bind("<Control-c>", lambda _: self.copy_ssid())
        self.status = tk.StringVar(value="按「重新掃描」搜尋附近的 Wi-Fi。")
        tk.Label(shell, textvariable=self.status, anchor="w", justify="left", wraplength=710,
                 fg="#d8e5f4", bg="#18212f", font=("Microsoft JhengHei UI", 10)).pack(fill="x", pady=(12, 6))
        footer = tk.Frame(shell, bg="#18212f")
        footer.pack(fill="x")
        ttk.Button(footer, text="複製 SSID", command=self.copy_ssid).pack(side="left")
        ttk.Button(footer, text="Wi-Fi 設定", command=lambda: os.startfile("ms-settings:network-wifi")).pack(side="right")
        ttk.Button(footer, text="定位設定", command=lambda: os.startfile("ms-settings:privacy-location")).pack(side="right", padx=8)
        entry.focus_set()
        root.after(100, self.poll)
        if auto_scan:
            root.after(250, self.start_scan)

    def render(self):
        self.table.delete(*self.table.get_children())
        self.visible.clear()
        query = self.query.get().casefold().strip()
        for n in self.networks:
            if query not in n.name.casefold():
                continue
            iid = self.table.insert("", "end", values=(n.name, f"{n.quality}%", format_rssi(n.rssi),
                    "已加密" if n.secure else "開放", "已連線" if n.connected else "未連線"),
                    tags=("connected",) if n.connected else ())
            self.visible[iid] = n
        if self.networks and not self.busy:
            self.status.set(f"找到 {len(self.networks)} 個網路 · 符合搜尋 {len(self.visible)} 個")

    def start_scan(self):
        if self.busy:
            return
        self.busy = True
        self.scan_button.configure(state="disabled")
        self.status.set("正在掃描附近的 Wi-Fi，請稍候…")
        def worker():
            try:
                self.results.put((True, scan_networks()))
            except Exception as exc:
                self.results.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            success, result = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.scan_button.configure(state="normal")
            if success:
                self.networks, warning = result
                self.render()
                summary = f"{datetime.now():%H:%M:%S} · 找到 {len(self.networks)} 個網路 · 符合搜尋 {len(self.visible)} 個"
                if not self.networks:
                    summary += "\n未找到網路，請確認 Wi-Fi 已開啟，或移近無線基地台後重試。"
                self.status.set(summary + ("\n" + warning if warning else ""))
            else:
                self.networks = []
                self.render()
                self.status.set(result)
        self.root.after(100, self.poll)

    def copy_ssid(self):
        selection = self.table.selection()
        if not selection:
            self.status.set("請先選取一個 Wi-Fi 名稱，再按「複製 SSID」。")
            return
        network = self.visible[selection[0]]
        if not network.raw_ssid:
            self.status.set("隱藏的網路未廣播名稱，無法取得 SSID。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(network.name)
        self.status.set("已複製選取的 SSID。")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", type=Path, help="Write a scan summary without SSID names")
    parser.add_argument("--smoke-test", type=Path, help="Write GUI verification result")
    args = parser.parse_args()
    if args.diagnose:
        try:
            networks, warning = scan_networks()
            result = {"ok": True, "network_count": len(networks), "warning": warning,
                      "rssi_count": sum(n.rssi is not None for n in networks)}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        args.diagnose.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return
    try:
        C.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    app = WifiApp(root, auto_scan=not args.smoke_test)
    if args.smoke_test:
        def verify():
            try:
                app.networks = merge_networks([
                    Network(b"Example-WiFi", "Example-WiFi", 75, True, True, -50),
                    Network(b"Guest-Network", "Guest-Network", 55, True, False),
                    Network("中文網路".encode(), "中文網路", 90, False, False)])
                app.render()
                assert len(app.visible) == 3
                assert app.table.heading("rssi", "text") == "RSSI"
                assert app.table.item(next(iter(app.visible)), "values")[2] == "-50 dBm"
                app.query.set("guest")
                assert len(app.visible) == 1
                app.table.selection_set(next(iter(app.visible)))
                app.copy_ssid()
                assert root.clipboard_get() == "Guest-Network"
                app.query.set("中文")
                assert len(app.visible) == 1
                app.query.set("missing")
                assert len(app.visible) == 0
                result = {"ok": True, "checks": ["window", "list", "rssi_column", "search", "unicode", "clipboard", "no_matches"]}
            except Exception as exc:
                result = {"ok": False, "error": repr(exc)}
            args.smoke_test.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            root.destroy()
        root.after(300, verify)
    root.mainloop()


if __name__ == "__main__":
    main()
