#!/usr/bin/env python3
"""Round 2: 狀態機完整流程測試"""
import xmlrpc.client, json, sys

URL = 'http://localhost:9097'
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
            # Method succeeded but returned None — that's OK for action methods
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

res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
RES_ID = res_ids[0]

def make_parcel(bc):
    return call('community.parcel', 'create', [{'barcode': bc, 'resident_id': RES_ID, 'parcel_type': 'parcel'}])

print("=" * 70)
print("Round 2: 狀態機完整流程測試")
print("=" * 70)

# ── Parcel State Machine ──
print("\n── 2.1 Parcel: draft → notified → picked_up ──")
def test_normal_flow():
    pid = make_parcel('TEST-R2-NORMAL')
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    assert d['state'] == 'draft', f"Expected draft, got {d['state']}"
    call_action('community.parcel', 'action_notify', [pid])
    d = call('community.parcel', 'read', [[pid], ['state', 'notified_date']])[0]
    assert d['state'] == 'notified', f"Expected notified, got {d['state']}"
    assert d['notified_date'], "notified_date should be set"
    call_action('community.parcel', 'action_pickup', [pid])
    d = call('community.parcel', 'read', [[pid], ['state', 'pickup_date', 'picked_by']])[0]
    ok = d['state'] == 'picked_up' and d['pickup_date'] and d['picked_by']
    return ok, f"state={d['state']}, pickup_date={d['pickup_date']}, picked_by={d['picked_by']}"
test("parcel_draft_notified_picked_up", test_normal_flow)

print("\n── 2.2 Parcel: draft → notified → overdue → picked_up ──")
def test_overdue_pickup():
    pid = make_parcel('TEST-R2-OD-PICKUP')
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_overdue', [pid])
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    assert d['state'] == 'overdue', f"Expected overdue, got {d['state']}"
    call_action('community.parcel', 'action_pickup', [pid])
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    return d['state'] == 'picked_up', f"state={d['state']}"
test("parcel_draft_notified_overdue_picked_up", test_overdue_pickup)

print("\n── 2.3 Parcel: draft → notified → returned ──")
def test_return_flow():
    pid = make_parcel('TEST-R2-RETURN')
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_return', [pid])
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    return d['state'] == 'returned', f"state={d['state']}"
test("parcel_draft_notified_returned", test_return_flow)

print("\n── 2.4 Parcel: draft → notified → overdue → returned ──")
def test_overdue_return():
    pid = make_parcel('TEST-R2-OD-RETURN')
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_overdue', [pid])
    call_action('community.parcel', 'action_return', [pid])
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    return d['state'] == 'returned', f"state={d['state']}"
test("parcel_draft_notified_overdue_returned", test_overdue_return)

# ── Storage State Machine ──
print("\n── 2.5 Storage: pending → storing → ready → done ──")
def test_storage_flow():
    sid = call('community.storage', 'create', [{'depositor_id': RES_ID, 'item_description': 'TEST-R2 storage flow'}])
    d = call('community.storage', 'read', [[sid], ['state']])[0]
    assert d['state'] == 'pending'
    call_action('community.storage', 'action_accept', [sid])
    d = call('community.storage', 'read', [[sid], ['state']])[0]
    assert d['state'] == 'storing', f"Expected storing, got {d['state']}"
    call_action('community.storage', 'action_ready', [sid])
    d = call('community.storage', 'read', [[sid], ['state']])[0]
    assert d['state'] == 'ready', f"Expected ready, got {d['state']}"
    call_action('community.storage', 'action_done', [sid])
    d = call('community.storage', 'read', [[sid], ['state', 'actual_pickup']])[0]
    ok = d['state'] == 'done' and d['actual_pickup']
    return ok, f"state={d['state']}, actual_pickup={d['actual_pickup']}"
test("storage_pending_storing_ready_done", test_storage_flow)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 2 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_02_results.json', 'w') as fh:
    json.dump({'round': 2, 'title': '狀態機完整流程', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
