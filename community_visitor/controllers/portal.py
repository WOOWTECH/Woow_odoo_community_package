import logging
from datetime import datetime

import pytz

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
            hours, minutes = value.split(':')
            hours, minutes = int(hours), int(minutes)
            if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
                raise ValueError('Invalid time')
            return hours + minutes / 60.0
        return float(value)

    @staticmethod
    def _local_datetime_to_utc(value, timezone):
        """HTML datetime-local has no offset; interpret it in the displayed zone."""
        if not value:
            return False
        local = datetime.fromisoformat(value)
        if local.tzinfo is not None:
            raise ValueError('Expected a local date and time')
        return pytz.timezone(timezone).localize(local, is_dst=None).astimezone(
            pytz.utc,
        ).replace(tzinfo=None)

    def _appointment_form_values(self, values=None, error=None):
        return {
            'units': request.env.user.partner_id.unit_ids,
            'page_name': 'appointment_new',
            'form_values': values or {},
            'timezone': request.env.user.tz or 'UTC',
            'error': error,
        }

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
                {'error': _('Invalid confirmation link.')},
            )

        if visit.state != 'pending_confirm':
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': _('This visit record has already been processed.')},
            )

        if visit.token_expiry and fields.Datetime.now() > visit.token_expiry:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': _('Confirmation link has expired.')},
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
                {'error': _('Invalid confirmation link.')},
            )

        try:
            partner = (
                request.env.user.partner_id
                if not request.env.user._is_public()
                else None
            )
            with request.env.cr.savepoint():
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
        methods=['GET', 'POST'],
        csrf=True,
    )
    def visitor_confirm_reject(self, token, **kwargs):
        # Previously sent emails linked here. GET only opens the decision page.
        if request.httprequest.method == 'GET':
            return self.visitor_confirm_page(token, **kwargs)
        visit = request.env['community.visit'].sudo().search([
            ('confirm_token', '=', token),
        ], limit=1)

        if not visit:
            return request.render(
                'community_visitor.portal_visitor_token_error',
                {'error': _('Invalid confirmation link.')},
            )

        try:
            partner = (
                request.env.user.partner_id
                if not request.env.user._is_public()
                else None
            )
            with request.env.cr.savepoint():
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
            'date_desc': {'label': _('Newest First'), 'order': 'create_date desc'},
            'date_asc': {'label': _('Oldest First'), 'order': 'create_date asc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'pending': {'label': _('Pending Confirm'), 'domain': [('state', '=', 'pending_confirm')]},
            'confirmed': {'label': _('Confirmed'), 'domain': [('state', '=', 'confirmed')]},
            'checked_in': {'label': _('Checked In'), 'domain': [('state', '=', 'checked_in')]},
            'checked_out': {'label': _('Checked Out'), 'domain': [('state', '=', 'checked_out')]},
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
        visit = request.env['community.visit'].search([
            ('id', '=', visit_id),
            ('unit_id.resident_ids', 'in', [request.env.user.partner_id.id]),
        ], limit=1)
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
            'date_desc': {'label': _('Newest First'), 'order': 'create_date desc'},
            'date_asc': {'label': _('Oldest First'), 'order': 'create_date asc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'active': {'label': _('Active'), 'domain': [('state', '=', 'active')]},
            'expired': {'label': _('Expired'), 'domain': [('state', '=', 'expired')]},
            'cancelled': {'label': _('Cancelled'), 'domain': [('state', '=', 'cancelled')]},
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
        appointment = request.env['community.appointment'].search([
            ('id', '=', appointment_id),
            ('unit_id.resident_ids', 'in', [request.env.user.partner_id.id]),
        ], limit=1)
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
        return request.render(
            'community_visitor.portal_appointment_new',
            self._appointment_form_values(),
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
        if unit_id not in partner.unit_ids.ids:
            return request.render(
                'community_visitor.portal_appointment_new',
                self._appointment_form_values(kwargs, _('請選擇您所屬的戶號。')),
            )

        try:
            timezone = request.env.user.tz or 'UTC'
            vals = {
                'resident_id': partner.id,
                'unit_id': unit_id,
                'visitor_name': (kwargs.get('visitor_name') or '').strip(),
                'visitor_phone': (kwargs.get('visitor_phone') or '').strip(),
                'valid_from': self._local_datetime_to_utc(kwargs.get('valid_from'), timezone),
                'valid_until': self._local_datetime_to_utc(kwargs.get('valid_until'), timezone),
                'schedule_tz': timezone,
                'max_entries': int(kwargs.get('max_entries') or 1),
                'appointment_type': kwargs.get('appointment_type', 'one_time'),
                'purpose': kwargs.get('purpose', ''),
            }
            if not vals['visitor_name'] or not vals['visitor_phone'] or not vals['valid_from']:
                raise ValidationError(_('請填寫訪客姓名、電話與有效起始時間。'))
            if vals['appointment_type'] not in ('one_time', 'recurring', 'permanent'):
                raise ValidationError(_('請選擇有效的預約類型。'))
            if vals['appointment_type'] == 'recurring':
                vals.update({
                    'recurring_days': (kwargs.get('recurring_days') or '').strip(),
                    'recurring_from': self._parse_time_to_float(kwargs.get('recurring_from')),
                    'recurring_until': self._parse_time_to_float(kwargs.get('recurring_until')),
                })
            # A caught constraint error must not commit the rejected create.
            with request.env.cr.savepoint():
                appointment = request.env['community.appointment'].sudo().create(vals)
        except (UserError, ValidationError) as exc:
            return request.render(
                'community_visitor.portal_appointment_new',
                self._appointment_form_values(kwargs, str(exc)),
            )
        except (ValueError, TypeError, pytz.InvalidTimeError):
            return request.render(
                'community_visitor.portal_appointment_new',
                self._appointment_form_values(
                    kwargs, _('日期、時間或次數格式不正確；日光節約時間切換時請選擇其他時間。'),
                ),
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
        appointment = request.env['community.appointment'].search([
            ('id', '=', appointment_id),
            ('unit_id.resident_ids', 'in', [request.env.user.partner_id.id]),
        ], limit=1)
        if not appointment.exists():
            return request.redirect('/my/appointments')

        # Security check: only residents of the unit can cancel
        partner = request.env.user.partner_id
        if partner.id not in appointment.unit_id.resident_ids.ids:
            return request.redirect('/my/appointments')

        try:
            appointment.sudo().action_cancel()
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
