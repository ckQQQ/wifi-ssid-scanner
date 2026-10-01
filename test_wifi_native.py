import ctypes as C
from ctypes import wintypes as W
import struct
import unittest

from wifi_native import BssEntry, Network, merge_networks, read_bss_rssi


class RssiTests(unittest.TestCase):
    def test_windows_sdk_layout_and_strongest_bssid(self):
        # Independent SDK offsets ensure ctypes padding/sign handling is correct.
        self.assertEqual(C.sizeof(BssEntry), 360)
        self.assertEqual(BssEntry.rssi.offset, 56)
        data = bytearray(8 + 4 * 360)
        struct.pack_into('<II', data, 0, len(data), 4)
        for index, (rssi, secure, bss_type) in enumerate([
                (-75, True, 1), (-42, True, 1), (-60, False, 1), (-55, True, 2)]):
            offset = 8 + index * 360
            struct.pack_into('<I', data, offset, 3)
            data[offset + 4:offset + 7] = b'AP1'
            struct.pack_into('<I', data, offset + 48, bss_type)
            struct.pack_into('<i', data, offset + 56, rssi)
            struct.pack_into('<H', data, offset + 88, 0x10 if secure else 0)
        buffer = C.create_string_buffer(bytes(data))
        values = read_bss_rssi(W.LPVOID(C.addressof(buffer)))
        self.assertEqual(values, {(b'AP1', True, 1): -42,
                                  (b'AP1', False, 1): -60, (b'AP1', True, 2): -55})

    def test_invalid_list_size_is_rejected(self):
        buffer = C.create_string_buffer(struct.pack('<II', 8, 1))
        with self.assertRaises(RuntimeError):
            read_bss_rssi(W.LPVOID(C.addressof(buffer)))

    def test_multi_adapter_merge_preserves_measured_rssi(self):
        rows = merge_networks([Network(b'a', 'a', 80, True, True, -65),
                               Network(b'a', 'a', 90, True, False, -48),
                               Network(b'a', 'a', 95, True, False)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].rssi, -48)
        self.assertTrue(rows[0].connected)


if __name__ == '__main__':
    unittest.main()
