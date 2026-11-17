#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || { echo 'Run as root' >&2; exit 1; }
[ -f /etc/openwrt_release ] || { echo 'OpenWrt required' >&2; exit 1; }
for cmd in uci ubus jsonfilter ip nohup; do
 command -v "$cmd" >/dev/null || { echo "Missing: $cmd" >&2; exit 1; }
done
DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
[ -s "$DIR/src/owp" ] || { echo 'Extract the complete release first' >&2; exit 1; }
sh -n "$DIR/src/owp"
[ ! -s /etc/owrt-pocket/pending ] || { echo 'Resolve pending change before installing' >&2; exit 1; }
mkdir -p /etc/owrt-pocket /usr/sbin
cp "$DIR/src/owp" /usr/sbin/owp
chmod 755 /usr/sbin/owp
cat > /etc/init.d/owrt-pocket <<'EOF'
#!/bin/sh /etc/rc.common
START=18
start() {
 /usr/sbin/owp _boot
}
EOF
chmod 755 /etc/init.d/owrt-pocket
/etc/init.d/owrt-pocket enable
echo 'Installed. Run: owp'
