#!/bin/sh
# Build pinned upstream host tools for integration tests, never on a router.
set -eu
root=$1
prefix=$root/prefix
mkdir -p "$root" "$prefix"
build() {
 repo=$1
 revision=$2
 curl --fail --location --retry 2 "https://codeload.github.com/openwrt/$repo/tar.gz/$revision" -o "$root/$repo.tar.gz"
 tar -xzf "$root/$repo.tar.gz" -C "$root"
 build_dir=$root/$repo-build
 # jsonpath's upstream parser generator uses source-relative paths.
 [ "$repo" != jsonpath ] || build_dir=$root/$repo-$revision
 cmake -S "$root/$repo-$revision" -B "$build_dir" \
  -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_PREFIX_PATH="$prefix" -DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF
 cmake --build "$build_dir" --parallel 2
 cmake --install "$build_dir"
}
build libubox a396f38a8568a1d670c240465cd8d24fdfdf6463
build uci 74f6277aabffc943d026f406df57c22595134c42
build jsonpath b9034210bd331749673416c6bf389cccd4e23610
