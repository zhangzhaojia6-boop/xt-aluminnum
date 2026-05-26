-- 给 5/26 新增的 15 个机列各补一张主操 QR（仅按机列，不绑姓名）
-- 真机列 → 同 workshop 下 virtual_role_qr 主操码（XT-{ws}-{machine}-OP 模式）

BEGIN;

-- 热轧 6 个新机
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'RZ-HE-OP', '热轧车间 加热炉东 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-RZ-HE-OP', now(), now()
  FROM workshops w WHERE w.code='RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'RZ-HW-OP', '热轧车间 加热炉西 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-RZ-HW-OP', now(), now()
  FROM workshops w WHERE w.code='RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'RZ-GL-OP', '热轧车间 锅炉 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-RZ-GL-OP', now(), now()
  FROM workshops w WHERE w.code='RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'RZ-DM-OP', '热轧车间 双面铣 主操', w.id, 'virtual_role_qr', true, 'running', 'two', 9980, 'XT-RZ-DM-OP', now(), now()
  FROM workshops w WHERE w.code='RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'RZ-FM-OP', '热轧车间 六面铣 主操', w.id, 'virtual_role_qr', true, 'running', 'two', 9980, 'XT-RZ-FM-OP', now(), now()
  FROM workshops w WHERE w.code='RZ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'RZ-MED-OP', '热轧车间 中厚板 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-RZ-MED-OP', now(), now()
  FROM workshops w WHERE w.code='RZ' ON CONFLICT (code) DO NOTHING;

-- 1850 冷轧 4 个新机（1# 已存在主操码，只补 2#-5#）
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'LZ1850-2-OP', '1850冷轧 2# 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-LZ1850-2-OP', now(), now()
  FROM workshops w WHERE w.code='LZ1850' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'LZ1850-3-OP', '1850冷轧 3# 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-LZ1850-3-OP', now(), now()
  FROM workshops w WHERE w.code='LZ1850' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'LZ1850-4-OP', '1850冷轧 4# 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-LZ1850-4-OP', now(), now()
  FROM workshops w WHERE w.code='LZ1850' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'LZ1850-5-OP', '1850冷轧 5# 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-LZ1850-5-OP', now(), now()
  FROM workshops w WHERE w.code='LZ1850' ON CONFLICT (code) DO NOTHING;

-- 园区剪切 5 个新机
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'JQ-LJ-OP', '剪切车间 拉矫 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-JQ-LJ-OP', now(), now()
  FROM workshops w WHERE w.code='JQ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'JQ-TH-OP', '剪切车间 退火炉 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-JQ-TH-OP', now(), now()
  FROM workshops w WHERE w.code='JQ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'JQ-19G-OP', '剪切车间 19辊 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-JQ-19G-OP', now(), now()
  FROM workshops w WHERE w.code='JQ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'JQ-19N-OP', '剪切车间 新19辊 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-JQ-19N-OP', now(), now()
  FROM workshops w WHERE w.code='JQ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, qr_code, created_at, updated_at)
SELECT 'JQ-ZJ-Z-OP', '剪切车间 纵剪 主操', w.id, 'virtual_role_qr', true, 'running', 'three', 9980, 'XT-JQ-ZJ-Z-OP', now(), now()
  FROM workshops w WHERE w.code='JQ' ON CONFLICT (code) DO NOTHING;

COMMIT;

SELECT '=== 主操 QR 校验（应为 15 行新增）===' AS section;
SELECT code, name, qr_code FROM equipment
 WHERE code IN ('RZ-HE-OP','RZ-HW-OP','RZ-GL-OP','RZ-DM-OP','RZ-FM-OP','RZ-MED-OP',
                'LZ1850-2-OP','LZ1850-3-OP','LZ1850-4-OP','LZ1850-5-OP',
                'JQ-LJ-OP','JQ-TH-OP','JQ-19G-OP','JQ-19N-OP','JQ-ZJ-Z-OP')
 ORDER BY code;
