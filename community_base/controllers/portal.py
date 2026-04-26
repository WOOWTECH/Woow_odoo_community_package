from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class CommunityPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'announcement_count' in counters:
            office_ids = partner.unit_ids.office_id.ids
            values['announcement_count'] = request.env[
                'community.announcement'
            ].search_count([
                ('state', '=', 'published'),
                ('office_id', 'in', office_ids),
            ])

        if 'feedback_count' in counters:
            values['feedback_count'] = request.env[
                'community.feedback'
            ].search_count([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['pending', 'in_progress']),
            ])

        return values

    # --- Announcements ---

    @http.route(
        '/my/announcements',
        type='http',
        auth='user',
        website=True,
    )
    def portal_announcements(self, category=None, **kwargs):
        partner = request.env.user.partner_id
        office_ids = partner.unit_ids.office_id.ids

        domain = [
            ('state', '=', 'published'),
            ('office_id', 'in', office_ids),
        ]

        current_category = False
        if category:
            category = int(category)
            domain.append(('category_id', '=', category))
            current_category = category

        announcements = request.env['community.announcement'].search(
            domain, order='publish_date desc'
        )
        categories = request.env['community.announcement.category'].search([])

        return request.render(
            'community_base.portal_announcements',
            {
                'announcements': announcements,
                'categories': categories,
                'current_category': current_category,
                'page_name': 'announcements',
            },
        )

    @http.route(
        '/my/announcements/<int:announcement_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_announcement_detail(self, announcement_id, **kwargs):
        announcement = request.env['community.announcement'].browse(
            announcement_id
        )
        if not announcement.exists() or announcement.state != 'published':
            return request.redirect('/my/announcements')

        # Security: check user belongs to announcement's office
        partner = request.env.user.partner_id
        office_ids = partner.unit_ids.office_id.ids
        if announcement.office_id.id not in office_ids:
            return request.redirect('/my/announcements')

        return request.render(
            'community_base.portal_announcement_detail',
            {
                'announcement': announcement,
                'page_name': 'announcements',
            },
        )

    # --- Feedbacks ---

    @http.route(
        '/my/feedbacks',
        type='http',
        auth='user',
        website=True,
    )
    def portal_feedbacks(self, **kwargs):
        partner = request.env.user.partner_id

        feedbacks = request.env['community.feedback'].search(
            [('partner_id', '=', partner.id)],
            order='create_date desc',
        )

        return request.render(
            'community_base.portal_feedbacks',
            {
                'feedbacks': feedbacks,
                'page_name': 'feedbacks',
            },
        )

    @http.route(
        '/my/feedbacks/new',
        type='http',
        auth='user',
        website=True,
    )
    def portal_feedback_new(self, **kwargs):
        partner = request.env.user.partner_id
        units = partner.unit_ids
        categories = request.env['community.feedback.category'].search([])

        return request.render(
            'community_base.portal_feedback_new',
            {
                'units': units,
                'categories': categories,
                'page_name': 'feedbacks',
            },
        )

    @http.route(
        '/my/feedbacks/create',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def portal_feedback_create(self, **kwargs):
        partner = request.env.user.partner_id

        unit_id = int(kwargs.get('unit_id', 0))
        unit = request.env['community.unit'].sudo().browse(unit_id)
        if not unit.exists() or partner.id not in unit.resident_ids.ids:
            return request.redirect('/my/feedbacks')

        vals = {
            'title': kwargs.get('title', ''),
            'content': kwargs.get('content', ''),
            'category_id': int(kwargs.get('category_id', 0)),
            'unit_id': unit_id,
            'partner_id': partner.id,
        }

        feedback = request.env['community.feedback'].sudo().create(vals)

        return request.redirect(f'/my/feedbacks/{feedback.id}')

    @http.route(
        '/my/feedbacks/<int:feedback_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_feedback_detail(self, feedback_id, **kwargs):
        feedback = request.env['community.feedback'].browse(feedback_id)
        if not feedback.exists():
            return request.redirect('/my/feedbacks')

        # Security: only own feedbacks
        partner = request.env.user.partner_id
        if feedback.partner_id.id != partner.id:
            return request.redirect('/my/feedbacks')

        return request.render(
            'community_base.portal_feedback_detail',
            {
                'feedback': feedback,
                'page_name': 'feedbacks',
            },
        )
