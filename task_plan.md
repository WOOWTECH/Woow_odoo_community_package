# Task Plan: 修復三模組所有 Code Review 發現的問題

## Goal
修復 community_base (4)、community_visitor (5 key)、community_parcel (8) 共 17 個問題。

## Current Phase
Phase 1

## Phases

### Phase 1: 修復 community_base（4 個問題）
- [ ] BASE-1: Office form view 加入 PropertiesDefinition 欄位
  - 檔案: `community_base/views/community_office_views.xml`
  - 修改: 在 form view 加入 notebook page 顯示 announcement_properties_definition 和 feedback_properties_definition
- [ ] BASE-2: Portal feedback create 驗證 category_id 存在性
  - 檔案: `community_base/controllers/portal.py`
  - 修改: 在 sudo().create() 前驗證 category_id 是否存在於 community.feedback.category
- [ ] BASE-3: State transition methods 加入 guard clauses
  - 檔案: `community_base/models/community_announcement.py` (3 methods)
  - 檔案: `community_base/models/community_feedback.py` (3 methods)
  - 修改: 每個 action method 加入 state 檢查，不符合則 raise UserError
- [ ] BASE-4: Portal 加入 office/unit record rules
  - 檔案: `community_base/security/ir_rules.xml`
  - 修改: 新增 community.office 和 community.unit 的 portal record rules
- **Status:** pending

### Phase 2: 修復 community_visitor（5 個關鍵問題）
- [ ] VIS-1 (Critical): 新增 /my/appointments/<id>/cancel 路由
  - 檔案: `community_visitor/controllers/portal.py`
  - 修改: 新增 POST 路由，驗證權限後呼叫 action_cancel()
- [ ] VIS-2 (Critical): visitor_phone 改為必填
  - 檔案: `community_visitor/models/community_appointment.py`
  - 修改: visitor_phone field 加 required=True
- [ ] VIS-3 (High): recurring 時間檢查改用 local timezone
  - 檔案: `community_visitor/models/community_appointment.py`
  - 修改: _check_recurring_schedule 中 now 轉換為使用者時區
- [ ] VIS-4 (Medium): mail templates 補 email_to
  - 檔案: `community_visitor/data/mail_templates.xml`
  - 修改: visit_confirm_request 和 blacklist_alert 補 email_to
- [ ] VIS-5 (Medium): action_reject 加入 token expiry 驗證
  - 檔案: `community_visitor/models/community_visit.py`
  - 修改: 仿照 action_confirm 加入 token_expiry 檢查
- **Status:** pending

### Phase 3: 修復 community_parcel（8 個問題）
- [ ] PKL-1 (Medium): is_overdue 改為 store=False 避免 stale
  - 檔案: `community_parcel/models/community_parcel.py`
  - 修改: 移除 store=True
- [ ] PKL-2 (Medium): barcode 加 SQL unique constraint
  - 檔案: `community_parcel/models/community_parcel.py`
  - 修改: 加入 _sql_constraints（barcode 可為空但不可重複）
- [ ] PKL-3 (Medium): email template 中 parcel_type 顯示 label
  - 檔案: `community_parcel/data/mail_template_data.xml`
  - 修改: 用 dict lookup 取得 selection label
- [ ] PKL-4 (Low): cron 批次處理取代逐筆迭代
  - 檔案: `community_parcel/models/community_parcel.py`
  - 修改: 批次 write state，再逐筆發 mail
- [ ] PKL-5 (Low): unit_address 顯示所有戶號
  - 檔案: `community_parcel/models/community_parcel.py`
  - 修改: join 所有 unit_ids 的 name
- [ ] PKL-6 (Low): recipient_id 加 domain filter
  - 檔案: `community_parcel/models/community_storage.py`
  - 修改: 加入 domain=[('is_resident', '=', True)]
- [ ] PKL-7 (Low): overdue template 補 lang field
  - 檔案: `community_parcel/data/mail_template_data.xml`
  - 修改: 加入 lang 欄位
- [ ] PKL-8 (Low): timedelta import 移到檔案頂部
  - 檔案: `community_parcel/models/community_parcel.py`
  - 修改: 移動 from datetime import timedelta 到 import 區
- **Status:** pending

### Phase 4: 推送到 main
- [ ] 建立 fix branch，commit 所有修改
- [ ] 建立 PR 並 merge 到 main
- **Status:** pending

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| is_overdue 改 store=False | 避免 stale 值，效能影響小（boolean computed 很快） |
| barcode 用 SQL constraint 而非 Python | SQL constraint 更快且更安全（UNIQUE 允許多個 NULL） |
| parcel_type label 用 dict lookup | 不需新增 computed field，直接在 template 處理 |
| visitor_phone 加 required=True | 最直接的修法，源頭防堵 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
