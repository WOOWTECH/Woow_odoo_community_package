from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class ParcelPortal(CustomerPortal):
    """Portal pages for parcel receiving and storage deposit management."""

    # ── Portal Home Counters ──────────────────────────────────

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        unit_ids = request.env['community.unit'].sudo().search([
            ('resident_ids', 'in', [partner.id]),
        ]).ids

        if 'parcel_count' in counters:
            values['parcel_count'] = request.env['community.parcel'].sudo().search_count([
                ('unit_id', 'in', unit_ids),
                ('state', 'in', ['notified', 'overdue']),
            ]) if unit_ids else 0

        if 'storage_count' in counters:
            values['storage_count'] = request.env['community.storage'].sudo().search_count([
                ('unit_id', 'in', unit_ids),
                ('state', 'in', ['storing', 'ready']),
            ]) if unit_ids else 0

        return values

    # ── Parcel List ───────────────────────────────────────────

    @http.route('/my/parcels', type='http', auth='user', website=True)
    def portal_parcels(self, **kw):
        partner = request.env.user.partner_id
        unit_ids = request.env['community.unit'].sudo().search([
            ('resident_ids', 'in', [partner.id]),
        ]).ids

        parcels = request.env['community.parcel'].sudo().search(
            [('unit_id', 'in', unit_ids)],
            order='received_date desc',
            limit=100,
        ) if unit_ids else request.env['community.parcel']

        return request.render('community_parcel.portal_parcels', {
            'parcels': parcels,
            'page_name': 'parcels',
        })

    # ── Parcel Detail ─────────────────────────────────────────

    @http.route('/my/parcels/<int:parcel_id>', type='http', auth='user', website=True)
    def portal_parcel_detail(self, parcel_id, **kw):
        partner = request.env.user.partner_id
        unit_ids = request.env['community.unit'].sudo().search([
            ('resident_ids', 'in', [partner.id]),
        ]).ids

        parcel = request.env['community.parcel'].sudo().search([
            ('id', '=', parcel_id),
            ('unit_id', 'in', unit_ids),
        ], limit=1)

        if not parcel:
            return request.redirect('/my/parcels')

        return request.render('community_parcel.portal_parcel_detail', {
            'parcel': parcel,
            'page_name': 'parcel_detail',
        })

    # ── Storage List ──────────────────────────────────────────

    @http.route('/my/storage', type='http', auth='user', website=True)
    def portal_storage(self, **kw):
        partner = request.env.user.partner_id
        unit_ids = request.env['community.unit'].sudo().search([
            ('resident_ids', 'in', [partner.id]),
        ]).ids

        items = request.env['community.storage'].sudo().search(
            [('unit_id', 'in', unit_ids)],
            order='deposit_date desc',
            limit=100,
        ) if unit_ids else request.env['community.storage']

        return request.render('community_parcel.portal_storage', {
            'items': items,
            'page_name': 'storage',
        })

    # ── Storage Detail ────────────────────────────────────────

    @http.route('/my/storage/<int:storage_id>', type='http', auth='user', website=True)
    def portal_storage_detail(self, storage_id, **kw):
        partner = request.env.user.partner_id
        unit_ids = request.env['community.unit'].sudo().search([
            ('resident_ids', 'in', [partner.id]),
        ]).ids

        item = request.env['community.storage'].sudo().search([
            ('id', '=', storage_id),
            ('unit_id', 'in', unit_ids),
        ], limit=1)

        if not item:
            return request.redirect('/my/storage')

        return request.render('community_parcel.portal_storage_detail', {
            'item': item,
            'page_name': 'storage_detail',
        })
