"""Verify contents and bounds; this is not a hardware boot test."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
for name in ('root', 'image', 'profiles', 'output'):
    p.add_argument('--' + name, required=True, type=Path)
a = p.parse_args()
profile = json.loads(a.profiles.read_text())['profiles']['cudy_wr300-v1']
metadata = json.loads((a.output / 'image-metadata.json').read_text())
assert 'cudy,wr300-v1' in metadata['supported_devices'], metadata
assert metadata['version']['target'] == 'ramips/mt76x8', metadata
required = ['usr/sbin/owp', 'usr/sbin/rw', 'usr/sbin/rw-setup',
            'etc/init.d/routewolf', 'etc/init.d/pocket-lists',
            'etc/uci-defaults/99-cudy-pocket', 'etc/owrt-pocket/language',
            'etc/routewolf/lists/domains.lst', 'etc/routewolf/lists/ipv4.lst',
            'lib/netifd/proto/wireguard.sh']
for name in required:
    assert (a.root / name).is_file(), 'Missing ' + name
assert any((a.root / 'lib/netifd/proto' / name).is_file() for name in ('amneziawg.sh', 'awg.sh'))
for name in ('wg', 'awg'):
    assert any((a.root / directory / name).is_file() for directory in ('usr/bin', 'usr/sbin', 'bin', 'sbin')), name
for name in ('wireguard.ko', 'amneziawg.ko'):
    assert list((a.root / 'lib/modules').rglob(name)), name
assert list((a.root / 'usr/lib/lua/luci/i18n').glob('base.ru.lmo')) or list((a.root / 'usr/share').rglob('base.ru.lmo')), 'Russian LuCI translation missing'
assert (a.root / 'etc/owrt-pocket/language').read_text().strip() == 'ru'
assert (a.root / 'etc/routewolf/user.conf').read_text().find("LIST_PROFILE='full'") >= 0
assert 'Cudy_WR-300' in (a.root / 'etc/uci-defaults/99-cudy-pocket').read_text()
assert (a.root / 'usr/libexec/ip-tiny').is_file(), 'Policy-routing ip utility missing'
assert not (a.root / 'usr/libexec/ip-full').exists(), 'Unexpected full ip utility'
for service in ('getdomains', 'vpnroute', 'routewolf-watchdog'):
    assert not list((a.root / 'etc/rc.d').glob('S*' + service)), 'Duplicate or premature startup: ' + service
size = a.image.stat().st_size
limit = profile['file_size_limits']['image']
reserve = limit - size
result = {'device': 'Cudy WR300 v1', 'target': 'ramips/mt76x8',
          'bytes': size, 'profile_image_limit': limit,
          'estimated_partition_headroom_bytes': reserve,
          'sha256': hashlib.sha256(a.image.read_bytes()).hexdigest(),
          'hardware_boot_tested': False, 'throughput_tested': False,
          'note': 'Headroom is a size estimate, not measured free JFFS2 space.'}
(a.output / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
assert size <= limit, 'Image exceeds the exact device profile limit'
assert reserve >= 1048576, 'Less than 1 MiB estimated writable headroom; requirements need review'
