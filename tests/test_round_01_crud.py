#!/usr/bin/env python3
"""
Round 1: API 基礎 CRUD 測試
測試 community.parcel / community.storage / community.office / res.partner 擴展
透過 XML-RPC 對 localhost:9098 進行測試
"""
import xmlrpc.client
import json
import sys

URL = 'http://localhost:9098'
DB = 'odoocommunitypackage'
USER = 'admin'
PASS = 'admin'

common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common.authenticate(DB, USER, PASS, {})
models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', allow_none=True)

results = []

def call(model, method, *args, **kwargs):
    return models.execute_kw(DB, uid, PASS, model, method, *args, **kwargs)

def test(name, func):
    try:
        ok, detail = func()
        status = 'PASS' if ok else 'FAIL'
    except Exception as e:
        status = 'FAIL'
        detail = str(e)[:200]
        ok = False
    results.append({'test': name, 'status': status, 'detail': detail})
    icon = '✅' if ok else '❌'
    print(f"  {icon} {name}: {status} — {detail}")
    return ok

print("=" * 70)
print("Round 1: API 基礎 CRUD 測試")
print("=" * 70)

# ──────────────────────────────────────────────────────────
# 1.1 res.partner 擴展欄位測試
# ──────────────────────────────────────────────────────────
print("\n── 1.1 res.partner 擴展欄位 ──")

def test_partner_create():
    pid = call('res.partner', 'create', [{'name': 'TEST-R1-住戶B', 'email': 'test_r1b@test.com', 'is_resident': True, 'unit_address': 'C棟-301'}])
    if pid:
        data = call('res.partner', 'read', [[pid], ['name', 'is_resident', 'unit_address']])[0]
        ok = data['is_resident'] == True and data['unit_address'] == 'C棟-301'
        return ok, f"id={pid}, is_resident={data['is_resident']}, unit_address={data['unit_address']}"
    return False, "create returned None"
test("partner_create_with_extension_fields", test_partner_create)

def test_partner_read():
    ids = call('res.partner', 'search', [[('email', '=', 'test_r1b@test.com')]])
    if ids:
        data = call('res.partner', 'read', [ids, ['name', 'is_resident', 'unit_address']])[0]
        return True, f"Found: {data['name']}, unit={data['unit_address']}"
    return False, "Not found"
test("partner_read_extension_fields", test_partner_read)

def test_partner_write():
    ids = call('res.partner', 'search', [[('email', '=', 'test_r1b@test.com')]])
    call('res.partner', 'write', [ids, {'unit_address': 'D棟-402'}])
    data = call('res.partner', 'read', [ids, ['unit_address']])[0]
    return data['unit_address'] == 'D棟-402', f"Updated unit_address={data['unit_address']}"
test("partner_write_extension_fields", test_partner_write)

def test_partner_non_resident():
    pid = call('res.partner', 'create', [{'name': 'TEST-R1-非住戶B', 'email': 'test_r1_nonresb@test.com', 'is_resident': False}])
    data = call('res.partner', 'read', [[pid], ['is_resident', 'unit_address']])[0]
    return data['is_resident'] == False, f"is_resident={data['is_resident']}"
test("partner_non_resident_default", test_partner_non_resident)

# ──────────────────────────────────────────────────────────
# 1.2 community.office CRUD (fields: name, building_id, responsible_id)
# ──────────────────────────────────────────────────────────
print("\n── 1.2 community.office CRUD ──")

def test_office_create():
    oid = call('community.office', 'create', [{'name': 'TEST-R1-管理室B', 'building_id': 'TEST大樓B'}])
    if oid:
        data = call('community.office', 'read', [[oid], ['name', 'building_id']])[0]
        return data['name'] == 'TEST-R1-管理室B', f"id={oid}, name={data['name']}, building={data['building_id']}"
    return False, "create returned None"
test("office_create", test_office_create)

def test_office_read():
    ids = call('community.office', 'search', [[('name', '=', 'TEST-R1-管理室B')]])
    return len(ids) == 1, f"Found {len(ids)} records"
test("office_read", test_office_read)

def test_office_write():
    ids = call('community.office', 'search', [[('name', '=', 'TEST-R1-管理室B')]])
    call('community.office', 'write', [ids, {'building_id': 'TEST大樓C'}])
    data = call('community.office', 'read', [ids, ['building_id']])[0]
    return data['building_id'] == 'TEST大樓C', f"Updated building_id={data['building_id']}"
test("office_write", test_office_write)

def test_office_unlink():
    oid = call('community.office', 'create', [{'name': 'TEST-R1-暫存管理室B'}])
    call('community.office', 'unlink', [[oid]])
    remaining = call('community.office', 'search', [[('id', '=', oid)]])
    return len(remaining) == 0, f"Deleted id={oid}"
test("office_unlink", test_office_unlink)

# ──────────────────────────────────────────────────────────
# 1.3 community.parcel CRUD
# ──────────────────────────────────────────────────────────
print("\n── 1.3 community.parcel CRUD ──")

# Get/create test resident
res_ids = call('res.partner', 'search', [[('email', '=', 'test_r1b@test.com')]])
test_resident_id = res_ids[0] if res_ids else None

# Get/create test office
off_ids = call('community.office', 'search', [[('name', '=', 'TEST-R1-管理室B')]])
test_office_id = off_ids[0] if off_ids else None

def test_parcel_create():
    pid = call('community.parcel', 'create', [{
        'barcode': 'TEST-R1-BC002',
        'resident_id': test_resident_id,
        'parcel_type': 'parcel',
        'office_id': test_office_id,
        'note': 'Round 1 CRUD test parcel v2',
    }])
    if pid:
        data = call('community.parcel', 'read', [[pid], ['name', 'barcode', 'state', 'resident_id']])[0]
        ok = data['name'].startswith('PKL/') and data['state'] == 'draft'
        return ok, f"id={pid}, name={data['name']}, state={data['state']}"
    return False, "create returned None"
test("parcel_create", test_parcel_create)

def test_parcel_create_letter():
    pid = call('community.parcel', 'create', [{
        'barcode': 'TEST-R1-LTR002',
        'resident_id': test_resident_id,
        'parcel_type': 'letter',
        'note': 'Round 1 letter type test v2',
    }])
    data = call('community.parcel', 'read', [[pid], ['parcel_type']])[0]
    return data['parcel_type'] == 'letter', f"parcel_type={data['parcel_type']}"
test("parcel_create_letter_type", test_parcel_create_letter)

def test_parcel_create_registered():
    pid = call('community.parcel', 'create', [{
        'barcode': 'TEST-R1-REG002',
        'resident_id': test_resident_id,
        'parcel_type': 'registered',
    }])
    data = call('community.parcel', 'read', [[pid], ['parcel_type']])[0]
    return data['parcel_type'] == 'registered', f"parcel_type={data['parcel_type']}"
test("parcel_create_registered_type", test_parcel_create_registered)

def test_parcel_create_other():
    pid = call('community.parcel', 'create', [{
        'barcode': 'TEST-R1-OTH001',
        'resident_id': test_resident_id,
        'parcel_type': 'other',
    }])
    data = call('community.parcel', 'read', [[pid], ['parcel_type']])[0]
    return data['parcel_type'] == 'other', f"parcel_type={data['parcel_type']}"
test("parcel_create_other_type", test_parcel_create_other)

def test_parcel_read():
    ids = call('community.parcel', 'search', [[('barcode', '=', 'TEST-R1-BC002')]])
    if ids:
        data = call('community.parcel', 'read', [ids, ['name', 'barcode', 'resident_id', 'state', 'parcel_type', 'received_date']])[0]
        return data['barcode'] == 'TEST-R1-BC002', f"Read barcode={data['barcode']}, name={data['name']}"
    return False, "Not found"
test("parcel_read", test_parcel_read)

def test_parcel_search_read():
    data = call('community.parcel', 'search_read', [[('barcode', 'like', 'TEST-R1-')]], {'fields': ['name', 'barcode', 'state'], 'limit': 20})
    return len(data) >= 4, f"Found {len(data)} TEST-R1 parcels"
test("parcel_search_read", test_parcel_search_read)

def test_parcel_write():
    ids = call('community.parcel', 'search', [[('barcode', '=', 'TEST-R1-BC002')]])
    call('community.parcel', 'write', [ids, {'note': 'Updated note v2 - Round 1'}])
    data = call('community.parcel', 'read', [ids, ['note']])[0]
    return 'Updated note v2' in data['note'], f"Updated note={data['note']}"
test("parcel_write", test_parcel_write)

def test_parcel_unlink():
    pid = call('community.parcel', 'create', [{
        'barcode': 'TEST-R1-DELETE2',
        'resident_id': test_resident_id,
        'parcel_type': 'other',
    }])
    call('community.parcel', 'unlink', [[pid]])
    remaining = call('community.parcel', 'search', [[('id', '=', pid)]])
    return len(remaining) == 0, f"Deleted id={pid}"
test("parcel_unlink", test_parcel_unlink)

# ──────────────────────────────────────────────────────────
# 1.4 community.storage CRUD
# ──────────────────────────────────────────────────────────
print("\n── 1.4 community.storage CRUD ──")

def test_storage_create():
    sid = call('community.storage', 'create', [{
        'depositor_id': test_resident_id,
        'item_description': 'TEST-R1 寄放測試物品B',
        'storage_location': 'A區櫃台',
    }])
    if sid:
        data = call('community.storage', 'read', [[sid], ['name', 'state', 'item_description']])[0]
        ok = data['name'].startswith('STG/') and data['state'] == 'pending'
        return ok, f"id={sid}, name={data['name']}, state={data['state']}"
    return False, "create returned None"
test("storage_create", test_storage_create)

def test_storage_read():
    ids = call('community.storage', 'search', [[('item_description', 'like', 'TEST-R1')]])
    if ids:
        data = call('community.storage', 'read', [[ids[0]], ['name', 'depositor_id', 'item_description', 'state']])[0]
        return True, f"Read: {data['name']}, desc={data['item_description']}"
    return False, "Not found"
test("storage_read", test_storage_read)

def test_storage_write():
    ids = call('community.storage', 'search', [[('item_description', 'like', 'TEST-R1 寄放測試物品B')]])
    call('community.storage', 'write', [ids, {'storage_location': 'C區後方'}])
    data = call('community.storage', 'read', [ids, ['storage_location']])[0]
    return data['storage_location'] == 'C區後方', f"Updated location={data['storage_location']}"
test("storage_write", test_storage_write)

def test_storage_unlink():
    sid = call('community.storage', 'create', [{
        'depositor_id': test_resident_id,
        'item_description': 'TEST-R1-暫存刪除B',
    }])
    call('community.storage', 'unlink', [[sid]])
    remaining = call('community.storage', 'search', [[('id', '=', sid)]])
    return len(remaining) == 0, f"Deleted id={sid}"
test("storage_unlink", test_storage_unlink)

# ── Summary ──
print("\n" + "=" * 70)
passed = sum(1 for r in results if r['status'] == 'PASS')
failed = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 1 結果: {passed} PASS / {failed} FAIL / {len(results)} Total")
print("=" * 70)

with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_01_results.json', 'w') as f:
    json.dump({'round': 1, 'title': 'API 基礎 CRUD', 'results': results, 'summary': {'pass': passed, 'fail': failed, 'total': len(results)}}, f, ensure_ascii=False, indent=2)

sys.exit(0 if failed == 0 else 1)
