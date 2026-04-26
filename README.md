# Woow Odoo Community Package

WoowTech 社區管理系統 Odoo 18 模組套件。

## 模組架構

```
community_base          # 基礎模組（必裝）
├── community_visitor   # 訪客管理（延伸）
└── community_parcel    # 包裹管理（延伸）
```

## 模組說明

### community_base (v18.0.2.0.0)

社區管理系統的基礎模組，提供：

- **管理室** (`community.office`) — 社區管理室設定
- **戶號** (`community.unit`) — 社區戶號管理
- **住戶關聯** — 住戶（`res.partner`）與戶號的多對多關聯
- **社區公布欄** (`community.announcement`) — 草稿→發布→封存 工作流，含分類與 chatter 追蹤
- **住戶意見反映** (`community.feedback`) — 待處理→處理中→完成 工作流，含自動序號
- **Portal 入口** — 住戶可在前台查看公告、提交意見反映

依賴：`base`, `mail`, `portal`

### community_visitor (v18.0.1.0.0)

社區訪客管理模組，提供：

- **訪客登記** (`community.visitor`) — 訪客基本資料與黑名單管理
- **到訪紀錄** (`community.visit`) — 臨時訪客登記與住戶確認放行
- **預約通行** (`community.appointment`) — QR Code + 驗證碼預約機制
- **警衛介面** — 快速登記 wizard
- **住戶 Portal** — 住戶可在前台管理訪客預約

依賴：`community_base`, `mail`, `portal`

### community_parcel (v18.0.1.0.0)

社區包裹管理模組，提供：

- **包裹登記** (`community.parcel`) — 收件登記、條碼掃描、狀態追蹤（待通知→已通知→已取件/逾期/已退回）
- **寄放物品** (`community.storage`) — 住戶間寄放物品登記、保管與交付
- **管理室工作台** — 今日到件、未取件、逾期包裹一覽
- **快速登記精靈** — 條碼掃描快速建立包裹記錄
- **郵件通知** — 到件通知、逾期提醒自動發送
- **自動逾期排程** — 7 天未取件自動標記逾期

依賴：`community_base`, `mail`

## 安裝

1. 將本 repo clone 到 Odoo 18 的 addons 路徑
2. 更新 `odoo.conf` 中的 `addons_path` 包含本目錄
3. 在 Odoo 後台「應用程式」中安裝 `社區基礎管理`
4. 依需求安裝延伸模組

## 授權

LGPL-3

## 作者

WoowTech
