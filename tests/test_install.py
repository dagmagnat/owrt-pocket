"""Execute the standalone installer with isolated storage and a fake downloader."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = os.environ.get('OWP_TEST_SHELL') or shutil.which('sh') or r'C:\Program Files\Git\bin\bash.exe'


class InstallTests(unittest.TestCase):
    def install(self, mode='ok', local=False, pending=False):
        with tempfile.TemporaryDirectory(prefix='owp-install-test-') as temp:
            base = Path(temp)
            for directory in ('etc/owrt-pocket', 'usr/sbin', 'tmp'):
                (base / directory).mkdir(parents=True)
            (base / 'etc/openwrt_release').write_text('DISTRIB_ID=OpenWrt\n')
            (base / 'etc/owrt-pocket/language').write_text('ru\n')
            (base / 'usr/sbin/owp').write_bytes(b'previous menu\n')
            if pending:
                (base / 'etc/owrt-pocket/pending').write_text('transaction\n')
            payload = base / 'payload'
            payload.write_bytes((ROOT / 'src/owp').read_bytes() if mode != 'bad-hash' else b'bad download\n')
            script = (ROOT / 'install.sh').read_text(encoding='utf-8')
            # Do not execute the real init framework or touch host/router paths.
            script = script.replace('\n/etc/init.d/owrt-pocket enable\n',
                                    '\nprintf enabled > "$TEST_ROOT/enabled"\n')
            for original in ('/etc/', '/usr/sbin', '/tmp/owrt-pocket.'):
                replacement = base.as_posix() + original
                script = script.replace(original, replacement)
            prefix = '''
id() { echo 0; }
uci() { :; }
ubus() { :; }
jsonfilter() { :; }
ip() { :; }
nohup() { :; }
wget() {
 printf '%s\n' "$3" >> "$TEST_ROOT/downloads"
 if [ "$DOWNLOAD_MODE" = live ]; then
  if [ "$REAL_DOWNLOADER" = wget ]; then command wget -O "$2" "$3"
  else command curl -fL -o "$2" "$3"; fi
  return
 fi
 [ "$DOWNLOAD_MODE" != failed ] || return 1
 cp "$TEST_ROOT/payload" "$2"
}
'''
            env = dict(os.environ, TEST_ROOT=base.as_posix(), DOWNLOAD_MODE=mode,
                       REAL_DOWNLOADER='wget' if shutil.which('wget') else 'curl')
            result = subprocess.run([SHELL, '-c', prefix + script,
                                     str(ROOT / 'install.sh'), *(['--local'] if local else [])],
                                    env=env, capture_output=True, timeout=15)
            installed = (base / 'usr/sbin/owp').read_bytes()
            self.assertEqual((base / 'etc/owrt-pocket/language').read_text(), 'ru\n')
            self.assertEqual(list((base / 'tmp').iterdir()), [], 'Temporary download leaked')
            self.assertEqual(list((base / 'usr/sbin').glob('.owp-install.*')), [])
            if result.returncode == 0:
                self.assertEqual(installed, (ROOT / 'src/owp').read_bytes())
                self.assertTrue((base / 'etc/init.d/owrt-pocket').is_file())
                self.assertTrue((base / 'enabled').is_file())
            else:
                self.assertEqual(installed, b'previous menu\n', 'Failed download replaced working menu')
                self.assertFalse((base / 'enabled').exists())
            return result, (base / 'downloads').exists()

    def test_online_without_checkout(self):
        result, downloaded = self.install()
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8'))
        self.assertTrue(downloaded)

    def test_download_failure_keeps_previous_menu(self):
        result, _ = self.install(mode='failed')
        self.assertNotEqual(result.returncode, 0)

    def test_hash_mismatch_keeps_previous_menu(self):
        result, _ = self.install(mode='bad-hash')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'SHA-256', result.stderr)

    def test_pending_change_blocks_download(self):
        result, downloaded = self.install(pending=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(downloaded)

    def test_offline_install_needs_no_downloader(self):
        result, downloaded = self.install(local=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8'))
        self.assertFalse(downloaded)

    @unittest.skipUnless(os.environ.get('OWP_INSTALL_LIVE_DOWNLOAD') == '1', 'Opt-in live GitHub download')
    def test_live_github_download(self):
        result, downloaded = self.install(mode='live')
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8'))
        self.assertTrue(downloaded)
