"""Generate a PDF of QR codes — one QR per A4 page — for posting on machine lines.

Each page has a large QR in the center plus the machine/role name, workshop,
and the login URL. Output: backend/二维码/二维码-A4逐页.pdf

Pulls the active QR rows from the production equipment table (same source and
PROD_DB_PASSWORD requirement as generate_qrcodes.py), so retired workshops are
skipped and every role / director code uses the qr_code that actually logs in.
"""
from __future__ import annotations

import io
from pathlib import Path
from urllib.parse import quote

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from generate_qrcodes import remote_json

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

PROD_URL = 'https://8.140.218.13'
OUT_PDF = Path(__file__).resolve().parents[1] / '二维码' / '二维码-A4逐页.pdf'
PAGE_W, PAGE_H = A4
QR_SIZE = 120 * mm

OWNER_LABEL = {
    'BZ': '班长',
    'EN': '电工',
    'CS': '内勤',
    'QM': '质检内勤',
    'PL': '计划内勤',
    'EC': '总电工',
    'FS': '成品库',
    'PSH': '园区剪切',
    'RC': '回收',
    'OH': '大修',
    'DIR': '车间主任看板',
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

    rows = remote_json(
        "SELECT json_agg(t) FROM ("
        "SELECT e.code, e.name, e.qr_code, e.equipment_type, w.name AS ws_name "
        "FROM equipment e LEFT JOIN workshops w ON e.workshop_id=w.id "
        "WHERE e.is_active=true AND e.qr_code IS NOT NULL "
        "  AND (e.equipment_type LIKE 'virtual_%' OR e.operational_status='running') "
        "ORDER BY e.equipment_type LIKE 'virtual_%', w.sort_order, e.sort_order, e.code"
        ") t;"
    )
    for row in rows:
        url = f"{PROD_URL}/login?machine={quote(row['qr_code'])}"
        if row['equipment_type'].startswith('virtual_'):
            label = OWNER_LABEL.get(row['code'].rsplit('-', 1)[-1], '角色')
            _draw_page(
                c,
                url=url,
                title=row['name'] or row['code'],
                subtitle=f"角色码 · {row['code']}",
                tag=f'{label}扫码入口',
            )
        else:
            _draw_page(
                c,
                url=url,
                title=f"{row['ws_name'] or ''}  {row['name']}",
                subtitle=f"机列码 · {row['code']}",
                tag='主操扫码填报',
            )
        count += 1

    c.save()
    print(f'Done: {OUT_PDF}  ({count} pages)')


if __name__ == '__main__':
    main()
