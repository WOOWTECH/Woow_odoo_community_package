#!/usr/bin/env python3
"""Round 5: Wizard 快速登記測試"""
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
off_ids = call('community.office', 'search', [[]], {'limit': 1})
OFF_ID = off_ids[0] if off_ids else None

print("=" * 70)
print("Round 5: Wizard 快速登記測試")
print("=" * 70)

# 5.1 基本登記流程
print("\n── 5.1 基本登記（自動通知）──")
def test_wizard_basic():
    before_count = call('community.parcel', 'search_count', [[]])
    wiz_id = call('parcel.quick.register', 'create', [{
        'resident_id': RES_ID,
        'barcode': 'TEST-R5-WIZ001',
        'parcel_type': 'parcel',
        'office_id': OFF_ID,
        'auto_notify': True,
    }])
    result = call('parcel.quick.register', 'action_register', [[wiz_id]])
    after_count = call('community.parcel', 'search_count', [[]])
    new_parcels = call('community.parcel', 'search_read', [[('barcode', '=', 'TEST-R5-WIZ001')]], {'fields': ['name', 'state']})
    if new_parcels:
        p = new_parcels[0]
        ok = after_count == before_count + 1 and p['state'] == 'notified'
        return ok, f"Created {p['name']}, state={p['state']} (auto_notify=True)"
    return False, "Parcel not created"
test("wizard_basic_with_auto_notify", test_wizard_basic)

# 5.2 不自動通知
print("\n── 5.2 不自動通知 ──")
def test_wizard_no_notify():
    wiz_id = call('parcel.quick.register', 'create', [{
        'resident_id': RES_ID,
        'barcode': 'TEST-R5-WIZ002',
        'parcel_type': 'letter',
        'office_id': OFF_ID,
        'auto_notify': False,
    }])
    call('parcel.quick.register', 'action_register', [[wiz_id]])
    p = call('community.parcel', 'search_read', [[('barcode', '=', 'TEST-R5-WIZ002')]], {'fields': ['state']})[0]
    return p['state'] == 'draft', f"state={p['state']} (auto_notify=False, stays draft)"
test("wizard_no_auto_notify_stays_draft", test_wizard_no_notify)

# 5.3 登記並繼續
print("\n── 5.3 登記並繼續 ──")
def test_wizard_register_and_new():
    wiz_id = call('parcel.quick.register', 'create', [{
        'resident_id': RES_ID,
        'barcode': 'TEST-R5-WIZ003',
        'parcel_type': 'registered',
        'office_id': OFF_ID,
        'auto_notify': True,
    }])
    result = call('parcel.quick.register', 'action_register_and_new', [[wiz_id]])
    p = call('community.parcel', 'search_read', [[('barcode', '=', 'TEST-R5-WIZ003')]], {'fields': ['name', 'state']})
    ok = len(p) == 1 and result and isinstance(result, dict)
    return ok, f"Created parcel, returned action type={result.get('type', 'N/A') if isinstance(result, dict) else 'N/A'}"
test("wizard_register_and_new", test_wizard_register_and_new)

# 5.4 必填欄位驗證
print("\n── 5.4 必填欄位驗證 ──")
def test_wizard_missing_resident():
    try:
        wiz_id = call('parcel.quick.register', 'create', [{
            'barcode': 'TEST-R5-NORES',
            'parcel_type': 'parcel',
        }])
        return False, "Should have raised error for missing resident_id"
    except xmlrpc.client.Fault as e:
        return True, "Blocked: missing required field resident_id"
test("wizard_missing_resident_id", test_wizard_missing_resident)

# 5.5 多種包裹類型透過 Wizard
print("\n── 5.5 各類型 Wizard 登記 ──")
for ptype in ['parcel', 'letter', 'registered', 'other']:
    def test_wiz_type(pt=ptype):
        wiz_id = call('parcel.quick.register', 'create', [{
            'resident_id': RES_ID,
            'barcode': f'TEST-R5-TYPE-{pt.upper()}',
            'parcel_type': pt,
            'office_id': OFF_ID,
            'auto_notify': False,
        }])
        call('parcel.quick.register', 'action_register', [[wiz_id]])
        p = call('community.parcel', 'search_read', [[('barcode', '=', f'TEST-R5-TYPE-{pt.upper()}')]], {'fields': ['parcel_type']})
        return len(p) == 1 and p[0]['parcel_type'] == pt, f"type={pt} created OK"
    test(f"wizard_type_{ptype}", test_wiz_type)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 5 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_05_results.json', 'w') as fh:
    json.dump({'round': 5, 'title': 'Wizard 快速登記', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
