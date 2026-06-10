from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class ParcelPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        if 'parcel_count' in counters:
            values['parcel_count'] = request.env[
                'community.parcel'
            ].search_count([
                ('unit_id', 'in', unit_ids),
                ('state', 'in', ['draft', 'notified', 'overdue']),
            ])

        if 'storage_count' in counters:
            values['storage_count'] = request.env[
                'community.storage'
            ].search_count([
                ('unit_id', 'in', unit_ids),
                ('state', 'in', ['pending', 'storing', 'ready']),
            ])

        return values

    # --- Parcels ---

    @http.route(
        '/my/parcels',
        type='http',
        auth='user',
        website=True,
    )
    def portal_parcels(self, state=None, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        domain = [('unit_id', 'in', unit_ids)]
        valid_states = ('draft', 'notified', 'overdue', 'picked_up', 'returned', 'scrapped')
        if state and state in valid_states:
            domain.append(('state', '=', state))

        parcels = request.env['community.parcel'].search(
            domain, order='received_date desc', limit=100,
        )

        return request.render(
            'community_parcel.portal_parcels',
            {
                'parcels': parcels,
                'current_state': state,
                'page_name': 'parcels',
            },
        )

    @http.route(
        '/my/parcels/<int:parcel_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_parcel_detail(self, parcel_id, **kwargs):
        parcel = request.env['community.parcel'].browse(parcel_id)
        if not parcel.exists():
            return request.redirect('/my/parcels')

        # Security: check user belongs to parcel's unit
        partner = request.env.user.partner_id
        if parcel.unit_id.id not in partner.unit_ids.ids:
            return request.redirect('/my/parcels')

        return request.render(
            'community_parcel.portal_parcel_detail',
            {
                'parcel': parcel,
                'page_name': 'parcels',
            },
        )

    # --- Storage ---

    @http.route(
        '/my/storage',
        type='http',
        auth='user',
        website=True,
    )
    def portal_storage(self, state=None, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        domain = [('unit_id', 'in', unit_ids)]
        valid_states = ('pending', 'storing', 'ready', 'done', 'scrapped')
        if state and state in valid_states:
            domain.append(('state', '=', state))

        items = request.env['community.storage'].search(
            domain, order='deposit_date desc', limit=100,
        )

        return request.render(
            'community_parcel.portal_storage',
            {
                'items': items,
                'current_state': state,
                'page_name': 'storage',
            },
        )

    @http.route(
        '/my/storage/<int:storage_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_storage_detail(self, storage_id, **kwargs):
        item = request.env['community.storage'].browse(storage_id)
        if not item.exists():
            return request.redirect('/my/storage')

        # Security: check user belongs to storage's unit
        partner = request.env.user.partner_id
        if item.unit_id.id not in partner.unit_ids.ids:
            return request.redirect('/my/storage')

        return request.render(
            'community_parcel.portal_storage_detail',
            {
                'item': item,
                'page_name': 'storage',
            },
        )
