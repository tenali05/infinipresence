"""Draws the app icon, adaptive-icon layers, splash screens and Play Store graphics.

Run from mobile/: python3 scripts/make-icons.py, then `npm run assets` to write the Android resources.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = (15, 23, 42, 255)
GREEN = (34, 197, 94, 255)
ROOT = Path(__file__).resolve().parent.parent
SS = 4  # supersampling


def pin(size, scale, bg=None):
	"""Location pin with a smiling face, centred; `scale` is the pin height as a fraction of size."""
	S = size * SS
	im = Image.new("RGBA", (S, S), bg or (0, 0, 0, 0))
	d = ImageDraw.Draw(im)
	h = S * scale  # pin height
	r = h * 0.39  # head radius
	cx = S / 2
	top = (S - h) / 2
	cy = top + r
	tip = top + h
	# tangent points from the tip to the head circle
	dist = tip - cy
	ang = math.asin(r / dist)
	tx = r * math.cos(ang)
	ty = r * math.sin(ang)
	d.polygon([(cx - tx, cy + ty), (cx + tx, cy + ty), (cx, tip)], fill=GREEN)
	d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN)
	fr = r * 0.58
	fy = cy + r * 0.04
	d.ellipse([cx - fr, fy - fr, cx + fr, fy + fr], fill=NAVY)
	er = fr * 0.14
	for ex in (cx - fr * 0.37, cx + fr * 0.37):
		ey = fy - fr * 0.24
		d.ellipse([ex - er, ey - er, ex + er, ey + er], fill=GREEN)
	sr = fr * 0.47
	sy = fy - fr * 0.05
	d.arc([cx - sr, sy - sr, cx + sr, sy + sr], 25, 155, fill=GREEN, width=int(fr * 0.11))
	return im.resize((size, size), Image.LANCZOS)


def main():
	a = ROOT / "assets"
	s = ROOT / "store"
	pin(1024, 0.62, NAVY).save(a / "icon-only.png")
	pin(1024, 0.45).save(a / "icon-foreground.png")  # adaptive icon: keep inside the safe zone
	Image.new("RGBA", (1024, 1024), NAVY).save(a / "icon-background.png")
	splash = Image.new("RGBA", (2732, 2732), NAVY)
	mark = pin(700, 0.9)
	splash.alpha_composite(mark, ((2732 - 700) // 2, (2732 - 700) // 2))
	splash.save(a / "splash.png")
	splash.save(a / "splash-dark.png")
	# Google Play listing: 512x512 icon and 1024x500 feature graphic
	pin(512, 0.62, NAVY).convert("RGB").save(s / "play-icon-512.png")
	fg = Image.new("RGBA", (1024, 500), NAVY)
	fg.alpha_composite(pin(360, 0.9), (50, 70))
	d = ImageDraw.Draw(fg)
	try:
		big = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
		small = ImageFont.truetype("DejaVuSans.ttf", 34)
	except OSError:
		big = small = ImageFont.load_default()
	d.text((420, 175), "infiniPresence", font=big, fill=(255, 255, 255, 255))
	d.text((424, 265), "Check in with your face,", font=small, fill=(203, 213, 225, 255))
	d.text((424, 310), "at your office.", font=small, fill=(203, 213, 225, 255))
	fg.convert("RGB").save(s / "feature-graphic-1024x500.png")


if __name__ == "__main__":
	main()
