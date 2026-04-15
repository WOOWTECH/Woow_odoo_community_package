#!/usr/bin/env python3
"""Round 7: Cron 逾期排程測試"""
import xmlrpc.client, json, sys
from datetime import datetime, timedelta

URL = 'http://localhost:9097'
DB = 'odoocommunitypackage'
common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common.authenticate(DB, 'admin', 'admin', {})
models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', allow_none=True)
results = []

def call(model, method, *args, **kwargs):
    return models.execute_kw(DB, uid, 'admin', model, method, *args, **kwargs)

def call_action(model, method, ids):
    try:
        result = call(model, method, [ids])
        return result
    except xmlrpc.client.Fault as e:
        if 'cannot marshal None' in str(e) or 'OdooMars' in str(e):
            return True
        raise

def run_cron():
    """Trigger the overdue cron job via ir.cron method_direct_trigger."""
    cron_ids = call('ir.cron', 'search', [[('code', 'like', '_cron_check_overdue')]])
    if cron_ids:
        call_action('ir.cron', 'method_direct_trigger', cron_ids)
    else:
        raise RuntimeError("Cron job not found")

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
print("Round 7: Cron 逾期排程測試")
print("=" * 70)

# 7.1 Cron job 存在
print("\n── 7.1 Cron Job 存在性 ──")
def test_cron_exists():
    cron = call('ir.cron', 'search_read', [[('code', 'like', '_cron_check_overdue')]], {'fields': ['name', 'active', 'interval_number', 'interval_type']})
    if cron:
        c = cron[0]
        ok = c['active'] and c['interval_type'] == 'days'
        return ok, f"name={c['name']}, active={c['active']}, interval={c['interval_number']} {c['interval_type']}"
    return False, "Cron job not found"
test("cron_job_exists_and_active", test_cron_exists)

# 7.2 超過 7 天的包裹應被標記逾期
print("\n── 7.2 逾期標記測試 ──")
def test_cron_marks_overdue():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R7-OVERDUE2', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    old_date = (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S')
    call('community.parcel', 'write', [[pid], {'notified_date': old_date}])
    run_cron()
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    return d['state'] == 'overdue', f"state={d['state']} (should be overdue after 8 days)"
test("cron_marks_overdue_after_7_days", test_cron_marks_overdue)

# 7.3 未超過 7 天的不被標記
print("\n── 7.3 未逾期不標記 ──")
def test_cron_skips_recent():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R7-RECENT2', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    recent_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    call('community.parcel', 'write', [[pid], {'notified_date': recent_date}])
    run_cron()
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    return d['state'] == 'notified', f"state={d['state']} (should remain notified)"
test("cron_skips_within_7_days", test_cron_skips_recent)

# 7.4 已取件不受影響
print("\n── 7.4 已取件不受影響 ──")
def test_cron_skips_picked():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R7-PICKED2', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_pickup', [pid])
    old_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
    call('community.parcel', 'write', [[pid], {'notified_date': old_date}])
    run_cron()
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    return d['state'] == 'picked_up', f"state={d['state']} (should remain picked_up)"
test("cron_skips_picked_up_parcels", test_cron_skips_picked)

# 7.5 已退回不受影響
print("\n── 7.5 已退回不受影響 ──")
def test_cron_skips_returned():
    pid = call('community.parcel', 'create', [{'barcode': 'TEST-R7-RETURNED2', 'resident_id': RES_ID, 'parcel_type': 'parcel'}])
    call_action('community.parcel', 'action_notify', [pid])
    call_action('community.parcel', 'action_return', [pid])
    old_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
    call('community.parcel', 'write', [[pid], {'notified_date': old_date}])
    run_cron()
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    return d['state'] == 'returned', f"state={d['state']} (should remain returned)"
test("cron_skips_returned_parcels", test_cron_skips_returned)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 7 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_07_results.json', 'w') as fh:
    json.dump({'round': 7, 'title': 'Cron 逾期排程', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
