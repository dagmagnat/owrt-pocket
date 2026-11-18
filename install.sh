#!/bin/sh
# Standalone online installer. --local also supports a complete offline checkout.
set -eu
umask 077
fail() { printf 'OWRT Pocket: %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Запустите установку от root / Run as root'
[ -f /etc/openwrt_release ] || fail 'Требуется OpenWrt / OpenWrt required'
for cmd in uci ubus jsonfilter ip nohup; do
 command -v "$cmd" >/dev/null || fail "Нет команды / Missing: $cmd"
done
[ ! -s /etc/owrt-pocket/pending ] || fail 'Сначала подтвердите или откатите ожидающее изменение: owp confirm / owp rollback'
case "${1:-}" in ''|--local) :;; *) fail 'Использование / Usage: sh install.sh [--local]';; esac
WORK=$(mktemp -d /tmp/owrt-pocket.XXXXXX) || fail 'Не удалось создать временный каталог'
STAGED_BIN=
STAGED_INIT=
cleanup() {
 rm -f "$WORK/owp"
 rmdir "$WORK" 2>/dev/null || :
 [ -z "$STAGED_BIN" ] || rm -f "$STAGED_BIN"
 [ -z "$STAGED_INIT" ] || rm -f "$STAGED_INIT"
 return 0
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if [ "${1:-}" = --local ]; then
 DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
 [ -s "$DIR/src/owp" ] || fail 'Для --local распакуйте полный проект / Extract the complete project for --local'
 cp "$DIR/src/owp" "$WORK/owp"
else
 # Pin the payload and its digest together; downloading just this installer is enough.
 URL=https://raw.githubusercontent.com/dagmagnat/owrt-pocket/d618a186529f31666f654ee9dee6a3c3d5f6399f/src/owp
 SHA256=41e06fb4f1157cd550e4ab685502f392a498d7ce2dc86b0ff92b89ef88cfada5
 command -v sha256sum >/dev/null || fail 'Нет sha256sum / Missing sha256sum'
 printf 'Скачивание OWRT Pocket 0.2.0 / Downloading OWRT Pocket 0.2.0...\n'
 if command -v wget >/dev/null; then
  wget -O "$WORK/owp" "$URL" || fail 'Не удалось скачать с GitHub. Проверьте интернет, DNS, дату и HTTPS-сертификаты.'
 elif command -v curl >/dev/null; then
  curl -fL --connect-timeout 15 --max-time 90 -o "$WORK/owp" "$URL" || fail 'Не удалось скачать с GitHub / GitHub download failed'
 else
  fail 'Требуется wget или curl / wget or curl required'
 fi
 [ -s "$WORK/owp" ] || fail 'GitHub вернул пустой файл / Empty download'
 printf '%s  %s\n' "$SHA256" "$WORK/owp" | sha256sum -c - || fail 'SHA-256 не совпадает; установка отменена / SHA-256 mismatch'
fi
sh -n "$WORK/owp" || fail 'Ошибка синтаксиса; установка отменена / Invalid shell syntax'
mkdir -p /etc/owrt-pocket /usr/sbin /etc/init.d
STAGED_BIN=$(mktemp /usr/sbin/.owp-install.XXXXXX)
STAGED_INIT=$(mktemp /etc/init.d/.owrt-pocket-install.XXXXXX)
cp "$WORK/owp" "$STAGED_BIN"
chmod 755 "$STAGED_BIN"
cat > "$STAGED_INIT" <<'EOF'
#!/bin/sh /etc/rc.common
START=18
start() {
 /usr/sbin/owp _boot
}
EOF
chmod 755 "$STAGED_INIT"
mv -f "$STAGED_BIN" /usr/sbin/owp
STAGED_BIN=
mv -f "$STAGED_INIT" /etc/init.d/owrt-pocket
STAGED_INIT=
/etc/init.d/owrt-pocket enable
printf '\nУстановлено! Открыть меню: owp\nInstalled! Open the menu: owp\n'
