#!/usr/bin/env bash
set -euo pipefail
REPO=$(pwd)
PROFILE_DIR=$REPO/firmware/cudy-wr300-v1
WORK=${BUILD_WORK:?BUILD_WORK required}
OUT=${BUILD_OUTPUT:?BUILD_OUTPUT required}
mkdir -p "$WORK" "$OUT"
exec > >(tee "$OUT/build.log") 2>&1
BASE=https://downloads.openwrt.org/releases/25.12.6/targets/ramips/mt76x8
IB_NAME=openwrt-imagebuilder-25.12.6-ramips-mt76x8.Linux-x86_64
IB=$WORK/$IB_NAME
curl -fL --retry 3 "$BASE/$IB_NAME.tar.zst" -o "$WORK/imagebuilder.tar.zst"
printf '%s  %s\n' '7f26c50440cadd83362c444778f80f4a214ee76f3c192ef85ef074f2c56d89ec' "$WORK/imagebuilder.tar.zst" | sha256sum -c -
tar --zstd -xf "$WORK/imagebuilder.tar.zst" -C "$WORK"
curl -fL --retry 3 "$BASE/profiles.json" -o "$WORK/profiles.json"
curl -fL --retry 3 https://github.com/dagmagnat/RouteWolf/releases/download/v59/routewolf-v59.tar.gz -o "$WORK/routewolf-v59.tar.gz"
printf '%s  %s\n' '1e7137952cc01453706d7168a640925df98613383f584119afddfad82bbdf3e0' "$WORK/routewolf-v59.tar.gz" | sha256sum -c -
curl -fL --retry 3 https://codeload.github.com/dagmagnat/RouteWolf/tar.gz/2f48db5c03ee2657fdd13a7f25978fbd0539ccc4 -o "$WORK/routewolf-source.tar.gz"
tar -xzf "$WORK/routewolf-source.tar.gz" -C "$WORK"
RW_SOURCE=$WORK/RouteWolf-2f48db5c03ee2657fdd13a7f25978fbd0539ccc4
AWG_ROOT=https://slava-shchipunov.github.io/awg-openwrt
curl -fL --retry 3 "$AWG_ROOT/keys/awg-openwrt-feed.pem" -o "$IB/keys/awg-openwrt-feed.pem"
printf '%s  %s\n' 'b4517063ef2994e7ea4f9ec21e1a9f8160ed9707a9faebe394919edf862adbe8' "$IB/keys/awg-openwrt-feed.pem" | sha256sum -c -
printf '\n%s\n' "$AWG_ROOT/25.12.6/ramips/mt76x8/packages.adb" >> "$IB/repositories"
# Signature checking stays enabled. APK must also accept the exact kernel ABI.
grep '^CONFIG_SIGNATURE_CHECK=y' "$IB/.config"
python3 "$PROFILE_DIR/prepare.py" --repo "$REPO" --source "$RW_SOURCE" --payload "$WORK/routewolf-v59.tar.gz" --overlay "$WORK/overlay" --output "$OUT"
mkdir -p "$WORK/overlay/etc/apk/keys" "$WORK/overlay/etc/apk/repositories.d"
cp "$IB/keys/awg-openwrt-feed.pem" "$WORK/overlay/etc/apk/keys/awg-openwrt-feed.pem"
printf '%s\n' "$AWG_ROOT/25.12.6/ramips/mt76x8/packages.adb" > "$WORK/overlay/etc/apk/repositories.d/awg.list"
cp "$PROFILE_DIR/profile.json" "$OUT/profile.json"
cp "$RW_SOURCE/lists/domains-dnsmasq-nfset.lst" "$OUT/full-domains-source.lst"
cp "$RW_SOURCE/lists/ipv4.lst" "$OUT/full-ipv4-source.lst"
PACKAGES=$(python3 -c 'import json,sys;print(" ".join(json.load(open(sys.argv[1]))["packages"]))' "$PROFILE_DIR/profile.json")
make -C "$IB" manifest PROFILE=cudy_wr300-v1 PACKAGES="$PACKAGES" > "$OUT/selected-packages.manifest"
make -C "$IB" image PROFILE=cudy_wr300-v1 PACKAGES="$PACKAGES" FILES="$WORK/overlay" \
  DISABLED_SERVICES="getdomains vpnroute routewolf-watchdog" \
  EXTRA_IMAGE_NAME=pocket-full-wg-awg BIN_DIR="$WORK/images"
IMAGE=$(find "$WORK/images" -maxdepth 1 -type f -name '*cudy_wr300-v1*squashfs-sysupgrade.bin' -print -quit)
test -n "$IMAGE"
"$IB/staging_dir/host/bin/fwtool" -i "$OUT/image-metadata.json" "$IMAGE"
ROOT=$(find "$IB/build_dir" -maxdepth 4 -type d -name 'root-ramips' -print -quit)
test -n "$ROOT"
python3 "$PROFILE_DIR/verify.py" --root "$ROOT" --image "$IMAGE" --profiles "$WORK/profiles.json" --output "$OUT"
# Only a size/contents-checked candidate is exposed as a flashable .bin.
cp "$IMAGE" "$OUT/cudy-wr300-v1-25.12.6-pocket-full-wg-awg-sysupgrade.bin"
cp "$PROFILE_DIR/README.md" "$OUT/README.md"
cd "$OUT"
sha256sum ./*.bin profile.json image-metadata.json selected-packages.manifest > SHA256SUMS
echo 'BUILD VERIFIED. Hardware boot and throughput have not been tested.'
