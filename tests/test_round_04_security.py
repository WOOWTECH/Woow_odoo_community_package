#!/usr/bin/env python3
"""Round 4: 安全性與權限測試"""
import xmlrpc.client, json, sys

URL = 'http://localhost:9097'
DB = 'odoocommunitypackage'
common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
admin_uid = common.authenticate(DB, 'admin', 'admin', {})
admin_models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', allow_none=True)
results = []

def admin_call(model, method, *args, **kwargs):
    return admin_models.execute_kw(DB, admin_uid, 'admin', model, method, *args, **kwargs)

def user_call(uid, model, method, *args, **kwargs):
    return admin_models.execute_kw(DB, uid, 'testpass123', model, method, *args, **kwargs)

def test(name, func):
    try:
        ok, detail = func()
        status = 'PASS' if ok else 'FAIL'
    except Exception as e:
        status = 'FAIL'; detail = str(e)[:300]; ok = False
    results.append({'test': name, 'status': status, 'detail': detail})
    print(f"  {'✅' if ok else '❌'} {name}: {status} — {detail}")
    return ok

print("=" * 70)
print("Round 4: 安全性與權限測試")
print("=" * 70)

# ── Setup test users ──
print("\n── Setup: 建立測試用戶 ──")

# Get group IDs
staff_group_id = admin_call('ir.model.data', 'search_read',
    [[('module', '=', 'community_parcel'), ('name', '=', 'community_parcel_group_office_staff')]],
    {'fields': ['res_id'], 'limit': 1})
manager_group_id = admin_call('ir.model.data', 'search_read',
    [[('module', '=', 'community_parcel'), ('name', '=', 'community_parcel_group_manager')]],
    {'fields': ['res_id'], 'limit': 1})

STAFF_GID = staff_group_id[0]['res_id'] if staff_group_id else None
MANAGER_GID = manager_group_id[0]['res_id'] if manager_group_id else None
print(f"  Staff group id: {STAFF_GID}, Manager group id: {MANAGER_GID}")

# Create test users
def create_test_user(login, name, group_ids):
    existing = admin_call('res.users', 'search', [[('login', '=', login)]])
    if existing:
        admin_call('res.users', 'write', [existing, {'groups_id': [(6, 0, group_ids)], 'password': 'testpass123'}])
        return existing[0]
    uid = admin_call('res.users', 'create', [{
        'name': name, 'login': login, 'email': f'{login}@test.com',
        'password': 'testpass123', 'groups_id': [(6, 0, group_ids)],
    }])
    return uid

# Base groups needed for ORM access
base_group_ids = admin_call('res.groups', 'search', [[('category_id.name', '=', 'User types'), ('name', 'ilike', 'Internal User')]])
base_gids = base_group_ids if base_group_ids else []

no_group_user = create_test_user('test_r4_nogroup', 'TEST-R4-無群組', base_gids)
staff_user = create_test_user('test_r4_staff', 'TEST-R4-Staff', base_gids + [STAFF_GID])
manager_user = create_test_user('test_r4_manager', 'TEST-R4-Manager', base_gids + [MANAGER_GID])

# Authenticate test users
no_uid = common.authenticate(DB, 'test_r4_nogroup', 'testpass123', {})
staff_uid = common.authenticate(DB, 'test_r4_staff', 'testpass123', {})
manager_uid = common.authenticate(DB, 'test_r4_manager', 'testpass123', {})
print(f"  no_uid={no_uid}, staff_uid={staff_uid}, manager_uid={manager_uid}")

# Get a resident for testing
res_ids = admin_call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
RES_ID = res_ids[0]

# ── 4.1 No-group user access ──
print("\n── 4.1 無群組用戶存取限制 ──")

def test_no_group_read():
    try:
        user_call(no_uid, 'community.parcel', 'search_read', [[]], {'limit': 1})
        return False, "Should be blocked from reading parcels"
    except xmlrpc.client.Fault as e:
        return 'AccessError' in str(e) or 'access' in str(e).lower(), f"Blocked: AccessError"
test("no_group_cannot_read_parcel", test_no_group_read)

def test_no_group_create():
    try:
        user_call(no_uid, 'community.parcel', 'create', [{'barcode': 'TEST-R4-NOACCESS', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
        return False, "Should be blocked"
    except xmlrpc.client.Fault as e:
        return 'AccessError' in str(e) or 'access' in str(e).lower(), f"Blocked: AccessError"
test("no_group_cannot_create_parcel", test_no_group_create)

# ── 4.2 Staff group access ──
print("\n── 4.2 Staff 群組權限 ──")

def test_staff_read():
    data = user_call(staff_uid, 'community.parcel', 'search_read', [[]], {'fields': ['name'], 'limit': 5})
    return len(data) > 0, f"Staff can read: found {len(data)} parcels"
test("staff_can_read_parcel", test_staff_read)

def test_staff_create():
    pid = user_call(staff_uid, 'community.parcel', 'create', [{'barcode': 'TEST-R4-STAFF-CREATE', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    return pid > 0, f"Staff created parcel id={pid}"
test("staff_can_create_parcel", test_staff_create)

def test_staff_write():
    ids = user_call(staff_uid, 'community.parcel', 'search', [[('barcode', '=', 'TEST-R4-STAFF-CREATE')]])
    user_call(staff_uid, 'community.parcel', 'write', [ids, {'note': 'Staff updated'}])
    d = user_call(staff_uid, 'community.parcel', 'read', [ids, ['note']])[0]
    return 'Staff updated' in d['note'], f"Staff can write: note={d['note']}"
test("staff_can_write_parcel", test_staff_write)

def test_staff_cannot_delete():
    ids = user_call(staff_uid, 'community.parcel', 'search', [[('barcode', '=', 'TEST-R4-STAFF-CREATE')]])
    try:
        user_call(staff_uid, 'community.parcel', 'unlink', [ids])
        return False, "Staff should NOT be able to delete"
    except xmlrpc.client.Fault as e:
        return 'AccessError' in str(e) or 'access' in str(e).lower(), f"Blocked: Staff cannot delete"
test("staff_cannot_delete_parcel", test_staff_cannot_delete)

# ── 4.3 Manager group access ──
print("\n── 4.3 Manager 群組權限 ──")

def test_manager_crud():
    pid = user_call(manager_uid, 'community.parcel', 'create', [{'barcode': 'TEST-R4-MGR-CRUD', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    d = user_call(manager_uid, 'community.parcel', 'read', [[pid], ['name']])[0]
    user_call(manager_uid, 'community.parcel', 'write', [[pid], {'note': 'Manager updated'}])
    user_call(manager_uid, 'community.parcel', 'unlink', [[pid]])
    remaining = user_call(manager_uid, 'community.parcel', 'search', [[('id', '=', pid)]])
    return len(remaining) == 0, f"Manager full CRUD OK, created+deleted id={pid}"
test("manager_full_crud", test_manager_crud)

# ── 4.4 Storage access ──
print("\n── 4.4 Storage 權限 ──")

def test_staff_storage_rw():
    sid = user_call(staff_uid, 'community.storage', 'create', [{'depositor_id': RES_ID, 'item_description': 'TEST-R4 staff storage'}])
    d = user_call(staff_uid, 'community.storage', 'read', [[sid], ['name']])[0]
    return sid > 0 and d['name'].startswith('STG/'), f"Staff storage RW OK: {d['name']}"
test("staff_storage_read_write_create", test_staff_storage_rw)

def test_staff_storage_no_delete():
    ids = user_call(staff_uid, 'community.storage', 'search', [[('item_description', 'like', 'TEST-R4 staff')]])
    try:
        user_call(staff_uid, 'community.storage', 'unlink', [ids])
        return False, "Staff should NOT delete storage"
    except xmlrpc.client.Fault as e:
        return 'AccessError' in str(e) or 'access' in str(e).lower(), "Blocked: Staff cannot delete storage"
test("staff_cannot_delete_storage", test_staff_storage_no_delete)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 4 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_04_results.json', 'w') as fh:
    json.dump({'round': 4, 'title': '安全性與權限', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
