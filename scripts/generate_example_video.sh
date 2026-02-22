#!/usr/bin/env bash
# Generate a ~1 minute example video for Jestify (1080p, H.264).
# Run from repo root: ./scripts/generate_example_video.sh
# Requires: ffmpeg

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$REPO_ROOT/storage/example"
OUT_FILE="$OUT_DIR/example-video.mp4"
DURATION=60

mkdir -p "$OUT_DIR"

# 1080p, 60 seconds, dark blue background, centered "Jestify Example" text
# drawtext without font uses default; works on macOS/Linux
ffmpeg -y -f lavfi -i "color=c=0x1a1a2e:s=1920x1080:d=$DURATION" \
  -vf "drawtext=text='Jestify Example':fontsize=72:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-40,drawtext=text='Sample video — 1 min':fontsize=32:fontcolor=0xcccccc:x=(w-text_w)/2:y=(h-text_h)/2+40" \
  -c:v libx264 -t "$DURATION" -pix_fmt yuv420p -movflags +faststart \
  "$OUT_FILE"

echo "Created: $OUT_FILE ($DURATION seconds)"
