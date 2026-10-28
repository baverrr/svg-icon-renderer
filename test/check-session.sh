#!/bin/bash
# After logging in with install.sh in place: shows whether the session and running KDE apps use the plugin.
# Run: bash check-session.sh
echo "systemd user env: $(systemctl --user show-environment | grep '^QT_PLUGIN_PATH=' || echo 'QT_PLUGIN_PATH not set')"
for name in plasmashell dolphin systemsettings; do
  for pid in $(pgrep -u "$USER" -x "$name"); do
    plugin=$(awk '{ $1=$2=$3=$4=$5=""; sub(/^ +/, "") } /imageformats\/[^/]*svg[^/]*\.so$/' "/proc/$pid/maps" | sort -u)
    echo "$name ($pid): ${plugin:-no svg image plugin loaded yet}"
  done
done
