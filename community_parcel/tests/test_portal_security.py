from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestCommunityParcelPortalSecurity(TransactionCase):

    def test_portal_cannot_read_parcel_or_storage_notes(self):
        portal = self.env['res.users'].with_context(
            no_reset_password=True,
        ).create({
            'name': 'Community parcel portal security test',
            'login': 'community-parcel-portal-security@example.test',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        unit = self.env['community.unit'].create({
            'building': 'Security test',
            'floor': '1',
            'number': '3',
            'resident_ids': [(4, portal.partner_id.id)],
        })
        records = (
            self.env['community.parcel'].create({
                'unit_id': unit.id, 'internal_note': 'staff only',
            }),
            self.env['community.storage'].create({
                'unit_id': unit.id, 'internal_note': 'staff only',
            }),
        )
        for record in records:
            self.assertTrue(record.with_user(portal).read(['name']))
            with self.assertRaises(AccessError):
                record.with_user(portal).read(['internal_note'])
