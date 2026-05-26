"""Generate QR codes for every active machine, every workshop kiosk that can
file consumables, and every consumable_stat user.

Runs locally; pulls master data from prod via SSH-tunneled psql in JSON form,
then renders PNGs into backend/二维码/ grouped by workshop. An HTML index is
emitted at backend/二维码/index.html — open in a browser to print the sheet.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import qrcode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '二维码'
PROD_HOST = 'root@8.140.218.13'
DB_PASS = 'xt_bypass_2026'
PROD_HOST_URL = 'http://8.140.218.13:8000'  # 现场扫码后端 base


def remote_json(sql: str) -> list[dict]:
    cmd = (
        f"PGPASSWORD={DB_PASS} psql -h 127.0.0.1 -U bypass_user -d aluminum_bypass "
        f"-tAc {shlex.quote(sql)}"
    )
    out = subprocess.run(
        ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=8', PROD_HOST, cmd],
        check=True, capture_output=True, text=True, encoding='utf-8',
    )
    text = out.stdout.strip()
    if not text or text == '\\N':
        return []
    return json.loads(text)


def safe(name: str) -> str:
    bad = '<>:"/\\|?*'
    return ''.join('_' if c in bad else c for c in name).strip() or 'unknown'


def render_qr(data: str, target: Path, label_lines: list[str]) -> None:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target, format='PNG')


def main() -> None:
    OUT.mkdir(exist_ok=True)
    print(f'Output → {OUT}')

    print('Pulling equipment list...')
    equipment = remote_json(
        "SELECT json_agg(t) FROM ("
        "SELECT e.id, e.code, e.name, e.qr_code, e.equipment_type, "
        "  w.code AS ws_code, w.name AS ws_name "
        "FROM equipment e LEFT JOIN workshops w ON e.workshop_id=w.id "
        "WHERE e.is_active=true AND e.qr_code IS NOT NULL "
        "  AND e.equipment_type NOT LIKE 'virtual_%' "
        "ORDER BY w.sort_order, e.sort_order, e.code"
        ") t;"
    )
    print(f'  {len(equipment)} machines')

    print('Pulling workshop kiosks (with consumables)...')
    workshops = remote_json(
        "SELECT json_agg(t) FROM ("
        "SELECT w.id, w.code, w.name "
        "FROM workshops w "
        "WHERE w.is_active=true "
        "ORDER BY w.sort_order, w.code"
        ") t;"
    )
    print(f'  {len(workshops)} workshops')

    print('Pulling consumable_stat personnel...')
    personnel = remote_json(
        "SELECT json_agg(t) FROM ("
        "SELECT u.id, u.username, u.name, w.code AS ws_code, w.name AS ws_name "
        "FROM users u LEFT JOIN workshops w ON u.workshop_id=w.id "
        "WHERE u.role='consumable_stat' AND u.is_active=true "
        "ORDER BY w.sort_order, u.username"
        ") t;"
    )
    print(f'  {len(personnel)} 内勤')

    sections: list[dict] = []

    # Machines.
    by_ws: dict[str, list] = {}
    for eq in equipment:
        by_ws.setdefault(f"{eq['ws_code'] or '未分配'} {eq['ws_name'] or ''}", []).append(eq)
    for ws_label, items in by_ws.items():
        cards = []
        for eq in items:
            url = f"{PROD_HOST_URL}/login?machine={quote(eq['qr_code'])}"
            fname = f"机列_{safe(eq['code'])}_{safe(eq['name'])}.png"
            target = OUT / safe(ws_label) / fname
            render_qr(url, target, [eq['name'], eq['code']])
            cards.append({
                'title': eq['name'],
                'subtitle': f"{eq['code']} · {eq['equipment_type']}",
                'url': url,
                'rel': str(target.relative_to(OUT)).replace('\\', '/'),
            })
        sections.append({'group': ws_label, 'kind': '机列', 'cards': cards})

    # Workshop kiosks (consumable filing landing).
    cards = []
    for ws in workshops:
        url = f"{PROD_HOST_URL}/login?workshop={quote(ws['code'])}"
        fname = f"车间_{safe(ws['code'])}.png"
        target = OUT / '_车间看板' / fname
        render_qr(url, target, [ws['name'], ws['code']])
        cards.append({
            'title': ws['name'],
            'subtitle': f"车间 · {ws['code']}",
            'url': url,
            'rel': str(target.relative_to(OUT)).replace('\\', '/'),
        })
    sections.append({'group': '车间扫码看板', 'kind': '车间', 'cards': cards})

    # Personnel personal-login QR.
    cards = []
    for u in personnel:
        url = f"{PROD_HOST_URL}/login?u={quote(u['username'])}"
        ws = u.get('ws_code') or '未分配'
        fname = f"内勤_{safe(u['username'])}_{safe(u['name'] or '')}.png"
        target = OUT / '_内勤' / safe(ws) / fname
        render_qr(url, target, [u['name'] or u['username'], u['username']])
        cards.append({
            'title': u['name'] or u['username'],
            'subtitle': f"{u['username']} · {u.get('ws_name') or '未分配'}",
            'url': url,
            'rel': str(target.relative_to(OUT)).replace('\\', '/'),
        })
    sections.append({'group': '生产内勤（辅材填报）', 'kind': '内勤', 'cards': cards})

    # Index HTML.
    index = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">']
    index.append('<title>鑫泰铝业 数据中枢 二维码总册</title>')
    index.append('<style>body{font-family:-apple-system,Segoe UI,sans-serif;background:#f5f6fa;margin:0;padding:24px;color:#1f2329}'
                 'h1{font-size:22px;margin:0 0 8px}h2{font-size:16px;margin:24px 0 12px;border-left:3px solid #2563eb;padding-left:8px}'
                 '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px}'
                 '.card{background:#fff;border:1px solid #e3e6ec;border-radius:6px;padding:10px;text-align:center;break-inside:avoid}'
                 '.card img{width:100%;height:auto;display:block}'
                 '.card .t{font-size:13px;font-weight:600;margin-top:6px;color:#1f2329}'
                 '.card .s{font-size:11px;color:#737a87;margin-top:2px;word-break:break-all}'
                 '@media print{body{background:#fff}.card{border-color:#bbb}h2{break-before:page}}'
                 '</style></head><body>')
    index.append(f'<h1>鑫泰铝业 数据中枢 · 扫码入口总册</h1>')
    index.append(f'<p style="color:#737a87;font-size:13px;margin:0 0 16px">'
                 f'机列 {len(equipment)} · 车间 {len(workshops)} · 内勤 {len(personnel)}</p>')
    for sec in sections:
        index.append(f'<h2>{sec["group"]} · {sec["kind"]} ({len(sec["cards"])})</h2>')
        index.append('<div class="grid">')
        for c in sec['cards']:
            index.append(f'<div class="card"><img src="{c["rel"]}" alt=""/>'
                         f'<div class="t">{c["title"]}</div>'
                         f'<div class="s">{c["subtitle"]}</div></div>')
        index.append('</div>')
    index.append('</body></html>')
    (OUT / 'index.html').write_text('\n'.join(index), encoding='utf-8')
    print(f'\nWrote {OUT / "index.html"}')


if __name__ == '__main__':
    main()
