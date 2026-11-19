"""No USB access: exercise production guards with synthetic GPTs and failing DAs."""
from pathlib import Path
from types import SimpleNamespace
import ast
import contextlib
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from check_layout import check_bytes
from check_runtime import check as check_runtime
from device_guard import guard_command
from package_release import package
from verify_files import digest, verify, verify_readback

EXPECTED = json.loads((ROOT / 'tools/expected_layout.json').read_text())


def gpt(expected=EXPECTED, sector=512):
    entries = bytearray(128 * 128)
    for index, (name, partition) in enumerate(expected.items()):
        start = index * 128
        entries[start:start + 16] = b'X' * 16
        first = partition['offset'] // sector
        last = first + partition['size'] // sector - 1
        struct.pack_into('<QQ', entries, start + 32, first, last)
        encoded = name.encode('utf-16le')
        entries[start + 56:start + 56 + len(encoded)] = encoded
    header = bytearray(92)
    header[:8] = b'EFI PART'
    struct.pack_into('<I', header, 12, len(header))
    struct.pack_into('<Q', header, 24, 1)
    struct.pack_into('<QIII', header, 72, 2, 128, 128, zlib.crc32(entries) & 0xffffffff)
    struct.pack_into('<I', header, 16, zlib.crc32(header) & 0xffffffff)
    data = bytearray(max(8192, 2 * sector + len(entries)))
    data[sector:sector + len(header)] = header
    data[2 * sector:2 * sector + len(entries)] = entries
    return bytes(data)


def fixture(root):
    (root / 'tools').mkdir()
    (root / 'tools/expected_layout.json').write_text(json.dumps(EXPECTED))
    manifest = {}
    for folder in ('images', 'rollback'):
        (root / folder).mkdir()
        for name in ('super.img', 'vbmeta.img'):
            path = root / folder / name
            path.write_bytes((folder + name).encode())
            manifest[f'{folder}/{name}'] = digest(path)
    (root / 'SHA256SUMS.json').write_text(json.dumps(manifest))
    return manifest


class FakeDevice:
    def __init__(self, data=None, meid=b'A' * 16, sector=512):
        self.data = data if data is not None else gpt(sector=sector)
        self.meid = meid
        self.reads = []
        self.config = SimpleNamespace(pagesize=sector, chipconfig=SimpleNamespace(meid_addr=0x102b38))
        self.daloader = SimpleNamespace(readflash=self.read, peek=lambda *args: self.meid)

    def read(self, **args):
        self.reads.append(args)
        return self.data[args['addr']:args['addr'] + args['length']]


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = fixture(self.root)
        self.args = SimpleNamespace(directory=str(self.root / 'backup'), parttype=None, gpt_file=None,
                                    partitionname='super,vbmeta', filename=','.join(str(self.root / 'images' / name) for name in ('super.img', 'vbmeta.img')))

    def enroll(self, device):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(guard_command(device, 'gpt', self.args, self.root))

    def test_gpt_valid_wrong_size_crc_and_truncation(self):
        for sector in (512, 4096):
            with self.subTest(sector=sector):
                valid = gpt(sector=sector)
                self.assertEqual(check_bytes(valid, EXPECTED), sector)
                wrong = {name: dict(value) for name, value in EXPECTED.items()}
                wrong['super']['size'] += sector
                with self.assertRaisesRegex(ValueError, 'Partition mismatch'):
                    check_bytes(gpt(wrong, sector), EXPECTED)
                for offset in (sector + 16, sector * 2 + 1):
                    bad = bytearray(valid)
                    bad[offset] ^= 1
                    with self.assertRaisesRegex(ValueError, 'CRC'):
                        check_bytes(bad, EXPECTED)
                with self.assertRaises(ValueError):
                    check_bytes(valid[:sector + 80], EXPECTED)
                with self.assertRaises(ValueError):
                    check_bytes(valid[:-1], EXPECTED)

    def test_optimized_cli_rejects_bad_gpt_and_missing_or_changed_files(self):
        for name in ('check_layout.py', 'verify_files.py'):
            shutil.copyfile(ROOT / 'tools' / name, self.root / 'tools' / name)
        wrong = {name: dict(value) for name, value in EXPECTED.items()}
        wrong['super']['size'] += 512
        path = self.root / 'bad.bin'
        path.write_bytes(gpt(wrong))
        (self.root / 'images/super.img').unlink()
        for optimization in ('0', '1', '2'):
            env = dict(os.environ, PYTHONOPTIMIZE=optimization)
            for command in ([str(self.root / 'tools/check_layout.py'), str(path)], [str(self.root / 'tools/verify_files.py')]):
                result = subprocess.run([sys.executable, *command], env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('PASS', result.stdout)
            (self.root / 'images/super.img').write_bytes(b'corrupt')
            result = subprocess.run([sys.executable, str(self.root / 'tools/verify_files.py')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            (self.root / 'images/super.img').unlink()

    def test_source_only_is_explicit_and_never_packages_missing_images(self):
        (self.root / 'images/super.img').unlink()
        (self.root / 'rollback/super.img').unlink()
        self.assertEqual(verify(self.root, source_only=True), 2)
        with self.assertRaises(FileNotFoundError):
            verify(self.root)
        with self.assertRaises(FileNotFoundError):
            package(self.root / 'incomplete.zip', self.root)
        self.assertFalse((self.root / 'incomplete.zip').exists())
        (self.root / 'images/vbmeta.img').unlink()
        with self.assertRaises(FileNotFoundError):
            verify(self.root, source_only=True)

    def test_stock_check_skips_only_the_project_super(self):
        (self.root / 'images/super.img').unlink()
        script = self.root / 'tools/verify_files.py'
        shutil.copyfile(ROOT / 'tools/verify_files.py', script)

        def stock_check():
            return subprocess.run([sys.executable, '-O', str(script), '--stock'],
                                  capture_output=True, text=True, timeout=10)

        result = stock_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('PASS STOCK FILES (offline)', result.stdout)
        with self.assertRaises(FileNotFoundError):
            verify(self.root)
        for name in ('rollback/super.img', 'rollback/vbmeta.img', 'images/vbmeta.img'):
            with self.subTest(name=name):
                path = self.root / name
                data = path.read_bytes()
                path.write_bytes(b'damaged')
                result = stock_check()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn('Hash mismatch: ' + name, result.stdout)
                path.write_bytes(data)

    def test_manifest_omission_and_path_escape_are_rejected(self):
        del self.manifest['images/super.img']
        (self.root / 'SHA256SUMS.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, 'omits'):
            verify(self.root)
        self.manifest['images/super.img'] = '0' * 64
        self.manifest['../outside.bin'] = '0' * 64
        self.manifest = dict(reversed(list(self.manifest.items())))
        (self.root / 'SHA256SUMS.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            verify(self.root)

    def test_readback_uses_manifest_even_if_local_image_was_changed(self):
        (self.root / 'readback').mkdir()
        for name in ('super.img', 'vbmeta.img'):
            shutil.copyfile(self.root / 'images' / name, self.root / 'readback' / name)
        verify_readback(self.root)
        for folder in ('images', 'readback'):
            (self.root / folder / 'super.img').write_bytes(b'X' * len(b'imagessuper.img'))
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            verify_readback(self.root)

    def test_enrollment_and_current_connection_are_required(self):
        device = FakeDevice()
        with self.assertRaisesRegex(ValueError, 'differs'):
            guard_command(device, 'w', self.args, self.root)
        self.enroll(device)
        device.reads.clear()
        guard_command(device, 'w', self.args, self.root)
        self.assertGreaterEqual(len(device.reads), 2)
        self.assertTrue(all(call['filename'] == '' for call in device.reads))
        with self.assertRaisesRegex(ValueError, 'differs'):
            guard_command(FakeDevice(meid=b'B' * 16), 'w', self.args, self.root)
        device.meid = bytes(16)
        with self.assertRaisesRegex(RuntimeError, 'identifier'):
            guard_command(device, 'w', self.args, self.root)

    def test_4096_sector_device_uses_the_same_live_guard(self):
        device = FakeDevice(sector=4096)
        self.enroll(device)
        self.assertFalse(guard_command(device, 'w', self.args, self.root))
        device.config.pagesize = 512
        with self.assertRaisesRegex(ValueError, 'sector size'):
            guard_command(device, 'w', self.args, self.root)

    def test_new_layout_read_archives_the_old_binding(self):
        self.enroll(FakeDevice())
        before = (self.root / 'backup/device.json').read_bytes()
        shutil.copyfile(ROOT / 'tools/prepare_read.py', self.root / 'tools/prepare_read.py')
        result = subprocess.run([sys.executable, '-O', str(self.root / 'tools/prepare_read.py'), 'layout'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'backup/device.json').exists())
        history = list((self.root / 'backup/history').glob('*/device.json'))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].read_bytes(), before)

    def test_changed_live_gpt_and_override_are_rejected_before_write(self):
        device = FakeDevice()
        self.enroll(device)
        broken = bytearray(device.data)
        broken[1024] ^= 1
        device.data = bytes(broken)
        with self.assertRaisesRegex(ValueError, 'CRC'):
            guard_command(device, 'w', self.args, self.root)
        self.args.gpt_file = 'old-gpt.bin'
        with self.assertRaisesRegex(ValueError, 'overrides'):
            guard_command(FakeDevice(), 'w', self.args, self.root)

    def test_erase_confirmation_and_partition_limits(self):
        device = FakeDevice()
        self.enroll(device)
        self.args.partitionname = 'userdata,metadata,md_udc,cache'
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            guard_command(device, 'e', self.args, self.root, confirm=lambda _: '')
        phrase = 'ERASE ' + hashlib.sha256(device.meid).hexdigest()[:12]
        self.assertFalse(guard_command(device, 'e', self.args, self.root, confirm=lambda _: phrase))
        self.args.partitionname = 'nvram'
        with self.assertRaisesRegex(ValueError, 'limited'):
            guard_command(device, 'e', self.args, self.root, confirm=lambda _: phrase)

    def test_runtime_rejects_310_and_32bit(self):
        for version, pointer_size in [((3, 10), 8), ((3, 11), 4)]:
            with self.assertRaises(RuntimeError):
                check_runtime(version, pointer_size)
        check_runtime((3, 11), 8)

    def test_release_zip_contains_manifest_and_preserves_existing_output(self):
        output = self.root / 'release.zip'
        package(output, self.root)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), set(self.manifest) | {'SHA256SUMS.json'})
        previous = output.read_bytes()
        with self.assertRaises(FileExistsError):
            package(output, self.root)
        self.assertEqual(output.read_bytes(), previous)

    def test_runner_turns_operation_exception_into_nonzero_exit(self):
        for name in ('run_mtk.py', 'check_runtime.py'):
            shutil.copyfile(ROOT / 'tools' / name, self.root / 'tools' / name)
        source = self.root / 'tools/mtkclient'
        source.mkdir()
        (source / 'mtk.py').write_text("raise RuntimeError('synthetic DA failure')\n")
        result = subprocess.run([sys.executable, str(self.root / 'tools/run_mtk.py')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('STOP: synthetic DA failure', result.stdout)


class DaFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load the production methods without importing Windows USB/native modules.
        tree = ast.parse((ROOT / 'tools/mtkclient/mtkclient/Library/DA/mtk_da_handler.py').read_text())
        cls.methods = {}
        methods = [method for node in tree.body if isinstance(node, ast.ClassDef)
                   for method in node.body if isinstance(method, ast.FunctionDef)
                   and method.name in ('da_write', 'da_read', 'da_erase', 'handle_da_cmds')]
        exec(compile(ast.Module(body=methods, type_ignores=[]), '<production DA methods>', 'exec'), {'os': os, 'sys': sys}, cls.methods)

    def setUp(self):
        self.calls = []
        partition = SimpleNamespace(sector=8, sectors=16, name='super')
        self.loader = SimpleNamespace(
            detect_partition=lambda *args: (True, partition),
            writeflash=lambda **args: self.calls.append('write') or False,
            formatflash=lambda **args: self.calls.append('erase') or False,
            readflash=lambda **args: self.calls.append('read') or False,
            get_partition_data=lambda **args: [partition])
        self.handler = SimpleNamespace(mtk=SimpleNamespace(daloader=self.loader), config=SimpleNamespace(pagesize=512), info=lambda *args: None)

    def test_write_failure_stops_before_second_partition(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = [str(Path(temporary) / name) for name in ('super.img', 'vbmeta.img')]
            for path in paths:
                Path(path).write_bytes(b'data')
            with self.assertRaisesRegex(RuntimeError, 'Failed to write'):
                self.methods['da_write'](self.handler, 'user', paths, ['super', 'vbmeta'])
            self.assertEqual(self.calls, ['write'])
            self.calls.clear()
            Path(paths[1]).unlink()
            with self.assertRaises(FileNotFoundError):
                self.methods['da_write'](self.handler, 'user', paths, ['super', 'vbmeta'])
            self.assertEqual(self.calls, [])

    def test_erase_and_read_failure_stop_immediately(self):
        with self.assertRaisesRegex(RuntimeError, 'Failed to format'):
            self.methods['da_erase'](self.handler, ['userdata', 'metadata'], 'user')
        self.assertEqual(self.calls, ['erase'])
        self.calls.clear()
        with self.assertRaisesRegex(RuntimeError, 'Failed to dump'):
            self.methods['da_read'](self.handler, 'super,vbmeta', 'user', 'a.img,b.img')
        self.assertEqual(self.calls, ['read'])

    def test_guard_cancellation_prevents_dispatch(self):
        device = SimpleNamespace(daloader=SimpleNamespace())
        with patch.dict(os.environ, C30_PACKAGE_ROOT='synthetic'), patch('device_guard.guard_command', side_effect=RuntimeError('Erase cancelled')):
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                self.methods['handle_da_cmds'](self.handler, device, 'e', SimpleNamespace())
        self.assertEqual(self.calls, [])

    def test_main_preflight_fails_before_loading_or_connecting_hardware(self):
        tree = ast.parse((ROOT / 'tools/mtkclient/mtkclient/Library/mtk_main.py').read_text())
        method = next(method for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Main'
                      for method in node.body if isinstance(method, ast.FunctionDef) and method.name == 'run')
        namespace = {'os': os}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<production Main.run>', 'exec'), namespace)
        handler = SimpleNamespace(args=SimpleNamespace(cmd='w'))
        with patch.dict(os.environ, C30_PACKAGE_ROOT='synthetic'), patch('verify_files.verify', side_effect=ValueError('bad package')) as preflight:
            with self.assertRaisesRegex(ValueError, 'bad package'):
                namespace['run'](handler, None)
            preflight.assert_called_once()
        handler.args.cmd = 'wf'
        with patch.dict(os.environ, C30_PACKAGE_ROOT='synthetic'):
            with self.assertRaisesRegex(ValueError, 'only supports'):
                namespace['run'](handler, None)


if __name__ == '__main__':
    unittest.main()
