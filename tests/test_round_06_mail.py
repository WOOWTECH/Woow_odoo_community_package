#!/usr/bin/env python3
"""Round 6: Mail Template 通知測試"""
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
print("Round 6: Mail Template 通知測試")
print("=" * 70)

# 6.1 到件通知模板存在
print("\n── 6.1 到件通知模板 ──")
def test_arrival_template_exists():
    tpl = call('ir.model.data', 'search_read',
        [[('module', '=', 'community_parcel'), ('name', '=', 'mail_template_parcel_arrival')]],
        {'fields': ['res_id']})
    if tpl:
        t = call('mail.template', 'read', [[tpl[0]['res_id']], ['name', 'subject', 'email_to', 'model_id']])[0]
        ok = '到件' in t['name'] and t['subject'] and t['email_to']
        return ok, f"name={t['name']}, subject={t['subject'][:40]}"
    return False, "Template not found"
test("arrival_template_exists", test_arrival_template_exists)

# 6.2 逾期提醒模板存在
print("\n── 6.2 逾期提醒模板 ──")
def test_overdue_template_exists():
    tpl = call('ir.model.data', 'search_read',
        [[('module', '=', 'community_parcel'), ('name', '=', 'mail_template_parcel_overdue')]],
        {'fields': ['res_id']})
    if tpl:
        t = call('mail.template', 'read', [[tpl[0]['res_id']], ['name', 'subject', 'email_to']])[0]
        ok = '逾期' in t['name'] and t['subject']
        return ok, f"name={t['name']}, subject={t['subject'][:40]}"
    return False, "Template not found"
test("overdue_template_exists", test_overdue_template_exists)

# 6.3 action_notify 觸發 mail.message
print("\n── 6.3 action_notify 觸發通知 ──")
def test_notify_creates_message():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid = call('community.parcel', 'create', [{
        'barcode': 'TEST-R6-NOTIFY',
        'resident_id': res_ids[0],
        'parcel_type': 'parcel',
    }])
    msgs_before = call('mail.message', 'search_count', [[('res_id', '=', pid), ('model', '=', 'community.parcel')]])
    call_action('community.parcel', 'action_notify', [pid])
    msgs_after = call('mail.message', 'search_count', [[('res_id', '=', pid), ('model', '=', 'community.parcel')]])
    d = call('community.parcel', 'read', [[pid], ['state', 'notified_date']])[0]
    new_msgs = msgs_after - msgs_before
    ok = d['state'] == 'notified' and new_msgs > 0
    return ok, f"state={d['state']}, new messages={new_msgs}"
test("action_notify_creates_message", test_notify_creates_message)

# 6.4 action_overdue 觸發 mail.message
print("\n── 6.4 action_overdue 觸發通知 ──")
def test_overdue_creates_message():
    res_ids = call('res.partner', 'search', [[('is_resident', '=', True)]], {'limit': 1})
    pid = call('community.parcel', 'create', [{
        'barcode': 'TEST-R6-OVERDUE',
        'resident_id': res_ids[0],
        'parcel_type': 'parcel',
    }])
    call_action('community.parcel', 'action_notify', [pid])
    msgs_before = call('mail.message', 'search_count', [[('res_id', '=', pid), ('model', '=', 'community.parcel')]])
    call_action('community.parcel', 'action_overdue', [pid])
    msgs_after = call('mail.message', 'search_count', [[('res_id', '=', pid), ('model', '=', 'community.parcel')]])
    d = call('community.parcel', 'read', [[pid], ['state']])[0]
    new_msgs = msgs_after - msgs_before
    ok = d['state'] == 'overdue' and new_msgs > 0
    return ok, f"state={d['state']}, new messages={new_msgs}"
test("action_overdue_creates_message", test_overdue_creates_message)

# 6.5 模板 body_html 包含必要欄位
print("\n── 6.5 模板內容驗證 ──")
def test_arrival_template_content():
    tpl = call('ir.model.data', 'search_read',
        [[('module', '=', 'community_parcel'), ('name', '=', 'mail_template_parcel_arrival')]],
        {'fields': ['res_id']})
    t = call('mail.template', 'read', [[tpl[0]['res_id']], ['body_html']])[0]
    body = t['body_html']
    checks = ['object.name', 'object.resident_id.name', 'object.barcode', 'object.parcel_type']
    found = [c for c in checks if c in body]
    return len(found) == len(checks), f"Template refs: {found}"
test("arrival_template_has_required_fields", test_arrival_template_content)

def test_overdue_template_content():
    tpl = call('ir.model.data', 'search_read',
        [[('module', '=', 'community_parcel'), ('name', '=', 'mail_template_parcel_overdue')]],
        {'fields': ['res_id']})
    t = call('mail.template', 'read', [[tpl[0]['res_id']], ['body_html']])[0]
    body = t['body_html']
    checks = ['object.name', 'object.notified_date']
    found = [c for c in checks if c in body]
    return len(found) == len(checks), f"Template refs: {found}"
test("overdue_template_has_required_fields", test_overdue_template_content)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 6 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_06_results.json', 'w') as fh:
    json.dump({'round': 6, 'title': 'Mail Template 通知', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
