"""Rename JZ2 workshop from 精整2 to 拉矫车间, set workshop_type to straightening."""
import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.models.master import Workshop

db = SessionLocal()
ws = db.query(Workshop).filter(Workshop.code == 'JZ2').first()
if ws:
    ws.name = '拉矫车间'
    ws.workshop_type = 'straightening'
    db.commit()
    print(f'Renamed: {ws.code} -> {ws.name} (type={ws.workshop_type})')
else:
    print('JZ2 not found')
db.close()
