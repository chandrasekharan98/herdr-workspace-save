#!/usr/bin/env bash
# Burn keypress captions into docs/demo.gif. Run after `vhs docs/demo.tape`.
# Timings come from the tape: it is deterministic, so they only move if the tape does.
# Verify with:  ffmpeg -ss <t> -i docs/demo.gif -frames:v 1 -update 1 /tmp/f.png
set -euo pipefail
cd "$(dirname "$0")/.."

FONT=${FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf}
cap() {  # start end text
  echo "drawtext=fontfile=${FONT}:text='$3':fontsize=19:fontcolor=white:x=w-tw-30:y=14\
:box=1:boxcolor=0x1c1c2aE6:boxborderw=12:enable='between(t,$1,$2)'"
}

ffmpeg -v error -i docs/demo.gif -filter_complex "
  $(cap 15.4 17.3 'ctrl+b  shift+S   save workspace'),
  $(cap 17.4 19.5 'ctrl+b  alt+w   open saved workspace'),
  $(cap 19.6 21.4 'enter   reopen — every pane armed, nothing run'),
  $(cap 21.5 24.6 'enter   run it — same session, history intact'),
  split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer
" -loop 0 -y docs/demo-captioned.gif

mv docs/demo-captioned.gif docs/demo.gif
echo "captions burned into docs/demo.gif"
