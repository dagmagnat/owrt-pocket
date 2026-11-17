# OWRT Pocket

A colourful SSH terminal companion for OpenWrt. **0.1.0 is an experimental first version; use a spare router for hardware validation.** Russian and English menus, remembered language, `0` back, case-sensitive `Yes` for changes.

Requires OpenWrt `/bin/sh`, UCI, ubus, jsonfilter, ip and nohup. No Python, Bash or cloud service is needed on the router. Target versions are OpenWrt 24.10/25.12; real hardware has not yet been validated.

```sh
cd /tmp
wget -O owrt-pocket.tar.gz https://codeload.github.com/dagmagnat/owrt-pocket/tar.gz/refs/heads/main
tar -xzf owrt-pocket.tar.gz
cd owrt-pocket-main
sh install.sh
owp
```

Review the code first, save an off-device OpenWrt backup, and keep Ethernet recovery access. Pin a reviewed commit instead of `main` for reproducibility. Offline installation works by copying the full archive using SCP/SFTP.

Commands: `owp`, `owp status`, `owp clients`, `owp interfaces`, `owp doctor`, `owp scan`, `owp confirm`, `owp rollback`, `owp demo`. Change language in menu 9 → 1. `NO_COLOR=1` disables ANSI colours. Run `sh src/owp demo` on a normal computer for a synthetic preview.

Features include status/RAM/storage/routes, DHCP and Wi-Fi client inspection, current-lease MAC/IP reservations, temporary 60-second Wi-Fi client bans, Wi-Fi on/off and personal WPA2/WPA3 credentials, network/DNS/VPN diagnostics, bounded LAN ICMP scanning, DNS restart, WAN renew, temporary VPN service stops, basic tunnel interface management, package installation through apk/opkg, service status and root password changes.

Configuration changes snapshot `network`, `wireless`, `dhcp` and `firewall`, ask for `Yes`, start a detached watchdog, and apply after two seconds. Without `owp confirm` and another `Yes`, the previous files return after 120 seconds. A boot recovery hook restores an unfinished transaction before network startup. Keep Wi-Fi off permanently only by confirming over Ethernet/another network; otherwise it will return automatically. Do not edit these files concurrently through LuCI or another tool: rollback restores whole files.

Package operations and root password changes have **no automatic rollback**. Temporary VPN stops start a 120-second recovery timer, do not change autostart, and do not guarantee removal of third-party kill-switch rules. No VPN removal or universal automatic repair is implemented.

WAN port replacement supports only conservatively detected simple DSA layouts: unfiltered `br-lan`, at least two LAN ports, existing `wan`, and an existing masqueraded WAN firewall zone with DROP/REJECT input. It removes the chosen port from LAN and moves WAN to it. VLAN/swconfig/complex layouts are refused. PPPoE reuses the existing WAN device and firewall zone; provider VLAN and custom IPv6 need separate configuration.

Backups contain plaintext Wi-Fi/PPPoE secrets, as normal UCI does; they are root-only and must never be published. After 20 prepared transactions, archive/remove completed transaction directories before continuing. Never remove a pending transaction. Logs may contain local addresses. Diagnostics contact two public ICMP targets and resolve `openwrt.org`; package installs use configured feeds. No telemetry is built in.

Lease counts are not online-client counts; bitrate is not an internet speed test. ICMP failure is not proof of an outage. Root renaming, arbitrary new networks, full VLAN setup and unsupported interface shutdowns are outside this version. Detailed output scrolls in the terminal.

See [Russian documentation](README.md) and the [hardware test plan](TESTING.md) for full limitations and recovery steps. Host tests use mocked router commands and do not establish hardware compatibility. MIT licensed.
