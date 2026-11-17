"""Host tests for actual shell transaction functions, with isolated config files."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SHELL = os.environ.get('OWP_TEST_SHELL') or shutil.which('sh') or r'C:\Program Files\Git\bin\bash.exe'


class SafetyTests(unittest.TestCase):
    def run_shell(self, body, stdin='', router=None):
        with tempfile.TemporaryDirectory(prefix='owp-test-') as temp:
            env = dict(os.environ, OWP_SOURCE_ONLY='1', NO_COLOR='1',
                       TEST_ROOT=Path(temp).as_posix(), SCRIPT=(ROOT / 'src/owp').as_posix(),
                       PYTHON=sys.executable.replace('\\', '/'),
                       FIXTURE=(ROOT / 'tests/router_fixture.py').as_posix(),
                       ROUTER_FIXTURE=json.dumps(router or {}))
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
ubus() { "$PYTHON" "$FIXTURE" ubus "$@"; }
jsonfilter() {
 if [ -n "${OWP_REAL_JSONFILTER:-}" ]; then "$OWP_REAL_JSONFILTER" "$@"
 else "$PYTHON" "$FIXTURE" jsonfilter "$@"; fi
}
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

    def test_subnet_overlap_handles_non_24_masks(self):
        self.run_shell('''
overlap 192.168.1.1 24 192.168.1.254 24
overlap 10.12.0.1 16 10.12.99.1 24
overlap 172.16.0.1 12 172.31.9.1 24
overlap 192.168.50.1 24 192.168.50.1 32
if overlap 192.168.1.1 24 192.168.50.1 24; then exit 1; fi
if overlap 192.168.1.1 25 192.168.1.200 25; then exit 1; fi
if overlap 1.2.3.4 33 1.2.3.4 24; then exit 1; fi
if overlap 1.2.3.999 24 1.2.3.4 24; then exit 1; fi
''')

    def test_private_lan_and_control_character_validation(self):
        self.run_shell('''
private_lan 192.168.50.1
private_lan 10.5.0.254
if private_lan 8.8.8.8; then exit 1; fi
if private_lan 172.32.0.1; then exit 1; fi
if private_lan 192.168.1.0; then exit 1; fi
if private_lan 192.168.1.255; then exit 1; fi
safe_text 'Cafe "$HOME" ; test'
if safe_text "$(printf 'SSID\\033[31m')"; then exit 1; fi
if psk_valid short; then exit 1; fi
psk_valid 'long password'
''')

    def test_lan_change_rejects_dhcp_pool_address(self):
        self.run_shell('if choose_lan; then exit 1; fi\n', '192.168.50.150\n')

    def test_new_lan_rejects_existing_uplink_overlap(self):
        self.run_shell('''
sections() { printf 'lan\\nowp_wwan\\n'; }
if choose_lan; then exit 1; fi
''', '192.168.50.1\n', router={
            'network.interface.owp_wwan': {'ipv4-address': [{'address': '192.168.50.20', 'mask': 24}]}})

    def test_repeater_confirmation_waits_for_verification(self):
        self.run_shell('''
begin
printf '%s\\n' "${TX##*/}" > "$BASE/pending"
touch "$TX/applied" "$TX/repeater"
if confirm; then exit 1; fi
test -f "$BASE/pending"
test ! -d "$TX/claim"
''', 'Yes\n')

    def test_worker_rolls_back_failed_repeater(self):
        self.run_shell('''
begin
id=${TX##*/}; printf '%s\\n' "$id" > "$BASE/pending"
touch "$TX/repeater"
printf 'changed\\n' > "$TX/stage/network"
repeater_verify() { return 1; }
if worker "$id"; then exit 1; fi
grep -qx original-network "$CONFIG/network"
test ! -e "$BASE/pending"
test ! -e "$TX/uplink-ready"
''')

    def test_repeater_detects_secondary_lan_subnet_conflict(self):
        self.run_shell('''
begin
printf '%s\\n' "${TX##*/}" > "$BASE/pending"
sections() { printf 'lan\\nowp_wwan\\n'; }
if repeater_verify; then exit 1; fi
grep -q '192.168.1.2/24' "$BASE/repeater-result"
''', router={
            'network.interface.owp_wwan': {'up': True, 'ipv4-address': [{'address': '192.168.1.2', 'mask': 24}]},
            'network.interface.lan': {'ipv4-address': [
                {'address': '192.168.50.1', 'mask': 24}, {'address': '192.168.1.1', 'mask': 24}]}})

    def test_repeater_accepts_disjoint_networks(self):
        self.run_shell('''
begin
printf '%s\\n' "${TX##*/}" > "$BASE/pending"
sections() { printf 'lan\\nowp_wwan\\n'; }
repeater_verify
grep -q 'owp confirm' "$BASE/repeater-result"
''', router={
            'network.interface.owp_wwan': {'up': True, 'ipv4-address': [{'address': '192.168.1.2', 'mask': 24}]},
            'network.interface.lan': {'ipv4-address': [{'address': '192.168.50.1', 'mask': 24}]}})

    def test_repeater_no_dhcp_address_times_out(self):
        self.run_shell('''
begin
printf '%s\\n' "${TX##*/}" > "$BASE/pending"
if repeater_verify; then exit 1; fi
grep -q 'DHCP' "$BASE/repeater-result"
''', router={'network.interface.owp_wwan': {'up': False}})

    def test_repeater_does_not_overwrite_unmanaged_names(self):
        self.run_shell('''
get() { case "$1" in network.owp_wwan) printf 'interface\\n';; esac; }
RADIO=radio0; AP=default_radio0; LAN_ADDR=
UP_SSID='Example'; UP_KEY='long password'; BSSID=AA:BB:CC:DD:EE:FF; CHANNEL=1; ENC=psk2
if repeater_stage; then exit 1; fi
test -z "$TX"
''')

    def test_repeater_stages_isolated_firewall_without_changing_ap_key(self):
        self.run_shell('''
get() { :; }
stage() { printf '%s\\n' "$*" >> "$TEST_ROOT/stage-commands"; }
RADIO=radio0; AP=default_radio0; LAN_ADDR=
UP_SSID='Cafe "$HOME"; test'; UP_KEY='long password'; BSSID=AA:BB:CC:DD:EE:FF; CHANNEL=1; ENC=psk2
repeater_stage
grep -qx 'set network.owp_wwan.proto=dhcp' "$TEST_ROOT/stage-commands"
grep -qx 'set firewall.owp_uplink.input=REJECT' "$TEST_ROOT/stage-commands"
grep -qx 'set firewall.owp_forward.dest=owp_uplink' "$TEST_ROOT/stage-commands"
if grep -q 'default_radio0.key' "$TEST_ROOT/stage-commands"; then exit 1; fi
test -f "$TX/repeater"
test ! -e "$BASE/pending"
''')

    def test_dhcp_switch_removes_pppoe_credentials_and_disables_owned_repeater(self):
        self.run_shell('''
begin
stage() { printf '%s\\n' "$*" >> "$TEST_ROOT/stage-commands"; }
get() { case "$1" in network.owp_wwan.owp_managed) printf '1\\n';; esac; }
dhcp_stage
grep -qx 'set network.wan.proto=dhcp' "$TEST_ROOT/stage-commands"
grep -qx -- '-q delete network.wan.password' "$TEST_ROOT/stage-commands"
grep -qx 'set wireless.owp_sta.disabled=1' "$TEST_ROOT/stage-commands"
grep -qx owp_wwan "$TX/down-interface"
''')

    @unittest.skipUnless(os.environ.get('OWP_REAL_UCI'), 'Native UCI integration runs in CI')
    def test_native_uci_repeater_staging_and_dhcp_switch(self):
        self.run_shell('''
mkdir -p "$TEST_ROOT/global-delta"
uci() { "$OWP_REAL_UCI" -c "$CONFIG" -t "$TEST_ROOT/global-delta" "$@"; }
# Use valid real UCI packages rather than the transaction-only text fixtures.
: > "$CONFIG/network"; : > "$CONFIG/wireless"
: > "$CONFIG/firewall"; : > "$CONFIG/dhcp"
uci set network.lan=interface
uci set network.lan.proto=static
uci set network.lan.ipaddr=192.168.50.1
uci set network.lan.netmask=255.255.255.0
uci set network.wan=interface
uci set network.wan.device=eth0.2
uci set network.wan.proto=pppoe
uci set network.wan.username=provider
uci set network.wan.password=provider-secret
uci set wireless.radio0=wifi-device
uci set wireless.radio0.type=mac80211
uci set wireless.default_radio0=wifi-iface
uci set wireless.default_radio0.device=radio0
uci set wireless.default_radio0.network=lan
uci set wireless.default_radio0.mode=ap
uci set wireless.default_radio0.key=original-ap-key
uci set firewall.lan=zone
uci set firewall.lan.name=lan
uci set firewall.lan.network=lan
uci set dhcp.lan=dhcp
uci set dhcp.lan.interface=lan
for package in network wireless firewall dhcp; do uci commit "$package"; done
RADIO=radio0; AP=default_radio0; LAN_ADDR=
UP_SSID='Cafe "$HOME"; test'; UP_KEY='long password'; BSSID=AA:BB:CC:DD:EE:FF; CHANNEL=1; ENC=psk2
repeater_stage
test "$(stage get wireless.owp_sta.ssid)" = "$UP_SSID"
test "$(stage get wireless.default_radio0.key)" = original-ap-key
test "$(stage get network.owp_wwan.proto)" = dhcp
test "$(stage get firewall.owp_uplink.input)" = REJECT
test -z "$(get network.owp_wwan)"
dhcp_stage
test "$(stage get network.wan.proto)" = dhcp
test "$(get network.wan.proto)" = pppoe
if stage -q get network.wan.password; then exit 1; fi
for package in network wireless firewall dhcp; do stage commit "$package"; done
test "$(stage get wireless.owp_sta.ssid)" = "$UP_SSID"
''')

    @unittest.skipUnless(os.environ.get('OWP_REAL_JSONFILTER'), 'Native jsonfilter integration runs in CI')
    def test_native_scan_result_paths(self):
        self.run_shell('''
SCAN='{"results":[{"ssid":"Cafe \\"quoted\\"","bssid":"AA:BB:CC:DD:EE:FF","channel":1,"encryption":{"wpa":[2,3],"authentication":["psk","sae"]}}]}'
ROW=0
test "$(row_value ssid)" = 'Cafe "quoted"'
row_value 'encryption.wpa[*]' | grep -qx 2
row_value 'encryption.authentication[*]' | grep -qx psk
''')


if __name__ == '__main__':
    unittest.main()
