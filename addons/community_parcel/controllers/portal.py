from odoo import fields, http, _
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


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
        ['/my/parcels', '/my/parcels/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_parcels(self, page=1, sortby=None, filterby=None, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids
        domain = [('unit_id', 'in', unit_ids)]

        searchbar_sortings = {
            'date_desc': {'label': _('Newest First'), 'order': 'received_date desc, id desc'},
            'date_asc': {'label': _('Oldest First'), 'order': 'received_date asc, id asc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'draft': {'label': _('Pending Notify'), 'domain': [('state', '=', 'draft')]},
            'notified': {'label': _('Notified'), 'domain': [('state', '=', 'notified')]},
            'returned': {'label': _('Returned'), 'domain': [('state', '=', 'returned')]},
            'scrapped': {'label': _('Scrapped'), 'domain': [('state', '=', 'scrapped')]},
            'picked_up': {'label': _('Picked Up'), 'domain': [('state', '=', 'picked_up')]},
            'overdue': {'label': _('Overdue'), 'domain': [('state', '=', 'overdue')]},
        }

        if not sortby or sortby not in searchbar_sortings:
            sortby = 'date_desc'
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        sort_order = searchbar_sortings[sortby]['order']
        search_domain = domain + searchbar_filters[filterby]['domain']

        total_count = request.env['community.parcel'].search_count(search_domain)
        pager = portal_pager(
            url='/my/parcels',
            total=total_count,
            page=int(page),
            step=20,
            url_args={'sortby': sortby, 'filterby': filterby},
        )

        parcels = request.env['community.parcel'].search(
            search_domain,
            order=sort_order,
            limit=20,
            offset=pager['offset'],
        )

        return request.render(
            'community_parcel.portal_parcels',
            {
                'parcels': parcels,
                'page_name': 'parcels',
                'default_url': '/my/parcels',
                'pager': pager,
                'searchbar_sortings': searchbar_sortings,
                'searchbar_filters': searchbar_filters,
                'sortby': sortby,
                'filterby': filterby,
            },
        )

    @http.route(
        '/my/parcels/<int:parcel_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_parcel_detail(self, parcel_id, **kwargs):
        partner = request.env.user.partner_id
        parcel = request.env['community.parcel'].search([
            ('id', '=', parcel_id),
            ('unit_id', 'in', partner.unit_ids.ids),
        ], limit=1)
        if not parcel:
            return request.redirect('/my/parcels')

        # prev/next navigation
        all_parcels = request.env['community.parcel'].search(
            [('unit_id', 'in', partner.unit_ids.ids)],
            order='received_date desc, id desc',
        )
        p_ids = all_parcels.ids
        idx = p_ids.index(parcel.id) if parcel.id in p_ids else -1
        prev_record = f'/my/parcels/{p_ids[idx - 1]}' if idx > 0 else None
        next_record = f'/my/parcels/{p_ids[idx + 1]}' if 0 <= idx < len(p_ids) - 1 else None

        return request.render(
            'community_parcel.portal_parcel_detail',
            {
                'parcel': parcel,
                'page_name': 'parcel_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    # --- Storage ---

    @http.route(
        ['/my/storage', '/my/storage/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_storage(self, page=1, sortby=None, filterby=None, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids
        domain = [('unit_id', 'in', unit_ids)]

        searchbar_sortings = {
            'date_desc': {'label': _('Newest First'), 'order': 'deposit_date desc, id desc'},
            'date_asc': {'label': _('Oldest First'), 'order': 'deposit_date asc, id asc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'pending': {'label': _('Pending Receipt'), 'domain': [('state', '=', 'pending')]},
            'storing': {'label': _('In Storage'), 'domain': [('state', '=', 'storing')]},
            'ready': {'label': _('Ready for Pickup'), 'domain': [('state', '=', 'ready')]},
            'scrapped': {'label': _('Scrapped'), 'domain': [('state', '=', 'scrapped')]},
            'done': {'label': _('Completed'), 'domain': [('state', '=', 'done')]},
        }

        if not sortby or sortby not in searchbar_sortings:
            sortby = 'date_desc'
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        sort_order = searchbar_sortings[sortby]['order']
        search_domain = domain + searchbar_filters[filterby]['domain']

        total_count = request.env['community.storage'].search_count(search_domain)
        pager = portal_pager(
            url='/my/storage',
            total=total_count,
            page=int(page),
            step=20,
            url_args={'sortby': sortby, 'filterby': filterby},
        )

        items = request.env['community.storage'].search(
            search_domain,
            order=sort_order,
            limit=20,
            offset=pager['offset'],
        )

        return request.render(
            'community_parcel.portal_storage',
            {
                'items': items,
                'page_name': 'storage',
                'default_url': '/my/storage',
                'pager': pager,
                'searchbar_sortings': searchbar_sortings,
                'searchbar_filters': searchbar_filters,
                'sortby': sortby,
                'filterby': filterby,
            },
        )

    @http.route(
        '/my/storage/<int:storage_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_storage_detail(self, storage_id, **kwargs):
        partner = request.env.user.partner_id
        item = request.env['community.storage'].search([
            ('id', '=', storage_id),
            ('unit_id', 'in', partner.unit_ids.ids),
        ], limit=1)
        if not item:
            return request.redirect('/my/storage')

        # prev/next navigation
        all_items = request.env['community.storage'].search(
            [('unit_id', 'in', partner.unit_ids.ids)],
            order='deposit_date desc, id desc',
        )
        s_ids = all_items.ids
        idx = s_ids.index(item.id) if item.id in s_ids else -1
        prev_record = f'/my/storage/{s_ids[idx - 1]}' if idx > 0 else None
        next_record = f'/my/storage/{s_ids[idx + 1]}' if 0 <= idx < len(s_ids) - 1 else None

        return request.render(
            'community_parcel.portal_storage_detail',
            {
                'item': item,
                'page_name': 'storage_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    # --- Storage New / Create ---

    @http.route(
        '/my/storage/new',
        type='http',
        auth='user',
        website=True,
    )
    def portal_storage_new(self, **kwargs):
        partner = request.env.user.partner_id
        units = partner.unit_ids
        storage_types = request.env['community.storage.type'].search([])

        return request.render(
            'community_parcel.portal_storage_new',
            {
                'units': units,
                'storage_types': storage_types,
                'page_name': 'storage_new',
                'form_values': {},
                'error': False,
            },
        )

    @http.route(
        '/my/storage/create',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def portal_storage_create(self, **kwargs):
        partner = request.env.user.partner_id

        try:
            unit_id = int(kwargs.get('unit_id') or 0)
            type_id = int(kwargs.get('type_id') or 0)
            if unit_id not in partner.unit_ids.ids:
                raise UserError(_('Please select one of your units.'))
            storage_type = request.env['community.storage.type'].search(
                [('id', '=', type_id)], limit=1,
            )
            if type_id and not storage_type:
                raise UserError(_('Please select a valid storage type.'))
            description = kwargs.get('item_description', '').strip()
            if not description:
                raise UserError(_('Please describe the stored items.'))
            pickup = kwargs.get('expected_pickup', '').strip()
            pickup_date = fields.Date.to_date(pickup) if pickup else False
            vals = {
                'unit_id': unit_id,
                'type_id': storage_type.id or False,
                'item_description': description,
                'expected_pickup': pickup_date,
                'recipient_name': kwargs.get('recipient_name', '').strip(),
            }
            # Keep the existing narrowly scoped sudo create after ownership validation.
            # A failed create must roll back before rendering the form again.
            with request.env.cr.savepoint():
                item = request.env['community.storage'].sudo().create(vals)
        except (UserError, ValueError, TypeError) as exc:
            error = str(exc) if isinstance(exc, UserError) else _(
                'Please check the selected unit, storage type and pickup date.'
            )
            return request.render(
                'community_parcel.portal_storage_new',
                {
                    'error': error,
                    'units': partner.unit_ids,
                    'storage_types': request.env['community.storage.type'].search([]),
                    'page_name': 'storage_new',
                    'form_values': kwargs,
                },
            )

        return request.redirect(f'/my/storage/{item.id}')
