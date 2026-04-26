#!/usr/bin/env python3
"""Round 10: 前端 HTTP 端點與 View 渲染測試"""
import xmlrpc.client, json, sys, re, requests

URL = 'http://localhost:9098'
DB = 'odoocommunitypackage'
results = []

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
print("Round 10: 前端 HTTP 端點與 View 渲染測試")
print("=" * 70)

# Create a session with login
session = requests.Session()

# 10.1 /web/login 可達
print("\n── 10.1 HTTP 端點可達性 ──")
def test_login_page():
    r = session.get(f'{URL}/web/login', timeout=10)
    ok = r.status_code == 200 and 'oe_login_form' in r.text
    return ok, f"status={r.status_code}, has login form={'oe_login_form' in r.text}"
test("web_login_reachable", test_login_page)

# 10.2 Login (requires CSRF token from login page)
def test_login():
    # First get the login page to extract CSRF token
    login_page = session.get(f'{URL}/web/login', timeout=10)
    csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page.text)
    csrf_token = csrf_match.group(1) if csrf_match else ''
    r = session.post(f'{URL}/web/login', data={
        'login': 'admin',
        'password': 'admin',
        'db': DB,
        'redirect': '/web',
        'csrf_token': csrf_token,
    }, allow_redirects=True, timeout=10)
    ok = r.status_code == 200 and ('web_client' in r.text or 'o_main_navbar' in r.text or '/web#' in r.url or r.url.endswith('/web'))
    return ok, f"status={r.status_code}, url={r.url[:60]}, csrf={'found' if csrf_token else 'missing'}"
test("web_login_success", test_login)

# 10.3 /web 可進入
def test_web_access():
    r = session.get(f'{URL}/web', timeout=10)
    ok = r.status_code == 200
    return ok, f"status={r.status_code}, url={r.url[:60]}"
test("web_main_accessible", test_web_access)

# 10.4 XML-RPC 驗證 view 存在
print("\n── 10.2 View XML 結構驗證 ──")
common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common.authenticate(DB, 'admin', 'admin', {})
mdls = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', allow_none=True)

def rpc(model, method, *args, **kwargs):
    return mdls.execute_kw(DB, uid, 'admin', model, method, *args, **kwargs)

# Check all views exist via ir.model.data
views_to_check = [
    ('community_parcel', 'community_parcel_view_form', 'Parcel Form'),
    ('community_parcel', 'community_parcel_view_tree', 'Parcel List'),
    ('community_parcel', 'community_parcel_view_kanban', 'Parcel Kanban'),
    ('community_parcel', 'community_parcel_view_search', 'Parcel Search'),
    ('community_parcel', 'community_storage_view_form', 'Storage Form'),
    ('community_parcel', 'community_storage_view_tree', 'Storage List'),
    ('community_parcel', 'community_storage_view_kanban', 'Storage Kanban'),
    ('community_parcel', 'community_storage_view_search', 'Storage Search'),
    ('community_base', 'view_community_office_form', 'Office Form'),
    ('community_base', 'view_community_office_list', 'Office List'),
]

for module, xml_id, label in views_to_check:
    def test_view(m=module, x=xml_id, l=label):
        rec = rpc('ir.model.data', 'search_read', [[('module', '=', m), ('name', '=', x)]], {'fields': ['res_id']})
        if rec:
            view = rpc('ir.ui.view', 'read', [[rec[0]['res_id']], ['name', 'model', 'type']])[0]
            return True, f"{l}: model={view['model']}, type={view['type']}"
        return False, f"{l}: XML ID {m}.{x} not found"
    test(f"view_exists_{xml_id}", test_view)

# 10.5 Action 載入
print("\n── 10.3 Actions 載入 ──")
actions_to_check = [
    ('community_parcel', 'action_community_parcel', 'All Parcels'),
    ('community_parcel', 'action_community_storage', 'All Storage'),
    ('community_base', 'action_community_office', 'Offices'),
]

for module, xml_id, label in actions_to_check:
    def test_action(m=module, x=xml_id, l=label):
        rec = rpc('ir.model.data', 'search_read', [[('module', '=', m), ('name', '=', x)]], {'fields': ['res_id']})
        if rec:
            action = rpc('ir.actions.act_window', 'read', [[rec[0]['res_id']], ['name', 'res_model', 'view_mode']])[0]
            return True, f"{l}: model={action['res_model']}, modes={action['view_mode']}"
        return False, f"{l}: Action {m}.{x} not found"
    test(f"action_exists_{xml_id}", test_action)

# 10.6 Dashboard actions
print("\n── 10.4 Dashboard Actions ──")
dashboard_actions = [
    ('community_parcel', 'action_parcel_today', 'Today Parcels'),
    ('community_parcel', 'action_parcel_uncollected', 'Uncollected'),
    ('community_parcel', 'action_parcel_overdue', 'Overdue'),
]
for module, xml_id, label in dashboard_actions:
    def test_dash(m=module, x=xml_id, l=label):
        rec = rpc('ir.model.data', 'search_read', [[('module', '=', m), ('name', '=', x)]], {'fields': ['res_id']})
        if rec:
            return True, f"{l}: found (res_id={rec[0]['res_id']})"
        return False, f"{l}: not found"
    test(f"dashboard_{xml_id}", test_dash)

# 10.7 Menu items exist
print("\n── 10.5 Menu Items ──")
def test_root_menu():
    menus = rpc('ir.ui.menu', 'search_read', [[('name', 'ilike', '社區包裹管理')]], {'fields': ['name', 'complete_name']})
    return len(menus) > 0, f"Found {len(menus)} menu items"
test("root_menu_exists", test_root_menu)

# ── Summary ──
print("\n" + "=" * 70)
p = sum(1 for r in results if r['status'] == 'PASS')
f = sum(1 for r in results if r['status'] == 'FAIL')
print(f"Round 10 結果: {p} PASS / {f} FAIL / {len(results)} Total")
print("=" * 70)
with open('/var/tmp/vibe-kanban/worktrees/803d-woow-odoo-commun/Woow_odoo_community_package/tests/round_10_results.json', 'w') as fh:
    json.dump({'round': 10, 'title': '前端 HTTP 端點', 'results': results, 'summary': {'pass': p, 'fail': f, 'total': len(results)}}, fh, ensure_ascii=False, indent=2)
sys.exit(0 if f == 0 else 1)
