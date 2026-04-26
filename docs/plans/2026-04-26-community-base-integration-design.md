# Community Base 整合設計

**日期：** 2026-04-26
**目標：** 將 `community_parcel` 改造為依賴 `community_base` 的延伸模組

---

## 1. 架構願景

```
community_base (基礎模組, depends: ['base'])
├── community_visitor (延伸：訪客管理, depends: ['community_base', 'mail', 'portal'])
└── community_parcel  (延伸：包裹管理, depends: ['community_base', 'mail'])
```

三個模組可獨立安裝，也可同時安裝在同一個 Odoo 實例。

## 2. 設計決策

| 項目 | 決策 |
|------|------|
| community_base 來源 | 從 9099 visitor worktree 原封不動複製 |
| office/partner 模型 | 完全以 community_base 為準，parcel 刪除自己的定義 |
| unit_id 欄位 | 不加，保持只選 resident_id，自動帶出第一個戶號 |
| 資料庫 | 重建乾淨環境 |
| 選單 | 統一根選單「社區管理」，包裹管理作為子選單 |
| community_base 主版本 | 暫時兩邊各放一份，之後再合併 |

## 3. 目錄結構

```
Woow_odoo_community_package/
├── addons/
│   ├── community_base/              ← 從 9099 原封不動複製
│   │   ├── __init__.py
│   │   ├── __manifest__.py              depends: ['base']
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── community_office.py      (name, building_name, responsible_id)
│   │   │   ├── community_unit.py        (building, floor, number, resident_ids M2M)
│   │   │   └── res_partner.py           (is_resident, unit_ids M2M)
│   │   ├── security/
│   │   │   └── ir.model.access.csv
│   │   └── views/
│   │       ├── community_office_views.xml
│   │       ├── community_unit_views.xml
│   │       ├── res_partner_views.xml
│   │       └── menus.xml
│   │
│   └── community_parcel/            ← 改造後
│       ├── __init__.py
│       ├── __manifest__.py              depends: ['community_base', 'mail']
│       ├── models/
│       │   ├── __init__.py              （移除 community_office, res_partner 引用）
│       │   ├── community_parcel.py      （unit_address 改 computed）
│       │   └── community_storage.py
│       ├── wizards/
│       │   ├── __init__.py
│       │   └── parcel_quick_register.py
│       ├── security/
│       │   ├── community_parcel_security.xml
│       │   └── ir.model.access.csv      （移除 community.office 存取規則）
│       ├── views/
│       │   ├── community_parcel_views.xml
│       │   ├── community_storage_views.xml
│       │   ├── parcel_quick_register_views.xml
│       │   ├── community_parcel_dashboard.xml
│       │   └── menu_views.xml           （掛入 community_base 根選單）
│       └── data/
│           ├── sequence_data.xml
│           ├── mail_template_data.xml
│           └── demo_data.xml            （移除 office demo，引用 base 的）
├── odoo.conf                            addons_path = /mnt/extra-addons
├── docker-compose.yml                   掛載 addons/ 目錄
└── tests/
```

## 4. 改動清單

### 4.1 刪除檔案
- `community_parcel/models/community_office.py`
- `community_parcel/models/res_partner.py`
- `community_parcel/views/community_office_views.xml`
- `community_parcel/views/res_partner_views.xml`

### 4.2 修改檔案

**`community_parcel/__manifest__.py`**
- depends: `['base', 'mail']` → `['community_base', 'mail']`
- 移除 data 中的 office/partner views 引用

**`community_parcel/models/__init__.py`**
- 移除 `from . import community_office`
- 移除 `from . import res_partner`

**`community_parcel/models/community_parcel.py`**
- `unit_address`: 從 `related='resident_id.unit_address'` 改為 computed field
  ```python
  unit_address = fields.Char(
      string='戶號',
      compute='_compute_unit_address',
      store=True,
  )
  @api.depends('resident_id', 'resident_id.unit_ids')
  def _compute_unit_address(self):
      for rec in self:
          if rec.resident_id and rec.resident_id.unit_ids:
              rec.unit_address = rec.resident_id.unit_ids[0].name
          else:
              rec.unit_address = False
  ```
- `office_id`: Many2one 保留不變（指向 community_base 的 community.office）
- `resident_id`: domain 保持 `[('is_resident', '=', True)]`（相容 base）

**`community_parcel/views/menu_views.xml`**
- 根選單改為引用 `community_base.menu_community_root`
- 加入「包裹管理」子選單分類

**`community_parcel/security/ir.model.access.csv`**
- 移除 `access_community_office_*` 行（由 base 管理）

**`community_parcel/security/community_parcel_security.xml`**
- 群組保持不變（社區主任/管理室人員）
- 確保群組分類不與 base 衝突

**`community_parcel/data/demo_data.xml`**
- office demo 資料改為引用 `community_base` 的 XML ID
- unit/partner demo 資料適配 base 的結構

### 4.3 容器配置

**`docker-compose.yml`**
- 掛載改為 `./addons:/mnt/extra-addons`（整個 addons 目錄）

**`odoo.conf`**
- `addons_path = /mnt/extra-addons` 不變

## 5. 相容性確認

確保以下介面與 9099 的 community_visitor 完全相容：
- `community.office` model（name, building_name, responsible_id）
- `community.unit` model（building, floor, number, resident_ids M2M）
- `res.partner` extension（is_resident, unit_ids M2M）
- 根選單 XML ID: `community_base.menu_community_root`
- 群組分類不衝突

## 6. 部署步驟

1. 複製 community_base 到 addons/
2. 搬移 community_parcel 到 addons/，同時改造
3. 更新 docker-compose.yml 掛載 addons/
4. 停止舊容器，刪除舊 volume
5. 啟動新容器
6. 初始化 DB：`odoo -i base --stop-after-init`
7. 安裝模組：`odoo -i community_base,community_parcel --stop-after-init`
8. 啟動 web 容器
9. 加入 admin 群組權限
10. 執行全部測試
