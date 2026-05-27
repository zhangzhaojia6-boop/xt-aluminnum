"""Generate a PDF of QR codes — one QR per A4 page — for posting on machine lines.

Each page has a large QR in the center plus the machine/role name, workshop,
and the login URL. Output: backend/二维码/二维码-A4逐页.pdf

Uses real_master_data config so it runs locally without SSH.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from urllib.parse import quote

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.real_master_data import (
    EQUIPMENT_BY_WORKSHOP,
    OWNER_QR_SPECS,
    WORKSHOPS,
)

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

PROD_URL = 'https://xtmijd.com'
OUT_PDF = Path(__file__).resolve().parents[1] / '二维码' / '二维码-A4逐页.pdf'
PAGE_W, PAGE_H = A4
QR_SIZE = 120 * mm

WORKSHOP_NAME = {w['code']: w['name'] for w in WORKSHOPS}

OWNER_LABEL = {
    'BZ': '班长',
    'EN': '电工',
    'QM': '质检内勤',
    'PL': '计划内勤',
    'EC': '总电工',
    'FS': '成品库',
    'PSH': '园区剪切',
    'RC': '回收',
    'OH': '大修',
}


def _qr_image_bytes(data: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()


def _draw_page(c: canvas.Canvas, *, url: str, title: str, subtitle: str, tag: str) -> None:
    from reportlab.lib.utils import ImageReader
    img_data = _qr_image_bytes(url)
    img = ImageReader(io.BytesIO(img_data))
    x = (PAGE_W - QR_SIZE) / 2
    y = (PAGE_H - QR_SIZE) / 2 + 15 * mm
    c.drawImage(img, x, y, width=QR_SIZE, height=QR_SIZE, preserveAspectRatio=True)

    c.setFont('STSong-Light', 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 18 * mm, '鑫泰铝业 · 数据中枢')

    c.setFont('STSong-Light', 11)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 28 * mm, tag)

    c.setFont('STSong-Light', 22)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(PAGE_W / 2, y - 12 * mm, title)

    c.setFont('STSong-Light', 13)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawCentredString(PAGE_W / 2, y - 26 * mm, subtitle)

    c.setFont('STSong-Light', 7)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(PAGE_W / 2, 14 * mm, url)

    c.showPage()


def main() -> None:
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT_PDF), pagesize=A4)
    c.setTitle('鑫泰铝业 数据中枢 · 二维码逐页')
    count = 0

    for ws_code, machines in EQUIPMENT_BY_WORKSHOP.items():
        ws_name = WORKSHOP_NAME.get(ws_code, ws_code)
        for m in machines:
            if m.get('operational_status', 'running') != 'running':
                continue
            qr_code = f"XT-{m['code']}"
            url = f"{PROD_URL}/login?machine={quote(qr_code)}"
            _draw_page(
                c,
                url=url,
                title=f"{ws_name}  {m['name']}",
                subtitle=f"机列码 · {m['code']}",
                tag='主操扫码填报',
            )
            count += 1

    _PER_WORKSHOP_SUFFIXES = {'BZ', 'EN', 'OP'}
    for suffix, label, host_code in OWNER_QR_SPECS:
        ws_name = WORKSHOP_NAME.get(host_code, host_code)
        eq_code = f"{host_code}-{suffix}"
        qr_code = f"XT-{eq_code}"
        url = f"{PROD_URL}/login?machine={quote(qr_code)}"
        if suffix in _PER_WORKSHOP_SUFFIXES:
            title = f"{ws_name} {label}"
            subtitle = f"角色码 · {eq_code}"
        else:
            title = label
            subtitle = f"全厂专项 · {eq_code}"
        _draw_page(
            c,
            url=url,
            title=title,
            subtitle=subtitle,
            tag=f'{label}扫码入口',
        )
        count += 1

    c.save()
    print(f'Done: {OUT_PDF}  ({count} pages)')


if __name__ == '__main__':
    main()
