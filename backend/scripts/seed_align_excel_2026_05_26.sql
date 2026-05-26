-- 5/26 真值底对齐 part1：workshop + equipment 主体
-- 真值底：底层/输入/铸轧铸锭（一）+ 其余分厂（二）26-5-24
-- 口径：严格按 Excel 车间列。厂级/分厂/老厂/花纹板/彩涂/回收/大修/辊涂/圆片/工程板 全停用。
-- 保留 active 车间 = 铸锭 / 铸轧二 / 铸轧三 / 热轧 / 2050冷轧 / 1850冷轧 / 1650冷轧 / 精整 / 拉矫 / 剪切 / 淬火 / 在线退火 / 成品库
-- 配套 qr 同步：seed_align_excel_2026_05_26_qr.sql

BEGIN;

-- ============ 1. 车间名对齐 ============
UPDATE workshops SET name='铸锭分厂' WHERE code='ZD';
UPDATE workshops SET name='铸轧二' WHERE code='ZR2';
UPDATE workshops SET name='铸轧三' WHERE code='ZR3';
UPDATE workshops SET name='热轧' WHERE code='RZ';
UPDATE workshops SET name='2050冷轧' WHERE code='LZ2050';
UPDATE workshops SET name='1850冷轧' WHERE code='LZ1850';
UPDATE workshops SET name='1650冷轧' WHERE code='LZ1650';
UPDATE workshops SET name='精整车间' WHERE code='JZ';
UPDATE workshops SET name='剪切车间' WHERE code='JQ';
UPDATE workshops SET name='在线退火分厂' WHERE code='ZXTF';

-- ============ 2. Excel 不显示的车间全部停用 ============
-- 厂级/分厂/老厂/花纹板/彩涂/回收/冷轧三/二分厂精整/铸五/铸六
UPDATE workshops SET is_active=false
 WHERE code IN ('LZ1450','LZ3','HWB','JZ2','HS','CT','ZR5','ZR6');

-- ============ 3. 新建车间（拉矫 + 淬火） ============
INSERT INTO workshops (code, name, sort_order, is_active, created_at, updated_at)
VALUES ('LJ','拉矫车间',16,true,now(),now())
ON CONFLICT (code) DO NOTHING;
INSERT INTO workshops (code, name, sort_order, is_active, created_at, updated_at)
VALUES ('CH','淬火车间',220,true,now(),now())
ON CONFLICT (code) DO NOTHING;

-- ============ 4. JQ 剪切车间 = 5 台（1#/2#/3#/4#/重卷） ============
UPDATE equipment SET name='1#' WHERE code='JQ-1';
UPDATE equipment SET name='2#' WHERE code='JQ-2';
UPDATE equipment SET name='3#' WHERE code='JQ-3';
UPDATE equipment SET name='4#' WHERE code='JQ-4';
UPDATE equipment SET name='重卷' WHERE code='JQ-ZJ';

-- 4b. 拉矫段 4 台迁到 LJ：拉矫 / 退火炉 / 大分切 / 小剪子
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='LJ'), name='拉矫'
 WHERE code='JQ-LJ';
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='LJ'), name='退火炉'
 WHERE code='JQ-TH';
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'LJ-DFC','大分切',w.id,'shear',true,'running','three',20,now(),now()
  FROM workshops w WHERE w.code='LJ' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'LJ-XJZ','小剪子',w.id,'shear',true,'running','three',21,now(),now()
  FROM workshops w WHERE w.code='LJ' ON CONFLICT (code) DO NOTHING;

-- 4c. 精整段 3 台从 JQ 迁到 JZ：19辊 / 新19辊 / 纵剪
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='JZ'), name='19辊'
 WHERE code='JQ-19G';
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='JZ'), name='新19辊'
 WHERE code='JQ-19N';
UPDATE equipment SET workshop_id=(SELECT id FROM workshops WHERE code='JZ'), name='纵剪'
 WHERE code='JQ-ZJ-Z';

-- ============ 5. JZ 精整车间 = 3 台，旧 11 台停用 ============
UPDATE equipment SET is_active=false
 WHERE workshop_id=(SELECT id FROM workshops WHERE code='JZ')
   AND code IN ('JZ-LWJ1','JZ-LWJ2','JZ-LWJ3','JZ-HJ1','JZ-HJ2','JZ-HJ3',
                'JZ-ZJ1','JZ-ZJ2','JZ-ZJ3','JZ-FT1','JZ-FJ');

-- ============ 6. RZ 热轧 = 6 台 ============
UPDATE equipment SET name='热轧机' WHERE code='RZ-ZJ';
UPDATE equipment SET name='锯床' WHERE code='RZ-JC';
UPDATE equipment SET name='中厚板' WHERE code='RZ-MED';
UPDATE equipment SET name='六面铣' WHERE code='RZ-FM';
UPDATE equipment SET name='双面铣2台' WHERE code='RZ-DM';
UPDATE equipment SET name='加热炉' WHERE code='RZ-HE';
UPDATE equipment SET is_active=false WHERE code IN ('RZ-XC','RZ-HW','RZ-GL');

-- ============ 7. ZXTF 在线退火 = 4 台 ============
UPDATE equipment SET name='新厂北' WHERE code='ZXTF-1';
UPDATE equipment SET name='新厂南' WHERE code='ZXTF-2';
UPDATE equipment SET name='园区北' WHERE code='ZXTF-3';
UPDATE equipment SET name='园区南' WHERE code='ZXTF-4';

-- ============ 8. ZD 铸锭 = 4 台（去线字） ============
UPDATE equipment SET name='1#' WHERE code='ZD-1';
UPDATE equipment SET name='2#' WHERE code='ZD-2';
UPDATE equipment SET name='3#' WHERE code='ZD-3';
UPDATE equipment SET name='4#' WHERE code='ZD-4';

-- ============ 9. LZ2050/LZ1650/LZ1850 机列名 ============
UPDATE equipment SET name='2050#' WHERE code='LZ2050-1';
UPDATE equipment SET name='1650#' WHERE code='LZ1650-1';
UPDATE equipment SET name='1#' WHERE code='LZ1850-1';

-- ============ 10. 淬火车间 = 7 台 ============
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'CH-CHX','淬火线',w.id,'annealing_line',true,'running','three',1,now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'CH-JZ1','矫直机1#',w.id,'straightener',true,'running','three',2,now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'CH-JZ2','矫直机2#',w.id,'straightener',true,'running','three',3,now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'CH-PG1','抛光机1#',w.id,'finishing',true,'running','three',4,now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'CH-PG2','抛光机2#',w.id,'finishing',true,'running','three',5,now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'CH-JQ','锯切机',w.id,'sawing',true,'running','three',6,now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;
INSERT INTO equipment (code, name, workshop_id, equipment_type, is_active, operational_status, shift_mode, sort_order, created_at, updated_at)
SELECT 'CH-LS','拉伸机',w.id,'straightener',true,'running','three',7,now(),now()
  FROM workshops w WHERE w.code='CH' ON CONFLICT (code) DO NOTHING;

-- ============ 11. 已停车间内全部机列停用 ============
UPDATE equipment SET is_active=false
 WHERE workshop_id IN (SELECT id FROM workshops
                        WHERE code IN ('LZ1450','LZ3','HWB','JZ2','HS','CT','ZR5','ZR6'));

COMMIT;

-- 校验
SELECT '=== 1. 车间状态（active 预期 13：ZD/ZR2/ZR3/RZ/LZ2050/LZ1850/LZ1650/JZ/LJ/JQ/CH/ZXTF/CPK；inactive：ZR5/ZR6/LZ1450/LZ3/HWB/JZ2/HS/CT）===' AS section;
SELECT code, name, is_active FROM workshops ORDER BY sort_order, code;

SELECT '=== 2. JQ 剪切车间（5 台：1#/2#/3#/4#/重卷）===' AS section;
SELECT code,name FROM equipment WHERE workshop_id=(SELECT id FROM workshops WHERE code='JQ') AND equipment_type NOT IN ('virtual_role_qr','virtual_workshop_qr') AND is_active=true ORDER BY sort_order,code;

SELECT '=== 3. LJ 拉矫车间（4 台：拉矫/大分切/小剪子/退火炉）===' AS section;
SELECT code,name FROM equipment WHERE workshop_id=(SELECT id FROM workshops WHERE code='LJ') AND equipment_type NOT IN ('virtual_role_qr','virtual_workshop_qr') AND is_active=true ORDER BY sort_order,code;

SELECT '=== 4. JZ 精整车间（3 台：19辊/新19辊/纵剪）===' AS section;
SELECT code,name FROM equipment WHERE workshop_id=(SELECT id FROM workshops WHERE code='JZ') AND equipment_type NOT IN ('virtual_role_qr','virtual_workshop_qr') AND is_active=true ORDER BY code;

SELECT '=== 5. RZ 热轧（6 台）===' AS section;
SELECT code,name FROM equipment WHERE workshop_id=(SELECT id FROM workshops WHERE code='RZ') AND equipment_type NOT IN ('virtual_role_qr','virtual_workshop_qr') AND is_active=true ORDER BY sort_order,code;

SELECT '=== 6. CH 淬火车间（7 台）===' AS section;
SELECT code,name FROM equipment WHERE workshop_id=(SELECT id FROM workshops WHERE code='CH') AND equipment_type NOT IN ('virtual_role_qr','virtual_workshop_qr') AND is_active=true ORDER BY sort_order,code;
