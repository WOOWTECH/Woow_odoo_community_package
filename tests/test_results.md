# Community Parcel Module - Enterprise Testing Report

**Module:** `community_parcel` (Odoo 18 CE)
**Date:** 2026-04-15
**Environment:** Podman container, Odoo 18 CE, PostgreSQL 16
**Endpoint:** `http://localhost:9098`
**Database:** `odoocommunitypackage`
**DB Container:** `odoo-communitypackage-db`
**Web Container:** `odoo-communitypackage-web`
**DB Credentials:** `odoocommunitypackage / odoocommunitypackage`

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Test Cases | **100** |
| Passed | **100** |
| Failed | **0** |
| Pass Rate | **100%** |
| Rounds | 10 |
| Testing Methods | XML-RPC API, HTTP/Session, Python `requests` |

All 100 test cases across 10 rounds passed successfully, covering API CRUD, state machine workflows, boundary conditions, security/permissions, wizard operations, mail notifications, cron scheduling, data integrity, batch performance, and frontend HTTP endpoints.

---

## Round-by-Round Results

### Round 1: API CRUD (20/20 PASS)

Basic Create/Read/Update/Delete operations for all 4 models via XML-RPC.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | partner_create_with_extension_fields | PASS | id=48, is_resident=True, unit_address=C棟-301 |
| 2 | partner_read_extension_fields | PASS | Found: TEST-R1-住戶B, unit=C棟-301 |
| 3 | partner_write_extension_fields | PASS | Updated unit_address=D棟-402 |
| 4 | partner_non_resident_default | PASS | is_resident=False |
| 5 | office_create | PASS | id=4, name=TEST-R1-管理室B, building=TEST大樓B |
| 6 | office_read | PASS | Found 1 records |
| 7 | office_write | PASS | Updated building_id=TEST大樓C |
| 8 | office_unlink | PASS | Deleted id=5 |
| 9 | parcel_create | PASS | id=10, name=PKL/0010, state=draft |
| 10 | parcel_create_letter_type | PASS | parcel_type=letter |
| 11 | parcel_create_registered_type | PASS | parcel_type=registered |
| 12 | parcel_create_other_type | PASS | parcel_type=other |
| 13 | parcel_read | PASS | Read barcode=TEST-R1-BC002, name=PKL/0010 |
| 14 | parcel_search_read | PASS | Found 6 TEST-R1 parcels |
| 15 | parcel_write | PASS | Updated note=Updated note v2 - Round 1 |
| 16 | parcel_unlink | PASS | Deleted id=14 |
| 17 | storage_create | PASS | id=7, name=STG/0007, state=pending |
| 18 | storage_read | PASS | Read: STG/0007, desc=TEST-R1 寄放測試物品B |
| 19 | storage_write | PASS | Updated location=C區後方 |
| 20 | storage_unlink | PASS | Deleted id=8 |

**Coverage:** `res.partner` (extension fields), `community.office`, `community.parcel` (4 types), `community.storage`

---

### Round 2: State Machine (5/5 PASS)

Complete workflow transitions for parcel and storage state machines.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | parcel_draft_notified_picked_up | PASS | state=picked_up, pickup_date set |
| 2 | parcel_draft_notified_overdue_picked_up | PASS | state=picked_up |
| 3 | parcel_draft_notified_returned | PASS | state=returned |
| 4 | parcel_draft_notified_overdue_returned | PASS | state=returned |
| 5 | storage_pending_storing_ready_done | PASS | state=done, actual_pickup set |

**Parcel flows verified:**
- `draft` -> `notified` -> `picked_up`
- `draft` -> `notified` -> `overdue` -> `picked_up`
- `draft` -> `notified` -> `returned`
- `draft` -> `notified` -> `overdue` -> `returned`

**Storage flow verified:**
- `pending` -> `storing` -> `ready` -> `done`

---

### Round 3: Boundary & Exception (12/12 PASS)

Edge cases, illegal state transitions, and input validation.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | empty_barcode_create | PASS | Created id=46, barcode=False |
| 2 | empty_note_create | PASS | Created, note=False |
| 3 | long_barcode_200_chars | PASS | barcode length=200 |
| 4 | illegal_draft_to_pickup | PASS | Blocked: UserError (faultCode=2) |
| 5 | illegal_draft_to_return | PASS | Blocked: UserError (faultCode=2) |
| 6 | illegal_draft_to_overdue | PASS | Blocked: UserError (faultCode=2) |
| 7 | illegal_picked_to_notify | PASS | Blocked: UserError (faultCode=2) |
| 8 | illegal_returned_to_pickup | PASS | Blocked: UserError (faultCode=2) |
| 9 | duplicate_barcode_allowed | PASS | Multiple parcels with same barcode allowed |
| 10 | missing_required_resident_id | PASS | Blocked: missing required field |
| 11 | storage_illegal_pending_to_ready | PASS | Blocked: UserError (faultCode=2) |
| 12 | storage_illegal_pending_to_done | PASS | Blocked: UserError (faultCode=2) |

**Key findings:**
- All 7 illegal state transitions properly blocked with Chinese UserError messages
- Barcode is optional (not required), supports up to 200+ characters
- Duplicate barcodes are allowed by design (no unique constraint)
- `resident_id` is properly required on parcel creation

---

### Round 4: Security & Permissions (9/9 PASS)

Role-based access control for 3 user types: no-group, staff, manager.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | no_group_cannot_read_parcel | PASS | Blocked: AccessError |
| 2 | no_group_cannot_create_parcel | PASS | Blocked: AccessError |
| 3 | staff_can_read_parcel | PASS | Staff can read: found 5 parcels |
| 4 | staff_can_create_parcel | PASS | Staff created parcel id=57 |
| 5 | staff_can_write_parcel | PASS | Staff can write: note updated |
| 6 | staff_cannot_delete_parcel | PASS | Blocked: Staff cannot delete |
| 7 | manager_full_crud | PASS | Manager full CRUD OK |
| 8 | staff_storage_read_write_create | PASS | Staff storage RWC OK |
| 9 | staff_cannot_delete_storage | PASS | Blocked: Staff cannot delete storage |

**Access matrix verified:**

| Role | Read | Create | Write | Delete |
|------|------|--------|-------|--------|
| No group | X | X | X | X |
| Staff | O | O | O | X |
| Manager | O | O | O | O |

---

### Round 5: Wizard Quick Register (8/8 PASS)

`community.parcel.quick.register` wizard functionality.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | wizard_basic_with_auto_notify | PASS | PKL created, state=notified |
| 2 | wizard_no_auto_notify_stays_draft | PASS | state=draft (auto_notify=False) |
| 3 | wizard_register_and_new | PASS | Returns ir.actions.act_window |
| 4 | wizard_missing_resident_id | PASS | Blocked: missing required field |
| 5 | wizard_type_parcel | PASS | type=parcel created OK |
| 6 | wizard_type_letter | PASS | type=letter created OK |
| 7 | wizard_type_registered | PASS | type=registered created OK |
| 8 | wizard_type_other | PASS | type=other created OK |

**Key findings:**
- `auto_notify=True` correctly transitions parcel to `notified` state
- `auto_notify=False` keeps parcel in `draft` state
- `register_and_new` returns a proper window action for continuous registration
- All 4 parcel types supported through wizard

---

### Round 6: Mail Template Notifications (6/6 PASS)

Email template existence, content validation, and message triggering.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | arrival_template_exists | PASS | name=包裹到件通知, subject includes object.name |
| 2 | overdue_template_exists | PASS | name=包裹逾期提醒, subject includes object.name |
| 3 | action_notify_creates_message | PASS | state=notified, 2 new messages |
| 4 | action_overdue_creates_message | PASS | state=overdue, 2 new messages |
| 5 | arrival_template_has_required_fields | PASS | Refs: object.name, resident_id.name, barcode, parcel_type |
| 6 | overdue_template_has_required_fields | PASS | Refs: object.name, notified_date |

**Templates verified:**
- `mail_template_parcel_arrival`: subject, email_to, body_html with required Jinja fields
- `mail_template_parcel_overdue`: subject, body_html with required Jinja fields
- Both `action_notify` and `action_overdue` create `mail.message` records in chatter

---

### Round 7: Cron Overdue Scheduling (5/5 PASS)

Automated overdue detection cron job testing.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | cron_job_exists_and_active | PASS | name=檢查逾期包裹, active=True, interval=1 days |
| 2 | cron_marks_overdue_after_7_days | PASS | state=overdue (8 days elapsed) |
| 3 | cron_skips_within_7_days | PASS | state=notified (3 days - not overdue) |
| 4 | cron_skips_picked_up_parcels | PASS | state=picked_up (terminal state) |
| 5 | cron_skips_returned_parcels | PASS | state=returned (terminal state) |

**Key findings:**
- Cron runs daily (`interval=1 days`)
- Correctly marks parcels overdue after 7-day threshold
- Respects terminal states (`picked_up`, `returned`) - does not overwrite them
- Does not false-positive on recently notified parcels

---

### Round 8: Data Integrity & Relations (9/9 PASS)

Related fields, sequences, Many2one integrity, computed fields, and chatter tracking.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | related_field_unit_address_sync | PASS | unit_address=E棟-501 synced from partner |
| 2 | sequence_continuity_pkl | PASS | PKL/0078 -> PKL/0079 (diff=1) |
| 3 | sequence_continuity_stg | PASS | STG/0018 -> STG/0019 (diff=1) |
| 4 | many2one_resident_integrity | PASS | resident_id correctly linked |
| 5 | many2one_office_integrity | PASS | office_id correctly linked |
| 6 | is_overdue_false_for_draft | PASS | is_overdue=False for draft |
| 7 | is_overdue_true_for_overdue_state | PASS | is_overdue=True for overdue |
| 8 | is_overdue_false_after_pickup | PASS | is_overdue=False for picked_up |
| 9 | state_change_tracked_in_chatter | PASS | Tracking messages found |

**Key findings:**
- `unit_address` related field syncs correctly from `res.partner`
- PKL and STG sequences are strictly consecutive (no gaps)
- Many2one relationships maintain referential integrity
- Computed field `is_overdue` correctly reflects state
- State changes are tracked in mail.message chatter

---

### Round 9: Batch Operations & Performance (7/7 PASS)

Bulk create, batch state transitions, and query performance benchmarks.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | batch_create_50_parcels | PASS | 50 parcels in 0.20s (4ms/each) |
| 2 | batch_notify_50_parcels | PASS | 50/50 notified in 0.84s |
| 3 | batch_pickup_25_parcels | PASS | 25/25 picked up in 0.16s |
| 4 | search_read_all_parcels | PASS | 180 records in 0.06s |
| 5 | search_read_with_domain_filter | PASS | 37 notified parcels in 0.03s |
| 6 | search_count_all | PASS | 180 total in 0.03s |
| 7 | batch_create_20_storage | PASS | 20 storage items in 0.12s |

**Performance benchmarks:**

| Operation | Volume | Time | Per-Record |
|-----------|--------|------|------------|
| Batch create (parcel) | 50 | 0.20s | 4ms |
| Batch notify | 50 | 0.84s | 17ms |
| Batch pickup | 25 | 0.16s | 6ms |
| search_read (all) | 180 | 0.06s | 0.3ms |
| search_read (filtered) | 37 | 0.03s | 0.8ms |
| search_count | 180 | 0.03s | - |
| Batch create (storage) | 20 | 0.12s | 6ms |

All operations well within acceptable performance thresholds for enterprise deployment.

---

### Round 10: Frontend HTTP & Views (20/20 PASS)

HTTP endpoints, login flow, view definitions, actions, and menu structure.

| # | Test | Result | Detail |
|---|------|--------|--------|
| 1 | web_login_reachable | PASS | status=200, login form present |
| 2 | web_login_success | PASS | status=200, redirect to /web, CSRF handled |
| 3 | web_main_accessible | PASS | status=200 |
| 4 | view_exists_community_parcel_view_form | PASS | type=form |
| 5 | view_exists_community_parcel_view_tree | PASS | type=list |
| 6 | view_exists_community_parcel_view_kanban | PASS | type=kanban |
| 7 | view_exists_community_parcel_view_search | PASS | type=search |
| 8 | view_exists_community_storage_view_form | PASS | type=form |
| 9 | view_exists_community_storage_view_tree | PASS | type=list |
| 10 | view_exists_community_storage_view_kanban | PASS | type=kanban |
| 11 | view_exists_community_storage_view_search | PASS | type=search |
| 12 | view_exists_community_office_view_form | PASS | type=form |
| 13 | view_exists_community_office_view_tree | PASS | type=list |
| 14 | action_exists_action_community_parcel | PASS | modes=list,kanban,form |
| 15 | action_exists_action_community_storage | PASS | modes=list,kanban,form |
| 16 | action_exists_action_community_office | PASS | modes=list,form |
| 17 | dashboard_action_parcel_today | PASS | Dashboard: Today Parcels |
| 18 | dashboard_action_parcel_uncollected | PASS | Dashboard: Uncollected |
| 19 | dashboard_action_parcel_overdue | PASS | Dashboard: Overdue |
| 20 | root_menu_exists | PASS | Root menu: 社區包裹管理 |

**View coverage:**
- 10 views (4 parcel + 4 storage + 2 office) across form, list, kanban, search types
- 3 main actions + 3 dashboard actions
- Root menu properly configured

---

## Test Coverage Matrix

| Dimension | Tests | Status |
|-----------|-------|--------|
| CRUD Operations | 20 | 100% |
| State Machine Flows | 5 | 100% |
| Boundary Conditions | 12 | 100% |
| Security & RBAC | 9 | 100% |
| Wizard Functionality | 8 | 100% |
| Mail Notifications | 6 | 100% |
| Cron Scheduling | 5 | 100% |
| Data Integrity | 9 | 100% |
| Batch & Performance | 7 | 100% |
| Frontend & Views | 20 | 100% |
| **Total** | **100** | **100%** |

## Models Tested

| Model | CRUD | State Machine | Security | Batch |
|-------|------|---------------|----------|-------|
| `res.partner` (extension) | O | - | - | - |
| `community.office` | O | - | - | - |
| `community.parcel` | O | O | O | O |
| `community.storage` | O | O | O | O |
| `community.parcel.quick.register` | - | - | - | - |

## Technical Notes

### XML-RPC Compatibility Patterns

1. **None return handling**: Odoo 18 action methods return `None`, but `OdooMarshaller(allow_none=False)` rejects it. Solution: catch `Fault` with 'cannot marshal None' and treat as success.

2. **UserError detection**: Odoo XML-RPC returns `Fault(faultCode=2, faultString='...')` for `UserError` - the string "UserError" is NOT present in the fault message.

3. **Private method restriction**: Methods starting with `_` cannot be called via XML-RPC (Fault 4). Use `ir.cron.method_direct_trigger` to invoke cron jobs.

4. **Batch create format**: `create([vals_list])` requires wrapping the list as a single positional argument.

5. **CSRF protection**: Odoo 18 enforces CSRF tokens on `/web/login` POST. Extract token from GET response before POSTing.

### Test Data

All test data remains in the database for future reference:
- Barcodes prefixed with `TEST-R{round}-` (e.g., `TEST-R1-BC001`, `TEST-R3-DUP`)
- Test users: `test_r4_nogroup@test.com`, `test_r4_staff@test.com`, `test_r4_manager@test.com`
- Partner emails: `test_r1_a@test.com`, `test_r8_sync@test.com`

### Files

| File | Description |
|------|-------------|
| `tests/test_round_01_crud.py` | API CRUD test script |
| `tests/test_round_02_state_machine.py` | State machine flow tests |
| `tests/test_round_03_edge_cases.py` | Boundary & exception tests |
| `tests/test_round_04_security.py` | Security & permission tests |
| `tests/test_round_05_wizard.py` | Wizard quick register tests |
| `tests/test_round_06_mail.py` | Mail template notification tests |
| `tests/test_round_07_cron.py` | Cron overdue scheduling tests |
| `tests/test_round_08_integrity.py` | Data integrity & relation tests |
| `tests/test_round_09_batch.py` | Batch operations & performance |
| `tests/test_round_10_http.py` | Frontend HTTP & view tests |
| `tests/round_01_results.json` | Round 1 JSON results |
| `tests/round_02_results.json` | Round 2 JSON results |
| `tests/round_03_results.json` | Round 3 JSON results |
| `tests/round_04_results.json` | Round 4 JSON results |
| `tests/round_05_results.json` | Round 5 JSON results |
| `tests/round_06_results.json` | Round 6 JSON results |
| `tests/round_07_results.json` | Round 7 JSON results |
| `tests/round_08_results.json` | Round 8 JSON results |
| `tests/round_09_results.json` | Round 9 JSON results |
| `tests/round_10_results.json` | Round 10 JSON results |
| `tests/test_results.md` | This consolidated report |
| `docs/plans/2026-04-15-enterprise-testing-prd.md` | Testing PRD |
