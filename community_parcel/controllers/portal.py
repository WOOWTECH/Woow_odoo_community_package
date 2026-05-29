from collections import OrderedDict

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.osv.expression import AND


class ParcelPortal(CustomerPortal):

    # ===================================================================
    # Parcels (login required)
    # ===================================================================

    @http.route('/my/parcels', type='http', auth='user', website=True)
    def portal_my_parcels(self, page=1, sortby=None, filterby=None,
                          search=None, search_in='name', **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids
        Parcel = request.env['community.parcel'].sudo()

        base_domain = [('unit_id', 'in', unit_ids)]

        # Sort
        searchbar_sortings = OrderedDict([
            ('date_desc', {'label': _('Newest'), 'order': 'received_date desc'}),
            ('date_asc', {'label': _('Oldest'), 'order': 'received_date asc'}),
        ])
        if not sortby:
            sortby = 'date_desc'
        order = searchbar_sortings[sortby]['order']

        # Filter
        searchbar_filters = OrderedDict([
            ('all', {'label': _('All'), 'domain': []}),
            ('notified', {'label': _('已通知'),
                          'domain': [('state', '=', 'notified')]}),
            ('overdue', {'label': _('逾期'),
                         'domain': [('state', '=', 'overdue')]}),
            ('picked_up', {'label': _('已取件'),
                           'domain': [('state', '=', 'picked_up')]}),
            ('returned', {'label': _('已退回'),
                          'domain': [('state', '=', 'returned')]}),
        ])
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        # Search
        searchbar_inputs = OrderedDict([
            ('name', {'input': 'name', 'label': _('編號')}),
            ('barcode', {'input': 'barcode', 'label': _('快遞條碼')}),
        ])
        search_domain = []
        if search and search_in:
            if search_in == 'name':
                search_domain = [('name', 'ilike', search)]
            elif search_in == 'barcode':
                search_domain = [('barcode', 'ilike', search)]

        domain = AND([
            base_domain,
            searchbar_filters[filterby]['domain'],
            search_domain,
        ])

        # Count + pager
        count = Parcel.search_count(domain)
        pager = portal_pager(
            url='/my/parcels',
            url_args={'sortby': sortby, 'filterby': filterby,
                      'search_in': search_in, 'search': search},
            total=count,
            page=page,
            step=10,
        )

        parcels = Parcel.search(
            domain, order=order, limit=10, offset=pager['offset']
        )

        return request.render(
            'community_parcel.portal_my_parcels',
            {
                'parcels': parcels,
                'page_name': 'parcels',
                'pager': pager,
                'default_url': '/my/parcels',
                'searchbar_sortings': searchbar_sortings,
                'sortby': sortby,
                'searchbar_filters': searchbar_filters,
                'filterby': filterby,
                'searchbar_inputs': searchbar_inputs,
                'search_in': search_in,
                'search': search,
            },
        )

    @http.route('/my/parcels/<int:parcel_id>', type='http',
                auth='user', website=True)
    def portal_parcel_detail(self, parcel_id, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        parcel = request.env['community.parcel'].sudo().browse(parcel_id)
        if not parcel.exists() or parcel.unit_id.id not in unit_ids:
            return request.redirect('/my/parcels')

        if partner.id not in parcel.unit_id.resident_ids.ids:
            return request.redirect('/my/parcels')

        # Prev/Next
        all_ids = request.env['community.parcel'].sudo().search(
            [('unit_id', 'in', unit_ids)], order='received_date desc'
        ).ids
        idx = all_ids.index(parcel.id) if parcel.id in all_ids else -1
        prev_record = '/my/parcels/%d' % all_ids[idx - 1] if idx > 0 else None
        next_record = (
            '/my/parcels/%d' % all_ids[idx + 1]
            if 0 <= idx < len(all_ids) - 1 else None
        )

        return request.render(
            'community_parcel.portal_parcel_detail',
            {
                'parcel': parcel,
                'page_name': 'parcel_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    @http.route('/my/parcels/<int:parcel_id>/pickup', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def portal_parcel_pickup(self, parcel_id, **kwargs):
        partner = request.env.user.partner_id
        parcel = request.env['community.parcel'].sudo().browse(parcel_id)

        if not parcel.exists() or partner.id not in parcel.unit_id.resident_ids.ids:
            return request.redirect('/my/parcels')

        if parcel.state in ('notified', 'overdue'):
            try:
                parcel.action_pickup()
            except Exception:
                pass

        return request.redirect('/my/parcels/%d' % parcel_id)

    # ===================================================================
    # Storage (login required)
    # ===================================================================

    @http.route('/my/storage', type='http', auth='user', website=True)
    def portal_my_storage(self, page=1, sortby=None, filterby=None,
                          search=None, search_in='name', **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids
        Storage = request.env['community.storage'].sudo()

        base_domain = [('unit_id', 'in', unit_ids)]

        # Sort
        searchbar_sortings = OrderedDict([
            ('date_desc', {'label': _('Newest'), 'order': 'deposit_date desc'}),
            ('date_asc', {'label': _('Oldest'), 'order': 'deposit_date asc'}),
        ])
        if not sortby:
            sortby = 'date_desc'
        order = searchbar_sortings[sortby]['order']

        # Filter
        searchbar_filters = OrderedDict([
            ('all', {'label': _('All'), 'domain': []}),
            ('pending', {'label': _('待接收'),
                         'domain': [('state', '=', 'pending')]}),
            ('storing', {'label': _('保管中'),
                         'domain': [('state', '=', 'storing')]}),
            ('ready', {'label': _('待取件'),
                       'domain': [('state', '=', 'ready')]}),
            ('done', {'label': _('已完成'),
                      'domain': [('state', '=', 'done')]}),
        ])
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        # Search
        searchbar_inputs = OrderedDict([
            ('name', {'input': 'name', 'label': _('編號')}),
            ('recipient', {'input': 'recipient', 'label': _('取件人')}),
        ])
        search_domain = []
        if search and search_in:
            if search_in == 'name':
                search_domain = [('name', 'ilike', search)]
            elif search_in == 'recipient':
                search_domain = [('recipient_name', 'ilike', search)]

        domain = AND([
            base_domain,
            searchbar_filters[filterby]['domain'],
            search_domain,
        ])

        # Count + pager
        count = Storage.search_count(domain)
        pager = portal_pager(
            url='/my/storage',
            url_args={'sortby': sortby, 'filterby': filterby,
                      'search_in': search_in, 'search': search},
            total=count,
            page=page,
            step=10,
        )

        storage_items = Storage.search(
            domain, order=order, limit=10, offset=pager['offset']
        )

        return request.render(
            'community_parcel.portal_my_storage',
            {
                'storage_items': storage_items,
                'page_name': 'storage',
                'pager': pager,
                'default_url': '/my/storage',
                'searchbar_sortings': searchbar_sortings,
                'sortby': sortby,
                'searchbar_filters': searchbar_filters,
                'filterby': filterby,
                'searchbar_inputs': searchbar_inputs,
                'search_in': search_in,
                'search': search,
            },
        )

    @http.route('/my/storage/<int:storage_id>', type='http',
                auth='user', website=True)
    def portal_storage_detail(self, storage_id, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        storage = request.env['community.storage'].sudo().browse(storage_id)
        if not storage.exists() or storage.unit_id.id not in unit_ids:
            return request.redirect('/my/storage')

        if partner.id not in storage.unit_id.resident_ids.ids:
            return request.redirect('/my/storage')

        # Prev/Next
        all_ids = request.env['community.storage'].sudo().search(
            [('unit_id', 'in', unit_ids)], order='deposit_date desc'
        ).ids
        idx = all_ids.index(storage.id) if storage.id in all_ids else -1
        prev_record = '/my/storage/%d' % all_ids[idx - 1] if idx > 0 else None
        next_record = (
            '/my/storage/%d' % all_ids[idx + 1]
            if 0 <= idx < len(all_ids) - 1 else None
        )

        return request.render(
            'community_parcel.portal_storage_detail',
            {
                'storage': storage,
                'page_name': 'storage_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    @http.route('/my/storage/new', type='http', auth='user', website=True)
    def portal_storage_new(self, **kwargs):
        partner = request.env.user.partner_id
        units = partner.unit_ids
        storage_types = request.env['community.storage.type'].sudo().search([])

        return request.render(
            'community_parcel.portal_storage_new',
            {
                'units': units,
                'storage_types': storage_types,
                'page_name': 'storage_new',
            },
        )

    @http.route('/my/storage/create', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def portal_storage_create(self, **kwargs):
        partner = request.env.user.partner_id

        unit_id = int(kwargs.get('unit_id', 0))
        unit = request.env['community.unit'].browse(unit_id)
        if not unit.exists() or partner.id not in unit.resident_ids.ids:
            return request.redirect('/my/storage')

        vals = {
            'unit_id': unit_id,
            'recipient_name': kwargs.get('recipient_name', ''),
            'item_description': kwargs.get('item_description', ''),
            'expected_pickup': kwargs.get('expected_pickup') or False,
        }

        type_id = int(kwargs.get('type_id', 0))
        if type_id:
            vals['type_id'] = type_id

        storage = request.env['community.storage'].sudo().create(vals)
        return request.redirect('/my/storage/%d' % storage.id)

    @http.route('/my/storage/<int:storage_id>/pickup', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def portal_storage_pickup(self, storage_id, **kwargs):
        partner = request.env.user.partner_id
        storage = request.env['community.storage'].sudo().browse(storage_id)

        if not storage.exists() or partner.id not in storage.unit_id.resident_ids.ids:
            return request.redirect('/my/storage')

        if storage.state == 'ready':
            try:
                storage.action_done()
            except Exception:
                pass

        return request.redirect('/my/storage/%d' % storage_id)
