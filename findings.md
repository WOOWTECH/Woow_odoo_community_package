# Findings: Code Review — Woow Odoo Community Package

## community_base (v18.0.2.0.0)

### Models
- **community.office** — 管理室，含 PropertiesDefinition 欄位（但 UI 未暴露）
- **community.unit** — 戶號，building+floor+number unique constraint，computed name
- **res.partner** — 延伸 unit_ids (M2M) + is_resident boolean
- **community.announcement** — 公告，draft→published→archived workflow，mail.thread
- **community.announcement.category** — 公告分類，drag-and-drop 排序
- **community.feedback** — 意見反映，auto-sequence FB/YYYYMM/XXXX，pending→in_progress→done
- **community.feedback.category** — 反映分類

### Security
- 13 ACL rules（staff CRUD + portal read-only + feedback create）
- 4 record rules（portal 限制只看自己 office 已發布公告、自己的反映）

### Portal
- 7 HTTP routes（公告列表/詳情、反映列表/詳情/建立）
- CSRF protection on feedback creation

### Bugs Found
1. PropertiesDefinition fields 定義了但 office form view 沒有暴露
2. Portal feedback creation 用 sudo() 但沒驗證 category_id 存在性
3. State transition methods 缺少 guard clauses（可透過 RPC 直接跳狀態）
4. Portal 可以枚舉 office/unit（沒有 record rules 限制）

---

## community_visitor (v18.0.1.0.0)

### Models
- **community.visitor** — 訪客主檔，含黑名單管理
- **community.visit** — 到訪紀錄，draft→pending_confirm→confirmed→checked_in workflow
- **community.appointment** — 預約通行，one-time/recurring/permanent，QR code + 6-char token

### Security
- 2 groups: Guard < Manager
- Row-level rules for portal（只看自己戶號的訪客）

### Features
- Token-based 住戶確認（16-byte URL-safe token，20 min expiry）
- bus.bus 即時通知 guards
- 2 cron jobs（visit timeout 5min / appointment expiry 1hr）

### Bugs Found (15 total)
1. **Critical**: 缺少 /my/appointments/<id>/cancel 路由（404）
2. **Critical**: appointment visitor_phone 非必填導致驗證時 crash
3. **High**: recurring appointment 時間檢查用 UTC 而非 local timezone
4. **Medium**: mail template 缺少 explicit email_to
5. **Medium**: action_reject 沒有驗證 token expiry（action_confirm 有）

---

## community_parcel (v18.0.1.0.0)

### Models
- **community.parcel** — 包裹，draft→notified→picked_up/returned/overdue workflow
  - 15 fields, mail.thread + mail.activity.mixin
  - barcode index, image attachment, computed unit_address, computed is_overdue
  - Cron: daily check 7-day overdue
- **community.storage** — 寄放物品，pending→storing→ready→done
  - 10 fields, mail.thread + mail.activity.mixin
- **parcel.quick.register** — TransientModel 快速登記精靈

### Security
- Module category + 2 groups: Office Staff < Manager
- 5 ACL rules, 2 record rules (staff see all)

### Mail Templates
- 包裹到件通知 (arrival)
- 包裹逾期提醒 (overdue)

### Bugs Found
1. **Medium**: is_overdue store=True 但依賴 wall-clock time，cron 間隔內可能 stale
2. **Medium**: barcode 無 unique constraint
3. **Medium**: parcel_type 在 email 中渲染為內部 key 而非 label
4. **Low**: cron 逐筆迭代而非批次處理
5. **Low**: 多戶住戶只顯示第一個 unit address
6. **Low**: recipient_id 沒有 domain filter（與 depositor_id 不一致）
7. **Low**: overdue template 缺少 lang field
8. **Low**: datetime import 在 method 內部而非檔案頂部

---

## Cross-Module Dependencies

```
community_base (base, mail, portal)
├── community_visitor (community_base, mail, portal)
└── community_parcel (community_base, mail)
```

### Shared References
- community_parcel 和 community_visitor 都使用 community_base 的:
  - `community.office` model
  - `community.unit` model
  - `res.partner.is_resident` / `res.partner.unit_ids`
  - `community_base.menu_community_root` menu item
