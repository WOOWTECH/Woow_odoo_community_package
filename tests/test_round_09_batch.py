#!/usr/bin/env python3
"""Round 9: 批次操作與效能測試"""
import xmlrpc.client, json, sys, time

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
print("Round 9: 批次操作與效能測試")
print("=" * 70)

# 9.1 批次建立 50 筆包裹
print("\n── 9.1 批次建立 50 筆包裹 ──")
def test_batch_create_50():
    vals_list = [{'barcode': f'TEST-R9-BATCH-{i:03d}', 'resident_id': RES_ID, 'parcel_type': 'parcel'} for i in range(50)]
    t0 = time.time()
    ids = call('community.parcel', 'create', [vals_list])
    elapsed = time.time() - t0
    ok = len(ids) == 50
    return ok, f"Created {len(ids)} parcels in {elapsed:.2f}s ({elapsed/50*1000:.0f}ms/each)"
test("batch_create_50_parcels", test_batch_create_50)

# 9.2 批次狀態更新
print("\n── 9.2 批次狀態更新 ──")
def test_batch_notify():
    ids = call('community.parcel', 'search', [[('barcode', 'like', 'TEST-R9-BATCH-'), ('state', '=', 'draft')]], {'limit': 50})
    t0 = time.time()
    call_action('community.parcel', 'action_notify', ids)
    elapsed = time.time() - t0
    states = call('community.parcel', 'read', [ids, ['state']])
    notified = sum(1 for s in states if s['state'] == 'notified')
    return notified == len(ids), f"Notified {notified}/{len(ids)} in {elapsed:.2f}s"
test("batch_notify_50_parcels", test_batch_notify)

def test_batch_pickup():
    ids = call('community.parcel', 'search', [[('barcode', 'like', 'TEST-R9-BATCH-'), ('state', '=', 'notified')]], {'limit': 25})
    t0 = time.time()
    call_action('community.parcel', 'action_pickup', ids)
    elapsed = time.time() - t0
    states = call('community.parcel', 'read', [ids, ['state']])
    picked = sum(1 for s in states if s['state'] == 'picked_up')
    return picked == len(ids), f"Picked up {picked}/{len(ids)} in {elapsed:.2f}s"
test("batch_pickup_25_parcels", test_batch_pickup)

# 9.3 search_read 效能
print("\n── 9.3 search_read 效能 ──")
def test_search_read_performance():
    t0 = time.time()
    data = call('community.parcel', 'search_read', [[]], {'fields': ['name', 'barcode', 'state', 'resident_id', 'unit_address'], 'limit': 200})
    elapsed = time.time() - t0
    return len(data) > 0 and elapsed < 10, f"Fetched {len(data)} records in {elapsed:.2f}s"
test("search_read_all_parcels", test_search_read_performance)

def test_search_with_domain():
    t0 = time.time()
    data = call('community.parcel', 'search_read', [[('state', '=', 'notified')]], {'fields': ['name', 'barcode'], 'limit': 100})
    elapsed = time.time() - t0
    return elapsed < 5, f"Found {len(data)} notified parcels in {elapsed:.2f}s"
test("search_read_with_domain_filter", test_search_with_domain)

def test_search_count_performance():
    t0 = time.time()
    count = call('community.parcel', 'search_count', [[]])
    elapsed = time.time() - t0
    return count > 0 and elapsed < 2, f"Total parcels: {count} in {elapsed:.2f}s"
test("search_count_all", test_search_count_performance)

# 9.4 Storage 批次建立
print("\n── 9.4 Storage 批次建立 ──")
def test_storage_batch():
    vals_list = [{'depositor_id': RES_ID, 'item_description': f'TEST-R9-SBATCH-{i:03d}'} for i in range(20)]
    t0 = time.time()
    ids = call('community.storage', 'create', [vals_list])
    elapsed = time.time() - t0
    ok = len(ids) == 20
    return ok, f"Created {len(ids)} storage items in {elapsed:.2f}s"
test("batch_create_20_storage", test_storage_batch)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 9 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_09_results.json', 'w') as fh:
    json.dump({'round': 9, 'title': '批次操作與效能', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
