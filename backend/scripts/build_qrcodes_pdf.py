"""Bundle every PNG under backend/二维码/ into one printable PDF.

Lays out 4×6 cards per A4 page (96 PNGs across 5 pages-ish). Section
headers (机列/车间/电工/全厂/内勤) start a new page. Output:
backend/二维码/二维码总册.pdf
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
QR_DIR = ROOT / '二维码'
OUT_PDF = QR_DIR / '二维码总册.pdf'

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

SECTIONS = [
    ('机列扫码', sorted(p for p in QR_DIR.glob('*/机列_*.png'))),
    ('车间看板', sorted((QR_DIR / '_车间看板').glob('车间_*.png'))),
    ('电工码',   sorted((QR_DIR / '_电工').glob('电工_*.png'))),
    ('全厂码',   sorted((QR_DIR / '_全厂').glob('全厂_*.png'))),
    ('内勤码',   sorted(p for p in (QR_DIR / '_内勤').glob('*/内勤_*.png'))),
]

PAGE_W, PAGE_H = A4
MARGIN = 12 * mm
COLS, ROWS = 3, 4
GAP = 4 * mm

cell_w = (PAGE_W - 2 * MARGIN - (COLS - 1) * GAP) / COLS
cell_h = (PAGE_H - 2 * MARGIN - 18 * mm - (ROWS - 1) * GAP) / ROWS
img_size = min(cell_w, cell_h - 14 * mm)


def draw_section_header(c: canvas.Canvas, title: str, count: int) -> None:
    c.setFont('STSong-Light', 16)
    c.drawString(MARGIN, PAGE_H - MARGIN - 6 * mm, f'{title} · {count} 张')
    c.setStrokeColorRGB(0.15, 0.39, 0.92)
    c.setLineWidth(1.2)
    c.line(MARGIN, PAGE_H - MARGIN - 9 * mm, PAGE_W - MARGIN, PAGE_H - MARGIN - 9 * mm)


def draw_card(c: canvas.Canvas, png: Path, x: float, y: float) -> None:
    c.drawImage(str(png), x + (cell_w - img_size) / 2, y + 12 * mm,
                width=img_size, height=img_size, preserveAspectRatio=True, mask='auto')
    c.setFont('STSong-Light', 8)
    parts = png.stem.split('_', 2)
    label = parts[-1] if len(parts) >= 2 else png.stem
    c.drawCentredString(x + cell_w / 2, y + 6 * mm, label[:24])
    c.setFont('STSong-Light', 7)
    c.setFillColorRGB(0.45, 0.48, 0.52)
    c.drawCentredString(x + cell_w / 2, y + 2.5 * mm, png.parent.name[:28])
    c.setFillColorRGB(0, 0, 0)


def build() -> None:
    c = canvas.Canvas(str(OUT_PDF), pagesize=A4)
    c.setTitle('鑫泰铝业 数据中枢 · 二维码总册')
    total = 0
    for title, pngs in SECTIONS:
        if not pngs:
            continue
        per_page = COLS * ROWS
        for page_idx in range(0, len(pngs), per_page):
            chunk = pngs[page_idx:page_idx + per_page]
            draw_section_header(c, title, len(pngs))
            for i, png in enumerate(chunk):
                col, row = i % COLS, i // COLS
                x = MARGIN + col * (cell_w + GAP)
                y = PAGE_H - MARGIN - 18 * mm - (row + 1) * cell_h - row * GAP
                draw_card(c, png, x, y)
            c.showPage()
        total += len(pngs)
    c.save()
    print(f'PDF: {OUT_PDF}  ({total} cards)')


if __name__ == '__main__':
    build()
