# DingTalk Semantic Text Deduplication Design

## Problem

Real DingTalk Stream evidence stores the same message in both `MultimodalEvidence.recognized_text` and payload text fields. DingTalk may normalize whitespace differently between those copies. `extract_daily_fact_update_candidates()` currently deduplicates only exact strings, so the two copies are concatenated. The strict plan-contract parser then sees two `投料量` sections and rejects the evidence as ambiguous.

Production read-only reproduction on 2026-08-21:

- Evidence `712`: direct parser returns 9 fields; aggregated candidate extraction returns 0.
- Evidence `725`: direct parser returns 9 fields; aggregated candidate extraction returns 0.
- The two stored copies differ only in whitespace.

## Goal

Treat Unicode- and whitespace-equivalent text copies as one input while preserving the strict rejection of genuinely different reports.

## Non-Goals

- Do not auto-confirm `machine_only` evidence.
- Do not relax field labels, numeric matching, business-date rules, or source priority.
- Do not add a page, API, table, migration, prompt, or new parser.
- Do not use `D:\输出skill` as a fact source.

## Options Considered

1. **Semantic duplicate key in the existing text collector (selected).** Normalize Unicode with NFKC and collapse whitespace only for duplicate comparison; keep the first original text for parsing and trace output.
2. Prefer `recognized_text` and ignore payload text. Smaller, but it can discard complementary attachment text.
3. Allow repeated parser sections when values match. This weakens the parser itself and risks accepting a message that really contains two reports.

## Design

Add one private duplicate-key helper to `hermes_daily_fact_update_service.py`. `_append_text_part()` uses that key instead of the raw string in its `seen` set.

The key performs only:

1. Unicode NFKC normalization.
2. Collapse every whitespace run to an empty string.

The returned candidate still carries the original first-seen text. Therefore source trace remains readable, while formatting-only duplication disappears before parsing.

Two texts with different labels or values produce different keys and remain separate. The strict `parse_plan_contract_message()` guard still rejects the resulting multi-report input.

## Data And Trust Boundaries

- Input remains real DingTalk `MultimodalEvidence`.
- Output remains candidate facts until existing confirmation rules allow adoption.
- `confirmation_status`, `metric_write_allowed`, business date, trace ID, and source priority are unchanged.
- MES/WMS remains read-only and is not touched.

## Acceptance Criteria

1. A production-shaped evidence object containing whitespace variants of the same plan-contract message yields exactly 9 candidates.
2. The candidates include `daily_input_weight`, `cold_roll_input_daily`, `remaining_contract_weight`, four input components, and two contract context fields.
3. Two different plan-contract messages in the same evidence still yield no candidates.
4. Existing candidate extraction and DailyFactBundle tests remain green.
5. Production read-only replay of evidence `712` and `725` yields 9 candidates each after deployment.
6. Production rows remain `machine_only`; no fact is silently confirmed and no outbox message is created by the replay.

## Rollback

Revert the single implementation commit. No schema, persisted-data, or configuration rollback is required.
