#!/usr/bin/env bash
# Run in Git Bash on Windows. Renders every icon named in icon-map.txt on your Linux machine over ssh
# (render.py runs there) and replaces ico/ with the result.
#
#   RENDER_HOST=my-linux-pc bash fetch.sh            # ssh host or alias with the icon theme
#   ICON_THEME=Manila-Folders (default)              # theme folder name on that machine
#
# ico/ and sources.txt (which SVG each icon came from) are only replaced when the render and the
# unpack both worked. Uses Windows' own ssh.exe when it's there, so keys in the Windows ssh-agent work.
set -euo pipefail
cd "$(dirname "$0")"
: "${RENDER_HOST:?set RENDER_HOST to the ssh host that has the icon theme, e.g. RENDER_HOST=my-linux-pc bash fetch.sh}"
THEME="${ICON_THEME:-Manila-Folders}"
SSH=ssh
[ -x /c/Windows/System32/OpenSSH/ssh.exe ] && SSH=/c/Windows/System32/OpenSSH/ssh.exe

# "<context>/<name>.svg", plus ":overlay" when the map's third column says overlay
tr -d '\r' < icon-map.txt | sed 's/#.*//' | awk 'NF >= 2 { print $2 ($3 == "overlay" ? ":overlay" : "") }' | sort -u > svgs.txt
mapfile -t svgs < svgs.txt
[ "${#svgs[@]}" -gt 0 ] || { echo "icon-map.txt names no icons" >&2; exit 1; }
# The same rule as render.py and build_theme.py, ASCII only; checked here too because the names go into a remote command.
rc=0
bad=$(grep -vE '^(places|devices|mimetypes|apps|actions|preferences|categories|status|emblems)/[A-Za-z0-9_.+-]+\.svg(:overlay)?$' svgs.txt) || rc=$?
if [ "$rc" -eq 0 ]; then
  echo "icon-map.txt has names that aren't '<context>/<name>.svg':" >&2; echo "$bad" >&2; exit 1
elif [ "$rc" -ne 1 ]; then  # 1 = every name is fine; anything else is grep failing
  echo "couldn't check the names in svgs.txt (grep exit $rc)" >&2; exit 1
fi
[[ "$THEME" =~ ^[A-Za-z0-9_.+-]+$ ]] || { echo "ICON_THEME must be a plain folder name" >&2; exit 1; }

args=$(printf '%q ' "${svgs[@]}")
if ! "$SSH" -o BatchMode=yes "$RENDER_HOST" "python3 - --theme $THEME $args" < render.py > ico.tgz 2> render.log; then
  grep -v '^USES' render.log >&2 || true
  echo "render failed (see render.log)" >&2; exit 1
fi
# One command per line: set -e doesn't stop on a failure early in an && chain.
rm -rf -- ico.new
mkdir ico.new
tar -C ico.new -xzf ico.tgz
got=$(find ico.new -name '*.ico' | wc -l)
[ "$got" -eq "${#svgs[@]}" ] || { echo "expected ${#svgs[@]} .ico files, got $got" >&2; exit 1; }
grep '^USES' render.log | cut -d' ' -f2- > sources.txt.new
rm -rf -- ico
mv ico.new ico
mv sources.txt.new sources.txt
rm -f ico.tgz
echo "$got icons rendered into ico/ (sources in sources.txt)"
if warnings=$(grep -v '^USES' render.log); then
  echo "$(echo "$warnings" | wc -l) warning line(s) from the render, in render.log:" >&2; echo "$warnings" >&2
fi
