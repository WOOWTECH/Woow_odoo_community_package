import logging

from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

_logger = logging.getLogger(__name__)


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

    @staticmethod
    def _safe_int(value, default=0):
        """Safely convert *value* to int; return *default* on failure."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'pending_visit_count' in counters:
            values['pending_visit_count'] = request.env[
                'community.visit'
            ].search_count([
                ('unit_id.resident_ids', 'in', [partner.id]),
                ('state', '=', 'pending_confirm'),
            ])

        if 'appointment_count' in counters:
            values['appointment_count'] = request.env[
                'community.appointment'
            ].search_count([
                ('unit_id.resident_ids', 'in', [partner.id]),
                ('state', '=', 'active'),
            ])

        return values

    # --- Token-based confirmation (public, no login required) ---

    @http.route(
        '/visitor/confirm/<string:token>',
        type='http',
        auth='public',
        website=True,
    )
    def visitor_confirm_page(self, token, **kwargs):
        visit = request.env['community.visit'].sudo().search([
            ('confirm_token', '=', token),
        ], limit=1)

        if not visit:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': _('無效的確認連結。')},
            )

        if visit.state != 'pending_confirm':
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': _('此訪問記錄已被處理。')},
            )

        if visit.token_expiry and fields.Datetime.now() > visit.token_expiry:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': _('確認連結已過期。')},
            )

        return request.render(
            'community_visitor.portal_visitor_confirm_page',
            {'visit': visit, 'token': token},
        )

    @http.route(
        '/visitor/confirm/<string:token>/accept',
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def visitor_confirm_accept(self, token, **kwargs):
        visit = request.env['community.visit'].sudo().search([
            ('confirm_token', '=', token),
        ], limit=1)

        if not visit:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': _('無效的確認連結。')},
            )

        try:
            partner = (
                request.env.user.partner_id
                if not request.env.user._is_public()
                else None
            )
            visit.action_confirm(token, partner=partner)
        except (UserError, ValidationError) as e:
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
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def visitor_confirm_reject(self, token, **kwargs):
        visit = request.env['community.visit'].sudo().search([
            ('confirm_token', '=', token),
        ], limit=1)

        if not visit:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': _('無效的確認連結。')},
            )

        try:
            partner = (
                request.env.user.partner_id
                if not request.env.user._is_public()
                else None
            )
            visit.action_reject(token, partner=partner)
        except (UserError, ValidationError) as e:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': str(e)},
            )

        return request.render(
            'community_visitor.portal_visitor_confirm_result',
            {'visit': visit, 'result': 'rejected'},
        )

    # --- Portal pages (login required) ---

    @http.route(
        ['/my/visitors', '/my/visitors/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_my_visitors(self, page=1, sortby=None, filterby=None, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids
        domain = [('unit_id', 'in', unit_ids)]

        searchbar_sortings = {
            'date_desc': {'label': _('最新優先'), 'order': 'create_date desc'},
            'date_asc': {'label': _('最舊優先'), 'order': 'create_date asc'},
        }
        searchbar_filters = {
            'all': {'label': _('全部'), 'domain': []},
            'pending': {'label': _('待確認'), 'domain': [('state', '=', 'pending_confirm')]},
            'confirmed': {'label': _('已確認'), 'domain': [('state', '=', 'confirmed')]},
            'checked_in': {'label': _('已入場'), 'domain': [('state', '=', 'checked_in')]},
            'checked_out': {'label': _('已離場'), 'domain': [('state', '=', 'checked_out')]},
        }

        if not sortby or sortby not in searchbar_sortings:
            sortby = 'date_desc'
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        sort_order = searchbar_sortings[sortby]['order']
        search_domain = domain + searchbar_filters[filterby]['domain']

        total_count = request.env['community.visit'].search_count(search_domain)
        pager = portal_pager(
            url='/my/visitors',
            total=total_count,
            page=int(page),
            step=20,
            url_args={'sortby': sortby, 'filterby': filterby},
        )

        visits = request.env['community.visit'].search(
            search_domain,
            order=sort_order,
            limit=20,
            offset=pager['offset'],
        )

        return request.render(
            'community_visitor.portal_my_visitors',
            {
                'visits': visits,
                'page_name': 'visitors',
                'default_url': '/my/visitors',
                'pager': pager,
                'searchbar_sortings': searchbar_sortings,
                'searchbar_filters': searchbar_filters,
                'sortby': sortby,
                'filterby': filterby,
            },
        )

    @http.route(
        '/my/visitors/<int:visit_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_visit_detail(self, visit_id, **kwargs):
        visit = request.env['community.visit'].browse(visit_id)
        if not visit.exists():
            return request.redirect('/my/visitors')

        # Security check: only residents of the unit can view
        partner = request.env.user.partner_id
        if partner.id not in visit.unit_id.resident_ids.ids:
            return request.redirect('/my/visitors')

        # prev/next navigation
        all_visits = request.env['community.visit'].search(
            [('unit_id', 'in', partner.unit_ids.ids)],
            order='create_date desc',
        )
        visit_ids = all_visits.ids
        idx = visit_ids.index(visit.id) if visit.id in visit_ids else -1
        prev_record = f'/my/visitors/{visit_ids[idx - 1]}' if idx > 0 else None
        next_record = f'/my/visitors/{visit_ids[idx + 1]}' if 0 <= idx < len(visit_ids) - 1 else None

        return request.render(
            'community_visitor.portal_visit_detail',
            {
                'visit': visit,
                'page_name': 'visit_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    @http.route(
        ['/my/appointments', '/my/appointments/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_my_appointments(self, page=1, sortby=None, filterby=None, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids
        domain = [('unit_id', 'in', unit_ids)]

        searchbar_sortings = {
            'date_desc': {'label': _('最新優先'), 'order': 'create_date desc'},
            'date_asc': {'label': _('最舊優先'), 'order': 'create_date asc'},
        }
        searchbar_filters = {
            'all': {'label': _('全部'), 'domain': []},
            'active': {'label': _('有效'), 'domain': [('state', '=', 'active')]},
            'expired': {'label': _('已過期'), 'domain': [('state', '=', 'expired')]},
            'cancelled': {'label': _('已撤銷'), 'domain': [('state', '=', 'cancelled')]},
        }

        if not sortby or sortby not in searchbar_sortings:
            sortby = 'date_desc'
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        sort_order = searchbar_sortings[sortby]['order']
        search_domain = domain + searchbar_filters[filterby]['domain']

        total_count = request.env['community.appointment'].search_count(search_domain)
        pager = portal_pager(
            url='/my/appointments',
            total=total_count,
            page=int(page),
            step=20,
            url_args={'sortby': sortby, 'filterby': filterby},
        )

        appointments = request.env['community.appointment'].search(
            search_domain,
            order=sort_order,
            limit=20,
            offset=pager['offset'],
        )

        return request.render(
            'community_visitor.portal_my_appointments',
            {
                'appointments': appointments,
                'page_name': 'appointments',
                'default_url': '/my/appointments',
                'pager': pager,
                'searchbar_sortings': searchbar_sortings,
                'searchbar_filters': searchbar_filters,
                'sortby': sortby,
                'filterby': filterby,
            },
        )

    @http.route(
        '/my/appointments/<int:appointment_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_appointment_detail(self, appointment_id, **kwargs):
        appointment = request.env['community.appointment'].browse(
            appointment_id
        )
        if not appointment.exists():
            return request.redirect('/my/appointments')

        # Security check
        partner = request.env.user.partner_id
        if partner.id not in appointment.unit_id.resident_ids.ids:
            return request.redirect('/my/appointments')

        # prev/next navigation
        all_apts = request.env['community.appointment'].search(
            [('unit_id', 'in', partner.unit_ids.ids)],
            order='create_date desc',
        )
        apt_ids = all_apts.ids
        idx = apt_ids.index(appointment.id) if appointment.id in apt_ids else -1
        prev_record = f'/my/appointments/{apt_ids[idx - 1]}' if idx > 0 else None
        next_record = f'/my/appointments/{apt_ids[idx + 1]}' if 0 <= idx < len(apt_ids) - 1 else None

        return request.render(
            'community_visitor.portal_appointment_detail',
            {
                'appointment': appointment,
                'page_name': 'appointment_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    @http.route(
        '/my/appointments/new',
        type='http',
        auth='user',
        website=True,
    )
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

    @http.route(
        '/my/appointments/create',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def portal_appointment_create(self, **kwargs):
        partner = request.env.user.partner_id

        try:
            unit_id = int(kwargs.get('unit_id', 0))
        except (ValueError, TypeError):
            unit_id = 0
        unit = request.env['community.unit'].browse(unit_id)
        if not unit.exists() or partner.id not in unit.resident_ids.ids:
            return request.redirect('/my/appointments')

        valid_until_raw = (kwargs.get('valid_until') or '').replace('T', ' ')
        vals = {
            'resident_id': partner.id,
            'unit_id': unit_id,
            'visitor_name': kwargs.get('visitor_name', ''),
            'visitor_phone': kwargs.get('visitor_phone', ''),
            'valid_from': (kwargs.get('valid_from') or '').replace('T', ' '),
            'max_entries': self._safe_int(kwargs.get('max_entries'), 1),
            'appointment_type': kwargs.get('appointment_type', 'one_time'),
            'purpose': kwargs.get('purpose', ''),
        }
        # Only set valid_until if provided (permanent type can omit)
        if valid_until_raw.strip():
            vals['valid_until'] = valid_until_raw

        if vals['appointment_type'] == 'recurring':
            recurring_days = kwargs.get('recurring_days', '')
            vals['recurring_days'] = recurring_days.strip()
            vals['recurring_from'] = self._parse_time_to_float(
                kwargs.get('recurring_from', 0)
            )
            vals['recurring_until'] = self._parse_time_to_float(
                kwargs.get('recurring_until', 0)
            )

        try:
            appointment = request.env['community.appointment'].sudo().create(
                vals,
            )
        except (UserError, ValidationError) as e:
            return request.render(
                'community_visitor.portal_appointment_new',
                {
                    'error': str(e),
                    'units': partner.unit_ids,
                    'page_name': 'appointment_new',
                },
            )

        return request.redirect(f'/my/appointments/{appointment.id}')

    @http.route(
        '/my/appointments/<int:appointment_id>/cancel',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def portal_appointment_cancel(self, appointment_id, **kwargs):
        appointment = request.env['community.appointment'].browse(
            appointment_id
        )
        if not appointment.exists():
            return request.redirect('/my/appointments')

        # Security check: only residents of the unit can cancel
        partner = request.env.user.partner_id
        if partner.id not in appointment.unit_id.resident_ids.ids:
            return request.redirect('/my/appointments')

        try:
            appointment.action_cancel()
        except (UserError, ValidationError) as e:
            _logger.warning(
                'Portal appointment cancel failed (id=%s): %s',
                appointment_id, e,
            )
            return request.render(
                'community_visitor.portal_appointment_detail',
                {
                    'appointment': appointment,
                    'error': str(e),
                    'page_name': 'appointment_detail',
                },
            )

        return request.redirect(f'/my/appointments/{appointment.id}')
