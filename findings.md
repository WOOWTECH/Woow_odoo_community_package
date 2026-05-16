# 測試發現記錄 — 50 輪企業級 E2E 測試

## Bugs Found
| # | Round | Severity | Description | Status |
|---|-------|----------|-------------|--------|
| B1 | R4 | HIGH | `community_appointment` 缺少 `max_entries` 欄位，Portal 建立預約時 500 Error。需執行 `odoo -u community_visitor` 升級模組。 | FIXED (module upgrade) |
| B2 | prev | HIGH | mail template `email_to` 使用 Jinja2 `reject` filter，Odoo 18 不支援 | FIXED (list comprehension) |
| B3 | prev | MEDIUM | 週期性預約時間欄位 `_parse_time_to_float` 無法處理 HH:MM 字串 | FIXED (added parser) |
| B4 | R4 | HIGH | Portal datetime 格式 `T` 分隔符未轉換，HTML `datetime-local` 送出 `YYYY-MM-DDTHH:MM` 但 Odoo 預期 `YYYY-MM-DD HH:MM` | FIXED (.replace('T', ' ')) |
| B5 | R24 | MEDIUM | 已過期預約仍可核銷 — `validate.appointment.wizard` 未檢查 `valid_until` 是否已過期 | OPEN |
| B6 | R25 | MEDIUM | 已撤銷預約仍可核銷 — wizard 未檢查 appointment state 是否為 `cancelled` | OPEN |
| B7 | R28 | LOW | 已使用中的訪客證可重複發放 — `in_use` 狀態的 badge 可同時指派給另一 visit，`current_visit_id` 未正確更新 | OPEN |
| B8 | R37 | LOW | `visit_count` computed field 可能未正確更新 — 訪客 id=52 顯示 visit_count=0 但實際有 5 筆訪問記錄 | OPEN |

## Observations
| # | Round | Category | Observation |
|---|-------|----------|-------------|
| O1 | R1 | UX | 訪問記錄 chatter 中郵件模板顯示未渲染的 `{{ object.* }}` 變數，但實際寄出的郵件是正確渲染的 |
| O2 | R1 | Data | 電話號碼 UNIQUE constraint 正常運作，重複電話會正確阻止 |
| O3 | R1 | UX | 訪客確認後狀態即時更新，Portal 顯示「已確認放行」/「已拒絕」結果頁面 |
| O4 | R5 | Logic | 週期性預約 `recurring_days` 使用數字格式 `0,1,2,3,4` (0=Mon, 6=Sun)，非文字縮寫 |
| O5 | R6 | Security | 黑名單機制完整：`action_blacklist` 標記 + `action_unblacklist` 解除，核銷時正確阻止黑名單訪客 |
| O6 | R7 | Logic | 訪客證生命週期正確：available → in_use (checkin) → available (checkout)，`current_visit_id` 自動追蹤 |
| O7 | R10 | Logic | 逾時排程 cron「社區訪客：逾時檢查」每 5 分鐘執行，`action_timeout` 正確轉換 pending_confirm → timeout |
| O8 | R14 | Logic | 包裹支持報廢 `action_scrap` → `scrapped` 狀態，逾期包裹仍可取件 |
| O9 | R18 | Data | 包裹條碼 UNIQUE constraint 正確：「此快遞條碼已存在！」 |
| O10 | R23 | Logic | 預約日期驗證正確：「有效截止時間必須晚於有效起始時間。」 |
| O11 | R27 | Data | 訪客證編號 UNIQUE constraint 正確：「訪客證編號不可重複！」 |
| O12 | R29 | Security | 8 條 record rules 覆蓋 4 個模型，Portal 用戶只能看到自己戶號資料 |
| O13 | R34 | Logic | 黑名單訪客帶包裹來訪：包裹可正常收件處理，但預約核銷未阻止（見 B5/B6 相關） |
| O14 | R38 | Portal | `/my/parcels` 和 `/my/storage` 返回 404，controller 路由尚未實作；`/my/visitors` 返回 403 |
| O15 | R39 | Logic | 工作流衝突保護正確：「只有已通知或逾期的包裹才能退回」 |
| O16 | R41-43 | Security | Record-level security (ir.rule) 正確運作，Portal 用戶無法跨戶存取包裹/訪問/預約 |
| O17 | R44 | Security | 未登入用戶正確重導向至登入頁面或返回 404 |

## Logic Issues
| # | Round | Issue | Expected | Actual |
|---|-------|-------|----------|--------|
| L1 | R24 | 過期預約核銷未阻止 | wizard 應拒絕過期預約 | 核銷成功 |
| L2 | R25 | 已撤銷預約核銷未阻止 | wizard 應拒絕 cancelled 預約 | 核銷成功 |
| L3 | R28 | in_use 訪客證可重複發放 | 應阻止重複指派 | 允許重複指派 |
| L4 | R37 | visit_count 計算不一致 | 應等於實際訪問數 | 顯示 0 |

## Portal 路由覆蓋狀態
| 路由 | 狀態 | 說明 |
|------|------|------|
| `/my/community` | 200 | 社區首頁正常 |
| `/my/appointments` | 200 | 預約列表正常 |
| `/my/appointments/<id>` | 200 | 預約詳情正常 |
| `/my/appointments/new` | 200 | 建立預約正常 |
| `/my/appointments/<id>/cancel` | 200 | 取消預約正常 |
| `/my/visitors` | 403 | 存取被拒（可能缺少 record rule） |
| `/my/parcels` | 404 | 路由未實作 |
| `/my/storage` | 404 | 路由未實作 |
| `/visitor/confirm/<token>` | 200 | 確認頁面正常 |
| `/visitor/confirm/<token>/accept` | 200 | 放行正常 |
| `/visitor/confirm/<token>/reject` | 200 | 拒絕正常 |
