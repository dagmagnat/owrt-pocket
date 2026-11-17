"""Host tests for actual shell transaction functions, with isolated config files."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = os.environ.get('OWP_TEST_SHELL') or shutil.which('sh') or r'C:\Program Files\Git\bin\bash.exe'


class SafetyTests(unittest.TestCase):
    def run_shell(self, body, stdin=''):
        with tempfile.TemporaryDirectory(prefix='owp-test-') as temp:
            env = dict(os.environ, OWP_SOURCE_ONLY='1', NO_COLOR='1',
                       TEST_ROOT=Path(temp).as_posix(), SCRIPT=(ROOT / 'src/owp').as_posix())
            setup = '''
set -e
. "$SCRIPT"
BASE=$TEST_ROOT/state
CONFIG=$TEST_ROOT/config
mkdir -p "$BASE/transactions" "$CONFIG"
printf 'original-network\\n' > "$CONFIG/network"
printf 'original-wireless\\n' > "$CONFIG/wireless"
uci() { return 0; }
reload_all() { printf 'reload\\n' >> "$TEST_ROOT/reloads"; }
nohup() { :; }
sleep() { :; }
'''
            result = subprocess.run([SHELL, '-c', setup + body], env=env, input=stdin.encode('utf-8'),
                                    capture_output=True, timeout=15)
            output = (result.stdout + result.stderr).decode('utf-8')
            self.assertEqual(result.returncode, 0, output)
            return result.stdout.decode('utf-8')

    def test_rollback_restores_and_removes_new_files(self):
        self.run_shell('''
begin
id=${TX##*/}; printf '%s\\n' "$id" > "$BASE/pending"
printf 'changed\\n' > "$CONFIG/network"
printf 'new\\n' > "$CONFIG/dhcp"
rollback "$id"
grep -qx original-network "$CONFIG/network"
test ! -e "$CONFIG/dhcp"
test ! -e "$BASE/pending"
grep -qx rolled-back "$TX/result"
''')

    def test_confirm_wins_against_watchdog(self):
        self.run_shell('''
begin
id=${TX##*/}; printf '%s\\n' "$id" > "$BASE/pending"
touch "$TX/applied"
printf 'changed\\n' > "$CONFIG/network"
confirm
if rollback "$id"; then exit 1; fi
grep -qx changed "$CONFIG/network"
grep -qx confirmed "$TX/result"
''', 'Yes\n')

    def test_confirmation_is_case_sensitive(self):
        for answer in ('yes', 'YES', 'Y', '', 'Yes '):
            self.run_shell('if yes; then exit 1; fi\n', answer + '\n')

    def test_pending_prevents_second_transaction(self):
        self.run_shell('''
begin
printf '%s\\n' "${TX##*/}" > "$BASE/pending"
if begin; then exit 1; fi
''')

    def test_external_change_blocks_apply(self):
        self.run_shell('''
begin
printf 'other-admin\\n' > "$CONFIG/network"
if apply; then exit 1; fi
test ! -e "$BASE/pending"
grep -qx other-admin "$CONFIG/network"
''', 'Yes\n')

    def test_boot_recovers_interrupted_rollback(self):
        self.run_shell('''
begin
id=${TX##*/}; printf '%s\\n' "$id" > "$BASE/pending"
mkdir "$TX/claim"
printf 'changed\\n' > "$CONFIG/network"
rollback "$id" boot
grep -qx original-network "$CONFIG/network"
test ! -e "$TEST_ROOT/reloads"
''')

    def test_cancel_does_not_touch_live_config(self):
        self.run_shell('''
begin
printf 'changed\\n' > "$TX/stage/network"
if apply; then exit 1; fi
grep -qx original-network "$CONFIG/network"
test ! -e "$BASE/pending"
''', 'no\n')

    def test_worker_applies_staged_config(self):
        self.run_shell('''
begin
id=${TX##*/}; printf '%s\\n' "$id" > "$BASE/pending"
printf 'changed\\n' > "$TX/stage/network"
worker "$id"
grep -qx changed "$CONFIG/network"
test -f "$TX/applied"
test -f "$TEST_ROOT/reloads"
''')

    def test_validators_reject_injection(self):
        self.run_shell('''
ident wan
mac_valid AA:bb:cc:DD:ee:01
ipv4 192.168.1.25
if ident 'wan;reboot'; then exit 1; fi
if mac_valid 'aa:bb:cc:dd:ee:ff"'; then exit 1; fi
if ipv4 192.168.1.999; then exit 1; fi
if ipv4 '1.2.3.4;reboot'; then exit 1; fi
if load_tx '../../etc'; then exit 1; fi
''')

    def test_dirty_uci_blocks_begin(self):
        self.run_shell('''
uci() { printf 'network.wan.proto=static\\n'; }
if begin; then exit 1; fi
''')

    def test_demo_is_available_without_openwrt(self):
        result = subprocess.run([SHELL, (ROOT / 'src/owp').as_posix(), 'demo'], text=True, encoding='utf-8',
                                capture_output=True, timeout=10,
                                env=dict(os.environ, NO_COLOR='1'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('synthetic data', result.stdout)


if __name__ == '__main__':
    unittest.main()
