from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class VisitorPortal(CustomerPortal):

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

    # --- Portal pages (login required) ---

    @http.route(
        '/my/visitors',
        type='http',
        auth='user',
        website=True,
    )
    def portal_my_visitors(self, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        pending_visits = request.env['community.visit'].search([
            ('unit_id', 'in', unit_ids),
            ('state', '=', 'pending_confirm'),
        ], order='create_date desc')

        recent_visits = request.env['community.visit'].search([
            ('unit_id', 'in', unit_ids),
            ('state', 'in', ['confirmed', 'checked_in', 'rejected', 'timeout']),
        ], order='create_date desc', limit=50)

        return request.render(
            'community_visitor.portal_my_visitors',
            {
                'pending_visits': pending_visits,
                'recent_visits': recent_visits,
                'page_name': 'visitors',
            },
        )

    @http.route(
        '/my/appointments',
        type='http',
        auth='user',
        website=True,
    )
    def portal_my_appointments(self, **kwargs):
        partner = request.env.user.partner_id
        unit_ids = partner.unit_ids.ids

        appointments = request.env['community.appointment'].search([
            ('unit_id', 'in', unit_ids),
        ], order='create_date desc')

        return request.render(
            'community_visitor.portal_my_appointments',
            {
                'appointments': appointments,
                'page_name': 'appointments',
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

        return request.render(
            'community_visitor.portal_appointment_detail',
            {
                'appointment': appointment,
                'page_name': 'appointments',
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
                'page_name': 'appointments',
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

        unit_id = int(kwargs.get('unit_id', 0))
        unit = request.env['community.unit'].browse(unit_id)
        if not unit.exists() or partner.id not in unit.resident_ids.ids:
            return request.redirect('/my/appointments')

        vals = {
            'resident_id': partner.id,
            'unit_id': unit_id,
            'visitor_name': kwargs.get('visitor_name', ''),
            'visitor_phone': kwargs.get('visitor_phone', ''),
            'valid_from': kwargs.get('valid_from'),
            'valid_until': kwargs.get('valid_until'),
            'max_entries': int(kwargs.get('max_entries', 1)),
            'appointment_type': kwargs.get('appointment_type', 'one_time'),
            'purpose': kwargs.get('purpose', ''),
        }

        if vals['appointment_type'] == 'recurring':
            days = kwargs.getlist('recurring_days') if hasattr(
                kwargs, 'getlist'
            ) else []
            vals['recurring_days'] = ','.join(days)
            vals['recurring_from'] = float(kwargs.get('recurring_from', 0))
            vals['recurring_until'] = float(kwargs.get('recurring_until', 0))

        appointment = request.env['community.appointment'].sudo().create(vals)

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
            appointment.sudo().action_cancel()
        except Exception:
            pass

        return request.redirect(f'/my/appointments/{appointment.id}')
