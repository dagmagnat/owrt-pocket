# OWRT Pocket

A colourful SSH control panel for OpenWrt. **Version 0.3.0.** Russian and English menus, remembered language, `0` back, case-sensitive `Yes` for changes.

Requires OpenWrt `/bin/sh`, UCI, ubus, jsonfilter and ip. Wi-Fi client details use the system's `jshn` and hostapd. Target versions are OpenWrt 24.10/25.12.

```sh
wget -O /tmp/owrt-pocket-install.sh https://raw.githubusercontent.com/dagmagnat/owrt-pocket/main/install.sh && sh /tmp/owrt-pocket-install.sh
```

Run that single command in the router's SSH session. The router downloads the
pinned 0.3.0 menu directly from GitHub and verifies its SHA-256 before installation.
No archive or manual file transfer is needed. After the success message, run:

```sh
owp
```

Review [install.sh](install.sh), save an off-device OpenWrt backup, and keep Ethernet
recovery access. HTTPS internet access is required; check DNS, time and certificates
if downloads fail. Never disable certificate verification. If wget is unavailable:

```sh
curl -fL -o /tmp/owrt-pocket-install.sh https://raw.githubusercontent.com/dagmagnat/owrt-pocket/main/install.sh && sh /tmp/owrt-pocket-install.sh
```

The same command reinstalls the tool while preserving language and settings.
Pending network changes must be confirmed or rolled back before installation.
Offline installation remains available: transfer and extract the complete project,
then run `sh install.sh --local` from its directory.

Commands: `owp`, `owp status`, `owp clients`, `owp interfaces`, `owp doctor`, `owp scan`, `owp confirm`, `owp rollback`, `owp demo`. Change language in menu 9 → 1. `NO_COLOR=1` disables ANSI colours. Run `sh src/owp demo` on a normal computer for a synthetic preview.

Status displays CPU, RAM and flash usage as percentages. Clients are grouped by MAC and show their name, IPv4 and presence when known. Interfaces show connection state, addresses, one-second RX/TX rates and cumulative device counters. Press `1` on the interfaces screen to sample again. Use `owp doctor --details` for technical output. For terminals that support ANSI but miss automatic colour detection, run `OWP_COLOR=always owp`.

Features include status/RAM/storage/routes, DHCP and Wi-Fi client inspection, current-lease MAC/IP reservations, temporary 60-second Wi-Fi client bans, Wi-Fi on/off and personal WPA2/WPA3 credentials, network/DNS/VPN diagnostics, bounded LAN ICMP scanning, DNS restart, WAN renew, temporary VPN service stops, basic tunnel interface management, package installation through apk/opkg, service status and root password changes.

Configuration changes snapshot `network`, `wireless`, `dhcp` and `firewall`, ask for `Yes`, start a detached watchdog, and apply after two seconds. Without `owp confirm` and another `Yes`, the previous files return after 120 seconds. A boot recovery hook restores an unfinished transaction before network startup. Keep Wi-Fi off permanently only by confirming over Ethernet/another network; otherwise it will return automatically. Do not edit these files concurrently through LuCI or another tool: rollback restores whole files.

Package operations and root password changes have **no automatic rollback**. Temporary VPN stops start a 120-second recovery timer, do not change autostart, and do not guarantee removal of third-party kill-switch rules. No VPN removal or universal automatic repair is implemented.

WAN port replacement supports only conservatively detected simple DSA layouts: unfiltered `br-lan`, at least two LAN ports, existing `wan`, and an existing masqueraded WAN firewall zone with DROP/REJECT input. It removes the chosen port from LAN and moves WAN to it. VLAN/swconfig/complex layouts are refused. PPPoE reuses the existing WAN device and firewall zone; provider VLAN and custom IPv6 need separate configuration.

Backups contain plaintext Wi-Fi/PPPoE secrets, as normal UCI does; they are root-only and must never be published. After 20 prepared transactions, archive/remove completed transaction directories before continuing. Never remove a pending transaction. Logs may contain local addresses. Diagnostics contact two public ICMP targets and resolve `openwrt.org`; package installs use configured feeds. No telemetry is built in.

Lease counts are not online-client counts; bitrate is not an internet speed test. ICMP failure is not proof of an outage. Root renaming, arbitrary new networks, full VLAN setup and unsupported interface shutdowns are outside this version. Detailed output scrolls in the terminal.

See [Russian documentation](README.md) and the [hardware test plan](TESTING.md) for full limitations and recovery steps. Host tests use mocked router commands and do not establish hardware compatibility. MIT licensed.

## Internet and repeater wizard in 0.2.0

`owp internet` (menu 7) adds wired DHCP/PPPoE switching, `owp repeater`, and `owp lan`.
Switching back to DHCP removes PPPoE credentials and obtains DNS automatically.
DHCP/PPPoE use the existing WAN device, including existing swconfig VLAN devices;
the DSA-only restriction applies to moving the physical WAN port.

The repeater is **IPv4 routed AP+STA/NAT with a separate LAN**, not 802.11s mesh,
WDS, an L2 bridge or seamless roaming. It scans using `rpcd-mod-iwinfo`, lets you
select a visible WPA2/WPA3 Personal AP, accepts a hidden passphrase, preserves
your existing secure LAN AP, and creates a restricted masqueraded uplink zone.
An existing active LAN DHCP server is required. BSSID and channel are pinned.
Open/WEP/WPA1/enterprise/hidden networks are refused. Passphrases are limited to
8–63 printable ASCII characters.

Keep LAN IP or explicitly choose a private `/24` router address outside the
new DHCP pool `.100`–`.199`. Custom DHCP options/reservations must be migrated
manually before a LAN change. Reconnect your phone with automatic DHCP after
changing LAN; SSH/LuCI move to the new local IP. Static clients need manual
address/gateway changes.

After applying, the detached worker waits up to about 40 seconds for upstream
DHCP and checks all IPv4 addresses of the other configured interfaces for subnet
overlap, including non-/24 masks. DHCP failure or overlap restores the old config.
`owp repeater-status` explains the result. Run the wizard again with a different
LAN IP after a conflict. The subnet is only known after association and DHCP.
Confirmation is blocked until these checks pass; manually check internet, then
run `owp confirm` and type `Yes` within the overall 120-second rollback window.

Wired WAN remains enabled and has priority at normal metrics (Wi-Fi uplink metric
500). Disconnect WAN while testing Wi-Fi internet, but keep LAN recovery access.
Returning to wired DHCP/PPPoE disables only this tool's STA/WWAN. Existing policy
routing/RouteWolf rules are preserved and need separate validation. IPv6 uplink
is not configured. Shared-radio airtime reduces throughput; losing the upstream
AP can also stop the local AP. A driver that cannot do AP+STA needs another mode
or hardware. There is no additional permanent watchdog daemon.

CI builds pinned upstream UCI/jsonfilter tools for real staging and JSON-path
tests, in addition to mocked network tests. Hardware has not been validated.
