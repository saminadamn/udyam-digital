"""Render business_case.html (10 slides) to site/img/Udyam_Digital_Business_Case.pdf plus a JPG preview per slide in site/img/deck/.

    python showcase/build/business_case_build.py
"""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SITE_IMG = HERE.parent / "site" / "img"
PDF = SITE_IMG / "Udyam_Digital_Business_Case.pdf"
DECK = SITE_IMG / "deck"
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

DECK.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME)
    pg = b.new_page(viewport={"width": 1280, "height": 720})
    pg.goto((HERE / "business_case.html").as_uri())
    pg.wait_for_load_state("networkidle")
    pg.evaluate("document.fonts.ready")
    slides = pg.locator("section.s")
    n = slides.count()
    assert n <= 10, f"{n} slides; the brief allows 10 or fewer"
    for i in range(n):
        el = slides.nth(i)
        over = el.evaluate("e => [...e.querySelectorAll('*')].some(c => c.getBoundingClientRect().bottom > e.getBoundingClientRect().bottom + 1 && !c.closest('.foot'))")
        if over:
            print(f"warning: slide {i + 1} content overflows")
        el.screenshot(path=str(DECK / f"s-{i + 1:02d}.jpg"), type="jpeg", quality=82)
    pg.emulate_media(media="print")
    pg.pdf(path=str(PDF), width="1280px", height="720px", print_background=True, prefer_css_page_size=True)
    b.close()
print(f"{n} slides -> {PDF.name} ({PDF.stat().st_size // 1024} KB) and {DECK}")
