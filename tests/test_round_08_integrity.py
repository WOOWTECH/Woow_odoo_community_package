#!/usr/bin/env python3
"""Round 8: 資料完整性與關聯測試"""
import xmlrpc.client, json, sys

URL = 'http://localhost:9098'
DB = 'odoocommunitypackage'
common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common.authenticate(DB, 'admin', 'admin', {})
models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', allow_none=True)
results = []

def call(model, method, *args, **kwargs):
    return models.execute_kw(DB, uid, 'admin', model, method, *args, **kwargs)

def call_action(model, method, ids):
    """Call action methods that return None — use execute_kw with context to ensure non-None return."""
    try:
        result = call(model, method, [ids])
        return result
    except xmlrpc.client.Fault as e:
        if 'cannot marshal None' in str(e) or 'OdooMars' in str(e):
            return True
        raise

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
print("Round 8: 資料完整性與關聯測試")
print("=" * 70)

# 8.1 Related field unit_address 同步
print("\n── 8.1 Related field 同步 ──")
def test_unit_address_sync():
    pid = call('res.partner', 'create', [{'name': 'TEST-R8-Sync', 'email': 'test_r8_sync@test.com', 'is_resident': True, 'unit_address': 'E棟-501'}])
    parcel_id = call('community.parcel', 'create', [{'barcode': 'TEST-R8-SYNC', 'resident_id': pid, 'parcel_type': 'parcel'}])
    d = call('community.parcel', 'read', [[parcel_id], ['unit_address']])[0]
    return d['unit_address'] == 'E棟-501', f"unit_address={d['unit_address']}"
test("related_field_unit_address_sync", test_unit_address_sync)

# 8.2 Sequence 連續性
print("\n── 8.2 Sequence 連續性 ──")
def test_sequence_continuity():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid1 = call('community.parcel', 'create', [{'barcode': 'TEST-R8-SEQ1', 'resident_id': res_ids[0], 'parcel_type': 'parcel'}])
    pid2 = call('community.parcel', 'create', [{'barcode': 'TEST-R8-SEQ2', 'resident_id': res_ids[0], 'parcel_type': 'parcel'}])
    d1 = call('community.parcel', 'read', [[pid1], ['name']])[0]
    d2 = call('community.parcel', 'read', [[pid2], ['name']])[0]
    # Extract numbers
    n1 = int(d1['name'].split('/')[1])
    n2 = int(d2['name'].split('/')[1])
    ok = n2 == n1 + 1
    return ok, f"{d1['name']} → {d2['name']}, diff={n2 - n1}"
test("sequence_continuity_pkl", test_sequence_continuity)

def test_storage_sequence():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    sid1 = call('community.storage', 'create', [{'depositor_id': res_ids[0], 'item_description': 'TEST-R8-SSEQ1'}])
    sid2 = call('community.storage', 'create', [{'depositor_id': res_ids[0], 'item_description': 'TEST-R8-SSEQ2'}])
    d1 = call('community.storage', 'read', [[sid1], ['name']])[0]
    d2 = call('community.storage', 'read', [[sid2], ['name']])[0]
    n1 = int(d1['name'].split('/')[1])
    n2 = int(d2['name'].split('/')[1])
    ok = n2 == n1 + 1
    return ok, f"{d1['name']} → {d2['name']}, diff={n2 - n1}"
test("sequence_continuity_stg", test_storage_sequence)

# 8.3 Many2one 關聯完整性
print("\n── 8.3 Many2one 關聯 ──")
def test_many2one_resident():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R8-M2O', 'resident_id': res_ids[0], 'parcel_type': 'parcel'}])
    d = call('community.parcel', 'read', [[pid], ['resident_id']])[0]
    ok = d['resident_id'] and d['resident_id'][0] == res_ids[0]
    return ok, f"resident_id={d['resident_id']}"
test("many2one_resident_integrity", test_many2one_resident)

def test_many2one_office():
    off_ids = call('community.office', 'search', [[]], {'limit': 1})
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R8-M2O-OFF', 'resident_id': res_ids[0], 'office_id': off_ids[0], 'parcel_type': 'parcel'}])
    d = call('community.parcel', 'read', [[pid], ['office_id']])[0]
    return d['office_id'] and d['office_id'][0] == off_ids[0], f"office_id={d['office_id']}"
test("many2one_office_integrity", test_many2one_office)

# 8.4 Computed field is_overdue
print("\n── 8.4 Computed field is_overdue ──")
def test_is_overdue_draft():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R8-ISOD1', 'resident_id': res_ids[0], 'parcel_type': 'parcel'}])
    d = call('community.parcel', 'read', [[pid], ['is_overdue', 'state']])[0]
    return d['is_overdue'] == False, f"state={d['state']}, is_overdue={d['is_overdue']}"
test("is_overdue_false_for_draft", test_is_overdue_draft)

def test_is_overdue_state():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R8-ISOD2', 'resident_id': res_ids[0], 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_overdue', [pid])
    d = call('community.parcel', 'read', [[pid], ['is_overdue', 'state']])[0]
    return d['is_overdue'] == True and d['state'] == 'overdue', f"state={d['state']}, is_overdue={d['is_overdue']}"
test("is_overdue_true_for_overdue_state", test_is_overdue_state)

def test_is_overdue_picked():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R8-ISOD3', 'resident_id': res_ids[0], 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_pickup', [pid])
    d = call('community.parcel', 'read', [[pid], ['is_overdue', 'state']])[0]
    return d['is_overdue'] == False, f"state={d['state']}, is_overdue={d['is_overdue']}"
test("is_overdue_false_after_pickup", test_is_overdue_picked)

# 8.5 Tracking fields
print("\n── 8.5 Tracking 欄位 ──")
def test_state_tracking():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R8-TRACK', 'resident_id': res_ids[0], 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    # Check tracking messages exist
    msgs = call('mail.message', 'search_count', [[('res_id', '=', pid), ('model', '=', 'community.parcel'), ('tracking_value_ids', '!=', False)]])
    return msgs > 0, f"Tracking messages found: {msgs}"
test("state_change_tracked_in_chatter", test_state_tracking)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 8 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_08_results.json', 'w') as fh:
    json.dump({'round': 8, 'title': '資料完整性與關聯', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
