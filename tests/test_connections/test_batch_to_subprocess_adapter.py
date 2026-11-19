import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests.import_helper import add_src_to_path

add_src_to_path()

from connections.batch_extension.batch_to_subprocess_adapter import \
    BatchToSubprocessAdapter, _validate_path  # noqa: E402


class TestValidatePath(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.script = self.dir / 'executor.py'
        self.script.write_text('print(1)')

    def test_valid_file(self):
        self.assertEqual(str(self.script.resolve()),
                         _validate_path(str(self.script), 'X', suffix='.py'))

    def test_valid_executable(self):
        self.assertEqual(str(Path(sys.executable).resolve()),
                         _validate_path(sys.executable, 'X', executable=True))

    def test_missing(self):
        with self.assertRaises(ValueError):
            _validate_path(str(self.dir / 'nope.py'), 'X')

    def test_directory(self):
        with self.assertRaises(ValueError):
            _validate_path(str(self.dir), 'X')

    def test_control_chars(self):
        for bad in ('a\nb', 'a\x00b', ''):
            with self.assertRaises(ValueError):
                _validate_path(bad, 'X')

    def test_injection_string(self):
        with self.assertRaises(ValueError):
            _validate_path('/bin/python; rm -rf /', 'X')

    def test_wrong_suffix(self):
        txt = self.dir / 'a.txt'
        txt.write_text('x')
        with self.assertRaises(ValueError):
            _validate_path(str(txt), 'X', suffix='.py')

    @unittest.skipIf(os.name == 'nt', 'POSIX exec bit')
    def test_not_executable(self):
        self.script.chmod(0o644)
        with self.assertRaises(ValueError):
            _validate_path(str(self.script), 'X', executable=True)


class TestResolvers(unittest.TestCase):
    def test_env_unset_falls_back(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('VENV_PATH', None)
            os.environ.pop('EXECUTOR_PATH', None)
            self.assertTrue(BatchToSubprocessAdapter.resolve_executor_venv())
            self.assertTrue(BatchToSubprocessAdapter.resolve_executor_path())

    def test_bad_env_rejected(self):
        with patch.dict(os.environ, {'VENV_PATH': '/x; id',
                                     'EXECUTOR_PATH': '/x; id'}):
            with self.assertRaises(ValueError):
                BatchToSubprocessAdapter.resolve_executor_venv()
            with self.assertRaises(ValueError):
                BatchToSubprocessAdapter.resolve_executor_path()


if __name__ == '__main__':
    unittest.main()
