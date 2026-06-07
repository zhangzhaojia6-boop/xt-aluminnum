"""Per-workshop QR PDF — one PDF file per workshop.

Each PDF contains the workshop's machine QRs + 电工 + 内勤 codes that
belong to that workshop. Output:
backend/二维码/<workshop>/二维码-<workshop>.pdf

Run after generate_qrcodes.py.
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

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

PAGE_W, PAGE_H = A4
MARGIN = 12 * mm
COLS, ROWS = 3, 4
GAP = 4 * mm
HEADER_H = 18 * mm

cell_w = (PAGE_W - 2 * MARGIN - (COLS - 1) * GAP) / COLS
cell_h = (PAGE_H - 2 * MARGIN - HEADER_H - (ROWS - 1) * GAP) / ROWS
img_size = min(cell_w, cell_h - 14 * mm)


def draw_section_header(c: canvas.Canvas, ws_name: str, section: str, count: int) -> None:
    c.setFont('STSong-Light', 16)
    c.drawString(MARGIN, PAGE_H - MARGIN - 6 * mm, f'{ws_name} · {section}（{count}）')
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
    c.drawCentredString(x + cell_w / 2, y + 2.5 * mm, parts[0] if parts else '')
    c.setFillColorRGB(0, 0, 0)


def render_section(c: canvas.Canvas, ws_name: str, section: str, pngs: list[Path]) -> None:
    if not pngs:
        return
    per_page = COLS * ROWS
    for page_idx in range(0, len(pngs), per_page):
        chunk = pngs[page_idx:page_idx + per_page]
        draw_section_header(c, ws_name, section, len(pngs))
        for i, png in enumerate(chunk):
            col, row = i % COLS, i // COLS
            x = MARGIN + col * (cell_w + GAP)
            y = PAGE_H - MARGIN - HEADER_H - (row + 1) * cell_h - row * GAP
            draw_card(c, png, x, y)
        c.showPage()


def safe_name(p: Path) -> str:
    return p.name


def find_workshop_code(ws_dir_name: str) -> str:
    return ws_dir_name.split(' ', 1)[0]


def main() -> None:
    workshop_dirs = [d for d in QR_DIR.iterdir() if d.is_dir() and not d.name.startswith('_')]
    energy_dir = QR_DIR / '_电工'
    cs_dir = QR_DIR / '_内勤'
    director_dir = QR_DIR / '_车间主任'

    built = []
    for ws_dir in sorted(workshop_dirs):
        ws_name = ws_dir.name
        ws_code = find_workshop_code(ws_name)
        machine_pngs = sorted(ws_dir.glob('机列_*.png'))
        energy_pngs = sorted(energy_dir.glob(f'电工_{ws_code}-*.png')) if energy_dir.exists() else []
        cs_pngs = sorted(cs_dir.glob(f'内勤_{ws_code}-*.png')) if cs_dir.exists() else []
        director_pngs = sorted(director_dir.glob(f'主任_{ws_code}-*.png')) if director_dir.exists() else []

        if not (machine_pngs or energy_pngs or cs_pngs or director_pngs):
            continue

        out_pdf = ws_dir / f'二维码-{ws_name}.pdf'
        c = canvas.Canvas(str(out_pdf), pagesize=A4)
        c.setTitle(f'鑫泰铝业 · {ws_name} · 二维码')

        render_section(c, ws_name, '机列', machine_pngs)
        render_section(c, ws_name, '电工', energy_pngs)
        render_section(c, ws_name, '内勤', cs_pngs)
        render_section(c, ws_name, '车间主任', director_pngs)

        c.save()
        total = len(machine_pngs) + len(energy_pngs) + len(cs_pngs) + len(director_pngs)
        built.append((ws_name, total, out_pdf))

    factory_dir = QR_DIR / '_全厂'
    if factory_dir.exists():
        factory_pngs = sorted(factory_dir.glob('全厂_*.png'))
        if factory_pngs:
            out_pdf = factory_dir / '二维码-全厂.pdf'
            c = canvas.Canvas(str(out_pdf), pagesize=A4)
            c.setTitle('鑫泰铝业 · 全厂 · 二维码')
            render_section(c, '全厂', '专项码', factory_pngs)
            c.save()
            built.append(('全厂', len(factory_pngs), out_pdf))

    print(f'\n生成 {len(built)} 个车间 PDF：')
    for name, n, path in built:
        print(f'  {name:18s}  {n:3d} 张  {path}')


if __name__ == '__main__':
    main()
