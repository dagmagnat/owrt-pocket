"""Compose firmware overlay; no package installation or router configuration on host."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile

p = argparse.ArgumentParser()
for name in ('repo', 'source', 'payload', 'overlay', 'output'):
    p.add_argument('--' + name, required=True, type=Path)
a = p.parse_args()
profile_dir = a.repo / 'firmware/cudy-wr300-v1'
profile = json.loads((profile_dir / 'profile.json').read_text())
assert hashlib.sha256(a.payload.read_bytes()).hexdigest() == profile['routewolf_archive_sha256']
a.overlay.mkdir(parents=True, exist_ok=True)
a.output.mkdir(parents=True, exist_ok=True)

def write(name, text, mode=0o644):
    dest = a.overlay / name.lstrip('/')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding='utf-8', newline='\n')
    dest.chmod(mode)

with tarfile.open(a.payload) as archive:
    members = archive.getmembers()
    assert len(members) == 30
    for member in members:
        path = PurePosixPath(member.name)
        assert member.isfile() and path.parts[0] == 'payload' and '..' not in path.parts
        dest = a.overlay.joinpath(*path.parts[1:])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(archive.extractfile(member).read())
        dest.chmod(0o755)

# The complete normalized lists are stored below. Raw source copies are build
# artifacts; keeping both on this 8-MB device would waste compressed flash.
shutil.rmtree(a.overlay / 'usr/share/routewolf/full-source', ignore_errors=True)

cache = a.overlay / 'etc/routewolf/lists'
cache.mkdir(parents=True, exist_ok=True)
report = a.output / 'list-validation.log'
# The user explicitly selected FULL. The existing source includes /7 networks.
# Keep every valid source range instead of the default /16 size policy; /0 and
# invalid/noncanonical/non-unicast entries remain subject to v59 validation.
env_script = '''
. "$1"
IPV6_SUPPORT=0
ROUTEWOLF_IPV4_MIN_PREFIX=7
VALIDATION_REPORT=$2
normalize_domain_list "$3/domains-dnsmasq-nfset.lst" "$4/domains.lst" &&
normalize_ipv4_cidr_list "$3/ipv4.lst" "$4/ipv4.lst"
'''
subprocess.run(['sh', '-c', env_script, 'prepare', (a.overlay / 'etc/init.d/routewolf').as_posix(),
                report.as_posix(), (a.source / 'lists').as_posix(), cache.as_posix()], check=True)
(cache / 'ipv6.lst').write_text('')
assert (cache / 'domains.lst').stat().st_size > 0 and (cache / 'ipv4.lst').stat().st_size > 0
write('/etc/routewolf/user.conf', """LIST_PROFILE='full'
DOMAINS_URL='https://raw.githubusercontent.com/dagmagnat/RouteWolf/main/lists/domains-dnsmasq-nfset.lst'
IPV4_URL='https://raw.githubusercontent.com/dagmagnat/RouteWolf/main/lists/ipv4.lst'
IPV6_URL=''
IPV6_SUPPORT='0'
ROUTEWOLF_IPV4_MIN_PREFIX='7'
""", 0o600)
write('/etc/routewolf/route.conf', "VPN_ROUTE_DEV=''\nVPN_ROUTE_GW=''\nVPN_ROUTE_MTU='1280'\n", 0o600)
write('/etc/routewolf/runtime_version', '59\n')
write('/etc/routewolf/installed_version', 'v59-list-validation\n')
write('/etc/routewolf/update.conf', 'AUTO_CODE_UPDATES=1\n', 0o600)
write('/etc/owrt-pocket/language', 'ru\n', 0o600)
write('/etc/owrt-pocket/wifi-always-on', '1\n', 0o600)

owp = (a.repo / 'src/owp').read_text(encoding='utf-8')
anchor = "wifi_menu() {\n"
assert owp.count(anchor) == 1
# The general project still supports Wi-Fi off. This dedicated profile guards it.
owp = owp.replace("   choice=$ANSWER; begin || return", "   choice=$ANSWER\n   if [ \"$choice\" = 2 ] && [ -f \"$BASE/wifi-always-on\" ]; then bad 'В этой прошивке Wi-Fi должен оставаться включённым'; return; fi\n   begin || return", 1)
write('/usr/sbin/owp', owp, 0o755)
write('/usr/sbin/rw-setup', (profile_dir / 'rw-setup').read_text(), 0o755)
write('/etc/init.d/owrt-pocket', '''#!/bin/sh /etc/rc.common
START=18
start() { /usr/sbin/owp _boot; }
''', 0o755)
write('/etc/init.d/pocket-lists', '''#!/bin/sh /etc/rc.common
START=17
start() {
 mkdir -p /tmp/dnsmasq.d /tmp/lst
 for item in domains ipv4 ipv6; do
  case "$item" in domains) target=/tmp/dnsmasq.d/domains.lst;; *) target=/tmp/lst/$item.lst;; esac
  [ -f "$target" ] || cp "/etc/routewolf/lists/$item.lst" "$target"
 done
}
''', 0o755)

firstboot = r'''#!/bin/sh
# Factory defaults only: uci-defaults is removed after successful first boot.
set -eu
uci -q get wireless.radio0 >/dev/null || wifi config
for radio in $(uci show wireless | sed -n 's/^wireless\.\([^.=]*\)=wifi-device$/\1/p'); do
 uci set "wireless.$radio.disabled=0"
 uci set "wireless.$radio.country=00"
 uci set "wireless.$radio.channel=6"
 uci set "wireless.$radio.htmode=HT20"
done
found=0
for iface in $(uci show wireless | sed -n 's/^wireless\.\([^.=]*\)=wifi-iface$/\1/p'); do
 [ "$(uci -q get "wireless.$iface.mode")" = ap ] || continue
 uci set "wireless.$iface.disabled=0"
 uci set "wireless.$iface.network=lan"
 uci set "wireless.$iface.ssid=Cudy_WR-300"
 uci set "wireless.$iface.encryption=none"
 uci -q delete "wireless.$iface.key" || :
 found=1
done
[ "$found" = 1 ]
uci commit wireless
# These open-access defaults were explicitly requested by the owner.
sed -i 's/^root:[^:]*:/root::/' /etc/shadow
uci set luci.main.lang=ru
uci commit luci
uci set network.wan.proto=dhcp
uci set network.wan.auto=1
uci commit network
uci set network.wg0=interface
uci set network.wg0.proto=wireguard
uci set network.wg0.auto=0
uci set network.wg0.mtu=1280
uci set network.awg0=interface
uci set network.awg0.proto=amneziawg
uci set network.awg0.auto=0
uci set network.awg0.mtu=1280
uci commit network
uci set dhcp.@dnsmasq[0].confdir=/tmp/dnsmasq.d
uci set dhcp.@dnsmasq[0].filter_aaaa=1
uci commit dhcp
# Ordinary WAN/LAN remain the board defaults; remote WAN management stays blocked.
# Do not force flow offload across policy-routing marks without hardware tests.
uci set firewall.@defaults[0].flow_offloading=0
uci set firewall.@defaults[0].flow_offloading_hw=0
uci set firewall.rw_domains=ipset
uci set firewall.rw_domains.name=vpn_domains
uci set firewall.rw_domains.family=ipv4
uci set firewall.rw_domains.match=dst_ip
uci set firewall.rw_subnets=ipset
uci set firewall.rw_subnets.name=vpn_subnets
uci set firewall.rw_subnets.family=ipv4
uci set firewall.rw_subnets.match=dst_net
uci set firewall.rw_subnets.loadfile=/tmp/lst/ipv4.lst
for kind in domains subnets; do
 uci set "firewall.rw_mark_$kind=rule"
 uci set "firewall.rw_mark_$kind.name=mark_$kind"
 uci set "firewall.rw_mark_$kind.src=lan"
 uci set "firewall.rw_mark_$kind.dest=*"
 uci set "firewall.rw_mark_$kind.proto=all"
 uci set "firewall.rw_mark_$kind.ipset=vpn_$kind"
 uci set "firewall.rw_mark_$kind.target=MARK"
 uci set "firewall.rw_mark_$kind.set_mark=0x1"
 uci set "firewall.rw_mark_$kind.family=ipv4"
done
for kind in wg awg; do
 uci set "firewall.rw_$kind=zone"
 uci set "firewall.rw_$kind.name=$kind"
 uci set "firewall.rw_$kind.network=${kind}0"
 uci set "firewall.rw_$kind.input=REJECT"
 uci set "firewall.rw_$kind.output=ACCEPT"
 uci set "firewall.rw_$kind.forward=REJECT"
 uci set "firewall.rw_$kind.masq=1"
 uci set "firewall.rw_$kind.mtu_fix=1"
 uci set "firewall.rw_forward_$kind=forwarding"
 uci set "firewall.rw_forward_$kind.src=lan"
 uci set "firewall.rw_forward_$kind.dest=$kind"
done
uci commit firewall
/etc/init.d/pocket-lists enable
/etc/init.d/pocket-lists start
/etc/init.d/owrt-pocket enable
/etc/init.d/routewolf enable
/etc/init.d/routewolf-route enable
/etc/init.d/routewolf-watchdog disable
/etc/init.d/getdomains disable
/etc/init.d/vpnroute disable
mkdir -p /etc/crontabs
touch /etc/crontabs/root
printf '0 2 * * * /usr/sbin/routewolf-update.sh --lists-auto >/tmp/routewolf-lists-update.log 2>&1\n0 3 * * * /usr/sbin/routewolf-update.sh --code-auto >/tmp/routewolf-code-update.log 2>&1\n*/5 * * * * /usr/sbin/routewolf-reliability.sh check >/tmp/routewolf-health.log 2>&1\n' >> /etc/crontabs/root
exit 0
'''
write('/etc/uci-defaults/99-cudy-pocket', firstboot, 0o755)
for path in a.overlay.rglob('*'):
    if path.is_file() and (path.read_bytes().startswith(b'#!/bin/sh') or path.name == '99-cudy-pocket'):
        subprocess.run(['sh', '-n', path.as_posix()], check=True)
counts = {
    'raw_domains': len((a.source / 'lists/domains-dnsmasq-nfset.lst').read_text().splitlines()),
    'raw_ipv4': len((a.source / 'lists/ipv4.lst').read_text().splitlines()),
    'effective_domain_rules': len((cache / 'domains.lst').read_text().splitlines()),
    'effective_ipv4_ranges': len((cache / 'ipv4.lst').read_text().splitlines()),
    'profile': 'full', 'minimum_ipv4_prefix': 7,
    'runtime_files': len(members), 'routewolf_commit': profile['routewolf_commit'],
}
(a.output / 'integration.json').write_text(json.dumps(counts, indent=2) + '\n')
print(json.dumps(counts))
