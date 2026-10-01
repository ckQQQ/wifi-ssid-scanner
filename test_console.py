import contextlib
import io
import unittest
from unittest.mock import patch

import wifi_scanner_console as app
from wifi_native import Network


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.networks = [Network(b'Example-WiFi', 'Example-WiFi', 70, True, True),
                         Network('中文網路'.encode(), '中文網路', 40, False, False)]

    def test_search_english_chinese_and_empty_matches(self):
        for keyword, expected in [('example', 1), ('中文', 1), ('missing', 0), ('', 2)]:
            with self.subTest(keyword=keyword), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.show_networks(self.networks, keyword), expected)

    def test_ssid_cannot_inject_terminal_escape_sequences(self):
        self.assertEqual(app.safe_text('AP\x1b[2J\n'), 'AP\\x1B[2J\\x0A')

    def test_rssi_uses_dbm_and_missing_is_not_estimated(self):
        output = io.StringIO()
        networks = [Network(b'a', 'a', 90, True, False, -48),
                    Network(b'b', 'b', 90, True, False)]
        with contextlib.redirect_stdout(output):
            app.show_networks(networks)
        self.assertIn('RSSI', output.getvalue())
        self.assertIn('-48 dBm', output.getvalue())
        self.assertIn('—', output.getvalue())

    def test_once_failure_exits_nonzero(self):
        with patch.object(app, 'scan_networks', side_effect=RuntimeError('denied')):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(app.main(['--once']), 1)

    def test_interactive_search_rescan_and_exit(self):
        output = io.StringIO()
        with patch.object(app, 'scan_networks', return_value=(self.networks, '')) as scanner:
            with patch('builtins.input', side_effect=['2', '中文', '1', '3', '0']):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(app.main([]), 0)
        self.assertEqual(scanner.call_count, 2)
        self.assertIn('搜尋關鍵字：中文', output.getvalue())

    def test_failed_rescan_does_not_keep_old_results(self):
        output = io.StringIO()
        with patch.object(app, 'scan_networks', side_effect=[(self.networks, ''), RuntimeError('denied')]):
            with patch('builtins.input', side_effect=['1', '3', '0']):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    app.main([])
        self.assertIn('目前沒有有效清單', output.getvalue())


if __name__ == '__main__':
    unittest.main()
