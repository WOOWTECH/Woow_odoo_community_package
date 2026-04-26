# Task Plan: 深度 Code Review 全部模組並更新 README

## Goal
深入了解 community_base / community_visitor / community_parcel 三個模組的完整 codebase，做詳細 code review，再撰寫一份完整詳細的 README.md。

## Current Phase
Phase 4

## Phases

### Phase 1: Code Review — community_base
- [x] __manifest__.py — 版本、依賴、data files
- [x] models/ — 所有 model 的欄位、關聯、computed fields、constraints
- [x] views/ — 所有 view XML，XML IDs、結構
- [x] security/ — access rules、record rules
- [x] controllers/ — portal controller
- [x] data/ — sequences
- [x] 記錄發現到 findings.md
- **Status:** complete

### Phase 2: Code Review — community_visitor
- [x] __manifest__.py — 版本、依賴
- [x] models/ — visitor、visit、appointment 模型
- [x] views/ — 所有 view XML
- [x] wizards/ — 快速登記精靈
- [x] security/ — groups、access rules、record rules
- [x] controllers/ — portal
- [x] data/ — sequences、cron、demo
- [x] 記錄發現到 findings.md
- **Status:** complete

### Phase 3: Code Review — community_parcel
- [x] models/ — parcel、storage 模型
- [x] views/ — 所有 view XML
- [x] wizards/ — 快速登記精靈
- [x] security/ — groups、access rules
- [x] data/ — sequences、mail templates、demo
- [x] 確認與 base v2 的相容性
- **Status:** complete

### Phase 4: 撰寫詳細 README.md
- [ ] 整體架構說明
- [ ] 各模組詳細功能、模型、欄位說明
- [ ] 安裝指南
- [ ] 設定說明
- [ ] 開發指南
- [ ] 推送到 main
- **Status:** in_progress

## Key Questions — Answered
1. community_base v2: 7 models (office, unit, partner ext, announcement, announcement category, feedback, feedback category), portal integration, PropertiesDefinition support
2. community_visitor: 3 models (visitor, visit, appointment), QR code, token-based confirmation, bus.bus notifications, 2 cron jobs
3. Dependencies: base→mail/portal, visitor→base/mail/portal, parcel→base/mail. Shared: office, unit, partner.is_resident
4. Code quality issues documented in findings.md — 4 bugs in base, 15 in visitor, 8 in parcel

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 先做完整 code review 再寫 README | 確保 README 內容準確反映實際程式碼 |
| README 用中文撰寫 | 配合現有 README 和模組語言 |

## Notes
- 三個模組都在 repo root level：community_base/、community_visitor/、community_parcel/
- community_base 是 v18.0.2.0.0（最新），visitor 和 parcel 是 v18.0.1.0.0
