from app.database import get_sessionmaker
from app.models.master import Workshop, WorkshopTemplateConfig
from app.models.shift import ShiftConfig

db = get_sessionmaker()()

print("=== Workshops ===")
for ws in db.query(Workshop).order_by(Workshop.id).all():
    wt = getattr(ws, "workshop_type", "N/A")
    print("  id=%d code=%s type=%s" % (ws.id, ws.code, wt))

print("\n=== ShiftConfigs ===")
shifts = db.query(ShiftConfig).all()
if not shifts:
    print("  EMPTY")
for s in shifts:
    print("  id=%d code=%s name=%s ws=%s" % (s.id, s.code, s.name, s.workshop_id))

print("\n=== WorkshopTemplateConfig ===")
configs = db.query(WorkshopTemplateConfig).all()
if not configs:
    print("  EMPTY")
for c in configs:
    print("  id=%d key=%s ws=%s" % (c.id, c.template_key, c.workshop_id))

try:
    from app.models.attendance import AttendanceSchedule
    cnt = db.query(AttendanceSchedule).count()
    print("\nAttendanceSchedule: %d records" % cnt)
except Exception as e:
    print("\nAttendanceSchedule: %s" % e)

db.close()
