-- 配套：seed_align_excel_2026_05_26 part2 — OP QR 同步
-- 跟随机列搬迁/重命名/停用，调整 virtual_role_qr 实体

BEGIN;

-- ============ JQ → LJ 拉矫段 OP QR 搬迁 ============
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='LJ'),
       name='拉矫车间 拉矫 主操'
 WHERE code='JQ-LJ-OP';
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='LJ'),
       name='拉矫车间 退火炉 主操'
 WHERE code='JQ-TH-OP';

-- LJ 大分切 / 小剪子 OP QR
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'LJ-DFC-OP','拉矫车间 大分切 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-LJ-DFC-OP',now(),now()
  FROM workshops w WHERE w.code='LJ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'LJ-XJZ-OP','拉矫车间 小剪子 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-LJ-XJZ-OP',now(),now()
  FROM workshops w WHERE w.code='LJ' ON CONFLICT (code) DO NOTHING;

-- ============ JQ → JZ 精整段 OP QR 搬迁 ============
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='JZ'),
       name='精整车间 19辊 主操'
 WHERE code='JQ-19G-OP';
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='JZ'),
       name='精整车间 新19辊 主操'
 WHERE code='JQ-19N-OP';
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='JZ'),
       name='精整车间 纵剪 主操'
 WHERE code='JQ-ZJ-Z-OP';

-- JQ 留下机列 OP QR 名规范化（剪切车间）
UPDATE equipment SET name=REPLACE(name,'园区剪切车间','剪切车间')
 WHERE workshop_id=(SELECT id FROM workshops WHERE code='JQ')
   AND equipment_type='virtual_role_qr';

-- ============ RZ 旧 OP QR 名规范化 + 停用未列项 ============
UPDATE equipment SET is_active=false
 WHERE code IN ('RZ-HW-OP','RZ-GL-OP','RZ-DMILL-OP','RZ-FMILL-OP','RZ-HEAT-OP','RZ-ROLL-OP','RZ-SAW-OP','RZ-XC-OP');
UPDATE equipment SET name='热轧 加热炉 主操' WHERE code='RZ-HE-OP';
UPDATE equipment SET name='热轧 双面铣2台 主操' WHERE code='RZ-DM-OP';
UPDATE equipment SET name='热轧 六面铣 主操' WHERE code='RZ-FM-OP';
UPDATE equipment SET name='热轧 中厚板 主操' WHERE code='RZ-MED-OP';

-- ============ 淬火车间 OP QR ============
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'CH-CHX-OP','淬火车间 淬火线 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-CH-CHX-OP',now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'CH-JZ1-OP','淬火车间 矫直机1# 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-CH-JZ1-OP',now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'CH-JZ2-OP','淬火车间 矫直机2# 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-CH-JZ2-OP',now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'CH-PG1-OP','淬火车间 抛光机1# 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-CH-PG1-OP',now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'CH-PG2-OP','淬火车间 抛光机2# 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-CH-PG2-OP',now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'CH-JQ-OP','淬火车间 锯切机 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-CH-JQ-OP',now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'CH-LS-OP','淬火车间 拉伸机 主操',w.id,'virtual_role_qr',true,'running','three',9980,'XT-CH-LS-OP',now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;

-- ============ 已停车间相关 OP QR 全部停用 ============
-- 厂级/分厂/老厂/花纹板/彩涂/回收/二分厂精整/铸五/铸六/冷轧三
UPDATE equipment SET is_active=false
 WHERE workshop_id IN (SELECT id FROM workshops
                        WHERE code IN ('LZ1450','LZ3','HWB','JZ2','HS','CT','ZR5','ZR6'));

-- ============ 已停 JZ 旧机列对应 OP QR 停用 ============
UPDATE equipment SET is_active=false
 WHERE code IN ('JZ-LWJ1-OP','JZ-LWJ2-OP','JZ-LWJ3-OP','JZ-HJ1-OP','JZ-HJ2-OP','JZ-HJ3-OP',
                'JZ-ZJ1-OP','JZ-ZJ2-OP','JZ-ZJ3-OP','JZ-FT1-OP','JZ-FJ-OP');

COMMIT;

SELECT '=== OP QR 校验：active 主操码 by 车间 ===' AS section;
SELECT w.code AS ws, w.name, COUNT(*) AS active_op_qr
  FROM equipment e JOIN workshops w ON e.workshop_id=w.id
 WHERE e.equipment_type='virtual_role_qr' AND e.is_active=true AND e.code LIKE '%-OP'
 GROUP BY w.code, w.name ORDER BY w.sort_order;
