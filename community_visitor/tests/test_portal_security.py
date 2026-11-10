from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestCommunityVisitorPortalSecurity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.portal = self.env['res.users'].with_context(
            no_reset_password=True,
        ).create({
            'name': 'Community visitor portal security test',
            'login': 'community-visitor-portal-security@example.test',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.unit = self.env['community.unit'].create({
            'building': 'Security test',
            'floor': '1',
            'number': '2',
            'resident_ids': [(4, self.portal.partner_id.id)],
        })
        self.appointment = self.env['community.appointment'].create({
            'resident_id': self.portal.partner_id.id,
            'unit_id': self.unit.id,
            'visitor_name': 'Guest',
            'visitor_phone': '0912345678',
            'valid_from': fields.Datetime.now(),
            'valid_until': fields.Datetime.now() + timedelta(days=1),
        })

    def test_portal_can_read_but_cannot_create_or_change_appointments(self):
        model = self.env['community.appointment'].with_user(self.portal)
        self.assertTrue(self.appointment.with_user(self.portal).read(['name']))
        self.assertFalse(model.check_access_rights('create', raise_exception=False))
        self.assertFalse(model.check_access_rights('write', raise_exception=False))
        with self.assertRaises(AccessError):
            self.appointment.with_user(self.portal).write({'state': 'cancelled'})

    def test_portal_cannot_read_visit_notes_or_blacklist_details(self):
        visitor = self.env['community.visitor'].create({
            'name': 'Guest', 'phone': '0912345678', 'id_last4': '1234',
            'blacklisted': True, 'blacklist_reason': 'staff only',
        })
        purpose = self.env['community.visit.purpose'].create({'name': 'Visit'})
        visit = self.env['community.visit'].create({
            'visitor_id': visitor.id,
            'unit_id': self.unit.id,
            'purpose_id': purpose.id,
            'note': 'staff only',
        })
        self.assertTrue(visit.with_user(self.portal).read(['name']))
        self.assertTrue(visitor.with_user(self.portal).read(['name']))
        with self.assertRaises(AccessError):
            visit.with_user(self.portal).read(['note'])
        for field in ('id_last4', 'blacklisted', 'blacklist_reason', 'blacklist_date'):
            with self.assertRaises(AccessError):
                visitor.with_user(self.portal).read([field])

    def test_portal_badge_search_is_limited_to_own_unit(self):
        purpose = self.env['community.visit.purpose'].create({'name': 'Visit'})
        visitor = self.env['community.visitor'].create({
            'name': 'Badge guest', 'phone': '0912345679',
        })
        other_unit = self.env['community.unit'].create({
            'building': 'Security test', 'floor': '1', 'number': '99',
        })
        own_badge = self.env['community.visitor.badge'].create({'name': 'OWN'})
        other_badge = self.env['community.visitor.badge'].create({'name': 'OTHER'})
        for unit, badge in ((self.unit, own_badge), (other_unit, other_badge)):
            self.env['community.visit'].create({
                'visitor_id': visitor.id, 'unit_id': unit.id,
                'purpose_id': purpose.id, 'badge_id': badge.id,
            })
        badges = self.env['community.visitor.badge'].with_user(self.portal)
        self.assertIn(own_badge.id, badges.search([]).ids)
        self.assertNotIn(other_badge.id, badges.search([]).ids)

    def test_unrelated_login_cannot_be_attributed_as_confirming_resident(self):
        outsider = self.env['res.partner'].create({'name': 'Outsider'})
        purpose = self.env['community.visit.purpose'].create({'name': 'Visit'})
        visitor = self.env['community.visitor'].create({
            'name': 'Confirmation guest', 'phone': '0912345680',
        })
        for action in ('action_confirm', 'action_reject'):
            visit = self.env['community.visit'].create({
                'visitor_id': visitor.id, 'unit_id': self.unit.id,
                'purpose_id': purpose.id, 'state': 'pending_confirm',
                'confirm_token': 'test-token-' + action,
                'token_expiry': fields.Datetime.now() + timedelta(minutes=20),
            })
            getattr(visit, action)(visit.confirm_token, partner=outsider)
            self.assertFalse(visit.resident_id)
