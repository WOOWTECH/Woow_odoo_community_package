# Woow Odoo Community Package

WoowTech 社區管理系統 — Odoo 18 模組套件。

提供社區大樓的**公告管理**、**住戶意見反映**、**訪客管理**（含 QR Code 預約與即時通知）以及**包裹收發管理**（含條碼掃描、自動逾期追蹤）等功能。

## 模組架構

```
community_base          v18.0.2.0.0  基礎模組（必裝）
├── community_visitor   v18.0.1.0.0  訪客管理（延伸）
└── community_parcel    v18.0.1.0.0  包裹管理（延伸）
```

> `community_base` 為核心依賴，提供管理室、戶號、住戶關聯等基礎資料模型。
> `community_visitor` 和 `community_parcel` 為互相獨立的延伸模組，可依需求選裝。

---

## 模組詳細說明

### community_base — 社區基礎管理

**版本：** 18.0.2.0.0 &nbsp;|&nbsp; **依賴：** `base`, `mail`, `portal` &nbsp;|&nbsp; **授權：** LGPL-3

社區管理系統的核心基礎模組，提供所有延伸模組共用的資料結構與 Portal 整合。

#### 資料模型

| 模型 | 技術名稱 | 說明 |
|------|---------|------|
| 管理室 | `community.office` | 社區管理室設定，含負責人、建物名稱、PropertiesDefinition 動態屬性欄位 |
| 戶號 | `community.unit` | 社區戶號，以棟別+樓層+號碼唯一識別，自動計算顯示名稱 |
| 住戶 | `res.partner`（延伸） | 新增 `unit_ids`（Many2many 關聯戶號）與 `is_resident` 住戶標記 |
| 社區公告 | `community.announcement` | 公告內容管理，支援分類、Chatter 追蹤 |
| 公告分類 | `community.announcement.category` | 公告分類，支援拖曳排序 |
| 住戶意見反映 | `community.feedback` | 住戶提交的意見或報修，自動編號 |
| 反映分類 | `community.feedback.category` | 意見反映分類 |

#### 工作流程

**公告：** `草稿 → 已發布 → 封存`
- 草稿狀態可編輯，發布後住戶可在 Portal 查看
- 支援 mail.thread 追蹤名稱、分類、管理室、狀態變更

**意見反映：** `待處理 → 處理中 → 完成`
- 自動序號格式：`FB/YYYYMM/XXXX`
- 住戶可透過 Portal 提交與查看進度

#### Portal 整合

| 路由 | 功能 |
|------|------|
| `/my/announcements` | 公告列表（依分類篩選） |
| `/my/announcements/<id>` | 公告詳情 |
| `/my/feedback` | 我的意見反映列表 |
| `/my/feedback/<id>` | 反映詳情（含 Chatter） |
| `/my/feedback/new` | 提交新意見反映 |

#### 安全機制

- **13 條 ACL 規則** — 內部人員完整 CRUD、Portal 使用者唯讀存取（反映可建立）
- **4 條 Record Rules** — Portal 使用者僅能看到：
  - 所屬管理室已發布的公告
  - 自己提交的意見反映
- CSRF 保護：Portal 表單提交均含 CSRF token 驗證

---

### community_visitor — 社區訪客管理

**版本：** 18.0.1.0.0 &nbsp;|&nbsp; **依賴：** `community_base`, `mail`, `portal` &nbsp;|&nbsp; **授權：** LGPL-3

完整的訪客進出管理系統，涵蓋臨時訪客登記、住戶即時確認放行、預約通行 QR Code 等功能。

#### 資料模型

| 模型 | 技術名稱 | 說明 |
|------|---------|------|
| 訪客主檔 | `community.visitor` | 訪客基本資料（姓名、電話、身分證）、來訪次數統計、黑名單管理 |
| 到訪紀錄 | `community.visit` | 每次到訪的登記記錄，含住戶確認機制 |
| 預約通行 | `community.appointment` | 住戶預先建立的訪客通行授權，支援 QR Code |

#### 工作流程

**臨時到訪：** `草稿 → 待確認 → 已確認 → 已報到`
1. 警衛透過快速登記精靈建立訪客紀錄
2. 系統自動發送 email 通知所有相關戶號住戶
3. 住戶點擊 email 中的確認/拒絕連結（含 16-byte URL-safe token，20 分鐘有效）
4. 確認後系統透過 bus.bus 即時通知警衛端瀏覽器
5. 警衛確認放行，訪客報到

**預約通行：** `草稿 → 確認 → 已使用 / 已過期 / 已取消`
- 支援三種類型：
  - **一次性** — 單次有效，使用後自動標記
  - **週期性** — 設定日期範圍與允許時段
  - **永久** — 長期有效（如外送員、清潔人員）
- 建立後自動產生 **6 字元存取碼** 與 **QR Code 圖片**
- 警衛掃描 QR Code 或輸入存取碼即可驗證

#### 自動排程

| 排程 | 頻率 | 功能 |
|------|------|------|
| 到訪逾時檢查 | 每 5 分鐘 | 超過等候時間未確認的到訪自動標記逾時 |
| 預約到期檢查 | 每 1 小時 | 已過期的預約自動標記為已過期 |

#### 安全機制

- **2 個使用者群組：** 警衛 (`Guard`) < 社區主任 (`Manager`)，階層繼承
- **ACL 規則：** 警衛可 CRUD 訪客/到訪/預約、Portal 使用者唯讀（預約可建立）
- **Record Rules：** Portal 使用者僅能存取與自己戶號相關的訪客紀錄
- **Token 驗證：** 確認/拒絕連結含 URL-safe token，20 分鐘過期保護

#### Portal 整合

住戶可在 Portal 前台：
- 查看待確認的到訪紀錄
- 確認或拒絕訪客進入
- 管理預約通行（建立、查看、取消）

---

### community_parcel — 社區包裹管理

**版本：** 18.0.1.0.0 &nbsp;|&nbsp; **依賴：** `community_base`, `mail` &nbsp;|&nbsp; **授權：** LGPL-3

包裹收發登記與住戶間寄放物品管理，提供管理室工作台、條碼掃描快速登記、郵件自動通知與逾期追蹤。

#### 資料模型

| 模型 | 技術名稱 | 說明 |
|------|---------|------|
| 包裹 | `community.parcel` | 包裹收件登記，含條碼掃描、照片拍攝、狀態追蹤 |
| 寄放物品 | `community.storage` | 住戶間寄放物品登記、保管與交付追蹤 |
| 快速登記精靈 | `parcel.quick.register` | TransientModel，管理員快速掃碼建立包裹紀錄 |

#### 包裹欄位明細

| 欄位 | 類型 | 說明 |
|------|------|------|
| `name` | Char | 流水編號（自動 `PKL/0001`），唯讀 |
| `barcode` | Char | 快遞條碼，建有索引 |
| `resident_id` | Many2one → res.partner | 收件住戶（限 `is_resident=True`） |
| `unit_address` | Char (computed) | 自動帶入住戶的第一個戶號名稱 |
| `parcel_type` | Selection | 包裹 / 信件 / 掛號 / 其他 |
| `image` | Binary | 包裹照片（attachment 儲存） |
| `received_date` | Datetime | 收件時間（預設 now） |
| `notified_date` | Datetime | 通知住戶時間 |
| `pickup_date` | Datetime | 取件時間 |
| `picked_by` | Many2one → res.users | 取件確認人員 |
| `state` | Selection | 待通知 / 已通知 / 已取件 / 已退回 / 逾期 |
| `is_overdue` | Boolean (computed, stored) | 是否逾期（>7 天未取） |
| `office_id` | Many2one → community.office | 所屬管理室 |
| `note` | Text | 備註 |

#### 工作流程

**包裹：** `待通知 → 已通知 → 已取件 / 已退回 / 逾期`

```
draft ──[通知住戶]──▶ notified ──[確認取件]──▶ picked_up
                         │
                         ├──[退回]──▶ returned
                         │
                         └──[逾期(7天)]──▶ overdue ──[確認取件]──▶ picked_up
                                              │
                                              └──[退回]──▶ returned
```

- 通知住戶時自動發送「包裹到件通知」email
- 標記逾期時自動發送「包裹逾期提醒」email
- 每日排程自動檢查通知超過 7 天未取件的包裹，自動標記逾期

**寄放物品：** `待接收 → 保管中 → 待取件 → 完成`

```
pending ──[受理]──▶ storing ──[通知取件]──▶ ready ──[完成交付]──▶ done
```

#### 寄放物品欄位

| 欄位 | 類型 | 說明 |
|------|------|------|
| `name` | Char | 寄放編號（自動 `STG/0001`） |
| `depositor_id` | Many2one → res.partner | 寄放住戶（限 `is_resident=True`） |
| `recipient_id` | Many2one → res.partner | 取件人 |
| `item_description` | Text | 物品描述（必填） |
| `storage_location` | Char | 寄放位置/格號 |
| `deposit_date` | Datetime | 寄放時間 |
| `expected_pickup` | Date | 預計取件日 |
| `actual_pickup` | Datetime | 實際取件時間 |
| `state` | Selection | 待接收 / 保管中 / 待取件 / 完成 |

#### 管理室工作台

| 選單 | 功能 | 篩選條件 |
|------|------|---------|
| 今日到件 | 今天收到的包裹 | `received_date` 在今日 |
| 未取件 | 所有待處理包裹 | `state ∈ (draft, notified, overdue)` |
| 逾期包裹 | 超期未取 | `state = overdue` |
| 快速登記 | 條碼掃描精靈 | 開啟 wizard dialog |

#### 快速登記精靈

提供管理員快速建立包裹紀錄的精簡介面：
1. 掃描或輸入快遞條碼
2. 選擇收件住戶與包裹類型
3. 可選拍照、填寫備註
4. 可勾選「自動通知住戶」（預設開啟）
5. 「登記」— 建立後查看包裹詳情
6. 「登記並繼續」— 建立後直接開啟新的登記精靈

#### 郵件通知

| 範本 | 觸發時機 | 收件人 |
|------|---------|--------|
| 包裹到件通知 | 點擊「通知住戶」按鈕 | 收件住戶 email |
| 包裹逾期提醒 | 手動標記逾期或排程自動標記 | 收件住戶 email |

寄件人：管理室負責人 email，若未設定則使用當前使用者 email。

#### 自動排程

| 排程 | 頻率 | 功能 |
|------|------|------|
| 檢查逾期包裹 | 每日 | 通知超過 7 天未取件自動標記為逾期並發送提醒 |

#### 安全機制

- **模組分類：** 社區包裹管理
- **2 個使用者群組：** 管理室人員 (`Office Staff`) < 社區主任 (`Manager`)
- **ACL 規則：**
  - 管理室人員：包裹/寄放物品/精靈 — 可讀寫建立（不可刪除）
  - 社區主任：包裹/寄放物品 — 完整 CRUD（含刪除）
- **Record Rules：** 管理室人員可查看所有包裹與寄放物品紀錄

#### 視圖

兩個模型均提供：
- **表單視圖** — 完整欄位編輯與工作流程按鈕
- **列表視圖** — 多欄顯示、支援批次編輯，逾期紅色標記
- **看板視圖** — 依狀態分組顯示，逾期邊框警示
- **搜尋視圖** — 多維度篩選與分組

---

## 安裝

### 系統需求

- Odoo 18 Community 或 Enterprise
- Python 3.10+
- PostgreSQL 14+

### 安裝步驟

1. 將本 repo clone 到 Odoo 18 的 addons 路徑：
   ```bash
   cd /path/to/odoo/addons
   git clone https://github.com/WOOWTECH/Woow_odoo_community_package.git
   ```

2. 更新 `odoo.conf` 的 `addons_path`：
   ```ini
   addons_path = /path/to/odoo/addons/Woow_odoo_community_package,/path/to/odoo/addons,...
   ```

3. 重啟 Odoo 並更新模組列表：
   ```bash
   ./odoo-bin -c odoo.conf -u base --stop-after-init
   ```

4. 在 Odoo 後台「應用程式」中搜尋並安裝 **「社區基礎管理」**

5. 依需求安裝延伸模組：
   - **「社區訪客管理」** — 訪客登記與預約通行
   - **「社區包裹管理」** — 包裹收發與寄放物品

### 安裝順序

`community_base` 必須先安裝。延伸模組會自動解析依賴，直接安裝即可。

---

## 初始設定

### 1. 建立管理室

`社區管理 → 基礎設定 → 管理室` → 新增管理室，設定：
- 管理室名稱
- 建物名稱
- 負責人（用於 email 寄件人）

### 2. 建立戶號

`社區管理 → 基礎設定 → 戶號管理` → 新增戶號：
- 棟別、樓層、號碼（組合唯一）
- 指派所屬管理室

### 3. 設定住戶

`聯絡人` → 編輯聯絡人 → 「社區資訊」分頁：
- 勾選「社區住戶」
- 關聯戶號（可多對多）

### 4. 設定使用者權限

依角色指派模組群組：
- **community_base：** 內部使用者自動取得管理權限
- **community_visitor：** 指派「警衛」或「社區主任」群組
- **community_parcel：** 指派「管理室人員」或「社區主任」群組

### 5. 啟用 Portal

住戶聯絡人需設定 Portal 存取權限，方可使用前台功能：
- 發送 Portal 邀請 email
- 住戶登入後即可查看公告、提交反映、管理訪客預約

---

## 技術架構

### 模型關聯圖

```
res.partner (住戶)
    ├── unit_ids ←──M2M──→ community.unit (戶號)
    │                           └── office_id → community.office (管理室)
    │
    ├── ← resident_id ── community.parcel (包裹)
    ├── ← depositor_id / recipient_id ── community.storage (寄放)
    ├── ← resident_id ── community.visit (到訪)
    └── ← resident_id ── community.appointment (預約)

community.visitor (訪客主檔)
    ├── ← visitor_id ── community.visit
    └── ← visitor_id ── community.appointment
```

### 序號格式

| 模組 | 序號 | 格式 | 範例 |
|------|------|------|------|
| community_base | 意見反映 | `FB/YYYYMM/XXXX` | FB/202604/0001 |
| community_visitor | 訪客 | `VST/XXXX` | VST/0001 |
| community_visitor | 到訪 | `VIS/XXXX` | VIS/0001 |
| community_visitor | 預約 | `APT/XXXX` | APT/0001 |
| community_parcel | 包裹 | `PKL/XXXX` | PKL/0001 |
| community_parcel | 寄放 | `STG/XXXX` | STG/0001 |

### Mixin 使用

| 模型 | mail.thread | mail.activity.mixin | portal.mixin |
|------|:-----------:|:-------------------:|:------------:|
| community.announcement | V | | |
| community.feedback | V | | |
| community.visitor | V | | |
| community.visit | V | V | |
| community.appointment | V | V | |
| community.parcel | V | V | |
| community.storage | V | V | |

### 排程任務總覽

| 模組 | 任務 | 頻率 | 方法 |
|------|------|------|------|
| community_visitor | 到訪逾時檢查 | 5 分鐘 | `community.visit._cron_check_timeout()` |
| community_visitor | 預約到期檢查 | 1 小時 | `community.appointment._cron_check_expired()` |
| community_parcel | 逾期包裹檢查 | 1 天 | `community.parcel._cron_check_overdue()` |

---

## 授權

LGPL-3

## 作者

WoowTech
