from odoo import http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class CommunityPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'community_count' in counters:
            office_ids = partner.unit_ids.office_id.ids
            ann_count = request.env['community.announcement'].search_count([
                ('state', '=', 'published'),
                ('office_id', 'in', office_ids),
            ])
            fb_count = request.env['community.feedback'].search_count([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['pending', 'in_progress']),
            ])
            values['community_count'] = ann_count + fb_count

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

    # --- Community Landing Page ---

    @http.route(
        '/my/community',
        type='http',
        auth='user',
        website=True,
    )
    def portal_community_home(self, **kwargs):
        return request.render(
            'community_base.portal_my_community',
            {
                'page_name': 'community',
            },
        )

    # --- Announcements ---

    @http.route(
        ['/my/announcements', '/my/announcements/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_announcements(self, page=1, sortby=None, filterby=None, **kwargs):
        partner = request.env.user.partner_id
        office_ids = partner.unit_ids.office_id.ids

        domain = [
            ('state', '=', 'published'),
            ('office_id', 'in', office_ids),
        ]

        searchbar_sortings = {
            'date_desc': {'label': _('最新優先'), 'order': 'publish_date desc'},
            'date_asc': {'label': _('最舊優先'), 'order': 'publish_date asc'},
        }

        categories = request.env['community.announcement.category'].search([])
        searchbar_filters = {
            'all': {'label': _('全部'), 'domain': []},
        }
        for cat in categories:
            searchbar_filters[str(cat.id)] = {
                'label': cat.name,
                'domain': [('category_id', '=', cat.id)],
            }

        if not sortby or sortby not in searchbar_sortings:
            sortby = 'date_desc'
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        sort_order = searchbar_sortings[sortby]['order']
        search_domain = domain + searchbar_filters[filterby]['domain']

        total_count = request.env['community.announcement'].search_count(search_domain)
        pager = portal_pager(
            url='/my/announcements',
            total=total_count,
            page=int(page),
            step=20,
            url_args={'sortby': sortby, 'filterby': filterby},
        )

        announcements = request.env['community.announcement'].search(
            search_domain,
            order=sort_order,
            limit=20,
            offset=pager['offset'],
        )

        return request.render(
            'community_base.portal_announcements',
            {
                'announcements': announcements,
                'page_name': 'announcements',
                'default_url': '/my/announcements',
                'pager': pager,
                'searchbar_sortings': searchbar_sortings,
                'searchbar_filters': searchbar_filters,
                'sortby': sortby,
                'filterby': filterby,
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

        # prev/next navigation
        all_ann = request.env['community.announcement'].search([
            ('state', '=', 'published'),
            ('office_id', 'in', office_ids),
        ], order='publish_date desc')
        ann_ids = all_ann.ids
        idx = ann_ids.index(announcement.id) if announcement.id in ann_ids else -1
        prev_record = f'/my/announcements/{ann_ids[idx - 1]}' if idx > 0 else None
        next_record = f'/my/announcements/{ann_ids[idx + 1]}' if 0 <= idx < len(ann_ids) - 1 else None

        return request.render(
            'community_base.portal_announcement_detail',
            {
                'announcement': announcement,
                'page_name': 'announcement_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    # --- Feedbacks ---

    @http.route(
        ['/my/feedbacks', '/my/feedbacks/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_feedbacks(self, page=1, sortby=None, filterby=None, **kwargs):
        partner = request.env.user.partner_id
        domain = [('partner_id', '=', partner.id)]

        searchbar_sortings = {
            'date_desc': {'label': _('最新優先'), 'order': 'create_date desc'},
            'date_asc': {'label': _('最舊優先'), 'order': 'create_date asc'},
        }
        searchbar_filters = {
            'all': {'label': _('全部'), 'domain': []},
            'pending': {'label': _('待處理'), 'domain': [('state', '=', 'pending')]},
            'in_progress': {'label': _('處理中'), 'domain': [('state', '=', 'in_progress')]},
            'done': {'label': _('已結案'), 'domain': [('state', '=', 'done')]},
        }

        if not sortby or sortby not in searchbar_sortings:
            sortby = 'date_desc'
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        sort_order = searchbar_sortings[sortby]['order']
        search_domain = domain + searchbar_filters[filterby]['domain']

        total_count = request.env['community.feedback'].search_count(search_domain)
        pager = portal_pager(
            url='/my/feedbacks',
            total=total_count,
            page=int(page),
            step=20,
            url_args={'sortby': sortby, 'filterby': filterby},
        )

        feedbacks = request.env['community.feedback'].search(
            search_domain,
            order=sort_order,
            limit=20,
            offset=pager['offset'],
        )

        return request.render(
            'community_base.portal_feedbacks',
            {
                'feedbacks': feedbacks,
                'page_name': 'feedbacks',
                'default_url': '/my/feedbacks',
                'pager': pager,
                'searchbar_sortings': searchbar_sortings,
                'searchbar_filters': searchbar_filters,
                'sortby': sortby,
                'filterby': filterby,
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
                'page_name': 'feedback_new',
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

        try:
            unit_id = int(kwargs.get('unit_id') or 0)
        except (ValueError, TypeError):
            return request.redirect('/my/feedbacks')
        unit = request.env['community.unit'].browse(unit_id)
        if not unit.exists() or partner.id not in unit.resident_ids.ids:
            return request.redirect('/my/feedbacks')

        try:
            category_id = int(kwargs.get('category_id') or 0)
        except (ValueError, TypeError):
            return request.redirect('/my/feedbacks')
        if not category_id or not request.env[
            'community.feedback.category'
        ].browse(category_id).exists():
            return request.redirect('/my/feedbacks')

        vals = {
            'title': kwargs.get('title', ''),
            'content': kwargs.get('content', ''),
            'category_id': category_id,
            'unit_id': unit_id,
            'partner_id': partner.id,
        }

        try:
            feedback = request.env['community.feedback'].sudo().create(vals)
        except (UserError, ValidationError) as e:
            categories = request.env[
                'community.feedback.category'
            ].search([])
            return request.render(
                'community_base.portal_feedback_new',
                {
                    'error': str(e),
                    'categories': categories,
                    'units': partner.unit_ids,
                    'page_name': 'feedback_new',
                },
            )

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

        # prev/next navigation
        all_fb = request.env['community.feedback'].search(
            [('partner_id', '=', partner.id)],
            order='create_date desc',
        )
        fb_ids = all_fb.ids
        idx = fb_ids.index(feedback.id) if feedback.id in fb_ids else -1
        prev_record = f'/my/feedbacks/{fb_ids[idx - 1]}' if idx > 0 else None
        next_record = f'/my/feedbacks/{fb_ids[idx + 1]}' if 0 <= idx < len(fb_ids) - 1 else None

        return request.render(
            'community_base.portal_feedback_detail',
            {
                'feedback': feedback,
                'page_name': 'feedback_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )
