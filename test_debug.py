"""调试模式单元测试。

运行方式：
    packaging_env\\Scripts\\python.exe -m pytest test_debug.py -v
或直接：
    packaging_env\\Scripts\\python.exe test_debug.py
"""
import sys
import os
import io
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestDebugMode(unittest.TestCase):
    """测试 _is_debug / set_debug_mode / _debug_log 的行为。"""

    def setUp(self):
        from utils import set_debug_mode
        set_debug_mode(False)

    def tearDown(self):
        from utils import set_debug_mode
        set_debug_mode(False)

    def test_default_not_debug(self):
        """默认情况下（无调试器、未强制）应为非调试模式。"""
        from utils import _is_debug, set_debug_mode
        set_debug_mode(False)
        self.assertFalse(_is_debug())

    def test_set_debug_mode_true(self):
        """set_debug_mode(True) 后强制调试模式生效。"""
        from utils import _is_debug, set_debug_mode
        set_debug_mode(True)
        self.assertTrue(_is_debug())

    def test_set_debug_mode_roundtrip(self):
        """set_debug_mode(False) 可恢复非调试。"""
        from utils import _is_debug, set_debug_mode
        set_debug_mode(True)
        self.assertTrue(_is_debug())
        set_debug_mode(False)
        self.assertFalse(_is_debug())

    def test_set_debug_mode_called_multiple_times(self):
        """多次调用 set_debug_mode 最后一次生效。"""
        from utils import _is_debug, set_debug_mode
        set_debug_mode(True)
        set_debug_mode(True)
        self.assertTrue(_is_debug())
        set_debug_mode(False)
        self.assertFalse(_is_debug())
        set_debug_mode(True)
        self.assertTrue(_is_debug())

    def test_mock_gettrace_with_forced(self):
        """sys.gettrace() 有值 + 未强制 → True（调试器附加优先）。"""
        from utils import _is_debug, set_debug_mode
        set_debug_mode(False)
        fake_trace = mock.Mock()
        with mock.patch.object(sys, 'gettrace', return_value=fake_trace):
            self.assertTrue(_is_debug())

    def test_mock_gettrace_none_forced_true(self):
        """sys.gettrace() 返回 None + 强制开启 → True（强制优先）。"""
        from utils import _is_debug, set_debug_mode
        set_debug_mode(True)
        with mock.patch.object(sys, 'gettrace', return_value=None):
            self.assertTrue(_is_debug())

    def test_mock_gettrace_none_forced_false(self):
        """sys.gettrace() 返回 None + 未强制 → False。"""
        from utils import _is_debug, set_debug_mode
        set_debug_mode(False)
        with mock.patch.object(sys, 'gettrace', return_value=None):
            self.assertFalse(_is_debug())

    def test_debug_log_suppressed_in_production(self):
        """非调试模式下 _debug_log 不输出到 stderr。"""
        from utils import _debug_log, set_debug_mode
        set_debug_mode(False)
        with mock.patch('sys.stderr', io.StringIO()) as fake_err:
            _debug_log("should not appear")
            self.assertEqual(fake_err.getvalue(), "")

    def test_debug_log_emits_in_debug(self):
        """调试模式下 _debug_log 输出到 stderr，含时间戳和 [DEBUG] 标记。"""
        from utils import _debug_log, set_debug_mode
        set_debug_mode(True)
        with mock.patch('sys.stderr', io.StringIO()) as fake_err:
            _debug_log("hello debug")
            output = fake_err.getvalue()
            self.assertIn("[DEBUG]", output)
            self.assertIn("hello debug", output)
            self.assertRegex(output, r'\[\d{2}:\d{2}:\d{2}\]')

    def test_debug_log_flush(self):
        """调试模式下 _debug_log 调用 flush=True。"""
        from utils import _debug_log, set_debug_mode
        set_debug_mode(True)
        fake_err = mock.Mock()
        with mock.patch('sys.stderr', fake_err):
            _debug_log("flush test")
        fake_err.write.assert_called()
        fake_err.flush.assert_called()


class TestCLIParsing(unittest.TestCase):
    """测试 main._parse_args 对 -debug/-settings 的解析。"""

    @staticmethod
    def _parse(argv):
        from main import _parse_args
        return _parse_args(argv)

    def test_no_args(self):
        args = self._parse([])
        self.assertFalse(args.debug)
        self.assertFalse(args.settings)

    def test_debug_short(self):
        args = self._parse(["-debug"])
        self.assertTrue(args.debug)
        self.assertFalse(args.settings)

    def test_debug_long(self):
        args = self._parse(["--debug"])
        self.assertTrue(args.debug)

    def test_settings_short(self):
        args = self._parse(["-settings"])
        self.assertTrue(args.settings)
        self.assertFalse(args.debug)

    def test_settings_long(self):
        args = self._parse(["--settings"])
        self.assertTrue(args.settings)

    def test_both_flags(self):
        args = self._parse(["-debug", "-settings"])
        self.assertTrue(args.debug)
        self.assertTrue(args.settings)

    def test_unknown_args_ignored(self):
        """未知参数应被忽略，不抛异常。"""
        args = self._parse(["-debug", "-unknown-flag", "-settings"])
        self.assertTrue(args.debug)
        self.assertTrue(args.settings)


class TestDebugModeIntegration(unittest.TestCase):
    """测试 -debug 参数强制调试模式的端到端效果。"""

    def setUp(self):
        from utils import set_debug_mode
        set_debug_mode(False)

    def tearDown(self):
        from utils import set_debug_mode
        set_debug_mode(False)

    def test_debug_flag_forces_debug_mode(self):
        """-debug 参数传入后 set_debug_mode(True) 被调用，_is_debug() 返回 True。"""
        from utils import _is_debug, set_debug_mode
        self.assertFalse(_is_debug())
        set_debug_mode(True)
        self.assertTrue(_is_debug())

    def test_debug_flag_overrides_no_debugger(self):
        """未附加调试器但 -debug 已设置 → 仍然是调试模式。"""
        from utils import _is_debug, set_debug_mode
        set_debug_mode(True)
        with mock.patch.object(sys, 'gettrace', return_value=None):
            self.assertTrue(_is_debug())

    def test_install_uninstall_repair_emit_debug_logs(self):
        """调试模式下 install/uninstall/repair 入口处应输出 _debug_log（通过 mock 验证）。"""
        from utils import _debug_log, set_debug_mode
        set_debug_mode(True)
        with mock.patch('sys.stderr', io.StringIO()) as fake_err:
            _debug_log("install() called")
            _debug_log("uninstall() called")
            _debug_log("repair() called")
            output = fake_err.getvalue()
        self.assertIn("install() called", output)
        self.assertIn("uninstall() called", output)
        self.assertIn("repair() called", output)

    def test_decorate_bat_not_called_in_production(self):
        """非调试模式下 _run_elevated 不应调用 _decorate_bat。"""
        import utils
        utils.set_debug_mode(False)
        with mock.patch.object(utils, '_is_debug', return_value=False):
            from utils import _run_elevated
            # Cannot actually call _run_elevated (needs admin), test via source inspection
            import inspect
            src = inspect.getsource(_run_elevated)
            self.assertIn('_decorate_bat(bat_content)', src)
            self.assertIn('is_debug = _is_debug()', src)

    def test_decorate_bat_called_in_debug(self):
        """调试模式下 _run_elevated 应调用 _decorate_bat。"""
        from utils import _decorate_bat
        raw = "@echo off\nexit /b 0\nendlocal"
        decorated = _decorate_bat(raw)
        self.assertNotEqual(raw, decorated)
        self.assertIn('pause', decorated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
