"""Windows Native Wi-Fi scanning shared by the GUI and console apps."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import sys
import threading


class GUID(C.Structure):
    _fields_ = [("a", W.DWORD), ("b", W.WORD), ("c", W.WORD), ("d", W.BYTE * 8)]


class Interface(C.Structure):
    _fields_ = [("guid", GUID), ("description", W.WCHAR * 256), ("state", W.DWORD)]


class SSID(C.Structure):
    _fields_ = [("length", W.DWORD), ("data", W.BYTE * 32)]


class AvailableNetwork(C.Structure):
    _fields_ = [
        ("profile", W.WCHAR * 256), ("ssid", SSID), ("bss_type", W.DWORD),
        ("bss_count", W.DWORD), ("connectable", W.BOOL), ("reason", W.DWORD),
        ("phy_count", W.DWORD), ("phy_types", W.DWORD * 8), ("more_phy", W.BOOL),
        ("quality", W.DWORD), ("secure", W.BOOL), ("auth", W.DWORD),
        ("cipher", W.DWORD), ("flags", W.DWORD), ("reserved", W.DWORD),
    ]


class Notification(C.Structure):
    _fields_ = [("source", W.DWORD), ("code", W.DWORD), ("guid", GUID),
                ("size", W.DWORD), ("data", W.LPVOID)]


class RateSet(C.Structure):
    _fields_ = [("length", W.DWORD), ("rates", W.USHORT * 126)]


class BssEntry(C.Structure):
    _fields_ = [
        ("ssid", SSID), ("phy_id", W.DWORD), ("bssid", W.BYTE * 6),
        ("bss_type", W.DWORD), ("phy_type", W.DWORD), ("rssi", W.LONG),
        ("quality", W.DWORD), ("in_reg_domain", W.BYTE), ("beacon_period", W.USHORT),
        ("timestamp", C.c_ulonglong), ("host_timestamp", C.c_ulonglong),
        ("capabilities", W.USHORT), ("frequency", W.DWORD), ("rates", RateSet),
        ("ie_offset", W.DWORD), ("ie_size", W.DWORD),
    ]


class BssListHeader(C.Structure):
    _fields_ = [("total_size", W.DWORD), ("count", W.DWORD)]


@dataclass(frozen=True)
class Network:
    raw_ssid: bytes
    name: str
    quality: int
    secure: bool
    connected: bool
    rssi: int | None = None


def format_rssi(rssi: int | None) -> str:
    return "—" if rssi is None else f"{rssi} dBm"


def read_bss_rssi(memory: W.LPVOID) -> dict[tuple[bytes, bool, int], int]:
    """Use the strongest measured BSSID for each SSID/security/BSS type."""
    header = BssListHeader.from_address(memory.value)
    offset = C.sizeof(BssListHeader)
    if header.total_size < offset or header.count > (header.total_size - offset) // C.sizeof(BssEntry):
        raise RuntimeError("Windows 回傳的 RSSI 清單長度無效。")
    result = {}
    for i in range(header.count):
        entry = BssEntry.from_address(memory.value + offset + i * C.sizeof(BssEntry))
        raw = bytes(entry.ssid.data[:min(entry.ssid.length, 32)])
        key = (raw, bool(entry.capabilities & 0x10), entry.bss_type)
        result[key] = max(result.get(key, entry.rssi), entry.rssi)
    return result


def decode_ssid(raw: bytes) -> str:
    if not raw:
        return "（隱藏的網路）"
    for encoding in ("utf-8", "cp950"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return "0x" + raw.hex().upper()


def merge_networks(networks: list[Network]) -> list[Network]:
    merged = {}
    for network in networks:
        key = (network.raw_ssid, network.secure)
        old = merged.get(key)
        if old:
            measurements = [v for v in (old.rssi, network.rssi) if v is not None]
            network = Network(network.raw_ssid, network.name,
                              max(old.quality, network.quality), network.secure,
                              old.connected or network.connected,
                              max(measurements) if measurements else None)
        merged[key] = network
    return sorted(merged.values(), key=lambda n: (not n.connected, -n.quality, n.name.casefold()))


def check(code: int, action: str) -> None:
    if not code:
        return
    if code == 5:
        detail = "Windows 拒絕存取。請開啟「定位設定」並允許定位／桌面應用程式存取後重試。"
    elif code == 1062:
        detail = "WLAN AutoConfig 服務未啟動，請在 Windows 服務管理中啟動該服務。"
    elif code == 5023:
        detail = "Wi-Fi 網卡尚未就緒，請確認已開啟 Wi-Fi 與關閉飛航模式。"
    else:
        detail = C.FormatError(code).strip()
    raise RuntimeError(f"{action}失敗（{code}）：{detail}")


def scan_networks() -> tuple[list[Network], str]:
    if sys.platform != "win32":
        raise RuntimeError("此程式適用於 Windows 10 / 11。")
    api = C.WinDLL("wlanapi.dll")
    signatures = {
        "WlanOpenHandle": [W.DWORD, W.LPVOID, C.POINTER(W.DWORD), C.POINTER(W.HANDLE)],
        "WlanCloseHandle": [W.HANDLE, W.LPVOID],
        "WlanEnumInterfaces": [W.HANDLE, W.LPVOID, C.POINTER(W.LPVOID)],
        "WlanScan": [W.HANDLE, C.POINTER(GUID), W.LPVOID, W.LPVOID, W.LPVOID],
        "WlanGetAvailableNetworkList": [W.HANDLE, C.POINTER(GUID), W.DWORD,
                                        W.LPVOID, C.POINTER(W.LPVOID)],
        "WlanGetNetworkBssList": [W.HANDLE, C.POINTER(GUID), C.POINTER(SSID),
                                  W.DWORD, W.BOOL, W.LPVOID, C.POINTER(W.LPVOID)],
        "WlanFreeMemory": [W.LPVOID],
    }
    for name, args in signatures.items():
        fn = getattr(api, name)
        fn.argtypes = args
        fn.restype = None if name == "WlanFreeMemory" else W.DWORD
    callback_type = C.WINFUNCTYPE(None, C.POINTER(Notification), W.LPVOID)
    api.WlanRegisterNotification.argtypes = [W.HANDLE, W.DWORD, W.BOOL,
        callback_type, W.LPVOID, W.LPVOID, C.POINTER(W.DWORD)]
    api.WlanRegisterNotification.restype = W.DWORD
    handle, version = W.HANDLE(), W.DWORD()
    check(api.WlanOpenHandle(2, None, C.byref(version), C.byref(handle)), "開啟 Wi-Fi 服務")
    all_networks, errors = [], []
    events: dict[bytes, threading.Event] = {}
    failed: set[bytes] = set()

    @callback_type
    def on_notification(ptr, context):
        info = ptr.contents
        key = bytes(info.guid)
        if info.source == 8 and info.code in (7, 8) and key in events:
            if info.code == 8:
                failed.add(key)
            events[key].set()

    try:
        memory = W.LPVOID()
        check(api.WlanEnumInterfaces(handle, None, C.byref(memory)), "讀取 Wi-Fi 網卡")
        try:
            count = C.cast(memory, C.POINTER(W.DWORD))[0]
            interfaces = []
            for i in range(count):
                address = memory.value + 8 + i * C.sizeof(Interface)
                interfaces.append(Interface.from_buffer_copy(C.string_at(address, C.sizeof(Interface))))
        finally:
            api.WlanFreeMemory(memory)
        if not interfaces:
            raise RuntimeError("找不到 Wi-Fi 網卡。請確認電腦有無線網卡且已啟用。")
        registered = api.WlanRegisterNotification(handle, 8, True, on_notification, None, None, None) == 0
        for interface in interfaces:
            label = interface.description
            key = bytes(interface.guid)
            events[key] = threading.Event()
            try:
                check(api.WlanScan(handle, C.byref(interface.guid), None, None, None), "掃描附近網路")
                completed = events[key].wait(4.0)
                if key in failed:
                    errors.append(f"{label}：掃描未完成，顯示 Windows 現有結果。")
                elif registered and not completed:
                    errors.append(f"{label}：掃描逾時，顯示 Windows 現有結果。")
                rssi_values = {}
                bss_memory = W.LPVOID()
                try:
                    check(api.WlanGetNetworkBssList(handle, C.byref(interface.guid), None,
                                                    3, False, None, C.byref(bss_memory)), "讀取 RSSI")
                    rssi_values = read_bss_rssi(bss_memory)
                except RuntimeError as exc:
                    errors.append(f"{label}：{exc} 未取得的 RSSI 顯示「—」。")
                finally:
                    if bss_memory.value:
                        api.WlanFreeMemory(bss_memory)
                memory = W.LPVOID()
                # Flags=0 excludes saved profiles that are not currently visible.
                check(api.WlanGetAvailableNetworkList(handle, C.byref(interface.guid), 0,
                                                       None, C.byref(memory)), "讀取 Wi-Fi 清單")
                try:
                    count = C.cast(memory, C.POINTER(W.DWORD))[0]
                    for i in range(count):
                        address = memory.value + 8 + i * C.sizeof(AvailableNetwork)
                        item = AvailableNetwork.from_address(address)
                        raw = bytes(item.ssid.data[:min(item.ssid.length, 32)])
                        all_networks.append(Network(raw, decode_ssid(raw), min(item.quality, 100),
                                                    bool(item.secure), bool(item.flags & 1),
                                                    rssi_values.get((raw, bool(item.secure), item.bss_type))))
                finally:
                    api.WlanFreeMemory(memory)
            except RuntimeError as exc:
                errors.append(f"{label}：{exc}")
        if errors and not all_networks:
            raise RuntimeError("\n".join(errors))
        return merge_networks(all_networks), "\n".join(errors)
    finally:
        # Closing the handle unregisters the callback; keep it alive until this point.
        api.WlanCloseHandle(handle, None)
