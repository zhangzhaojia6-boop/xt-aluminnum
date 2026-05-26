-- 5/26 培训前主数据对齐脚本 — 真值底来自 底层/输入/铸轧铸锭(一) + 其余分厂(二) 26-5-24
-- 幂等：所有 INSERT 都带 ON CONFLICT DO NOTHING；UPDATE 用具体条件。
-- 在 prod 跑：psql ... -f seed_master_2026_05_26.sql

BEGIN;

-- ============== 1. 关停零主操车间（ZR5/ZR6）==============
UPDATE workshops SET is_active = false WHERE code IN ('ZR5', 'ZR6');

-- ============== 2. 退役冗余角色（DB 仍残留 weigher / maintenance_lead / hydraulic_lead）==============
-- 已校验：mobile_shift_reports.leader_user_id 没有引用这三类角色，可安全软停用。
UPDATE users SET is_active = false
 WHERE role IN ('weigher', 'maintenance_lead', 'hydraulic_lead')
   AND is_active = true;

-- ============== 3. 热轧车间补缺机列（加热炉东/西、锅炉、双面铣、六面铣、中厚板）==============
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'RZ-HE', '加热炉东', w.id, 'hot_mill', true, 'running', 'three', 4, now(), now()
  FROM workshops w WHERE w.code = 'RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'RZ-HW', '加热炉西', w.id, 'hot_mill', true, 'running', 'three', 5, now(), now()
  FROM workshops w WHERE w.code = 'RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'RZ-GL', '锅炉', w.id, 'hot_mill', true, 'running', 'three', 6, now(), now()
  FROM workshops w WHERE w.code = 'RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'RZ-DM', '双面铣', w.id, 'milling', true, 'running', 'two', 7, now(), now()
  FROM workshops w WHERE w.code = 'RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'RZ-FM', '六面铣', w.id, 'milling', true, 'running', 'two', 8, now(), now()
  FROM workshops w WHERE w.code = 'RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'RZ-MED', '中厚板', w.id, 'hot_mill', true, 'running', 'three', 9, now(), now()
  FROM workshops w WHERE w.code = 'RZ' ON CONFLICT (code) DO NOTHING;

-- ============== 4. 1850 冷轧车间补 2#-5# 机列 ==============
-- 已存的 LZ1850-1 = "1850轧机" 改名为 "1#" 与 1#-5# 习惯一致
UPDATE equipment SET name = '1#' WHERE code = 'LZ1850-1' AND name = '1850轧机';
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'LZ1850-2', '2#', w.id, 'cold_mill', true, 'running', 'three', 2, now(), now()
  FROM workshops w WHERE w.code = 'LZ1850' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'LZ1850-3', '3#', w.id, 'cold_mill', true, 'running', 'three', 3, now(), now()
  FROM workshops w WHERE w.code = 'LZ1850' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'LZ1850-4', '4#', w.id, 'cold_mill', true, 'running', 'three', 4, now(), now()
  FROM workshops w WHERE w.code = 'LZ1850' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'LZ1850-5', '5#', w.id, 'cold_mill', true, 'running', 'three', 5, now(), now()
  FROM workshops w WHERE w.code = 'LZ1850' ON CONFLICT (code) DO NOTHING;

-- ============== 5. 园区剪切补：拉矫、退火炉、19辊、新19辊、纵剪 ==============
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'JQ-LJ', '拉矫', w.id, 'straightener', true, 'running', 'three', 10, now(), now()
  FROM workshops w WHERE w.code = 'JQ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'JQ-TH', '退火炉', w.id, 'annealing_line', true, 'running', 'three', 11, now(), now()
  FROM workshops w WHERE w.code = 'JQ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'JQ-19G', '19辊', w.id, 'cold_mill', true, 'running', 'three', 12, now(), now()
  FROM workshops w WHERE w.code = 'JQ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'JQ-19N', '新19辊', w.id, 'cold_mill', true, 'running', 'three', 13, now(), now()
  FROM workshops w WHERE w.code = 'JQ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'JQ-ZJ-Z', '纵剪', w.id, 'slitter', true, 'running', 'three', 14, now(), now()
  FROM workshops w WHERE w.code = 'JQ' ON CONFLICT (code) DO NOTHING;

COMMIT;

-- 校验
SELECT '=== 1. 车间状态 ===' AS section;
SELECT code, name, is_active FROM workshops WHERE code IN ('ZR5', 'ZR6', 'RZ', 'LZ1850', 'JQ') ORDER BY code;

SELECT '=== 2. 退役角色账号数（应该全部 0 active）===' AS section;
SELECT role, COUNT(*) FILTER (WHERE is_active) AS active_cnt, COUNT(*) AS total FROM users
 WHERE role IN ('weigher', 'maintenance_lead', 'hydraulic_lead') GROUP BY role;

SELECT '=== 3. 热轧机列 ===' AS section;
SELECT code, name FROM equipment WHERE workshop_id = (SELECT id FROM workshops WHERE code = 'RZ')
   AND equipment_type = 'real' ORDER BY sort_order;

SELECT '=== 4. 1850 冷轧机列 ===' AS section;
SELECT code, name FROM equipment WHERE workshop_id = (SELECT id FROM workshops WHERE code = 'LZ1850')
   AND equipment_type = 'real' ORDER BY sort_order;

SELECT '=== 5. 园区剪切机列 ===' AS section;
SELECT code, name FROM equipment WHERE workshop_id = (SELECT id FROM workshops WHERE code = 'JQ')
   AND equipment_type = 'real' ORDER BY sort_order;
