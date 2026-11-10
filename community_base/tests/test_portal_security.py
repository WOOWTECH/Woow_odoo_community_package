from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestCommunityBasePortalSecurity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.portal = self.env['res.users'].with_context(
            no_reset_password=True,
        ).create({
            'name': 'Community portal security test',
            'login': 'community-base-portal-security@example.test',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.office = self.env['community.office'].create({
            'name': 'Security test office',
            'internal_note': 'staff only',
        })
        self.unit = self.env['community.unit'].create({
            'building': 'Security test',
            'floor': '1',
            'number': '1',
            'office_id': self.office.id,
            'resident_ids': [(4, self.portal.partner_id.id)],
            'internal_note': 'staff only',
        })

    def test_portal_cannot_create_feedback_via_orm(self):
        self.assertFalse(
            self.env['community.feedback'].with_user(self.portal)
            .check_access_rights('create', raise_exception=False)
        )

    def test_portal_cannot_read_office_or_unit_notes(self):
        self.assertTrue(self.office.with_user(self.portal).exists())
        self.assertTrue(self.unit.with_user(self.portal).exists())
        for record in (self.office, self.unit):
            with self.assertRaises(AccessError):
                record.with_user(self.portal).read(['internal_note'])
