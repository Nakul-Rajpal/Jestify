#!/usr/bin/env python3
"""
Generate a ~1 minute example video for Jestify (1080p, H.264).
Uses imageio + imageio-ffmpeg (bundled FFmpeg), no system FFmpeg needed.

Install: pip install imageio imageio-ffmpeg pillow
Run from repo root: python scripts/generate_example_video.py
"""
from pathlib import Path

import numpy as np

# Optional: use PIL for text; fallback to solid color only
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import imageio
except ImportError:
    raise SystemExit("Install with: pip install imageio imageio-ffmpeg pillow")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
OUT_DIR = REPO_ROOT / "storage" / "example"
OUT_FILE = OUT_DIR / "example-video.mp4"
DURATION_SEC = 60
FPS = 30
WIDTH, HEIGHT = 1920, 1080
# Dark blue background (Jestify-style)
BG_R, BG_G, BG_B = 0x1A, 0x1A, 0x2E


def make_frame(sec: float) -> np.ndarray:
    """One frame as RGB array (H, W, 3) uint8."""
    arr = np.full((HEIGHT, WIDTH, 3), [BG_R, BG_G, BG_B], dtype=np.uint8)
    if not HAS_PIL:
        return arr
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    # Prefer a built-in font; avoid missing-font errors
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
    except Exception:
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 72)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        except Exception:
            font_large = ImageFont.load_default()
            font_small = font_large
    text1 = "Jestify Example"
    text2 = "Sample video — 1 min"
    b1 = draw.textbbox((0, 0), text1, font=font_large)
    b2 = draw.textbbox((0, 0), text2, font=font_small)
    x1 = (WIDTH - (b1[2] - b1[0])) // 2
    y1 = (HEIGHT - (b1[3] - b1[1])) // 2 - 40
    x2 = (WIDTH - (b2[2] - b2[0])) // 2
    y2 = (HEIGHT - (b2[3] - b2[1])) // 2 + 40
    draw.text((x1, y1), text1, fill=(255, 255, 255), font=font_large)
    draw.text((x2, y2), text2, fill=(0xCC, 0xCC, 0xCC), font=font_small)
    return np.array(img)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_frames = DURATION_SEC * FPS
    print(f"Writing {n_frames} frames to {OUT_FILE}...")
    writer = imageio.get_writer(
        str(OUT_FILE),
        format="ffmpeg",
        mode="I",
        fps=FPS,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        output_params=["-movflags", "+faststart"],
    )
    for i in range(n_frames):
        sec = i / FPS
        frame = make_frame(sec)
        writer.append_data(frame)
        if (i + 1) % (FPS * 10) == 0:
            print(f"  {i // FPS + 1}s / {DURATION_SEC}s")
    writer.close()
    print(f"Created: {OUT_FILE} ({DURATION_SEC} seconds)")


if __name__ == "__main__":
    main()
