"""Offline demo: a sample screenshot drawn with Pillow plus matching canned output.

Nothing here calls any API. The demo project is NOT AI-generated; the UI labels it as such.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from pixelforge.schemas import GeneratedFile, GenerationResult, Project
from pixelforge.services.code_validator import sanitize_result

DEMO_NAME = "demo-landing-page.png"
_W, _H = 1280, 800
_BRAND, _ACCENT, _INK, _MUTED = (109, 40, 217), (109, 40, 217), (30, 27, 75), (75, 85, 99)

_FEATURES = (
    ("Plan", "Turn goals into a clear, shared roadmap."),
    ("Track", "See progress at a glance, always."),
    ("Ship", "Release with confidence and fewer surprises."),
)


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except (TypeError, OSError):  # very old Pillow / no FreeType
        return ImageFont.load_default()


def demo_screenshot_png() -> bytes:
    """Render the sample landing-page screenshot (1280×800 PNG)."""
    img = Image.new("RGB", (_W, _H), "white")
    d = ImageDraw.Draw(img)
    # navigation
    d.line([(0, 64), (_W, 64)], fill=(229, 231, 235), width=1)
    d.ellipse([48, 22, 68, 42], fill=_BRAND)
    d.text((80, 32), "Lumen", font=_font(24), fill=_INK, anchor="lm", stroke_width=1)
    for x, label in ((780, "Product"), (880, "Pricing"), (980, "Docs")):
        d.text((x, 32), label, font=_font(16), fill=_MUTED, anchor="lm")
    d.rounded_rectangle([1104, 16, 1232, 48], radius=8, fill=_ACCENT)
    d.text((1168, 32), "Get started", font=_font(15), fill="white", anchor="mm")
    # hero
    d.rectangle([0, 65, _W, 440], fill=(245, 243, 255))
    d.text((_W / 2, 190), "Build calmer software, faster", font=_font(54), fill=_INK, anchor="mm", stroke_width=1)
    d.text((_W / 2, 262), "Lumen helps small teams plan, track and ship work without the noise.", font=_font(20), fill=_MUTED, anchor="mm")
    d.rounded_rectangle([480, 316, 636, 364], radius=10, fill=_ACCENT)
    d.text((558, 340), "Start free trial", font=_font(16), fill="white", anchor="mm")
    d.rounded_rectangle([652, 316, 800, 364], radius=10, fill="white", outline=_ACCENT, width=2)
    d.text((726, 340), "View demo", font=_font(16), fill=_ACCENT, anchor="mm")
    # feature cards
    for i, (title, text) in enumerate(_FEATURES):
        x0 = 80 + i * 380
        d.rounded_rectangle([x0, 490, x0 + 340, 650], radius=14, fill="white", outline=(229, 231, 235), width=2)
        d.text((x0 + 28, 530), title, font=_font(24), fill=_INK, anchor="lm", stroke_width=1)
        d.text((x0 + 28, 580), text, font=_font(15), fill=_MUTED, anchor="lm")
    # footer
    d.line([(0, 730), (_W, 730)], fill=(229, 231, 235), width=1)
    d.text((_W / 2, 765), "© Lumen Labs. All rights reserved.", font=_font(14), fill=_MUTED, anchor="mm")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lumen: Build calmer software, faster</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <a class="brand" href="#"><span class="brand-dot" aria-hidden="true"></span>Lumen</a>
    <button class="menu-toggle" aria-expanded="false" aria-controls="site-nav">Menu</button>
    <nav id="site-nav" class="site-nav" aria-label="Primary">
      <a href="#">Product</a>
      <a href="#">Pricing</a>
      <a href="#">Docs</a>
      <a class="btn btn-small" href="#">Get started</a>
    </nav>
  </header>
  <main>
    <section class="hero">
      <h1>Build calmer software, faster</h1>
      <p>Lumen helps small teams plan, track and ship work without the noise.</p>
      <div class="actions">
        <a class="btn" href="#">Start free trial</a>
        <a class="btn btn-outline" href="#">View demo</a>
      </div>
    </section>
    <section class="features" aria-label="Features">
      <article class="card"><h2>Plan</h2><p>Turn goals into a clear, shared roadmap.</p></article>
      <article class="card"><h2>Track</h2><p>See progress at a glance, always.</p></article>
      <article class="card"><h2>Ship</h2><p>Release with confidence and fewer surprises.</p></article>
    </section>
  </main>
  <footer class="site-footer"><p>&copy; Lumen Labs. All rights reserved.</p></footer>
  <script src="script.js" defer></script>
</body>
</html>
"""

_CSS = """:root {
  --brand: #6d28d9;
  --ink: #1e1b4b;
  --muted: #4b5563;
  --line: #e5e7eb;
  --tint: #f5f3ff;
  --radius: 10px;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: #fff; line-height: 1.5; }
a { color: inherit; text-decoration: none; }

.site-header { display: flex; align-items: center; justify-content: space-between; height: 64px; padding: 0 48px; border-bottom: 1px solid var(--line); position: relative; }
.brand { display: flex; align-items: center; gap: 12px; font-size: 24px; font-weight: 700; }
.brand-dot { width: 20px; height: 20px; border-radius: 50%; background: var(--brand); }
.site-nav { display: flex; align-items: center; gap: 32px; color: var(--muted); font-size: 16px; }
.menu-toggle { display: none; border: 1px solid var(--line); background: #fff; border-radius: 8px; padding: 6px 12px; font: inherit; cursor: pointer; }

.btn { display: inline-block; padding: 14px 28px; border-radius: var(--radius); background: var(--brand); color: #fff; font-weight: 600; border: 2px solid var(--brand); }
.btn:hover, .btn:focus-visible { filter: brightness(1.1); }
.btn-small { padding: 6px 20px; font-size: 15px; border-radius: 8px; }
.btn-outline { background: #fff; color: var(--brand); }

.hero { text-align: center; background: var(--tint); padding: 96px 24px 76px; }
.hero h1 { margin: 0 0 20px; font-size: clamp(2rem, 5vw, 3.4rem); line-height: 1.15; }
.hero p { margin: 0 auto 36px; max-width: 40rem; font-size: 1.25rem; color: var(--muted); }
.actions { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }

.features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 40px; padding: 48px 80px; }
.card { border: 2px solid var(--line); border-radius: 14px; padding: 28px; }
.card h2 { margin: 0 0 16px; font-size: 1.5rem; }
.card p { margin: 0; color: var(--muted); }

.site-footer { border-top: 1px solid var(--line); padding: 28px 24px; text-align: center; color: var(--muted); font-size: 0.9rem; }
.site-footer p { margin: 0; }

@media (max-width: 900px) {
  .features { grid-template-columns: 1fr; padding: 32px 24px; gap: 20px; }
}
@media (max-width: 700px) {
  .site-header { padding: 0 20px; }
  .menu-toggle { display: inline-block; }
  .site-nav { display: none; position: absolute; top: 64px; left: 0; right: 0; flex-direction: column; align-items: flex-start; gap: 16px; padding: 20px; background: #fff; border-bottom: 1px solid var(--line); z-index: 5; }
  .site-nav.open { display: flex; }
  .hero { padding: 64px 20px 48px; }
}
"""

_JS = """(function () {
  var toggle = document.querySelector(".menu-toggle");
  var nav = document.getElementById("site-nav");
  if (!toggle || !nav) return;
  toggle.addEventListener("click", function () {
    var open = nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
  });
})();
"""

_NOTES = (
    "Offline demo output: hand-written to match the built-in sample screenshot. It was NOT generated by an AI model "
    "and uses a system font stack instead of the original typeface."
)


def demo_project() -> Project:
    """Canned project matching ``demo_screenshot_png`` (passes the normal sanitiser)."""
    result = GenerationResult(
        title="Lumen landing page (demo)",
        files=[
            GeneratedFile(path="index.html", content=_HTML),
            GeneratedFile(path="styles.css", content=_CSS),
            GeneratedFile(path="script.js", content=_JS),
        ],
        notes=_NOTES,
    )
    return sanitize_result(result)
