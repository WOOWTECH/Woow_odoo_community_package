from collections import OrderedDict

from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.osv.expression import AND


class VisitorPortal(CustomerPortal):

    @staticmethod
    def _parse_time_to_float(value):
        """Convert 'HH:MM' time string or numeric value to float hours."""
        if not value:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).strip()
        if ':' in value:
            parts = value.split(':')
            return int(parts[0]) + int(parts[1]) / 60.0
        return float(value)

    # ===================================================================
    # Token-based confirmation (public, no login required)
    # ===================================================================

    @http.route(
        '/visitor/confirm/<string:token>',
        type='http', auth='public', website=True,
    )
    def visitor_confirm_page(self, token, **kwargs):
        visit = request.env['community.visit'].sudo().search([
            ('confirm_token', '=', token),
        ], limit=1)

        if not visit:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': '無效的確認連結。'},
            )

        if visit.state != 'pending_confirm':
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': '此訪問記錄已被處理。'},
            )

        if visit.token_expiry and fields.Datetime.now() > visit.token_expiry:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': '確認連結已過期。'},
            )

        return request.render(
            'community_visitor.portal_visitor_confirm_page',
            {'visit': visit, 'token': token},
        )

    @http.route(
        '/visitor/confirm/<string:token>/accept',
        type='http', auth='public', website=True,
        methods=['POST'], csrf=True,
    )
    def visitor_confirm_accept(self, token, **kwargs):
        visit = request.env['community.visit'].sudo().search([
            ('confirm_token', '=', token),
        ], limit=1)

        if not visit:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': '無效的確認連結。'},
            )

        try:
            partner = (
                request.env.user.partner_id
                if not request.env.user._is_public()
                else None
            )
            visit.action_confirm(token, partner=partner)
        except Exception as e:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': str(e)},
            )

        return request.render(
            'community_visitor.portal_visitor_confirm_result',
            {'visit': visit, 'result': 'confirmed'},
        )

    @http.route(
        '/visitor/confirm/<string:token>/reject',
        type='http', auth='public', website=True,
        methods=['POST'], csrf=True,
    )
    def visitor_confirm_reject(self, token, **kwargs):
        visit = request.env['community.visit'].sudo().search([
            ('confirm_token', '=', token),
        ], limit=1)

        if not visit:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': '無效的確認連結。'},
            )

        try:
            partner = (
                request.env.user.partner_id
                if not request.env.user._is_public()
                else None
            )
            visit.action_reject(token, partner=partner)
        except Exception as e:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': str(e)},
            )

        return request.render(
            'community_visitor.portal_visitor_confirm_result',
            {'visit': visit, 'result': 'rejected'},
        )

    # ===================================================================
    # Visitors (login required)
    # ===================================================================

    @http.route('/my/visitors', type='http', auth='user', website=True)
    def portal_my_visitors(self, page=1, sortby=None, filterby=None,
                           search=None, search_in='visitor', **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids
        Visit = request.env['community.visit']

        base_domain = [('unit_id', 'in', unit_ids)]

        # Sort
        searchbar_sortings = OrderedDict([
            ('date_desc', {'label': _('Newest'), 'order': 'create_date desc'}),
            ('date_asc', {'label': _('Oldest'), 'order': 'create_date asc'}),
        ])
        if not sortby:
            sortby = 'date_desc'
        order = searchbar_sortings[sortby]['order']

        # Filter
        searchbar_filters = OrderedDict([
            ('all', {'label': _('All'), 'domain': []}),
            ('pending', {'label': _('Pending Confirm'),
                         'domain': [('state', '=', 'pending_confirm')]}),
            ('confirmed', {'label': _('Confirmed'),
                           'domain': [('state', '=', 'confirmed')]}),
            ('checked_in', {'label': _('Checked In'),
                            'domain': [('state', '=', 'checked_in')]}),
        ])
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        # Search
        searchbar_inputs = OrderedDict([
            ('visitor', {'input': 'visitor', 'label': _('Visitor Name')}),
        ])
        search_domain = []
        if search and search_in:
            if search_in == 'visitor':
                search_domain = [('visitor_id.name', 'ilike', search)]

        domain = AND([
            base_domain,
            searchbar_filters[filterby]['domain'],
            search_domain,
        ])

        # Count + pager
        count = Visit.search_count(domain)
        pager = portal_pager(
            url='/my/visitors',
            url_args={'sortby': sortby, 'filterby': filterby,
                      'search_in': search_in, 'search': search},
            total=count,
            page=page,
            step=10,
        )

        visits = Visit.search(
            domain, order=order, limit=10, offset=pager['offset']
        )

        return request.render(
            'community_visitor.portal_my_visitors',
            {
                'visits': visits,
                'page_name': 'visitors',
                'pager': pager,
                'default_url': '/my/visitors',
                'searchbar_sortings': searchbar_sortings,
                'sortby': sortby,
                'searchbar_filters': searchbar_filters,
                'filterby': filterby,
                'searchbar_inputs': searchbar_inputs,
                'search_in': search_in,
                'search': search,
            },
        )

    @http.route('/my/visitors/<int:visit_id>', type='http',
                auth='user', website=True)
    def portal_visit_detail(self, visit_id, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        visit = request.env['community.visit'].browse(visit_id)
        if not visit.exists() or visit.unit_id.id not in unit_ids:
            return request.redirect('/my/visitors')

        if partner.id not in visit.unit_id.resident_ids.ids:
            return request.redirect('/my/visitors')

        # Prev/Next
        all_ids = request.env['community.visit'].search(
            [('unit_id', 'in', unit_ids)], order='create_date desc'
        ).ids
        idx = all_ids.index(visit.id) if visit.id in all_ids else -1
        prev_record = '/my/visitors/%d' % all_ids[idx - 1] if idx > 0 else None
        next_record = (
            '/my/visitors/%d' % all_ids[idx + 1]
            if 0 <= idx < len(all_ids) - 1 else None
        )

        return request.render(
            'community_visitor.portal_visit_detail',
            {
                'visit': visit,
                'page_name': 'visit_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    @http.route('/my/visitors/<int:visit_id>/confirm', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def portal_visit_confirm(self, visit_id, **kwargs):
        partner = request.env.user.partner_id
        visit = request.env['community.visit'].browse(visit_id)

        if not visit.exists() or partner.id not in visit.unit_id.resident_ids.ids:
            return request.redirect('/my/visitors')

        if visit.state == 'pending_confirm' and visit.confirm_token:
            try:
                visit.sudo().action_confirm(
                    visit.confirm_token, partner=partner
                )
            except Exception:
                pass

        return request.redirect('/my/visitors/%d' % visit_id)

    @http.route('/my/visitors/<int:visit_id>/reject', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def portal_visit_reject(self, visit_id, **kwargs):
        partner = request.env.user.partner_id
        visit = request.env['community.visit'].browse(visit_id)

        if not visit.exists() or partner.id not in visit.unit_id.resident_ids.ids:
            return request.redirect('/my/visitors')

        if visit.state == 'pending_confirm' and visit.confirm_token:
            try:
                visit.sudo().action_reject(
                    visit.confirm_token, partner=partner
                )
            except Exception:
                pass

        return request.redirect('/my/visitors/%d' % visit_id)

    # ===================================================================
    # Appointments (login required)
    # ===================================================================

    @http.route('/my/appointments', type='http', auth='user', website=True)
    def portal_my_appointments(self, page=1, sortby=None, filterby=None,
                               search=None, search_in='name', **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids
        Appointment = request.env['community.appointment']

        base_domain = [('unit_id', 'in', unit_ids)]

        # Sort
        searchbar_sortings = OrderedDict([
            ('date_desc', {'label': _('Newest'), 'order': 'create_date desc'}),
            ('date_asc', {'label': _('Oldest'), 'order': 'create_date asc'}),
        ])
        if not sortby:
            sortby = 'date_desc'
        order = searchbar_sortings[sortby]['order']

        # Filter
        searchbar_filters = OrderedDict([
            ('all', {'label': _('All'), 'domain': []}),
            ('active', {'label': _('Active'),
                        'domain': [('state', '=', 'active')]}),
            ('expired', {'label': _('Expired'),
                         'domain': [('state', '=', 'expired')]}),
            ('cancelled', {'label': _('Cancelled'),
                           'domain': [('state', '=', 'cancelled')]}),
        ])
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        # Search
        searchbar_inputs = OrderedDict([
            ('name', {'input': 'name', 'label': _('Reference Number')}),
            ('visitor', {'input': 'visitor', 'label': _('Visitor Name')}),
        ])
        search_domain = []
        if search and search_in:
            if search_in == 'name':
                search_domain = [('name', 'ilike', search)]
            elif search_in == 'visitor':
                search_domain = [('visitor_name', 'ilike', search)]

        domain = AND([
            base_domain,
            searchbar_filters[filterby]['domain'],
            search_domain,
        ])

        # Count + pager
        count = Appointment.search_count(domain)
        pager = portal_pager(
            url='/my/appointments',
            url_args={'sortby': sortby, 'filterby': filterby,
                      'search_in': search_in, 'search': search},
            total=count,
            page=page,
            step=10,
        )

        appointments = Appointment.search(
            domain, order=order, limit=10, offset=pager['offset']
        )

        return request.render(
            'community_visitor.portal_my_appointments',
            {
                'appointments': appointments,
                'page_name': 'appointments',
                'pager': pager,
                'default_url': '/my/appointments',
                'searchbar_sortings': searchbar_sortings,
                'sortby': sortby,
                'searchbar_filters': searchbar_filters,
                'filterby': filterby,
                'searchbar_inputs': searchbar_inputs,
                'search_in': search_in,
                'search': search,
            },
        )

    @http.route('/my/appointments/<int:appointment_id>', type='http',
                auth='user', website=True)
    def portal_appointment_detail(self, appointment_id, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        appointment = request.env['community.appointment'].browse(
            appointment_id
        )
        if not appointment.exists() or appointment.unit_id.id not in unit_ids:
            return request.redirect('/my/appointments')

        if partner.id not in appointment.unit_id.resident_ids.ids:
            return request.redirect('/my/appointments')

        # Prev/Next
        all_ids = request.env['community.appointment'].search(
            [('unit_id', 'in', unit_ids)], order='create_date desc'
        ).ids
        idx = all_ids.index(appointment.id) if appointment.id in all_ids else -1
        prev_record = '/my/appointments/%d' % all_ids[idx - 1] if idx > 0 else None
        next_record = (
            '/my/appointments/%d' % all_ids[idx + 1]
            if 0 <= idx < len(all_ids) - 1 else None
        )

        return request.render(
            'community_visitor.portal_appointment_detail',
            {
                'appointment': appointment,
                'page_name': 'appointment_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    @http.route('/my/appointments/new', type='http', auth='user', website=True)
    def portal_appointment_new(self, **kwargs):
        partner = request.env.user.partner_id
        units = partner.unit_ids

        return request.render(
            'community_visitor.portal_appointment_new',
            {
                'units': units,
                'page_name': 'appointment_new',
            },
        )

    @http.route('/my/appointments/create', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def portal_appointment_create(self, **kwargs):
        partner = request.env.user.partner_id

        unit_id = int(kwargs.get('unit_id', 0))
        unit = request.env['community.unit'].browse(unit_id)
        if not unit.exists() or partner.id not in unit.resident_ids.ids:
            return request.redirect('/my/appointments')

        vals = {
            'resident_id': partner.id,
            'unit_id': unit_id,
            'visitor_name': kwargs.get('visitor_name', ''),
            'visitor_phone': kwargs.get('visitor_phone', ''),
            'valid_from': (kwargs.get('valid_from') or '').replace('T', ' '),
            'valid_until': (kwargs.get('valid_until') or '').replace('T', ' '),
            'max_entries': int(kwargs.get('max_entries', 1)),
            'appointment_type': kwargs.get('appointment_type', 'one_time'),
            'purpose': kwargs.get('purpose', ''),
        }

        if vals['appointment_type'] == 'recurring':
            days = kwargs.getlist('recurring_days') if hasattr(
                kwargs, 'getlist'
            ) else []
            vals['recurring_days'] = ','.join(days)
            vals['recurring_from'] = self._parse_time_to_float(
                kwargs.get('recurring_from', 0)
            )
            vals['recurring_until'] = self._parse_time_to_float(
                kwargs.get('recurring_until', 0)
            )

        appointment = request.env['community.appointment'].sudo().create(vals)

        return request.redirect('/my/appointments/%d' % appointment.id)

    @http.route('/my/appointments/<int:appointment_id>/cancel', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def portal_appointment_cancel(self, appointment_id, **kwargs):
        appointment = request.env['community.appointment'].browse(
            appointment_id
        )
        if not appointment.exists():
            return request.redirect('/my/appointments')

        partner = request.env.user.partner_id
        if partner.id not in appointment.unit_id.resident_ids.ids:
            return request.redirect('/my/appointments')

        try:
            appointment.sudo().action_cancel()
        except Exception:
            pass

        return request.redirect('/my/appointments/%d' % appointment.id)
