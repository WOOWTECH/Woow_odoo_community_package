#!/usr/bin/env python3
"""
Seed remaining data: Appointments, Parcels, Storage
(Steps 0-3 already completed successfully)
"""
import random
import secrets
from datetime import datetime, timedelta

from odoo import fields

env = env  # noqa: provided by odoo shell

# ============================================================
# Re-fetch existing references
# ============================================================
print("=== Fetching existing references ===")

Office = env['community.office']
Unit = env['community.unit']
Partner = env['res.partner']
Users = env['res.users']
Visitor = env['community.visitor']
Purpose = env['community.visit.purpose']

office = Office.search([('name', '=', '陽光社區管理室')], limit=1)
office2 = Office.search([('name', '=', '星河社區管理室')], limit=1)

units = Unit.search([], order='building, floor, number')
portal_user = Users.search([('login', '=', 'wang.daming@test.com')], limit=1)
portal_partner = portal_user.partner_id
admin_user = env.ref('base.user_admin')
now = datetime.now()

# Get all visitors by phone
all_visitors = Visitor.search([])
visitor_by_phone = {v.phone: v for v in all_visitors}

print(f"  Office: {office.name}, Units: {len(units)}, Portal: {portal_partner.name}")
print(f"  Visitors: {len(all_visitors)}")

# ============================================================
# 4. Appointments (~20)
# ============================================================
print("\n=== Step 4: Creating Appointments ===")

Appointment = env['community.appointment']

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
portal_units = units[:4]  # first 4 units belong to portal user
for idx, (vphone, appt_type, purpose_name, state) in enumerate(appt_items):
    unit = portal_units[idx % len(portal_units)]
    visitor = visitor_by_phone.get(vphone)
    if not visitor:
        print(f"  WARNING: Visitor with phone {vphone} not found, skipping")
        continue

    existing = Appointment.search([
        ('visitor_id', '=', visitor.id),
        ('unit_id', '=', unit.id),
        ('appointment_type', '=', appt_type),
    ], limit=1)
    if existing:
        continue

    # Find or create matching purpose
    purpose = Purpose.search([('name', '=', purpose_name)], limit=1)
    if not purpose:
        purpose = Purpose.create({'name': purpose_name})

    valid_from = now - timedelta(days=random.randint(0, 30))
    valid_until = now + timedelta(days=random.randint(1, 90))
    if state == 'expired':
        valid_from = now - timedelta(days=60)
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
        appt.with_context(tracking_disable=True).write({'state': 'expired'})
    elif state == 'cancelled':
        appt.with_context(tracking_disable=True).write({'state': 'cancelled'})
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
    unit = portal_units[idx % len(portal_units)]
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

    # Progress state using direct writes to bypass action constraints
    if state in ('notified', 'picked_up', 'returned', 'overdue'):
        parcel.with_context(tracking_disable=True).write({
            'state': 'notified',
            'notified_date': received + timedelta(hours=random.randint(1, 4)),
        })
    if state == 'picked_up':
        parcel.with_context(tracking_disable=True).write({
            'state': 'picked_up',
            'pickup_date': received + timedelta(days=random.randint(1, 3)),
            'picked_by': admin_user.id,
        })
    if state == 'returned':
        parcel.with_context(tracking_disable=True).write({'state': 'returned'})
    if state == 'overdue':
        parcel.with_context(tracking_disable=True).write({
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
    unit = portal_units[idx % len(portal_units)]
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
        storage.with_context(tracking_disable=True).write({'state': 'storing'})
    if state in ('ready', 'done'):
        storage.with_context(tracking_disable=True).write({'state': 'ready'})
    if state == 'done':
        storage.with_context(tracking_disable=True).write({
            'state': 'done',
            'actual_pickup': deposit + timedelta(days=random.randint(2, 10)),
        })
    storage_count += 1

print(f"  Created {storage_count} storage items")
env.cr.commit()

# ============================================================
# Summary
# ============================================================
Visit = env['community.visit']
Ann = env['community.announcement']
Fb = env['community.feedback']

print("\n" + "=" * 60)
print("=== Data Seeding Complete ===")
print(f"  Appointments:  {Appointment.search_count([])}")
print(f"  Parcels:       {Parcel.search_count([])}")
print(f"  Storage:       {Storage.search_count([])}")
print(f"  ---")
print(f"  Announcements: {Ann.search_count([])}")
print(f"  Feedbacks:     {Fb.search_count([])}")
print(f"  Visitors:      {Visitor.search_count([])}")
print(f"  Visits:        {Visit.search_count([])}")
print("=" * 60)
