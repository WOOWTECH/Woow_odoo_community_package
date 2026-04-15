# PRD: community_parcel 企業級全面測試計畫

## 文件資訊
- **版本**: 1.0
- **日期**: 2026-04-15
- **模組**: community_parcel (Odoo 18)
- **測試站**: http://localhost:9097

---

## 1. 測試目標

確保 `community_parcel` 模組達到商用企業部署等級，涵蓋：
- 功能正確性（所有 CRUD、狀態機、Wizard）
- 安全性（群組權限、資料隔離）
- 資料完整性（關聯、序號、computed fields）
- 邊界條件（空值、重複、極端資料）
- 通知機制（mail template、chatter）
- 排程任務（cron 逾期偵測）
- 前端端點可達性（HTTP 200、View 載入）
- 批次操作效能

---

## 2. 測試範圍（10 Rounds）

### Round 1: API 基礎 CRUD
- community.parcel: create / read / write / unlink
- community.storage: create / read / write / unlink
- community.office: create / read / write / unlink
- res.partner 擴展欄位: unit_address / is_resident

### Round 2: 狀態機完整流程
- Parcel: draft → notified → picked_up（正常流程）
- Parcel: draft → notified → overdue → picked_up
- Parcel: draft → notified → returned
- Parcel: draft → notified → overdue → returned
- Storage: pending → storing → ready → done

### Round 3: 邊界條件與異常
- 空 barcode / 空 note 建立包裹
- 超長條碼（200 字元）
- 狀態機非法跳轉（draft → picked_up）
- 重複條碼允許（同一條碼多筆包裹）
- 必填欄位遺漏測試

### Round 4: 安全性與權限
- 無群組用戶無法存取 community.parcel
- Staff 群組可 RWC 但不可 delete
- Manager 群組可完整 CRUD
- 跨用戶資料可見性（Record Rules）

### Round 5: Wizard 快速登記
- 基本登記流程（建立 + 自動通知）
- 登記並繼續（保留 office 設定）
- 不自動通知模式
- 必填欄位驗證

### Round 6: Mail Template 通知
- 到件通知模板存在且格式正確
- 逾期提醒模板存在且格式正確
- action_notify 觸發 mail.message
- action_overdue 觸發 mail.message

### Round 7: Cron 逾期排程
- _cron_check_overdue 正確標記逾期包裹
- 未超過 7 天的不被標記
- 已取件/已退回的不被影響

### Round 8: 資料完整性與關聯
- related field unit_address 同步
- sequence 連續性（PKL/0001, 0002...）
- Many2one 關聯完整性
- computed field is_overdue 正確計算

### Round 9: 批次操作與效能
- 批次建立 50 筆包裹
- 批次狀態更新
- search_read 效能（大量資料）

### Round 10: 前端 HTTP 端點
- /web/login 可達
- /web 登入後可進入
- 選單 actions 可載入
- 各 view 的 XML 結構驗證

---

## 3. 測試資料保留策略

所有測試產生的資料**全部保留在資料庫中**，不做清理。
- 測試包裹以 `TEST-` 前綴 barcode 識別
- 測試住戶以 `test_` 前綴 email 識別
- 測試結果寫入 `tests/` 目錄

---

## 4. 通過標準

| 等級 | 標準 |
|------|------|
| PASS | 測試結果完全符合預期 |
| WARN | 功能正確但有非關鍵性問題 |
| FAIL | 功能不符合預期，需修復 |

**企業部署標準**: 所有 Round 必須 PASS 或 WARN（無 FAIL）

---

## 5. 產出物

- `docs/plans/2026-04-15-enterprise-testing-prd.md` — 本文件
- `tests/test_round_*.py` — 各 Round 測試腳本
- `tests/test_results.md` — 彙整測試報告
- 資料庫中所有測試資料保留
