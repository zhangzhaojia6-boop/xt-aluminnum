# 验收差距封闭 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `docs/superpowers/specs/2026-05-07-acceptance-gap-closure-spec.md` 里 D1-D7 七个交付项变成可执行的 commits，让数据中枢字段适配通过 5.6 现场事实底验收。

**Architecture:** 本 Plan 不引入新架构，全部在现有 backend/frontend 文件树内增量改动。后端只新增一个只读 endpoint（D4），前端只新增 echarts 依赖与 3 个图表组件（D5）。每个 D 项独立 commit，独立 revert。

**Tech Stack:** FastAPI + SQLAlchemy + pytest（后端）；Vue 3 + Vite + Element Plus + echarts（前端）；脚本用 Python 3.11 + pandas + openpyxl + xlrd。

---

## 工作约定

- 每个 Task 完成后单独 commit；commit message 前缀严格用 `feat(D1):` / `fix(D2):` / `refactor(D3):` 等，括号内必须是 D 编号。
- 每个 Task 第一步永远是写**失败测试**；测试不通过不要写实现。
- 每次 commit 之前跑相关 pytest，全绿才提交。
- 不许用 `git commit --no-verify` 跳 hook。
- 不许在本 Plan 之外动其它文件；如果发现需要改其它文件，先在 commit message 末尾说明并把修改限制到最小范围。

---

## Task 0: 准备 baseline

**Files:**
- 只读：`docs/superpowers/specs/2026-05-07-acceptance-gap-closure-spec.md`

- [ ] **Step 0.1: 确认 baseline 干净**

```bash
cd "D:/zzj Claude code/aluminum-bypass"
git status
git log -1 --oneline
```

Expected:
```
On branch main
nothing to commit, working tree clean
e97f5ee ... 或 main 上更新的 commit
```

如果不干净，停止并向用户报告。

- [ ] **Step 0.2: 跑一遍当前测试做 baseline**

```bash
python -m pytest backend/tests/test_real_master_data.py backend/tests/test_daily_production_mapping_service.py backend/tests/test_daily_production_canonical_service.py backend/tests/test_config_readiness_service.py -q
```

Expected: 全部 pass。记录 pass 数。如果有 fail 先停止，让用户先修。

---

## Task 1 (D1-A): 主数据加 LZ1650 / LZ1850 / HWB（失败测试）

**Files:**
- Modify: `backend/tests/test_real_master_data.py`

- [ ] **Step 1.1: 读现有测试结构**

```bash
python -c "import re; t=open('backend/tests/test_real_master_data.py',encoding='utf-8').read(); print('\n'.join(re.findall(r'def (test_\w+)',t)))"
```

记录现有测试函数名。

- [ ] **Step 1.2: 追加 1650/1850/HWB 缺失测试**

把以下测试函数追加到 `backend/tests/test_real_master_data.py` 末尾：

```python
def test_seed_real_master_data_includes_1650_1850_hwb(tmp_path):
    db = build_session(tmp_path)
    from app.services.real_master_data import seed_real_master_data
    seed_real_master_data(db)

    workshops = {item.code: item for item in db.execute(select(Workshop)).scalars().all() if item.is_active}
    for code in ('LZ1650', 'LZ1850', 'HWB'):
        assert code in workshops, f'workshop {code} missing after seed'

    equipment = {item.code: item for item in db.execute(select(Equipment)).scalars().all() if item.is_active}
    for code in ('LZ1650-1', 'LZ1850-1', 'HWB-1'):
        assert code in equipment, f'equipment {code} missing after seed'


def test_seed_real_master_data_aliases_1650_1850_hwb(tmp_path):
    db = build_session(tmp_path)
    from app.services.real_master_data import seed_real_master_data
    seed_real_master_data(db)

    aliases = {(item.alias_code, item.canonical_code) for item in db.execute(select(MasterCodeAlias)).scalars().all() if item.is_active}
    expected = {
        ('1650车间', 'LZ1650'),
        ('冷轧1650车间', 'LZ1650'),
        ('1850车间', 'LZ1850'),
        ('冷轧1850车间', 'LZ1850'),
        ('花纹板', 'HWB'),
        ('花纹板车间', 'HWB'),
    }
    missing = expected - aliases
    assert not missing, f'missing aliases: {missing}'
```

- [ ] **Step 1.3: 跑测试确认 fail**

```bash
python -m pytest backend/tests/test_real_master_data.py::test_seed_real_master_data_includes_1650_1850_hwb backend/tests/test_real_master_data.py::test_seed_real_master_data_aliases_1650_1850_hwb -v
```

Expected: 两个测试都 FAIL（assertion error，因为代码还没改）。

---

## Task 2 (D1-B): 主数据加 LZ1650 / LZ1850 / HWB（实现）

**Files:**
- Modify: `backend/app/services/real_master_data.py:35-48,136-141,222-239,243,272-286,318-319,397-399`

- [ ] **Step 2.1: 在 WORKSHOPS 列表追加 3 条**

文件 `backend/app/services/real_master_data.py:35-48`，把：

```python
WORKSHOPS = [
    {'code': 'ZD', 'name': '铸锭车间', 'sort_order': 1},
    {'code': 'ZR2', 'name': '铸二车间', 'sort_order': 2},
    {'code': 'ZR3', 'name': '铸三车间', 'sort_order': 3},
    {'code': 'RZ', 'name': '热轧车间', 'sort_order': 4},
    {'code': 'LZ2050', 'name': '2050冷轧车间', 'sort_order': 5},
    {'code': 'LZ1450', 'name': '1450冷轧车间', 'sort_order': 6},
    {'code': 'LZ3', 'name': '冷轧三车间', 'sort_order': 7},
    {'code': 'JZ', 'name': '精整车间', 'sort_order': 8},
    {'code': 'JZ2', 'name': '二分厂精整车间', 'sort_order': 9},
    {'code': 'JQ', 'name': '园区剪切车间', 'sort_order': 10},
    {'code': 'CPK', 'name': '成品库', 'sort_order': 11},
    {'code': 'ZXTF', 'name': '在线退火车间', 'sort_order': 200},
]
```

改为：

```python
WORKSHOPS = [
    {'code': 'ZD', 'name': '铸锭车间', 'sort_order': 1},
    {'code': 'ZR2', 'name': '铸二车间', 'sort_order': 2},
    {'code': 'ZR3', 'name': '铸三车间', 'sort_order': 3},
    {'code': 'RZ', 'name': '热轧车间', 'sort_order': 4},
    {'code': 'LZ2050', 'name': '2050冷轧车间', 'sort_order': 5},
    {'code': 'LZ1850', 'name': '1850冷轧车间', 'sort_order': 6},
    {'code': 'LZ1650', 'name': '1650冷轧车间', 'sort_order': 7},
    {'code': 'LZ1450', 'name': '1450冷轧车间', 'sort_order': 8},
    {'code': 'LZ3', 'name': '冷轧三车间', 'sort_order': 9},
    {'code': 'HWB', 'name': '花纹板车间', 'sort_order': 10},
    {'code': 'JZ', 'name': '精整车间', 'sort_order': 11},
    {'code': 'JZ2', 'name': '二分厂精整车间', 'sort_order': 12},
    {'code': 'JQ', 'name': '园区剪切车间', 'sort_order': 13},
    {'code': 'CPK', 'name': '成品库', 'sort_order': 14},
    {'code': 'ZXTF', 'name': '在线退火车间', 'sort_order': 200},
]
```

- [ ] **Step 2.2: 在 EQUIPMENT_BY_WORKSHOP 增 3 条机列**

在文件中找到 `'LZ1450': [...]` 后面，紧挨着插入：

```python
    'LZ1850': [
        {'code': 'LZ1850-1', 'name': '1850轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'LZ1650': [
        {'code': 'LZ1650-1', 'name': '1650轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'HWB': [
        {'code': 'HWB-1', 'name': '花纹板主轧', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
```

- [ ] **Step 2.3: 在 MES_WORKSHOP_ALIASES 追加 6 条别名**

文件 `backend/app/services/real_master_data.py:222-239`。在 `('LZ1450', '冷轧1450车间'),` 后面插入：

```python
    ('LZ1850', '1850车间'),
    ('LZ1850', '冷轧1850车间'),
    ('LZ1850', '1850冷轧'),
    ('LZ1650', '1650车间'),
    ('LZ1650', '冷轧1650车间'),
    ('LZ1650', '1650冷轧'),
    ('HWB', '花纹板'),
    ('HWB', '花纹板车间'),
```

- [ ] **Step 2.4: 在 PROCESS_BUSINESS_UNITS 把 3 条加进 rolling_branch**

把：

```python
    {'unit_code': 'rolling_branch', 'unit_name': '轧制分厂', 'workshop_codes': ['RZ', 'LZ2050', 'LZ1450', 'LZ3']},
```

改为：

```python
    {'unit_code': 'rolling_branch', 'unit_name': '轧制分厂', 'workshop_codes': ['RZ', 'LZ2050', 'LZ1850', 'LZ1650', 'LZ1450', 'LZ3', 'HWB']},
```

- [ ] **Step 2.5: 在 WORKSHOP_PROCESS_BUSINESS 追加 3 条**

文件 `backend/app/services/real_master_data.py:272-286`。在 `'LZ1450': {...}` 后面插入：

```python
    'LZ1850': {
        'process_business': '1850冷轧',
        'process_tags': ['冷轧', '1850'],
        'area_status': 'confirmed',
    },
    'LZ1650': {
        'process_business': '1650冷轧',
        'process_tags': ['冷轧', '1650'],
        'area_status': 'confirmed',
    },
    'HWB': {
        'process_business': '花纹板冷轧',
        'process_tags': ['冷轧', '花纹板'],
        'area_status': 'confirmed',
    },
```

- [ ] **Step 2.6: 在 MACHINE_PROCESS_BUSINESS_BY_CODE 追加 3 条**

文件 `backend/app/services/real_master_data.py:314-332`。在 `'LZ1450-1': '1450冷轧',` 后面插入：

```python
    'LZ1850-1': '1850冷轧',
    'LZ1650-1': '1650冷轧',
    'HWB-1': '花纹板冷轧',
```

- [ ] **Step 2.7: 删除 open_items 第一条**

文件 `backend/app/services/real_master_data.py:396-400`。把：

```python
        'open_items': [
            '冷轧1650和1850需要补入标准车间/机列后才能正式承接日报未解析行',
            '新厂在线车间和园区在线车间当前映射到ZXTF，仍需MES设备/南北线字段拆分',
            'JZ2二分厂精整当前只有1#到8#机列，具体横剪/纵剪/拉矫职责需要现场确认',
        ],
```

改为：

```python
        'open_items': [
            '新厂在线车间和园区在线车间当前映射到ZXTF，仍需MES设备/南北线字段拆分',
            'JZ2二分厂精整当前只有1#到8#机列，具体横剪/纵剪/拉矫职责需要现场确认',
        ],
```

- [ ] **Step 2.8: 跑测试确认 pass**

```bash
python -m pytest backend/tests/test_real_master_data.py -v
```

Expected: 全部 pass，包括 Task 1 加的两个测试。

- [ ] **Step 2.9: 跑全量主数据相关回归**

```bash
python -m pytest backend/tests/test_real_master_data.py backend/tests/test_yield_matrix_canonical_service.py backend/tests/test_master_service.py -q
```

Expected: 全部 pass。如果 yield_matrix 测试失败，进入 Task 3；否则跳过 Task 3 直接进 Task 4。

- [ ] **Step 2.10: Commit**

```bash
git add backend/app/services/real_master_data.py backend/tests/test_real_master_data.py
git commit -m "feat(D1): add LZ1650 LZ1850 HWB workshops and aliases for 5.6 dataset"
```

---

## Task 3 (D1-C): yield_matrix 别名拆 1650 与 2050

**Files:**
- Modify: `backend/app/services/yield_matrix_canonical_service.py:31-38`
- Modify: `backend/tests/test_yield_matrix_canonical_service.py`

仅当 Task 2.9 yield_matrix 测试 fail 才执行。否则跳过。

- [ ] **Step 3.1: 写失败测试**

在 `backend/tests/test_yield_matrix_canonical_service.py` 末尾追加：

```python
def test_workshop_aliases_split_1650_2050():
    from app.services.yield_matrix_canonical_service import WORKSHOP_ALIASES
    assert 'cold_roll_1650' in WORKSHOP_ALIASES
    assert 'cold_roll_2050' in WORKSHOP_ALIASES
    assert '1650' in WORKSHOP_ALIASES['cold_roll_1650']
    assert '2050' in WORKSHOP_ALIASES['cold_roll_2050']
    assert 'cold_roll_1650_2050' not in WORKSHOP_ALIASES
```

- [ ] **Step 3.2: 跑测试确认 fail**

```bash
python -m pytest backend/tests/test_yield_matrix_canonical_service.py::test_workshop_aliases_split_1650_2050 -v
```

Expected: FAIL。

- [ ] **Step 3.3: 拆别名**

文件 `backend/app/services/yield_matrix_canonical_service.py:31-38`。把：

```python
WORKSHOP_ALIASES: dict[str, tuple[str, ...]] = {
    'cold_roll_1450': ('1450', '1450冷轧', '1450车间'),
    'cold_roll_1650_2050': ('1650+2050', '1650 / 2050', '2050', '2050冷轧', '2050车间'),
    'cold_roll_1850': ('1850', '1850冷轧', '1850车间'),
    'stretch': ('拉矫',),
    'finishing': ('精整',),
    'park_cutting': ('园区飞剪', '飞剪', '园区剪切', '剪切'),
}
```

改为：

```python
WORKSHOP_ALIASES: dict[str, tuple[str, ...]] = {
    'cold_roll_1450': ('1450', '1450冷轧', '1450车间'),
    'cold_roll_1650': ('1650', '1650冷轧', '1650车间'),
    'cold_roll_1850': ('1850', '1850冷轧', '1850车间'),
    'cold_roll_2050': ('2050', '2050冷轧', '2050车间'),
    'cold_roll_pattern_plate': ('花纹板', '花纹板车间'),
    'stretch': ('拉矫',),
    'finishing': ('精整',),
    'park_cutting': ('园区飞剪', '飞剪', '园区剪切', '剪切'),
}
```

- [ ] **Step 3.4: 找下游引用**

```bash
grep -rn "cold_roll_1650_2050" backend/
```

如果有下游代码引用 `cold_roll_1650_2050` key（应该有，至少 `realtime_service.py:535-536` 我看到过），把它们改成根据 workshop_code 选择 `cold_roll_1650` 或 `cold_roll_2050`。具体改法：

文件 `backend/app/services/realtime_service.py:533-538`，把：

```python
    if '1450' in text:
        return 'cold_roll_1450'
    if '1650' in text or '2050' in text:
        return 'cold_roll_1650_2050'
    if '1850' in text:
        return 'cold_roll_1850'
```

改为：

```python
    if '1450' in text:
        return 'cold_roll_1450'
    if '1650' in text:
        return 'cold_roll_1650'
    if '2050' in text:
        return 'cold_roll_2050'
    if '1850' in text:
        return 'cold_roll_1850'
    if '花纹板' in text:
        return 'cold_roll_pattern_plate'
```

- [ ] **Step 3.5: 跑回归**

```bash
python -m pytest backend/tests/test_yield_matrix_canonical_service.py backend/tests/test_realtime_service.py -q
```

Expected: 全部 pass。

- [ ] **Step 3.6: Commit**

```bash
git add backend/app/services/yield_matrix_canonical_service.py backend/app/services/realtime_service.py backend/tests/test_yield_matrix_canonical_service.py
git commit -m "refactor(D1): split cold_roll_1650_2050 alias into 1650 and 2050"
```

---

## Task 4 (D2-A): daily_production 映射规则补全（失败测试）

**Files:**
- Modify: `backend/tests/test_daily_production_mapping_service.py`

- [ ] **Step 4.1: 追加 5.6 实际 label 的测试用例**

在 `backend/tests/test_daily_production_mapping_service.py` 末尾追加：

```python
def test_mapping_rules_cover_5_6_workbook_labels():
    from app.services.daily_production_mapping_service import DAILY_PRODUCTION_MAPPING_RULES

    expected_keys = {
        ('冷轧', '1650'): ('LZ1650', 'LZ1650-1'),
        ('冷轧', '1850'): ('LZ1850', 'LZ1850-1'),
        ('冷轧', '花纹板'): ('HWB', 'HWB-1'),
        ('精整', '纵剪'): ('JZ', 'JZ-ZJ1'),
        ('精整', '横剪'): ('JZ', 'JZ-HJ1'),
        ('精整', '剪子'): ('JZ', 'JZ-HJ1'),
        ('精整', '剪切'): ('JZ', 'JZ-HJ1'),
        ('精整', '包装'): ('JZ', None),
        ('拉矫', '拉矫'): ('JZ', 'JZ-LWJ1'),
        ('拉矫', '洗拉'): ('JZ', 'JZ-LWJ1'),
        ('拉矫', '分切'): ('JZ', 'JZ-FT1'),
        ('拉矫', '大分切'): ('JZ', 'JZ-FT1'),
        ('退火炉', '拉矫'): ('JZ', None),
        ('在线退火', '新厂北线'): ('ZXTF', 'ZXTF-1'),
        ('在线退火', '园区北线'): ('ZXTF', 'ZXTF-3'),
        ('在线退火', '南线'): ('ZXTF', None),
        ('园区淬火', ''): ('JQ', None),
        ('园区精整', ''): ('JQ', None),
        ('回收', ''): ('ZD', None),
        ('大修', ''): ('RZ', None),
    }

    missing = []
    wrong = []
    for key, (workshop_code, equipment_code) in expected_keys.items():
        rule = DAILY_PRODUCTION_MAPPING_RULES.get(key)
        if rule is None:
            missing.append(key)
            continue
        if rule.workshop_code != workshop_code:
            wrong.append((key, 'workshop', rule.workshop_code, workshop_code))
        if rule.equipment_code != equipment_code:
            wrong.append((key, 'equipment', rule.equipment_code, equipment_code))

    assert not missing, f'missing rules: {missing}'
    assert not wrong, f'wrong rules: {wrong}'
```

- [ ] **Step 4.2: 跑测试确认 fail**

```bash
python -m pytest backend/tests/test_daily_production_mapping_service.py::test_mapping_rules_cover_5_6_workbook_labels -v
```

Expected: FAIL with `missing rules: [...]`。

---

## Task 5 (D2-B): daily_production 映射规则补全（实现）

**Files:**
- Modify: `backend/app/services/daily_production_mapping_service.py:75-83`

- [ ] **Step 5.1: 替换 DAILY_PRODUCTION_MAPPING_RULES 为完整版**

文件 `backend/app/services/daily_production_mapping_service.py:75-83`。把整段 `DAILY_PRODUCTION_MAPPING_RULES = {...}` 替换为：

```python
DAILY_PRODUCTION_MAPPING_RULES: dict[tuple[str, str], MappingRule] = {
    # 铸轧分厂
    ('铸锭', ''): MappingRule(workshop_code='ZD'),
    ('铸轧', '铸二'): MappingRule(workshop_code='ZR2', equipment_code='ZR2'),
    ('铸轧', '铸三'): MappingRule(workshop_code='ZR3', equipment_code='ZR3'),

    # 热轧
    ('热轧', '铣床'): MappingRule(workshop_code='RZ', equipment_code='RZ-XC', equipment_required=True),
    ('热轧', '热轧'): MappingRule(workshop_code='RZ', equipment_code='RZ-ZJ', equipment_required=True),

    # 冷轧（含花纹板）
    ('冷轧', '2050'): MappingRule(workshop_code='LZ2050', equipment_code='LZ2050-1', equipment_required=True),
    ('冷轧', '1850'): MappingRule(workshop_code='LZ1850', equipment_code='LZ1850-1', equipment_required=True),
    ('冷轧', '1650'): MappingRule(workshop_code='LZ1650', equipment_code='LZ1650-1', equipment_required=True),
    ('冷轧', '1450'): MappingRule(workshop_code='LZ1450', equipment_code='LZ1450-1', equipment_required=True),
    ('冷轧', '花纹板'): MappingRule(workshop_code='HWB', equipment_code='HWB-1', equipment_required=True),

    # 精整（横剪/纵剪/包装）
    ('精整', '纵剪'): MappingRule(workshop_code='JZ', equipment_code='JZ-ZJ1', equipment_required=True),
    ('精整', '横剪'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
    ('精整', '剪子'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
    ('精整', '剪切'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
    ('精整', '包装'): MappingRule(workshop_code='JZ'),

    # 拉矫工序
    ('拉矫', '拉矫'): MappingRule(workshop_code='JZ', equipment_code='JZ-LWJ1', equipment_required=True),
    ('拉矫', '洗拉'): MappingRule(workshop_code='JZ', equipment_code='JZ-LWJ1', equipment_required=True),
    ('拉矫', '分切'): MappingRule(workshop_code='JZ', equipment_code='JZ-FT1', equipment_required=True),
    ('拉矫', '大分切'): MappingRule(workshop_code='JZ', equipment_code='JZ-FT1', equipment_required=True),
    ('退火炉', '拉矫'): MappingRule(workshop_code='JZ'),

    # 在线退火（南北线暂挂车间，待 MES 字段拆分）
    ('在线退火', '新厂北线'): MappingRule(workshop_code='ZXTF', equipment_code='ZXTF-1', equipment_required=True),
    ('在线退火', '园区北线'): MappingRule(workshop_code='ZXTF', equipment_code='ZXTF-3', equipment_required=True),
    ('在线退火', '南线'): MappingRule(workshop_code='ZXTF'),

    # 园区
    ('园区剪切', ''): MappingRule(workshop_code='JQ'),
    ('园区淬火', ''): MappingRule(workshop_code='JQ'),
    ('园区精整', ''): MappingRule(workshop_code='JQ'),

    # 辅助（暂挂最相关车间，等现场确认后细分）
    ('回收', ''): MappingRule(workshop_code='ZD'),
    ('大修', ''): MappingRule(workshop_code='RZ'),
}
```

- [ ] **Step 5.2: 跑测试确认 pass**

```bash
python -m pytest backend/tests/test_daily_production_mapping_service.py -v
```

Expected: 全部 pass。

- [ ] **Step 5.3: Commit**

```bash
git add backend/app/services/daily_production_mapping_service.py backend/tests/test_daily_production_mapping_service.py
git commit -m "feat(D2): expand daily production mapping rules to cover 5.6 workbook labels"
```

---

## Task 6 (D3-A): 单位推断硬阻断（失败测试）

**Files:**
- Modify: `backend/tests/test_daily_production_canonical_service.py`

- [ ] **Step 6.1: 看现有 SUSPICIOUS 阈值代码**

```bash
grep -n "SUSPICIOUS_DAILY_OUTPUT_TONS\|hard_block\|kg_as_tons" backend/app/services/daily_production_canonical_service.py
```

记录定义行号。

- [ ] **Step 6.2: 追加测试**

在 `backend/tests/test_daily_production_canonical_service.py` 末尾追加：

```python
import pandas as pd
from app.services.daily_production_canonical_service import parse_daily_production_sheet


def _build_frame(rows):
    columns = ['车间', '项目', '日投料(t)', '月投料(t)', '日产量(t)', '月产量(t)', '日合格(t)', '日废料(t)', '月废料(t)', '成品率', '指标']
    return pd.DataFrame(rows, columns=columns)


def test_parse_daily_production_hard_blocks_kg_as_tons_above_50000():
    frame = _build_frame([
        ['冷轧', '2050', 100, 1000, 60000, 80000, 0, 0, 0, 0.95, 0.96],
    ])
    parsed = parse_daily_production_sheet('5-1', frame, source_batch_id=1, year_hint=2026)
    issue_codes = {item.get('code') for item in parsed.mapped_data.get('issues', [])}
    assert 'hard_block_kg_as_tons' in issue_codes
    assert parsed.status == 'blocked'


def test_parse_daily_production_warns_kg_as_tons_above_5000():
    frame = _build_frame([
        ['冷轧', '2050', 100, 1000, 6000, 80000, 0, 0, 0, 0.95, 0.96],
    ])
    parsed = parse_daily_production_sheet('5-1', frame, source_batch_id=1, year_hint=2026)
    issue_codes = {item.get('code') for item in parsed.mapped_data.get('issues', [])}
    assert 'suspicious_daily_output_tons' in issue_codes
    assert parsed.status in ('warning', 'ready')


def test_parse_daily_production_passes_5_6_realistic_values():
    frame = _build_frame([
        ['铸锭', '', 0, 0, 369, 8000, 0, 0, 0, 0, 0],
        ['冷轧', '1650', 100, 3000, 220, 6500, 0, 0, 0, 0.95, 0.96],
        ['冷轧', '2050', 80, 2400, 59, 1700, 0, 0, 0, 0.95, 0.96],
    ])
    parsed = parse_daily_production_sheet('5-6', frame, source_batch_id=1, year_hint=2026)
    issue_codes = {item.get('code') for item in parsed.mapped_data.get('issues', [])}
    assert 'hard_block_kg_as_tons' not in issue_codes
    assert 'suspicious_daily_output_tons' not in issue_codes
```

- [ ] **Step 6.3: 跑测试确认 fail**

```bash
python -m pytest backend/tests/test_daily_production_canonical_service.py::test_parse_daily_production_hard_blocks_kg_as_tons_above_50000 backend/tests/test_daily_production_canonical_service.py::test_parse_daily_production_warns_kg_as_tons_above_5000 backend/tests/test_daily_production_canonical_service.py::test_parse_daily_production_passes_5_6_realistic_values -v
```

Expected: 头两个 FAIL（缺新阻断逻辑），第三个可能 pass。

---

## Task 7 (D3-B): 单位推断硬阻断（实现）

**Files:**
- Modify: `backend/app/services/daily_production_canonical_service.py`

- [ ] **Step 7.1: 找现有阈值常量**

```bash
grep -n "SUSPICIOUS_DAILY_OUTPUT_TONS\s*=" backend/app/services/daily_production_canonical_service.py
```

记下行号。

- [ ] **Step 7.2: 加新常量并改阈值**

把 `SUSPICIOUS_DAILY_OUTPUT_TONS = 10000` 那行改为：

```python
SUSPICIOUS_DAILY_OUTPUT_TONS = 5000
HARD_BLOCK_DAILY_OUTPUT_TONS = 50000
```

- [ ] **Step 7.3: 改阻断逻辑**

文件 `backend/app/services/daily_production_canonical_service.py:172-186`。把：

```python
        if not _has_production_values(row_payload):
            continue
        daily_output = row_payload.get('daily_output_tons')
        if daily_output is not None and daily_output > SUSPICIOUS_DAILY_OUTPUT_TONS:
            issues.append(
                {
                    'code': 'suspicious_daily_output_tons',
                    'message': '每日产量日报值超过 10000t，请核对是否把 kg 当作 t。',
                    'row_index': row_index,
                    'workshop_label': row_payload['workshop_label'],
                    'project_label': row_payload['project_label'],
                    'value': daily_output,
                }
            )
        rows.append(row_payload)
```

改为：

```python
        if not _has_production_values(row_payload):
            continue
        daily_output = row_payload.get('daily_output_tons')
        if daily_output is not None and daily_output > HARD_BLOCK_DAILY_OUTPUT_TONS:
            issues.append(
                {
                    'code': 'hard_block_kg_as_tons',
                    'message': f'每日产量日报值 {daily_output} 超过 {HARD_BLOCK_DAILY_OUTPUT_TONS}t，疑似把 kg 当作 t，已硬阻断。',
                    'row_index': row_index,
                    'workshop_label': row_payload['workshop_label'],
                    'project_label': row_payload['project_label'],
                    'value': daily_output,
                }
            )
        elif daily_output is not None and daily_output > SUSPICIOUS_DAILY_OUTPUT_TONS:
            issues.append(
                {
                    'code': 'suspicious_daily_output_tons',
                    'message': f'每日产量日报值超过 {SUSPICIOUS_DAILY_OUTPUT_TONS}t，请核对是否把 kg 当作 t。',
                    'row_index': row_index,
                    'workshop_label': row_payload['workshop_label'],
                    'project_label': row_payload['project_label'],
                    'value': daily_output,
                }
            )
        rows.append(row_payload)
```

- [ ] **Step 7.4: parse_daily_production_sheet 阻断后的 status**

文件 `backend/app/services/daily_production_canonical_service.py:201-208`。把：

```python
    business_date = _detect_business_date(sheet_name, frame, year_hint=year_hint)
    rows, issues = _extract_rows(frame)
    quality_status = 'ready'
    if issues:
        quality_status = 'warning'
    if not rows or business_date is None:
        quality_status = 'blocked'
```

改为：

```python
    business_date = _detect_business_date(sheet_name, frame, year_hint=year_hint)
    rows, issues = _extract_rows(frame)
    quality_status = 'ready'
    if issues:
        quality_status = 'warning'
    if any(item.get('code') == 'hard_block_kg_as_tons' for item in issues):
        quality_status = 'blocked'
    if not rows or business_date is None:
        quality_status = 'blocked'
```

- [ ] **Step 7.5: 跑测试确认 pass**

```bash
python -m pytest backend/tests/test_daily_production_canonical_service.py -v
```

Expected: 全部 pass。

- [ ] **Step 7.6: 跑导入回归**

```bash
python -m pytest backend/tests/test_daily_production_canonical_service.py backend/tests/test_import_service_daily_production.py backend/tests/test_daily_production_mapping_service.py -q
```

Expected: 全部 pass。

- [ ] **Step 7.7: Commit**

```bash
git add backend/app/services/daily_production_canonical_service.py backend/tests/test_daily_production_canonical_service.py
git commit -m "feat(D3): hard-block kg-as-tons inputs above 50000 threshold"
```

---

## Task 8 (D4-A): 机列绑定覆盖率门禁（失败测试）

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/tests/test_config_readiness_service.py`

- [ ] **Step 8.1: 加配置项**

文件 `backend/app/config.py`，在 `MES_SYNC_BACKOFF_SECONDS: float = 2.0` 之后插入：

```python
    PILOT_WORKSHOP_CODES: str = ''
    PILOT_BINDING_COVERAGE_THRESHOLD: float = 0.8
```

- [ ] **Step 8.2: 写失败测试**

在 `backend/tests/test_config_readiness_service.py` 末尾追加：

```python
def test_evaluate_equipment_binding_warns_when_pilot_coverage_below_threshold(monkeypatch):
    from app.services.config_readiness_service import evaluate_equipment_binding
    from app.config import settings

    monkeypatch.setattr(settings, 'PILOT_WORKSHOP_CODES', 'LZ2050,LZ1650', raising=False)
    monkeypatch.setattr(settings, 'PILOT_BINDING_COVERAGE_THRESHOLD', 0.8, raising=False)

    workshops = [
        SimpleNamespace(id=1, code='LZ2050', is_active=True),
        SimpleNamespace(id=2, code='LZ1650', is_active=True),
        SimpleNamespace(id=3, code='LZ1450', is_active=True),
    ]
    equipment_rows = [
        SimpleNamespace(id=10, code='LZ2050-1', workshop_id=1, is_active=True, bound_user_id=100, name='2050轧机'),
        SimpleNamespace(id=11, code='LZ1650-1', workshop_id=2, is_active=True, bound_user_id=None, name='1650轧机'),
        SimpleNamespace(id=12, code='LZ1450-1', workshop_id=3, is_active=True, bound_user_id=200, name='1450轧机'),
    ]
    user_map = {100: SimpleNamespace(id=100, workshop_id=1), 200: SimpleNamespace(id=200, workshop_id=3)}

    result = evaluate_equipment_binding(equipment_rows=equipment_rows, user_map=user_map, workshop_rows=workshops)

    assert result['status'] == 'warning'
    assert result['action_required'] == 'bind_pilot_machine_users'
    assert result['detail'] == 'pilot_binding_coverage_below_threshold'
    assert result['coverage'] == 0.5
    assert 'LZ1650-1' in result['unbound']


def test_evaluate_equipment_binding_ok_when_pilot_fully_bound(monkeypatch):
    from app.services.config_readiness_service import evaluate_equipment_binding
    from app.config import settings

    monkeypatch.setattr(settings, 'PILOT_WORKSHOP_CODES', 'LZ2050', raising=False)
    monkeypatch.setattr(settings, 'PILOT_BINDING_COVERAGE_THRESHOLD', 0.8, raising=False)

    workshops = [SimpleNamespace(id=1, code='LZ2050', is_active=True)]
    equipment_rows = [
        SimpleNamespace(id=10, code='LZ2050-1', workshop_id=1, is_active=True, bound_user_id=100, name='2050轧机'),
    ]
    user_map = {100: SimpleNamespace(id=100, workshop_id=1)}

    result = evaluate_equipment_binding(equipment_rows=equipment_rows, user_map=user_map, workshop_rows=workshops)

    assert result['status'] == 'ok'
    assert result['coverage'] == 1.0
```

文件顶部如果还没有 `from types import SimpleNamespace` 就加上。

- [ ] **Step 8.3: 跑测试确认 fail**

```bash
python -m pytest backend/tests/test_config_readiness_service.py::test_evaluate_equipment_binding_warns_when_pilot_coverage_below_threshold backend/tests/test_config_readiness_service.py::test_evaluate_equipment_binding_ok_when_pilot_fully_bound -v
```

Expected: 两个测试 FAIL（函数签名变了 / 字段没有 coverage）。

---

## Task 9 (D4-B): 机列绑定覆盖率门禁（实现）

**Files:**
- Modify: `backend/app/services/config_readiness_service.py:175-211`

- [ ] **Step 9.1: 看现有 evaluate_equipment_binding 完整实现**

```bash
grep -n "def evaluate_equipment_binding" backend/app/services/config_readiness_service.py
```

读取该函数前后 40 行，确认参数签名。

- [ ] **Step 9.2: 重构 evaluate_equipment_binding**

定位 `def evaluate_equipment_binding(...)` 函数，整段替换为（注意保持原 signature 兼容现有调用方）：

```python
def evaluate_equipment_binding(
    *,
    equipment_rows: list[Any],
    user_map: dict[int, Any],
    workshop_rows: list[Any] | None = None,
) -> dict[str, Any]:
    """评估机列与用户绑定情况。

    试点车间内的机列覆盖率达到阈值才返回 ok；否则 warning 并给出未绑机列清单。
    """
    if not equipment_rows:
        return {
            'status': 'warning',
            'action_required': 'seed_equipment',
            'detail': 'no_equipment_data',
        }

    pilot_codes_raw = (settings.PILOT_WORKSHOP_CODES or '').strip()
    pilot_codes = {code.strip() for code in pilot_codes_raw.split(',') if code.strip()}
    threshold = float(settings.PILOT_BINDING_COVERAGE_THRESHOLD or 0.8)

    workshop_code_by_id: dict[int, str] = {}
    for item in workshop_rows or []:
        ws_id = getattr(item, 'id', None)
        ws_code = getattr(item, 'code', None)
        if ws_id is not None and ws_code:
            workshop_code_by_id[int(ws_id)] = str(ws_code)

    def _is_pilot(item: Any) -> bool:
        if not pilot_codes:
            return True
        ws_code = workshop_code_by_id.get(int(getattr(item, 'workshop_id', 0) or 0))
        return ws_code in pilot_codes if ws_code else False

    pilot_equipment = [item for item in equipment_rows if getattr(item, 'is_active', True) and _is_pilot(item)]
    if not pilot_equipment:
        return {
            'status': 'warning',
            'action_required': 'seed_pilot_equipment',
            'detail': 'no_pilot_equipment',
            'pilot_codes': sorted(pilot_codes),
        }

    bound_pilot = [item for item in pilot_equipment if getattr(item, 'bound_user_id', None) is not None]
    unbound_pilot = [item for item in pilot_equipment if getattr(item, 'bound_user_id', None) is None]
    coverage = len(bound_pilot) / len(pilot_equipment)

    bad_binding: list[str] = []
    for item in bound_pilot:
        user = user_map.get(item.bound_user_id)
        if user is None:
            bad_binding.append(f"{item.code}({item.name})")
            continue
        if getattr(user, 'workshop_id', None) != item.workshop_id:
            bad_binding.append(f"{item.code}({item.name})")

    if bad_binding:
        return {
            'status': 'error',
            'action_required': 'fix_machine_user_binding',
            'detail': 'invalid_equipment_user_binding',
            'sample': bad_binding,
            'coverage': round(coverage, 2),
        }

    if coverage < threshold:
        return {
            'status': 'warning',
            'action_required': 'bind_pilot_machine_users',
            'detail': 'pilot_binding_coverage_below_threshold',
            'coverage': round(coverage, 2),
            'threshold': threshold,
            'unbound': [item.code for item in unbound_pilot][:20],
        }

    return {
        'status': 'ok',
        'action_required': None,
        'detail': 'pilot_binding_coverage_ok',
        'coverage': round(coverage, 2),
    }
```

- [ ] **Step 9.3: 同步函数 caller**

定位 `inspect_pilot_config` 内部调用 `evaluate_equipment_binding(...)` 的地方：

```bash
grep -n "evaluate_equipment_binding" backend/app/services/config_readiness_service.py
```

调用处必须传 `workshop_rows=workshops`。具体看上下文调整传参；如果原来是 positional，改成 keyword 调用，例如：

```python
checks['equipment_binding'] = evaluate_equipment_binding(
    equipment_rows=equipment_rows,
    user_map=user_map,
    workshop_rows=workshops,
)
```

- [ ] **Step 9.4: 跑测试确认 pass**

```bash
python -m pytest backend/tests/test_config_readiness_service.py -v
```

Expected: 全部 pass，包括新加的两个，**也包括原有的 test_inspect_pilot_config_*** 几个**。

- [ ] **Step 9.5: 跑 readyz 相关回归**

```bash
python -m pytest backend/tests/test_config_readiness_service.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
```

Expected: 全部 pass。

- [ ] **Step 9.6: Commit**

```bash
git add backend/app/config.py backend/app/services/config_readiness_service.py backend/tests/test_config_readiness_service.py
git commit -m "feat(D4): gate readyz on pilot equipment binding coverage threshold"
```

---

## Task 10 (D7): 5.6 dry-run 回放脚本

**Files:**
- Create: `backend/scripts/import_5_6_dry_run.py`

- [ ] **Step 10.1: 创建脚本**

新建文件 `backend/scripts/import_5_6_dry_run.py`：

```python
"""5.6 现场原始数据 dry-run 回放脚本。

用法:
    python backend/scripts/import_5_6_dry_run.py [--workbook PATH] [--report PATH]

不写库，只输出 markdown 报告。报告必须能与现场事实底对账。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path('C:/Users/xt/Desktop/5.6')

GROUND_TRUTH = {
    '铸锭': 369,
    '铸二': 24,
    '铸三': 39,
    '热轧': 92,
    '1650': 220,
    '1850': 41,
    '2050': 59,
    '冷轧合计': 532,
    '回收': 70,
}

SUMMARY_WORKBOOK = '鑫泰每日产量5月.xls'


def load_summary_sheet(path: Path) -> pd.DataFrame:
    """读综合报表 sheet，没有则报错退出。"""
    try:
        xls = pd.ExcelFile(path)
    except Exception as exc:
        print(f'[ERROR] 打开 {path} 失败: {exc}', file=sys.stderr)
        sys.exit(2)
    sheet_candidates = [name for name in xls.sheet_names if '综合' in name or '报表' in name]
    if not sheet_candidates:
        print(f'[ERROR] {path} 找不到综合报表 sheet', file=sys.stderr)
        sys.exit(2)
    return xls.parse(sheet_candidates[0], header=None)


def parse_with_canonical_service(frame: pd.DataFrame, sheet_name: str = '5-6'):
    """走 daily_production_canonical_service 实际逻辑解析。"""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.daily_production_canonical_service import parse_daily_production_sheet
    return parse_daily_production_sheet(sheet_name, frame, source_batch_id=None, year_hint=2026)


def run_mapping_preview(rows: list[dict]) -> dict:
    """模拟 daily_production_mapping_service 在内存里跑一遍。"""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.daily_production_mapping_service import DAILY_PRODUCTION_MAPPING_RULES, _normalize_label

    summary = {'total': 0, 'ready': 0, 'unresolved': 0, 'needs_equipment_mapping': 0, 'unresolved_labels': []}
    for row in rows:
        summary['total'] += 1
        key = (_normalize_label(row.get('workshop_label')), _normalize_label(row.get('project_label')))
        rule = DAILY_PRODUCTION_MAPPING_RULES.get(key)
        if rule is None:
            summary['unresolved'] += 1
            summary['unresolved_labels'].append(key)
        elif rule.equipment_required and not rule.equipment_code:
            summary['needs_equipment_mapping'] += 1
        else:
            summary['ready'] += 1
    return summary


def reconcile_against_truth(rows: list[dict]) -> list[tuple[str, float, float, float]]:
    """把解析后的 rows 与 GROUND_TRUTH 对账，返回 (label, expected, actual, diff)。"""
    actuals = {}
    for row in rows:
        ws = (row.get('workshop_label') or '').strip()
        proj = (row.get('project_label') or '').strip()
        out = float(row.get('daily_output_tons') or 0)
        if ws == '铸锭':
            actuals['铸锭'] = actuals.get('铸锭', 0) + out
        elif ws == '铸轧' and proj == '铸二':
            actuals['铸二'] = actuals.get('铸二', 0) + out
        elif ws == '铸轧' and proj == '铸三':
            actuals['铸三'] = actuals.get('铸三', 0) + out
        elif ws == '热轧':
            actuals['热轧'] = actuals.get('热轧', 0) + out
        elif ws == '冷轧' and proj in ('1650', '1850', '2050'):
            actuals[proj] = actuals.get(proj, 0) + out
            actuals['冷轧合计'] = actuals.get('冷轧合计', 0) + out
        elif ws == '回收':
            actuals['回收'] = actuals.get('回收', 0) + out

    rows_out = []
    for label, expected in GROUND_TRUTH.items():
        actual = actuals.get(label, 0.0)
        rows_out.append((label, float(expected), round(actual, 2), round(actual - expected, 2)))
    return rows_out


def render_report(args, parsed, mapping_summary, recon_rows) -> str:
    lines = []
    lines.append('# 5.6 dry-run 验收报告')
    lines.append('')
    lines.append(f'- 工作簿: `{args.workbook}`')
    lines.append(f'- 解析行数: {parsed.mapped_data.get("row_count", 0)}')
    lines.append(f'- 业务日期: {parsed.mapped_data.get("business_date")}')
    lines.append(f'- 质量状态: {parsed.status}')
    lines.append('')
    lines.append('## 映射规则覆盖')
    lines.append(f'- 总行数: {mapping_summary["total"]}')
    lines.append(f'- ready: {mapping_summary["ready"]}')
    lines.append(f'- needs_equipment_mapping: {mapping_summary["needs_equipment_mapping"]}')
    lines.append(f'- unresolved: {mapping_summary["unresolved"]}')
    if mapping_summary['unresolved_labels']:
        lines.append('  - 未解析 labels:')
        for label in mapping_summary['unresolved_labels']:
            lines.append(f'    - `{label}`')
    lines.append('')
    lines.append('## 事实底对账（单位：吨）')
    lines.append('| 口径 | 期望 | 实际 | 差额 | 状态 |')
    lines.append('| --- | --- | --- | --- | --- |')
    for label, expected, actual, diff in recon_rows:
        tolerance = max(expected * 0.05, 5)
        status = 'OK' if abs(diff) <= tolerance else 'FAIL'
        lines.append(f'| {label} | {expected:.1f} | {actual:.2f} | {diff:+.2f} | {status} |')
    lines.append('')
    issues = parsed.mapped_data.get('issues') or []
    if issues:
        lines.append('## 数据质量 issue')
        for item in issues:
            lines.append(f'- `{item.get("code")}` {item.get("message")}')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workbook', type=Path, default=DEFAULT_DATA_DIR / SUMMARY_WORKBOOK)
    parser.add_argument('--report', type=Path, default=Path('tmp') / 'import_5_6_dry_run.md')
    args = parser.parse_args(argv)

    if not args.workbook.exists():
        print(f'[ERROR] workbook 不存在: {args.workbook}', file=sys.stderr)
        return 2

    frame = load_summary_sheet(args.workbook)
    parsed = parse_with_canonical_service(frame)
    rows = parsed.mapped_data.get('workshop_rows') or []
    mapping_summary = run_mapping_preview(rows)
    recon_rows = reconcile_against_truth(rows)
    report = render_report(args, parsed, mapping_summary, recon_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding='utf-8')
    print(report)
    print(f'\n[OK] 报告已写入 {args.report}')

    failed = [item for item in recon_rows if abs(item[3]) > max(item[1] * 0.05, 5)]
    if failed or mapping_summary['unresolved'] > 2:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 10.2: 跑脚本**

```bash
cd "D:/zzj Claude code/aluminum-bypass"
python backend/scripts/import_5_6_dry_run.py
```

Expected: 输出报告到 `tmp/import_5_6_dry_run.md`，stdout 同步打印。

如果 `unresolved_rows > 2` 或事实底对账失败（FAIL 行），看报告里 unresolved labels，回到 Task 5 补 mapping 规则；看实际值差额过大，可能是 D3 单位逻辑问题，回到 Task 7。

- [ ] **Step 10.3: 调到通过**

反复运行直到：
- 所有事实底行 status=OK（差额 ≤ max(期望×5%, 5)）
- `mapping_summary['unresolved'] ≤ 2`

每次调整 mapping 后重 commit 一次（`fix(D2): refine mapping for ...`）。

- [ ] **Step 10.4: Commit 脚本本身**

```bash
git add backend/scripts/import_5_6_dry_run.py
git commit -m "feat(D7): add 5.6 dry-run replay script with ground-truth reconciliation"
```

---

## Task 11 (D5-A): 引入 echarts 依赖

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 11.1: 安装依赖**

```bash
cd "D:/zzj Claude code/aluminum-bypass/frontend"
npm install echarts@^5.5.0 vue-echarts@^7.0.3 --save
```

Expected: `node_modules/echarts` 与 `node_modules/vue-echarts` 存在；`package.json` `dependencies` 多两条。

- [ ] **Step 11.2: 跑构建确认无破坏**

```bash
npm run build
```

Expected: build 成功。

- [ ] **Step 11.3: Commit**

```bash
cd "D:/zzj Claude code/aluminum-bypass"
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(D5): add echarts and vue-echarts dependencies"
```

---

## Task 12 (D5-B): ShiftOutputTrend 折线图

**Files:**
- Create: `frontend/src/components/charts/ShiftOutputTrend.vue`

- [ ] **Step 12.1: 创建组件**

新建 `frontend/src/components/charts/ShiftOutputTrend.vue`：

```vue
<script setup>
import { computed, defineProps } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const props = defineProps({
  workshops: { type: Array, default: () => [] },
  shifts: { type: Array, default: () => [] },
})

const ENTERPRISE_COLORS = ['#1f6feb', '#2da44e', '#bf8700', '#cf222e', '#8250df', '#0969da']

const option = computed(() => {
  const shiftLabels = props.shifts.map((shift) => shift.shift_name)
  const series = props.workshops.map((workshop, idx) => {
    const data = props.shifts.map((shift) => {
      const cell = (workshop.shift_summary || []).find((row) => row.shift_id === shift.shift_id)
      return cell ? Number((cell.total_output || 0).toFixed(2)) : 0
    })
    return {
      name: workshop.workshop_name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { width: 2 },
      itemStyle: { color: ENTERPRISE_COLORS[idx % ENTERPRISE_COLORS.length] },
      data,
    }
  })
  return {
    title: { text: '车间班次产量趋势', left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 600, color: '#1f2328' } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 8, right: 12, textStyle: { color: '#57606a' } },
    grid: { left: 48, right: 24, top: 48, bottom: 32 },
    xAxis: { type: 'category', data: shiftLabels, axisLine: { lineStyle: { color: '#d0d7de' } }, axisLabel: { color: '#57606a' } },
    yAxis: { type: 'value', name: '吨', nameTextStyle: { color: '#57606a' }, axisLine: { show: false }, splitLine: { lineStyle: { color: '#eaeef2' } }, axisLabel: { color: '#57606a' } },
    series,
  }
})

const hasData = computed(() => props.workshops.length > 0 && props.shifts.length > 0)
</script>

<template>
  <div class="shift-output-trend">
    <VChart v-if="hasData" :option="option" autoresize />
    <div v-else class="empty">暂无班次产量数据</div>
  </div>
</template>

<style scoped>
.shift-output-trend { height: 320px; background: #ffffff; border: 1px solid #d0d7de; border-radius: 8px; padding: 4px; }
.shift-output-trend :deep(.echarts) { width: 100%; height: 100%; }
.empty { display: flex; align-items: center; justify-content: center; height: 100%; color: #6e7781; font-size: 14px; }
</style>
```

- [ ] **Step 12.2: 构建确认无报错**

```bash
cd "D:/zzj Claude code/aluminum-bypass/frontend"
npm run build
```

Expected: build 成功。

- [ ] **Step 12.3: Commit**

```bash
cd "D:/zzj Claude code/aluminum-bypass"
git add frontend/src/components/charts/ShiftOutputTrend.vue
git commit -m "feat(D5): add ShiftOutputTrend line chart component"
```

---

## Task 13 (D5-C): PendingAssignmentHeatmap 热力图

**Files:**
- Create: `frontend/src/components/charts/PendingAssignmentHeatmap.vue`

- [ ] **Step 13.1: 创建组件**

新建 `frontend/src/components/charts/PendingAssignmentHeatmap.vue`：

```vue
<script setup>
import { computed, defineProps } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, TitleComponent])

const props = defineProps({
  rows: { type: Array, default: () => [] },
})

const matrix = computed(() => {
  const workshopNames = []
  const shiftNames = []
  const cellMap = new Map()
  for (const row of props.rows) {
    if (!workshopNames.includes(row.workshop_name)) workshopNames.push(row.workshop_name)
    if (!shiftNames.includes(row.shift_name)) shiftNames.push(row.shift_name)
    cellMap.set(`${row.workshop_name}::${row.shift_name}`, row.entry_count || 0)
  }
  const data = []
  workshopNames.forEach((ws, y) => {
    shiftNames.forEach((sh, x) => {
      const value = cellMap.get(`${ws}::${sh}`) || 0
      data.push([x, y, value])
    })
  })
  return { workshopNames, shiftNames, data }
})

const option = computed(() => {
  const { workshopNames, shiftNames, data } = matrix.value
  const maxValue = data.reduce((acc, item) => Math.max(acc, item[2]), 0)
  return {
    title: { text: '草稿待归属热力', left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 600, color: '#1f2328' } },
    tooltip: {
      position: 'top',
      formatter: (params) => `${workshopNames[params.data[1]]} · ${shiftNames[params.data[0]]}<br/>未归属: <b>${params.data[2]}</b> 条`,
    },
    grid: { left: 96, right: 24, top: 48, bottom: 32 },
    xAxis: { type: 'category', data: shiftNames, splitArea: { show: true }, axisLine: { lineStyle: { color: '#d0d7de' } }, axisLabel: { color: '#57606a' } },
    yAxis: { type: 'category', data: workshopNames, splitArea: { show: true }, axisLine: { lineStyle: { color: '#d0d7de' } }, axisLabel: { color: '#57606a' } },
    visualMap: { min: 0, max: maxValue || 1, calculable: false, orient: 'horizontal', right: 24, top: 12, inRange: { color: ['#eef4ff', '#79b8ff', '#1f6feb', '#0a3069'] }, textStyle: { color: '#57606a' } },
    series: [{ name: '草稿数', type: 'heatmap', data, label: { show: true, color: '#1f2328' }, emphasis: { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.2)' } } }],
  }
})

const hasData = computed(() => props.rows.length > 0)
</script>

<template>
  <div class="pending-assignment-heatmap">
    <VChart v-if="hasData" :option="option" autoresize />
    <div v-else class="empty">无草稿待归属</div>
  </div>
</template>

<style scoped>
.pending-assignment-heatmap { height: 320px; background: #ffffff; border: 1px solid #d0d7de; border-radius: 8px; padding: 4px; }
.pending-assignment-heatmap :deep(.echarts) { width: 100%; height: 100%; }
.empty { display: flex; align-items: center; justify-content: center; height: 100%; color: #6e7781; font-size: 14px; }
</style>
```

- [ ] **Step 13.2: 构建确认**

```bash
cd "D:/zzj Claude code/aluminum-bypass/frontend"
npm run build
```

Expected: build 成功。

- [ ] **Step 13.3: Commit**

```bash
cd "D:/zzj Claude code/aluminum-bypass"
git add frontend/src/components/charts/PendingAssignmentHeatmap.vue
git commit -m "feat(D5): add PendingAssignmentHeatmap heatmap component"
```

---

## Task 14 (D5-D): ReconciliationWaterfall 瀑布图

**Files:**
- Create: `frontend/src/components/charts/ReconciliationWaterfall.vue`

- [ ] **Step 14.1: 创建组件**

新建 `frontend/src/components/charts/ReconciliationWaterfall.vue`：

```vue
<script setup>
import { computed, defineProps } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent])

const props = defineProps({
  items: { type: Array, default: () => [] },
})

const option = computed(() => {
  const labels = props.items.map((item) => item.workshop_name || item.label)
  const mesData = props.items.map((item) => Number((item.mes_output_tons || 0).toFixed(2)))
  const fillData = props.items.map((item) => Number((item.fill_output_tons || 0).toFixed(2)))
  const diffData = props.items.map((item) => Number((item.diff_tons ?? (item.fill_output_tons - item.mes_output_tons) ?? 0).toFixed(2)))
  return {
    title: { text: 'MES vs 填报 对账瀑布', left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 600, color: '#1f2328' } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 8, right: 12, textStyle: { color: '#57606a' } },
    grid: { left: 64, right: 24, top: 48, bottom: 64 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#57606a', rotate: 30 }, axisLine: { lineStyle: { color: '#d0d7de' } } },
    yAxis: { type: 'value', name: '吨', nameTextStyle: { color: '#57606a' }, axisLine: { show: false }, splitLine: { lineStyle: { color: '#eaeef2' } }, axisLabel: { color: '#57606a' } },
    series: [
      { name: 'MES', type: 'bar', data: mesData, itemStyle: { color: '#79b8ff' }, barGap: 0 },
      { name: '填报', type: 'bar', data: fillData, itemStyle: { color: '#1f6feb' } },
      { name: '差额', type: 'bar', data: diffData, itemStyle: { color: (params) => (params.value >= 0 ? '#2da44e' : '#cf222e') } },
    ],
  }
})

const hasData = computed(() => props.items.length > 0)
</script>

<template>
  <div class="reconciliation-waterfall">
    <VChart v-if="hasData" :option="option" autoresize />
    <div v-else class="empty">暂无对账数据</div>
  </div>
</template>

<style scoped>
.reconciliation-waterfall { height: 360px; background: #ffffff; border: 1px solid #d0d7de; border-radius: 8px; padding: 4px; }
.reconciliation-waterfall :deep(.echarts) { width: 100%; height: 100%; }
.empty { display: flex; align-items: center; justify-content: center; height: 100%; color: #6e7781; font-size: 14px; }
</style>
```

- [ ] **Step 14.2: 构建确认**

```bash
cd "D:/zzj Claude code/aluminum-bypass/frontend"
npm run build
```

Expected: build 成功。

- [ ] **Step 14.3: Commit**

```bash
cd "D:/zzj Claude code/aluminum-bypass"
git add frontend/src/components/charts/ReconciliationWaterfall.vue
git commit -m "feat(D5): add ReconciliationWaterfall bar chart component"
```

---

## Task 15 (D5-E): 把 3 张图嵌入工厂指挥首页

**Files:**
- Modify: `frontend/src/views/factory-command/FactoryOverview.vue`
- Modify: `frontend/src/stores/factory-command.js`（如果数据源不在 store 里需要新加 action）

- [ ] **Step 15.1: 看 FactoryOverview.vue 现有结构**

```bash
head -120 "D:/zzj Claude code/aluminum-bypass/frontend/src/views/factory-command/FactoryOverview.vue"
```

记录 `<script setup>` 中已 import 的内容、`<template>` 末尾的容器位置。

- [ ] **Step 15.2: 在 FactoryOverview.vue 顶部 import 3 个图组件**

在 `<script setup>` 块顶部 import 区域追加：

```js
import ShiftOutputTrend from '@/components/charts/ShiftOutputTrend.vue'
import PendingAssignmentHeatmap from '@/components/charts/PendingAssignmentHeatmap.vue'
import ReconciliationWaterfall from '@/components/charts/ReconciliationWaterfall.vue'
```

- [ ] **Step 15.3: 在 store 暴露 3 张图所需 computed**

打开 `frontend/src/stores/factory-command.js`，确认是否已有：
- `liveAggregation` (含 `workshop_items[].machine_items[].shift_items`)
- `pendingAssignmentRows` (含 `rows`)
- `reconciliationItems` (含 `production_vs_mes`)

如缺，新增 `getters`：

```js
chartShiftOutputData: (state) => {
  const items = state.liveAggregation?.workshop_items || []
  return items.map((ws) => ({
    workshop_name: ws.workshop_name,
    shift_summary: (ws.shift_summary || []).map((row) => ({
      shift_id: row.shift_id,
      total_output: row.total_output,
    })),
  }))
},
chartShiftLabels: (state) => state.liveAggregation?.shifts || [],
chartPendingRows: (state) => state.liveAggregation?.overall_progress?.pending_assignment?.rows || [],
chartReconciliationItems: (state) => state.reconciliationItems?.production_vs_mes || [],
```

如果 store 已有等价 getter，按现有命名引用，不必新加。

- [ ] **Step 15.4: 在 FactoryOverview.vue template 末尾追加 3 张图区**

定位 `<template>` 内容区最末尾，紧贴最后一个 `</section>` 或 `</div>` 之前插入：

```html
    <section class="charts-grid">
      <ShiftOutputTrend
        :workshops="store.chartShiftOutputData"
        :shifts="store.chartShiftLabels"
      />
      <PendingAssignmentHeatmap :rows="store.chartPendingRows" />
      <ReconciliationWaterfall :items="store.chartReconciliationItems" />
    </section>
```

`<style scoped>` 末尾追加：

```css
.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
```

- [ ] **Step 15.5: 构建确认**

```bash
cd "D:/zzj Claude code/aluminum-bypass/frontend"
npm run build
```

Expected: build 成功。

- [ ] **Step 15.6: 跑前端单元测试**

```bash
npm test
```

Expected: 全部 pass。

- [ ] **Step 15.7: Commit**

```bash
cd "D:/zzj Claude code/aluminum-bypass"
git add frontend/src/views/factory-command/FactoryOverview.vue frontend/src/stores/factory-command.js
git commit -m "feat(D5): embed shift trend / pending heatmap / reconciliation charts in factory overview"
```

---

## Task 16 (D6): Draft 提升联动

**Files:**
- 看现有：`backend/app/routers/assistant_actions.py`、`backend/app/services/assistant_action_service.py`
- Modify: 视情况补充 `promote_draft_entry` action（若不存在）
- Modify: `frontend/src/views/review/*` 的 pending_assignment 卡片组件（按现有命名定位）

- [ ] **Step 16.1: 探查 assistant_actions 是否已支持 promote**

```bash
grep -rn "promote_draft\|promote_entry\|提升" backend/app/routers/assistant_actions.py backend/app/services/assistant_action_service.py
```

- 如果已有：跳到 Step 16.4 直接接前端
- 如果没有：进入 Step 16.2-16.3 后端实现

- [ ] **Step 16.2 (条件): 写后端失败测试**

新建或追加到 `backend/tests/test_assistant_action_service.py`：

```python
def test_promote_draft_entry_changes_status_to_submitted_and_aggregates(db_session, basic_workshop_setup):
    from app.models.production import WorkOrderEntry, WorkOrder
    from app.services.assistant_action_service import promote_draft_entry

    work_order = WorkOrder(tracking_card_no='T001', overall_status='created', alloy_grade='3003', process_route_code='mobile')
    db_session.add(work_order)
    db_session.flush()
    entry = WorkOrderEntry(
        work_order_id=work_order.id,
        workshop_id=basic_workshop_setup['workshop_id'],
        machine_id=basic_workshop_setup['machine_id'],
        shift_id=basic_workshop_setup['shift_id'],
        business_date=basic_workshop_setup['business_date'],
        entry_type='in_progress',
        entry_status='draft',
        input_weight=12000,
        output_weight=11500,
    )
    db_session.add(entry)
    db_session.commit()

    result = promote_draft_entry(db_session, entry_id=entry.id, operator_id=basic_workshop_setup['admin_user_id'])

    db_session.refresh(entry)
    assert entry.entry_status == 'submitted'
    assert result['aggregation_triggered'] is True
```

如果项目里有 `basic_workshop_setup` fixture 用之；没有则在 conftest 现编一个，保留 4 个 key：`workshop_id / machine_id / shift_id / business_date / admin_user_id`。

- [ ] **Step 16.3 (条件): 实现 promote_draft_entry**

在 `backend/app/services/assistant_action_service.py` 末尾追加：

```python
def promote_draft_entry(db: Session, *, entry_id: int, operator_id: int) -> dict:
    """把 draft 状态的 work_order_entry 提升为 submitted 并触发聚合。

    审阅闸门保留：只有具备审阅或管理权限的 operator 才能调用，由路由层守卫。
    """
    from app.models.production import WorkOrderEntry
    from app.services.mobile_report.summary import _aggregate_coil_to_shift

    entry = db.get(WorkOrderEntry, entry_id)
    if entry is None:
        raise ValueError(f'work_order_entry {entry_id} not found')
    if entry.entry_status != 'draft':
        return {'entry_id': entry_id, 'previous_status': entry.entry_status, 'aggregation_triggered': False, 'note': 'not draft'}

    entry.entry_status = 'submitted'
    db.flush()
    aggregation_triggered = False
    if entry.workshop_id and entry.shift_id:
        _aggregate_coil_to_shift(
            db,
            business_date=entry.business_date,
            shift_id=entry.shift_id,
            workshop_id=entry.workshop_id,
            machine_id=entry.machine_id,
        )
        aggregation_triggered = True
    db.commit()
    return {
        'entry_id': entry_id,
        'previous_status': 'draft',
        'aggregation_triggered': aggregation_triggered,
    }
```

在 `backend/app/routers/assistant_actions.py` 暴露 endpoint：

```python
@router.post('/promote-draft-entry/{entry_id}', name='assistant-promote-draft')
def promote_draft_entry_route(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_review_or_admin),
):
    return assistant_action_service.promote_draft_entry(db, entry_id=entry_id, operator_id=current_user.id)
```

权限守卫使用项目已有的 `require_review_or_admin` 或同类 dependency；查不到时新加：

```python
def require_review_or_admin(current_user: User = Depends(get_current_user)):
    if not (current_user.is_reviewer or current_user.is_manager or current_user.role == 'admin'):
        raise HTTPException(status_code=403, detail='reviewer or admin required')
    return current_user
```

- [ ] **Step 16.4: 跑测试**

```bash
python -m pytest backend/tests/test_assistant_action_service.py -v
```

Expected: 全部 pass。

- [ ] **Step 16.5: 前端审阅中心加按钮**

定位审阅中心或工厂指挥的 pending_assignment 表格组件，找到每行的操作列。在表格列定义内追加一个按钮，点击调 `axios.post('/api/v1/assistant-actions/promote-draft-entry/' + row.entry_id)`，成功后 toast + 刷新当前列表。

具体文件路径要先 grep 定位：

```bash
grep -rln "pending_assignment\|pendingAssignment" frontend/src/views/ | head
```

按结果改最相关的 .vue 文件。改动控制在 30 行内。

- [ ] **Step 16.6: 构建 + commit**

```bash
cd "D:/zzj Claude code/aluminum-bypass/frontend"
npm run build
cd ..
git add backend/app/routers/assistant_actions.py backend/app/services/assistant_action_service.py backend/tests/test_assistant_action_service.py frontend/src/views/
git commit -m "feat(D6): add draft entry promotion linking pending assignment to shift aggregation"
```

---

## Task 17: 终轮回归 + 部署预演

**Files:** 不改文件，只跑命令。

- [ ] **Step 17.1: 全量后端测试**

```bash
cd "D:/zzj Claude code/aluminum-bypass"
python -m pytest backend/tests -q
```

Expected: pass 数 ≥ baseline + 新增测试数；无 fail。

- [ ] **Step 17.2: 前端测试 + 构建**

```bash
npm --prefix frontend test
npm --prefix frontend run build
```

Expected: 全部 pass + build 成功。

- [ ] **Step 17.3: 5.6 dry-run 终验**

```bash
python backend/scripts/import_5_6_dry_run.py
```

Expected: 报告里所有事实底口径 status=OK，`unresolved ≤ 2`。

- [ ] **Step 17.4: git 状态干净**

```bash
git status
git log --oneline -20
```

Expected: 工作树干净，commit 历史里清晰看到 `feat(D1)` … `feat(D7)`。

- [ ] **Step 17.5: 部署预演（可选、可由用户决定是否执行）**

不要直接 push 到 main，先开 PR 或推 feature branch：

```bash
git checkout -b feat/2026-05-07-acceptance-gap-closure
git push -u origin feat/2026-05-07-acceptance-gap-closure
```

由用户决定何时合并和何时部署到 8.140.218.13。**不要在用户未授权情况下直接登服务器。**

---

## 验收红线（最后再贴一次）

执行完毕后必须满足，缺一不可：

1. `python -m pytest backend/tests -q` 全绿。
2. `npm --prefix frontend run build` 成功。
3. `curl -s http://localhost:8000/api/v1/master/workshops | jq 'length'` ≥ 15（开发环境）。
4. `python backend/scripts/import_5_6_dry_run.py` 退出码 0，报告里事实底全 OK。
5. `/readyz` 响应里 `pipeline.checks.equipment_binding` 含 `coverage` 字段。
6. 浏览器访问管理端工厂指挥首页可见 3 张图，无 console 报错。
7. git log 至少 7 个 `feat(D...)` commit，每个 commit 单独可 revert。

任意一项不达标即视为本 Plan 未闭环。

---

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 1 | CEO | Accept premises as valid | Mechanical | P6 (action) | All 4 premises grounded in real factory context | N/A |
| 2 | CEO | Flag proxy problem but don't change scope | Taste | P3 (pragmatic) | Plan is data accuracy first; mobile is Phase 2 | Reframe to mobile-first |
| 3 | CEO | Flag D5/D6 scope creep but keep in plan | Taste | P1 (completeness) | D5/D6 already implemented; splitting = churn | Split into separate branch |
| 4 | CEO | Commit uncommitted changes immediately | Mechanical | P6 (action) | 12 files at risk of accidental loss | N/A |
| 5 | CEO | Accept single-source ground truth | Mechanical | P3 (pragmatic) | Hand records are only available baseline | Cross-validate with MES |
| 6 | CEO | Acknowledge dependency chain D1→D2→D7 | Mechanical | P5 (explicit) | Atomic rollback unit, not independent | N/A |
| 7 | Design | Flag hierarchy inversion (pending above charts) | Taste | P1 (completeness) | Boss sees data-ops before production data | Keep current order |
| 8 | Design | Flag missing loading states | Mechanical | P3 (pragmatic) | Important but not acceptance-blocking | N/A |
| 9 | Design | Flag jargon in pending assignment | Mechanical | P3 (pragmatic) | Text fix, not acceptance-blocking | N/A |
| 10 | Design | Flag hardcoded chart colors | Mechanical | P5 (explicit) | Design system consistency | N/A |
| 11 | Design | Flag accessibility gaps | Mechanical | P5 (explicit) | Important for long-term | N/A |
| 12 | Design | ShiftOutputTrend dead import | Mechanical | P4 (DRY) | Unused import cleanup | N/A |
| 13 | Eng | D7 must be implemented | Mechanical | P1 (completeness) | Integration test = acceptance gate | Ship without D7 |
| 14 | Eng | Hard-block row append acceptable with docs | Mechanical | P5 (explicit) | Downstream checks status field | N/A |
| 15 | Eng | Coverage field missing = bug to fix | Mechanical | P1 (completeness) | Acceptance criterion requires it | N/A |
| 16 | Eng | Plan doc staleness = documentation debt | Mechanical | P3 (pragmatic) | Actual code is source of truth | N/A |
| 17 | Eng | Unicode whitespace test = nice-to-have | Mechanical | P3 (pragmatic) | Low risk | N/A |

---

## 失败回退策略

- 单 Task 失败：当前 commit 还没打的话直接改；已 commit 但发现错的，先看是否影响下游 Task：
  - 如果不影响下游：新加一个 `fix(D?): xxx` commit。
  - 如果影响下游：`git revert <commit>` 后重做。
- 整轮失败超过 3 个 Task：停手，不再继续；写 `docs/known-gaps-and-todos.md` 记录未完成项 + 失败原因，交回用户决策。
