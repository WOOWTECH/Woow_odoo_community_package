#!/usr/bin/env python3
"""Round 3: 邊界條件與異常測試"""
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

res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
RES_ID = res_ids[0]

print("=" * 70)
print("Round 3: 邊界條件與異常測試")
print("=" * 70)

# 3.1 空 barcode 建立包裹（barcode 非必填）
print("\n── 3.1 空 barcode 建立包裹 ──")
def test_empty_barcode():
    pid = call('community.parcel', 'create', [{'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    d = call('community.parcel', 'read', [[pid], ['barcode', 'name']])[0]
    return pid > 0, f"Created id={pid}, name={d['name']}, barcode={d['barcode']}"
test("empty_barcode_create", test_empty_barcode)

# 3.2 空 note 建立包裹
print("\n── 3.2 空 note 建立包裹 ──")
def test_empty_note():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R3-NONOTE', 'resident_id': RES_ID, 'parcel_type': 'letter'}])
    d = call('community.parcel', 'read', [[pid], ['note']])[0]
    return pid > 0, f"Created, note={d['note']}"
test("empty_note_create", test_empty_note)

# 3.3 超長條碼 (200 字元)
print("\n── 3.3 超長條碼 ──")
def test_long_barcode():
    long_bc = 'TEST-R3-' + 'X' * 192
    pid = call('community.parcel', 'create', [{'barcode': long_bc, 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    d = call('community.parcel', 'read', [[pid], ['barcode']])[0]
    return len(d['barcode']) == 200, f"barcode length={len(d['barcode'])}"
test("long_barcode_200_chars", test_long_barcode)

# 3.4 狀態機非法跳轉 draft → picked_up
print("\n── 3.4 非法狀態跳轉 ──")
def test_illegal_draft_to_pickup():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R3-ILLEGAL1', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    try:
        call('community.parcel', 'action_pickup', [[pid]])
        return False, "Should have raised error"
    except xmlrpc.client.Fault as e:
        return 'UserError' in str(e) or '已通知' in str(e) or '逾期' in str(e), f"Blocked: {str(e)[:100]}"
test("illegal_draft_to_pickup", test_illegal_draft_to_pickup)

def test_illegal_draft_to_return():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R3-ILLEGAL2', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    try:
        call('community.parcel', 'action_return', [[pid]])
        return False, "Should have raised error"
    except xmlrpc.client.Fault as e:
        return 'UserError' in str(e) or '已通知' in str(e), f"Blocked: {str(e)[:100]}"
test("illegal_draft_to_return", test_illegal_draft_to_return)

def test_illegal_draft_to_overdue():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R3-ILLEGAL3', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    try:
        call('community.parcel', 'action_overdue', [[pid]])
        return False, "Should have raised error"
    except xmlrpc.client.Fault as e:
        return e.faultCode == 2, f"Blocked: {str(e)[:100]}"
test("illegal_draft_to_overdue", test_illegal_draft_to_overdue)

def test_illegal_picked_to_notify():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R3-ILLEGAL4', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_pickup', [pid])
    try:
        call('community.parcel', 'action_notify', [[pid]])
        return False, "Should have raised error"
    except xmlrpc.client.Fault as e:
        return e.faultCode == 2, f"Blocked: {str(e)[:100]}"
test("illegal_picked_to_notify", test_illegal_picked_to_notify)

def test_illegal_returned_to_pickup():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R3-ILLEGAL5', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_return', [pid])
    try:
        call('community.parcel', 'action_pickup', [[pid]])
        return False, "Should have raised error"
    except xmlrpc.client.Fault as e:
        return e.faultCode == 2, f"Blocked: {str(e)[:100]}"
test("illegal_returned_to_pickup", test_illegal_returned_to_pickup)

# 3.5 重複條碼（同條碼多筆包裹）
print("\n── 3.5 重複條碼 ──")
def test_duplicate_barcode():
    pid1 = call('community.parcel', 'create', [{'barcode': 'TEST-R3-DUP', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    pid2 = call('community.parcel', 'create', [{'barcode': 'TEST-R3-DUP', 'resident_id': RES_ID, 'parcel_type': 'letter'}])
    ids = call('community.parcel', 'search', [[('barcode', '=', 'TEST-R3-DUP')]])
    return len(ids) >= 2 and pid1 != pid2, f"Created 2+ parcels with same barcode: count={len(ids)}"
test("duplicate_barcode_allowed", test_duplicate_barcode)

# 3.6 必填欄位遺漏 (resident_id 為必填)
print("\n── 3.6 必填欄位遺漏 ──")
def test_missing_resident():
    try:
        call('community.parcel', 'create', [{'barcode': 'TEST-R3-NORES', 'parcel_type': 'parcel'}])
        return False, "Should have raised error for missing resident_id"
    except xmlrpc.client.Fault as e:
        return True, f"Blocked: missing resident_id"
test("missing_required_resident_id", test_missing_resident)

# 3.7 Storage 非法跳轉
print("\n── 3.7 Storage 非法狀態跳轉 ──")
def test_storage_illegal_pending_to_ready():
    sid = call('community.storage', 'create', [{'depositor_id': RES_ID, 'item_description': 'TEST-R3 illegal'}])
    try:
        call('community.storage', 'action_ready', [[sid]])
        return False, "Should have raised error"
    except xmlrpc.client.Fault as e:
        return e.faultCode == 2, f"Blocked: {str(e)[:100]}"
test("storage_illegal_pending_to_ready", test_storage_illegal_pending_to_ready)

def test_storage_illegal_pending_to_done():
    sid = call('community.storage', 'create', [{'depositor_id': RES_ID, 'item_description': 'TEST-R3 illegal2'}])
    try:
        call('community.storage', 'action_done', [[sid]])
        return False, "Should have raised error"
    except xmlrpc.client.Fault as e:
        return e.faultCode == 2, f"Blocked: {str(e)[:100]}"
test("storage_illegal_pending_to_done", test_storage_illegal_pending_to_done)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 3 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_03_results.json', 'w') as fh:
    json.dump({'round': 3, 'title': '邊界條件與異常', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
