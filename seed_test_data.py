#!/usr/bin/env python3
"""
Seed script for Woow Odoo Community Package.
Creates ~20 records per module for portal user testing.
Run inside Odoo shell: cat seed_test_data.py | odoo shell -d <dbname>
"""
import random
import secrets
from datetime import datetime, timedelta

from odoo import fields

env = env  # noqa: provided by odoo shell

# ============================================================
# 0. Base setup: Office, Units, Portal User
# ============================================================
print("=== Step 0: Setting up Office, Units, Portal User ===")

Office = env['community.office']
Unit = env['community.unit']
Partner = env['res.partner']
Users = env['res.users']

# Create office if not exists
office = Office.search([('name', '=', '陽光社區管理室')], limit=1)
if not office:
    office = Office.create({
        'name': '陽光社區管理室',
        'building_name': '陽光大廈',
        'internal_note': '測試用管理室',
    })
    print(f"  Created office: {office.name}")
else:
    print(f"  Office already exists: {office.name}")

office2 = Office.search([('name', '=', '星河社區管理室')], limit=1)
if not office2:
    office2 = Office.create({
        'name': '星河社區管理室',
        'building_name': '星河花園',
        'internal_note': '第二個測試管理室',
    })
    print(f"  Created office: {office2.name}")

# Create units (apartments)
unit_data = [
    ('A', '1', '01'), ('A', '1', '02'), ('A', '2', '01'), ('A', '2', '02'),
    ('A', '3', '01'), ('A', '3', '02'), ('A', '4', '01'), ('A', '4', '02'),
    ('B', '1', '01'), ('B', '1', '02'), ('B', '2', '01'), ('B', '2', '02'),
    ('B', '3', '01'), ('B', '3', '02'), ('B', '4', '01'), ('B', '4', '02'),
    ('C', '1', '01'), ('C', '1', '02'), ('C', '2', '01'), ('C', '2', '02'),
]

units = []
for building, floor, number in unit_data:
    unit = Unit.search([
        ('building', '=', building),
        ('floor', '=', floor),
        ('number', '=', number),
    ], limit=1)
    if not unit:
        unit = Unit.create({
            'building': building,
            'floor': floor,
            'number': number,
            'office_id': office.id if building in ('A', 'B') else office2.id,
        })
    units.append(unit)
print(f"  {len(units)} units ready")

# Create or find portal user: 王大明
portal_group = env.ref('base.group_portal')
portal_user = Users.search([('login', '=', 'wang.daming@test.com')], limit=1)
if not portal_user:
    portal_user = Users.with_context(no_reset_password=True).create({
        'name': '王大明',
        'login': 'wang.daming@test.com',
        'email': 'wang.daming@test.com',
        'password': 'test1234',
        'groups_id': [(6, 0, [portal_group.id])],
    })
    print(f"  Created portal user: {portal_user.name}")
else:
    print(f"  Portal user already exists: {portal_user.name}")

portal_partner = portal_user.partner_id
portal_partner.write({'is_resident': True})

# Assign portal user to first 4 units (A棟1F-01, A棟1F-02, A棟2F-01, A棟2F-02)
for u in units[:4]:
    u.write({'resident_ids': [(4, portal_partner.id)]})
print(f"  Portal user assigned to {len(units[:4])} units")

# Create additional residents for variety
extra_residents = []
resident_names = [
    ('李小華', 'li.xiaohua@test.com'),
    ('陳美玲', 'chen.meiling@test.com'),
    ('張志強', 'zhang.zhiqiang@test.com'),
    ('林淑芬', 'lin.shufen@test.com'),
    ('黃建國', 'huang.jianguo@test.com'),
]
for rname, remail in resident_names:
    ruser = Users.search([('login', '=', remail)], limit=1)
    if not ruser:
        ruser = Users.with_context(no_reset_password=True).create({
            'name': rname,
            'login': remail,
            'email': remail,
            'password': 'test1234',
            'groups_id': [(6, 0, [portal_group.id])],
        })
    ruser.partner_id.write({'is_resident': True})
    extra_residents.append(ruser.partner_id)

# Assign extra residents to various units
for i, rp in enumerate(extra_residents):
    unit_idx = (i * 3 + 4) % len(units)
    units[unit_idx].write({'resident_ids': [(4, rp.id)]})
    units[(unit_idx + 1) % len(units)].write({'resident_ids': [(4, rp.id)]})

print(f"  {len(extra_residents)} extra residents created and assigned")
env.cr.commit()

# ============================================================
# 1. Announcement Categories & Announcements (~20)
# ============================================================
print("\n=== Step 1: Creating Announcements ===")

AnnCat = env['community.announcement.category']
Ann = env['community.announcement']

ann_cat_names = ['社區維護', '管理費通知', '活動通知', '公共設施', '安全提醒', '住戶公約']
ann_cats = []
for cn in ann_cat_names:
    cat = AnnCat.search([('name', '=', cn)], limit=1)
    if not cat:
        cat = AnnCat.create({'name': cn})
    ann_cats.append(cat)
print(f"  {len(ann_cats)} announcement categories ready")

ann_items = [
    ('2025年6月份管理費繳納通知', '管理費通知', '各位住戶您好，2025年6月份管理費已開立，請於6月15日前完成繳納。逾期將產生滯納金，感謝配合。'),
    ('頂樓防水工程施工通知', '社區維護', '預計6月10日至6月20日進行頂樓防水工程，施工期間頂樓區域暫停開放，造成不便敬請見諒。'),
    ('中庭花園噴水池維修公告', '社區維護', '中庭噴水池因設備老舊，將於6月5日進行維修更換。維修期間約3天，請住戶留意。'),
    ('夏季游泳池開放時間調整', '公共設施', '自6月1日起，社區游泳池開放時間調整為每日上午7:00至晚上9:00。請住戶遵守使用規範。'),
    ('社區中元普渡活動', '活動通知', '今年社區中元普渡活動訂於農曆7月15日舉辦，歡迎住戶踴躍參與。報名表請至管理室索取。'),
    ('地下室消防設備年度檢查', '安全提醒', '地下室消防設備將於6月25日進行年度檢查，屆時可能觸發消防警報，請住戶勿驚慌。'),
    ('社區監視系統升級公告', '安全提醒', '社區將於7月份全面升級監視系統，包含增設高解析度攝影機，提升社區安全。'),
    ('健身房新設備啟用通知', '公共設施', '社區健身房已新增跑步機3台、飛輪2台，歡迎住戶多加利用。使用前請詳閱使用說明。'),
    ('停車場車位重新劃線通知', '社區維護', '地下停車場將於6月底重新劃設車位線，施工期間請配合臨時停車安排。'),
    ('寵物飼養管理辦法修訂', '住戶公約', '經區分所有權人會議決議，寵物飼養管理辦法已修訂，新版規範自7月1日起生效。'),
    ('電梯定期保養通知', '社區維護', 'A棟電梯將於每月第一個週六上午進行定期保養，期間暫停使用約2小時。'),
    ('社區聖誕節聯歡晚會', '活動通知', '今年聖誕節聯歡晚會訂於12月24日晚間在中庭花園舉辦，活動含抽獎、表演節目。'),
    ('大廳地板翻新工程', '社區維護', 'A棟大廳地板翻新工程預計6月底動工，工期約一週。施工期間請走側門進出。'),
    ('社區Wi-Fi升級公告', '公共設施', '社區公共區域Wi-Fi已升級至Wi-Fi 6，新的連線密碼可至管理室查詢。'),
    ('垃圾分類新措施公告', '住戶公約', '自7月起社區將執行新的垃圾分類措施，廚餘需使用專用袋投入指定收集桶。'),
    ('颱風季防災準備提醒', '安全提醒', '颱風季節即將到來，請住戶檢查窗戶鎖扣，陽台物品固定。管理室已備妥沙袋。'),
    ('7月份管理費繳納通知', '管理費通知', '7月份管理費已開立，請於7月15日前完成繳納。可透過銀行轉帳或至管理室繳納。'),
    ('兒童遊戲室使用規範更新', '公共設施', '兒童遊戲室使用規範已更新，12歲以下兒童需有家長陪同，使用時間為8:00-20:00。'),
    ('社區中秋烤肉活動通知', '活動通知', '中秋節社區烤肉活動將於9月17日晚間在B棟中庭舉行，每戶可免費領取烤肉組一份。'),
    ('自來水管線汰換工程通知', '社區維護', 'B棟給水管線汰換工程將於8月初動工，施工期間部分時段將暫停供水，請住戶事先儲水。'),
    ('社區清潔日志工招募', '活動通知', '社區將於每月最後一個週六舉辦清潔日活動，歡迎住戶報名擔任志工，一起維護美好環境。'),
]

admin_user = env.ref('base.user_admin')
now = datetime.now()
ann_count = 0
for idx, (title, cat_name, content) in enumerate(ann_items):
    existing = Ann.search([('name', '=', title)], limit=1)
    if existing:
        continue
    cat = [c for c in ann_cats if c.name == cat_name][0]
    off = office if idx % 3 != 2 else office2
    ann = Ann.with_user(admin_user).create({
        'name': title,
        'category_id': cat.id,
        'office_id': off.id,
        'content': f'<p>{content}</p>',
        'state': 'draft',
    })
    # Publish most of them
    if idx < 18:
        ann.write({
            'state': 'published',
            'publish_date': now - timedelta(days=random.randint(1, 60)),
        })
    if idx >= 18 and idx < 20:
        ann.write({'state': 'archived'})
    ann_count += 1

print(f"  Created {ann_count} announcements")
env.cr.commit()

# ============================================================
# 2. Feedback Categories & Feedbacks (~20)
# ============================================================
print("\n=== Step 2: Creating Feedbacks ===")

FbCat = env['community.feedback.category']
Fb = env['community.feedback']

fb_cat_names = ['環境清潔', '設備維修', '噪音問題', '安全疑慮', '停車問題', '管理建議', '鄰里糾紛']
fb_cats = []
for cn in fb_cat_names:
    cat = FbCat.search([('name', '=', cn)], limit=1)
    if not cat:
        cat = FbCat.create({'name': cn})
    fb_cats.append(cat)
print(f"  {len(fb_cats)} feedback categories ready")

fb_items = [
    ('B棟3樓走廊燈損壞', '設備維修', '走廊盡頭的日光燈管已損壞數日未修理，夜間行走不便。', 'pending'),
    ('地下室滲水問題', '設備維修', '地下二樓B區車位旁天花板持續滲水，已有水漬擴大現象。', 'in_progress'),
    ('中庭垃圾桶溢出', '環境清潔', '中庭的垃圾桶經常在下午時段就已滿溢，建議增加清運頻率。', 'done'),
    ('隔壁裝潢噪音太大', '噪音問題', '隔壁A棟2F-02正在裝潢，每天早上8點就開始施工，嚴重影響休息。', 'pending'),
    ('大門感應門鎖故障', '設備維修', 'A棟大門感應門鎖時常無法辨識磁扣，需按多次才能開門。', 'in_progress'),
    ('停車場出口指示不清', '停車問題', '地下停車場出口處的指示標誌模糊不清，新住戶容易走錯方向。', 'pending'),
    ('頂樓公共區域髒亂', '環境清潔', '頂樓曬衣區經常有住戶遺留垃圾和雜物，建議加強巡查和清潔。', 'done'),
    ('電梯內廣告張貼問題', '管理建議', '建議管理室嚴格管理電梯內的廣告張貼，目前張貼過多影響美觀。', 'pending'),
    ('深夜寵物吠叫擾人', '噪音問題', '某住戶的狗在深夜經常吠叫，已持續一個多月，嚴重影響睡眠品質。', 'in_progress'),
    ('消防通道被雜物堵塞', '安全疑慮', 'B棟2樓消防通道被住戶放置鞋櫃和腳踏車，影響逃生安全。', 'pending'),
    ('游泳池水質需改善', '設備維修', '近期游泳池水質較為混濁，建議增加過濾和消毒頻率。', 'done'),
    ('停車位被他人佔用', '停車問題', '我的停車位A-15經常被不明車輛佔用，管理室是否能加強巡查？', 'pending'),
    ('公共廁所衛生紙缺補', '環境清潔', '1樓公共廁所經常沒有衛生紙，建議增加補充頻率或設置備用。', 'in_progress'),
    ('建議增設腳踏車停車架', '管理建議', '社區目前腳踏車停車空間不足，建議在B棟側門增設停車架。', 'pending'),
    ('樓上漏水影響天花板', '設備維修', '樓上浴室疑似漏水，我家天花板出現水漬且範圍逐漸擴大。', 'in_progress'),
    ('垃圾場蟑螂出沒', '環境清潔', '社區垃圾場近期蟑螂大量出沒，建議進行消毒滅蟲處理。', 'done'),
    ('機車停車場照明不足', '安全疑慮', '機車停車場角落區域照明不足，出入時有安全疑慮。', 'pending'),
    ('鄰居陽台曬棉被滴水', '鄰里糾紛', '樓上住戶經常在陽台曬棉被，水滴落到我的陽台，溝通無效。', 'pending'),
    ('管理費收據格式建議', '管理建議', '建議管理費收據增加明細項目分列，讓住戶了解各項費用用途。', 'done'),
    ('公共區域禁菸標示不足', '安全疑慮', '建議在中庭和走廊增設禁菸標示，部分住戶仍在公共區域吸菸。', 'pending'),
]

fb_count = 0
all_residents = [portal_partner] + extra_residents
for idx, (title, cat_name, content, state) in enumerate(fb_items):
    existing = Fb.search([('title', '=', title)], limit=1)
    if existing:
        continue
    cat = [c for c in fb_cats if c.name == cat_name][0]
    resident = all_residents[idx % len(all_residents)]
    # Pick a unit that belongs to the resident
    resident_units = resident.unit_ids
    if not resident_units:
        resident_units = units[0]
    unit = resident_units[0] if len(resident_units) else units[0]

    fb = Fb.with_user(admin_user).create({
        'title': title,
        'content': content,
        'category_id': cat.id,
        'unit_id': unit.id,
        'partner_id': resident.id,
        'state': state,
    })
    fb_count += 1

print(f"  Created {fb_count} feedbacks")
env.cr.commit()

# ============================================================
# 3. Visitors & Visits (~20)
# ============================================================
print("\n=== Step 3: Creating Visitors and Visits ===")

Visitor = env['community.visitor']
Visit = env['community.visit']

# Visit purposes
Purpose = env['community.visit.purpose']
purpose_names = ['拜訪親友', '送貨', '維修', '快遞', '家教', '看護', '房仲帶看', '搬家']
purposes = []
for pn in purpose_names:
    p = Purpose.search([('name', '=', pn)], limit=1)
    if not p:
        p = Purpose.create({'name': pn})
    purposes.append(p)

# Visitor badges
Badge = env['community.visitor.badge']
for i in range(1, 21):
    badge = Badge.search([('name', '=', f'V-{i:03d}')], limit=1)
    if not badge:
        Badge.create({
            'name': f'V-{i:03d}',
            'state': 'available',
        })

visitor_data = [
    ('張三', '0912345001', '1234', '台達電子', False),
    ('李四', '0912345002', '5678', '宅配通', False),
    ('王五', '0912345003', '9012', '', False),
    ('趙六', '0912345004', '3456', '水電行', False),
    ('孫七', '0912345005', '7890', '', False),
    ('周八', '0912345006', '2345', '家樂福', False),
    ('吳九', '0912345007', '6789', '黑貓宅急便', False),
    ('鄭十', '0912345008', '0123', '', False),
    ('馬大力', '0912345009', '4567', '搬家公司', False),
    ('陳小明', '0912345010', '8901', '', False),
    ('劉美芳', '0912345011', '3210', '', False),
    ('許志明', '0912345012', '6543', '冷氣維修', False),
    ('蔡依倫', '0912345013', '9876', '', False),
    ('謝佳慧', '0912345014', '2109', '', False),
    ('林大雄', '0912345015', '5432', '搬家公司', True),  # blacklisted
    ('楊小薇', '0912345016', '8765', '', False),
    ('洪志偉', '0912345017', '1098', '網路安裝', False),
    ('葉美麗', '0912345018', '4321', '', False),
    ('廖國華', '0912345019', '7654', '房仲', False),
    ('施雅琪', '0912345020', '0987', '', False),
]

visitors = []
for vname, phone, id4, company, blacklisted in visitor_data:
    v = Visitor.search([('phone', '=', phone)], limit=1)
    if not v:
        vals = {
            'name': vname,
            'phone': phone,
            'id_last4': id4,
            'company': company or False,
            'blacklisted': blacklisted,
        }
        if blacklisted:
            vals['blacklist_reason'] = '曾有不當行為紀錄'
            vals['blacklist_date'] = fields.Date.today()
        v = Visitor.create(vals)
    visitors.append(v)
print(f"  {len(visitors)} visitors ready")

# Create visits
visit_states = [
    'checked_out', 'checked_out', 'checked_out', 'checked_out',
    'checked_in', 'checked_in',
    'confirmed', 'confirmed',
    'pending_confirm', 'pending_confirm', 'pending_confirm',
    'rejected', 'timeout',
    'checked_out', 'checked_out', 'checked_out',
    'checked_in',
    'pending_confirm', 'confirmed', 'draft',
]

visit_count = 0
for idx in range(20):
    visitor = visitors[idx]
    if visitor.blacklisted:
        continue  # skip blacklisted visitors
    purpose = purposes[idx % len(purposes)]
    unit = units[idx % 4]  # portal user's units
    target_state = visit_states[idx]

    existing = Visit.search([
        ('visitor_id', '=', visitor.id),
        ('unit_id', '=', unit.id),
    ], limit=1)
    if existing:
        continue

    visit = Visit.with_user(admin_user).create({
        'visitor_id': visitor.id,
        'unit_id': unit.id,
        'purpose_id': purpose.id,
        'visit_type': 'walk_in',
        'state': 'draft',
    })

    # Use direct SQL-like writes to bypass state machine constraints
    if target_state in ('pending_confirm', 'confirmed', 'rejected', 'timeout', 'checked_in', 'checked_out'):
        visit.with_context(tracking_disable=True).write({
            'state': 'pending_confirm',
            'confirm_token': secrets.token_urlsafe(16),
            'token_expiry': now + timedelta(minutes=20),
        })
    if target_state in ('confirmed', 'checked_in', 'checked_out'):
        visit.with_context(tracking_disable=True).write({
            'state': 'confirmed',
            'resident_id': portal_partner.id,
            'resident_confirm_time': now - timedelta(hours=random.randint(1, 48)),
        })
    if target_state == 'rejected':
        visit.with_context(tracking_disable=True).write({
            'state': 'rejected',
            'resident_id': portal_partner.id,
        })
    if target_state == 'timeout':
        visit.with_context(tracking_disable=True).write({'state': 'timeout'})
    if target_state in ('checked_in', 'checked_out'):
        visit.with_context(tracking_disable=True).write({
            'state': 'checked_in',
            'checkin_time': now - timedelta(hours=random.randint(1, 48)),
        })
    if target_state == 'checked_out':
        visit.with_context(tracking_disable=True).write({
            'state': 'checked_out',
            'checkout_time': now - timedelta(minutes=random.randint(10, 120)),
            'guard_out_id': admin_user.id,
        })
    visit_count += 1

print(f"  Created {visit_count} visits")
env.cr.commit()

# ============================================================
# 4. Appointments (~20)
# ============================================================
print("\n=== Step 4: Creating Appointments ===")

Appointment = env['community.appointment']

# Map visitor phone -> visitor record for appointment linking
visitor_by_phone = {v.phone: v for v in visitors}

appt_items = [
    ('0912345001', 'one_time', '拜訪親友', 'active'),
    ('0912345002', 'one_time', '送貨', 'active'),
    ('0912345003', 'recurring', '家教', 'active'),
    ('0912345004', 'one_time', '維修', 'active'),
    ('0912345005', 'one_time', '看護', 'active'),
    ('0912345006', 'one_time', '送貨', 'expired'),
    ('0912345007', 'one_time', '快遞', 'active'),
    ('0912345008', 'recurring', '看護', 'active'),
    ('0912345009', 'one_time', '搬家', 'active'),
    ('0912345010', 'one_time', '拜訪親友', 'cancelled'),
    ('0912345011', 'one_time', '拜訪親友', 'active'),
    ('0912345012', 'recurring', '維修', 'active'),
    ('0912345013', 'one_time', '拜訪親友', 'active'),
    ('0912345014', 'one_time', '拜訪親友', 'expired'),
    ('0912345016', 'one_time', '拜訪親友', 'active'),
    ('0912345017', 'one_time', '維修', 'active'),
    ('0912345018', 'recurring', '看護', 'active'),
    ('0912345019', 'one_time', '房仲帶看', 'active'),
    ('0912345020', 'one_time', '拜訪親友', 'cancelled'),
    ('0912345001', 'recurring', '拜訪親友', 'active'),
]

appt_count = 0
for idx, (vphone, appt_type, purpose_name, state) in enumerate(appt_items):
    unit = units[idx % 4]  # portal user's units
    visitor = visitor_by_phone.get(vphone)
    if not visitor:
        continue

    existing = Appointment.search([
        ('visitor_id', '=', visitor.id),
        ('unit_id', '=', unit.id),
        ('appointment_type', '=', appt_type),
    ], limit=1)
    if existing:
        continue

    # Find matching purpose
    purpose = Purpose.search([('name', '=', purpose_name)], limit=1)
    if not purpose:
        purpose = Purpose.create({'name': purpose_name})

    valid_from = now - timedelta(days=random.randint(0, 30))
    valid_until = now + timedelta(days=random.randint(1, 90))
    if state == 'expired':
        valid_until = now - timedelta(days=random.randint(1, 10))

    vals = {
        'resident_id': portal_partner.id,
        'unit_id': unit.id,
        'visitor_id': visitor.id,
        'valid_from': valid_from,
        'valid_until': valid_until,
        'appointment_type': appt_type,
        'purpose_id': purpose.id,
        'state': 'active',
    }
    if appt_type == 'recurring':
        vals['mon'] = True
        vals['wed'] = True
        vals['fri'] = True
        vals['recurring_from'] = 9.0
        vals['recurring_until'] = 18.0

    appt = Appointment.with_user(admin_user).create(vals)
    if state == 'expired':
        appt.write({'state': 'expired'})
    elif state == 'cancelled':
        appt.write({'state': 'cancelled'})
    appt_count += 1

print(f"  Created {appt_count} appointments")
env.cr.commit()

# ============================================================
# 5. Parcels (~20)
# ============================================================
print("\n=== Step 5: Creating Parcels ===")

Parcel = env['community.parcel']
ParcelType = env['community.parcel.type']

pt_names = ['一般包裹', '掛號信件', '快遞', '大型包裹', '冷藏包裹', '文件']
parcel_types = []
for ptn in pt_names:
    pt = ParcelType.search([('name', '=', ptn)], limit=1)
    if not pt:
        pt = ParcelType.create({'name': ptn})
    parcel_types.append(pt)
print(f"  {len(parcel_types)} parcel types ready")

parcel_items = [
    ('1234567890001', '一般包裹', 'picked_up', 'momo購物'),
    ('1234567890002', '快遞', 'notified', 'PChome'),
    ('1234567890003', '掛號信件', 'notified', '中華郵政'),
    ('1234567890004', '大型包裹', 'draft', 'IKEA'),
    ('1234567890005', '冷藏包裹', 'notified', '全聯冷凍'),
    ('1234567890006', '一般包裹', 'picked_up', '蝦皮'),
    ('1234567890007', '文件', 'notified', '法院通知'),
    ('1234567890008', '快遞', 'picked_up', '黑貓宅急便'),
    ('1234567890009', '一般包裹', 'returned', '退貨-尺寸不合'),
    ('1234567890010', '大型包裹', 'notified', '特力屋'),
    ('1234567890011', '一般包裹', 'overdue', 'Yahoo購物'),
    ('1234567890012', '掛號信件', 'picked_up', '稅務通知'),
    ('1234567890013', '快遞', 'notified', 'Amazon'),
    ('1234567890014', '一般包裹', 'draft', '淘寶集運'),
    ('1234567890015', '冷藏包裹', 'picked_up', '鮮食配送'),
    ('1234567890016', '文件', 'notified', '銀行信件'),
    ('1234567890017', '一般包裹', 'picked_up', 'Costco線上'),
    ('1234567890018', '快遞', 'overdue', '日本代購'),
    ('1234567890019', '大型包裹', 'notified', '家具配送'),
    ('1234567890020', '一般包裹', 'draft', '生日禮物'),
]

parcel_count = 0
for idx, (barcode, type_name, state, desc) in enumerate(parcel_items):
    existing = Parcel.search([('barcode', '=', barcode)], limit=1)
    if existing:
        continue
    ptype = [pt for pt in parcel_types if pt.name == type_name][0]
    unit = units[idx % 4]  # portal user's units
    received = now - timedelta(days=random.randint(0, 30))

    vals = {
        'unit_id': unit.id,
        'barcode': barcode,
        'type_id': ptype.id,
        'description': desc,
        'received_date': received,
        'state': 'draft',
    }

    parcel = Parcel.with_user(admin_user).create(vals)

    # Progress state
    if state in ('notified', 'picked_up', 'returned', 'overdue'):
        parcel.write({
            'state': 'notified',
            'notified_date': received + timedelta(hours=random.randint(1, 4)),
        })
    if state == 'picked_up':
        parcel.write({
            'state': 'picked_up',
            'pickup_date': received + timedelta(days=random.randint(1, 3)),
        })
    if state == 'returned':
        parcel.write({'state': 'returned'})
    if state == 'overdue':
        parcel.write({
            'state': 'overdue',
            'notified_date': now - timedelta(days=10),
        })
    parcel_count += 1

print(f"  Created {parcel_count} parcels")
env.cr.commit()

# ============================================================
# 6. Storage (~20)
# ============================================================
print("\n=== Step 6: Creating Storage Items ===")

Storage = env['community.storage']
StorageType = env['community.storage.type']

st_names = ['鑰匙', '文件', '小型物品', '大型物品', '食品', '電器']
storage_types = []
for stn in st_names:
    st = StorageType.search([('name', '=', stn)], limit=1)
    if not st:
        st = StorageType.create({'name': stn})
    storage_types.append(st)
print(f"  {len(storage_types)} storage types ready")

storage_items = [
    ('鑰匙', '備用門鑰匙一串', '管理室櫃台', 'done', '李小華'),
    ('文件', '社區規約文件', '管理室抽屜A', 'storing', ''),
    ('小型物品', '藍牙耳機', '管理室保管箱', 'ready', '王大明'),
    ('大型物品', '腳踏車（紅色）', '地下室儲藏間', 'storing', '陳美玲'),
    ('食品', '中秋月餅禮盒', '管理室冰箱', 'done', '張志強'),
    ('電器', '電風扇（維修完成）', '管理室角落', 'ready', '林淑芬'),
    ('鑰匙', '信箱備用鑰匙', '管理室櫃台', 'storing', ''),
    ('小型物品', '遮陽傘', '管理室傘架', 'pending', ''),
    ('文件', '管委會會議記錄', '管理室抽屜B', 'done', '黃建國'),
    ('大型物品', '嬰兒推車', '地下室儲藏間', 'storing', '王大明'),
    ('食品', '宅配蛋糕', '管理室冰箱', 'ready', '李小華'),
    ('電器', '延長線（待修）', '管理室維修區', 'pending', ''),
    ('小型物品', '太陽眼鏡', '管理室失物招領', 'storing', ''),
    ('鑰匙', '社區活動室鑰匙', '管理室鑰匙箱', 'storing', ''),
    ('大型物品', '滑板車', '地下室儲藏間', 'done', '陳美玲'),
    ('文件', '裝潢申請書', '管理室抽屜A', 'ready', '張志強'),
    ('食品', '水果禮盒', '管理室冰箱', 'pending', ''),
    ('電器', '除濕機', '管理室角落', 'storing', '王大明'),
    ('小型物品', '手電筒', '管理室保管箱', 'done', '林淑芬'),
    ('大型物品', '折疊桌', '地下室儲藏間', 'ready', '黃建國'),
]

storage_count = 0
for idx, (type_name, desc, location, state, recipient_name) in enumerate(storage_items):
    existing = Storage.search([
        ('item_description', '=', desc),
        ('storage_location', '=', location),
    ], limit=1)
    if existing:
        continue
    stype = [st for st in storage_types if st.name == type_name][0]
    unit = units[idx % 4]
    deposit = now - timedelta(days=random.randint(1, 45))

    vals = {
        'unit_id': unit.id,
        'type_id': stype.id,
        'item_description': desc,
        'storage_location': location,
        'deposit_date': deposit,
        'recipient_name': recipient_name or False,
        'state': 'pending',
    }
    if state != 'pending':
        vals['expected_pickup'] = (deposit + timedelta(days=random.randint(3, 14))).date()

    storage = Storage.with_user(admin_user).create(vals)

    if state in ('storing', 'ready', 'done'):
        storage.write({'state': 'storing'})
    if state in ('ready', 'done'):
        storage.write({'state': 'ready'})
    if state == 'done':
        storage.write({
            'state': 'done',
            'actual_pickup': deposit + timedelta(days=random.randint(2, 10)),
        })
    storage_count += 1

print(f"  Created {storage_count} storage items")
env.cr.commit()

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("=== Data Seeding Complete ===")
print(f"  Office:        2")
print(f"  Units:         {len(units)}")
print(f"  Portal User:   王大明 (wang.daming@test.com / test1234)")
print(f"  Residents:     {1 + len(extra_residents)}")
print(f"  Announcements: {Ann.search_count([])}")
print(f"  Feedbacks:     {Fb.search_count([])}")
print(f"  Visitors:      {Visitor.search_count([])}")
print(f"  Visits:        {Visit.search_count([])}")
print(f"  Appointments:  {Appointment.search_count([])}")
print(f"  Parcels:       {Parcel.search_count([])}")
print(f"  Storage:       {Storage.search_count([])}")
print("=" * 60)
