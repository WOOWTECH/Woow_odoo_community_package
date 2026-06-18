from odoo import http, _
from odoo.exceptions import UserError, ValidationError
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
            'date_desc': {'label': _('最新優先'), 'order': 'received_date desc'},
            'date_asc': {'label': _('最舊優先'), 'order': 'received_date asc'},
        }
        searchbar_filters = {
            'all': {'label': _('全部'), 'domain': []},
            'draft': {'label': _('待通知'), 'domain': [('state', '=', 'draft')]},
            'notified': {'label': _('已通知'), 'domain': [('state', '=', 'notified')]},
            'picked_up': {'label': _('已取件'), 'domain': [('state', '=', 'picked_up')]},
            'overdue': {'label': _('逾期'), 'domain': [('state', '=', 'overdue')]},
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
        parcel = request.env['community.parcel'].browse(parcel_id)
        if not parcel.exists():
            return request.redirect('/my/parcels')

        # Security: check user belongs to parcel's unit
        partner = request.env.user.partner_id
        if parcel.unit_id.id not in partner.unit_ids.ids:
            return request.redirect('/my/parcels')

        # prev/next navigation
        all_parcels = request.env['community.parcel'].search(
            [('unit_id', 'in', partner.unit_ids.ids)],
            order='received_date desc',
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
            'date_desc': {'label': _('最新優先'), 'order': 'deposit_date desc'},
            'date_asc': {'label': _('最舊優先'), 'order': 'deposit_date asc'},
        }
        searchbar_filters = {
            'all': {'label': _('全部'), 'domain': []},
            'pending': {'label': _('待接收'), 'domain': [('state', '=', 'pending')]},
            'storing': {'label': _('保管中'), 'domain': [('state', '=', 'storing')]},
            'ready': {'label': _('待取件'), 'domain': [('state', '=', 'ready')]},
            'done': {'label': _('已完成'), 'domain': [('state', '=', 'done')]},
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
        item = request.env['community.storage'].browse(storage_id)
        if not item.exists():
            return request.redirect('/my/storage')

        # Security: check user belongs to storage's unit
        partner = request.env.user.partner_id
        if item.unit_id.id not in partner.unit_ids.ids:
            return request.redirect('/my/storage')

        # prev/next navigation
        all_items = request.env['community.storage'].search(
            [('unit_id', 'in', partner.unit_ids.ids)],
            order='deposit_date desc',
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

        # Security: validate unit ownership
        unit_id = int(kwargs.get('unit_id', 0))
        unit = request.env['community.unit'].browse(unit_id)
        if not unit.exists() or partner.id not in unit.resident_ids.ids:
            return request.redirect('/my/storage')

        vals = {
            'unit_id': unit_id,
            'item_description': kwargs.get('item_description', ''),
        }

        # Optional: type_id
        type_id = int(kwargs.get('type_id', 0) or 0)
        if type_id and request.env['community.storage.type'].browse(type_id).exists():
            vals['type_id'] = type_id

        # Optional: expected_pickup
        expected_pickup = kwargs.get('expected_pickup', '').strip()
        if expected_pickup:
            vals['expected_pickup'] = expected_pickup

        try:
            item = request.env['community.storage'].sudo().create(vals)
        except (UserError, ValidationError) as e:
            storage_types = request.env['community.storage.type'].search([])
            return request.render(
                'community_parcel.portal_storage_new',
                {
                    'error': str(e),
                    'units': partner.unit_ids,
                    'storage_types': storage_types,
                    'page_name': 'storage_new',
                },
            )

        return request.redirect(f'/my/storage/{item.id}')
