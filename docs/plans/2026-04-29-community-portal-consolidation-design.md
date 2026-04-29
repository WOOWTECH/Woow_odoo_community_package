# 社區管理 Portal 入口整合設計

## 目標

將目前散佈在 `/my` 首頁的 6 張獨立卡片整合為一張「社區管理」主卡片，點擊後進入 `/my/community` 中間落地頁，再從 6 張子分類卡片進入各功能列表。

## 導航流程

```
/my (首頁)
  └─ 社區管理 (單一卡片，無數量 badge)
       └─ /my/community (落地頁，3×2 網格)
            ├─ 社區公告 → /my/announcements
            ├─ 意見反映 → /my/feedbacks
            ├─ 我的訪客 → /my/visitors
            ├─ 我的預約 → /my/appointments
            ├─ 包裹收件 → /my/parcels
            └─ 物品寄放 → /my/storage
```

## 設計決策

| 項目 | 決策 |
|------|------|
| 落地頁佈局 | 3×2 網格 |
| RWD 響應式 | 桌面 3 欄 / 平板 2 欄 / 手機 1 欄 |
| 圖示風格 | Odoo 預設色系 64×64 SVG（#C1DBF6, #FBDBD0, #374874） |
| 首頁主卡片 | 不顯示數量 badge |
| 子卡片排列 | 按功能性質分群：資訊→人員→物品 |
| 子卡片數量 | 不顯示數量 badge |
| 導航 | 麵包屑 + 返回按鈕 |

## 落地頁子卡片排列

| 位置 | 功能 | 描述 |
|------|------|------|
| 1 | 社區公告 | 瀏覽社區公布欄 |
| 2 | 意見反映 | 提交意見或查看處理進度 |
| 3 | 我的訪客 | 查看與管理待確認的訪客 |
| 4 | 我的預約 | 管理訪客預約通行單 |
| 5 | 包裹收件 | 查看待取包裹 |
| 6 | 物品寄放 | 查看寄放物品狀態 |

## RWD 斷點

| 裝置 | 每行卡片數 | Bootstrap class |
|------|-----------|----------------|
| 桌面 (≥992px) | 3 張 | col-lg-4 |
| 平板 (≥768px) | 2 張 | col-md-6 |
| 手機 (<768px) | 1 張 | col-12 |

## 需修改的檔案

1. `community_base/views/portal_templates.xml` — 移除舊卡片，改為單一主卡片 + 新增落地頁模板
2. `community_base/controllers/portal.py` — 新增 /my/community 路由
3. `community_visitor/views/portal_visitor_templates.xml` — 移除首頁卡片注入
4. `community_parcel/views/portal_templates.xml` — 移除首頁卡片注入

## 需新增的檔案

`community_base/static/src/img/` 下 7 個 SVG 圖示：
- community-home.svg（主卡片）
- community-announcement.svg
- community-feedback.svg
- community-visitor.svg
- community-appointment.svg
- community-parcel.svg
- community-storage.svg

## 不變動的部分

- 各功能列表頁/詳情頁模板
- 各功能 controller 路由
- model、security、chatter
