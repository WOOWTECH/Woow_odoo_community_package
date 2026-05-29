from collections import OrderedDict

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.osv.expression import AND


class CommunityPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'community_count' in counters:
            # Aggregate pending count across all community sub-modules
            count = 0
            office_ids = partner.unit_ids.office_id.ids
            unit_ids = partner.unit_ids.ids

            # Pending feedbacks
            count += request.env['community.feedback'].search_count([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['pending', 'in_progress']),
            ])

            # Pending visits (if module installed)
            if 'community.visit' in request.env:
                count += request.env['community.visit'].sudo().search_count([
                    ('unit_id', 'in', unit_ids),
                    ('state', '=', 'pending_confirm'),
                ])

            # Notified parcels (if module installed)
            if 'community.parcel' in request.env:
                count += request.env['community.parcel'].sudo().search_count([
                    ('unit_id', 'in', unit_ids),
                    ('state', 'in', ['notified', 'overdue']),
                ])

            # Ready storage (if module installed)
            if 'community.storage' in request.env:
                count += request.env['community.storage'].sudo().search_count([
                    ('unit_id', 'in', unit_ids),
                    ('state', '=', 'ready'),
                ])

            values['community_count'] = count

        return values

    # ===================================================================
    # Community Hub
    # ===================================================================

    @http.route('/my/community', type='http', auth='user', website=True)
    def portal_community_home(self, **kwargs):
        return request.render(
            'community_base.portal_my_community',
            {'page_name': 'community'},
        )

    # ===================================================================
    # Announcements
    # ===================================================================

    @http.route('/my/announcements', type='http', auth='user', website=True)
    def portal_announcements(self, page=1, sortby=None, filterby=None,
                             search=None, search_in='title', **kwargs):
        partner = request.env.user.partner_id
        Announcement = request.env['community.announcement']
        office_ids = partner.unit_ids.office_id.ids

        base_domain = [
            ('state', '=', 'published'),
            ('office_id', 'in', office_ids),
        ]

        # Sort
        searchbar_sortings = OrderedDict([
            ('date_desc', {'label': _('Newest'), 'order': 'publish_date desc'}),
            ('date_asc', {'label': _('Oldest'), 'order': 'publish_date asc'}),
        ])
        if not sortby:
            sortby = 'date_desc'
        order = searchbar_sortings[sortby]['order']

        # Filter (dynamic categories)
        categories = request.env['community.announcement.category'].search([])
        searchbar_filters = OrderedDict([
            ('all', {'label': _('All'), 'domain': []}),
        ])
        for cat in categories:
            searchbar_filters[str(cat.id)] = {
                'label': cat.name,
                'domain': [('category_id', '=', cat.id)],
            }
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        # Search
        searchbar_inputs = OrderedDict([
            ('title', {'input': 'title', 'label': _('Title')}),
            ('content', {'input': 'content', 'label': _('Content')}),
        ])
        search_domain = []
        if search and search_in:
            if search_in == 'title':
                search_domain = [('title', 'ilike', search)]
            elif search_in == 'content':
                search_domain = [('content', 'ilike', search)]

        domain = AND([
            base_domain,
            searchbar_filters[filterby]['domain'],
            search_domain,
        ])

        # Count + pager
        count = Announcement.search_count(domain)
        pager = portal_pager(
            url='/my/announcements',
            url_args={'sortby': sortby, 'filterby': filterby,
                      'search_in': search_in, 'search': search},
            total=count,
            page=page,
            step=10,
        )

        announcements = Announcement.search(
            domain, order=order, limit=10, offset=pager['offset']
        )

        return request.render(
            'community_base.portal_announcements',
            {
                'announcements': announcements,
                'page_name': 'announcements',
                'pager': pager,
                'default_url': '/my/announcements',
                'searchbar_sortings': searchbar_sortings,
                'sortby': sortby,
                'searchbar_filters': searchbar_filters,
                'filterby': filterby,
                'searchbar_inputs': searchbar_inputs,
                'search_in': search_in,
                'search': search,
            },
        )

    @http.route('/my/announcements/<int:announcement_id>', type='http',
                auth='user', website=True)
    def portal_announcement_detail(self, announcement_id, **kwargs):
        partner = request.env.user.partner_id
        office_ids = partner.unit_ids.office_id.ids

        announcement = request.env['community.announcement'].browse(
            announcement_id
        )
        if (not announcement.exists()
                or announcement.state != 'published'
                or announcement.office_id.id not in office_ids):
            return request.redirect('/my/announcements')

        # Prev/Next
        base_domain = [
            ('state', '=', 'published'),
            ('office_id', 'in', office_ids),
        ]
        all_ids = request.env['community.announcement'].search(
            base_domain, order='publish_date desc'
        ).ids
        idx = all_ids.index(announcement.id) if announcement.id in all_ids else -1
        prev_record = '/my/announcements/%d' % all_ids[idx - 1] if idx > 0 else None
        next_record = (
            '/my/announcements/%d' % all_ids[idx + 1]
            if 0 <= idx < len(all_ids) - 1 else None
        )

        return request.render(
            'community_base.portal_announcement_detail',
            {
                'announcement': announcement,
                'page_name': 'announcement_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )

    # ===================================================================
    # Feedbacks
    # ===================================================================

    @http.route('/my/feedbacks', type='http', auth='user', website=True)
    def portal_feedbacks(self, page=1, sortby=None, filterby=None,
                         search=None, search_in='title', **kwargs):
        partner = request.env.user.partner_id
        Feedback = request.env['community.feedback']

        base_domain = [('partner_id', '=', partner.id)]

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
            ('pending', {'label': _('Pending'), 'domain': [('state', '=', 'pending')]}),
            ('in_progress', {'label': _('In Progress'), 'domain': [('state', '=', 'in_progress')]}),
            ('closed', {'label': _('Closed'), 'domain': [('state', '=', 'closed')]}),
        ])
        if not filterby or filterby not in searchbar_filters:
            filterby = 'all'

        # Search
        searchbar_inputs = OrderedDict([
            ('title', {'input': 'title', 'label': _('Title')}),
            ('name', {'input': 'name', 'label': _('Reference')}),
        ])
        search_domain = []
        if search and search_in:
            if search_in == 'title':
                search_domain = [('title', 'ilike', search)]
            elif search_in == 'name':
                search_domain = [('name', 'ilike', search)]

        domain = AND([
            base_domain,
            searchbar_filters[filterby]['domain'],
            search_domain,
        ])

        count = Feedback.search_count(domain)
        pager = portal_pager(
            url='/my/feedbacks',
            url_args={'sortby': sortby, 'filterby': filterby,
                      'search_in': search_in, 'search': search},
            total=count,
            page=page,
            step=10,
        )

        feedbacks = Feedback.search(
            domain, order=order, limit=10, offset=pager['offset']
        )

        return request.render(
            'community_base.portal_feedbacks',
            {
                'feedbacks': feedbacks,
                'page_name': 'feedbacks',
                'pager': pager,
                'default_url': '/my/feedbacks',
                'searchbar_sortings': searchbar_sortings,
                'sortby': sortby,
                'searchbar_filters': searchbar_filters,
                'filterby': filterby,
                'searchbar_inputs': searchbar_inputs,
                'search_in': search_in,
                'search': search,
            },
        )

    @http.route('/my/feedbacks/new', type='http', auth='user', website=True)
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

    @http.route('/my/feedbacks/create', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def portal_feedback_create(self, **kwargs):
        partner = request.env.user.partner_id

        unit_id = int(kwargs.get('unit_id', 0))
        unit = request.env['community.unit'].sudo().browse(unit_id)
        if not unit.exists() or partner.id not in unit.resident_ids.ids:
            return request.redirect('/my/feedbacks')

        category_id = int(kwargs.get('category_id', 0))
        if not category_id or not request.env[
            'community.feedback.category'
        ].sudo().browse(category_id).exists():
            return request.redirect('/my/feedbacks')

        vals = {
            'title': kwargs.get('title', ''),
            'content': kwargs.get('content', ''),
            'category_id': category_id,
            'unit_id': unit_id,
            'partner_id': partner.id,
        }

        feedback = request.env['community.feedback'].sudo().create(vals)
        return request.redirect('/my/feedbacks/%d' % feedback.id)

    @http.route('/my/feedbacks/<int:feedback_id>', type='http',
                auth='user', website=True)
    def portal_feedback_detail(self, feedback_id, **kwargs):
        partner = request.env.user.partner_id

        feedback = request.env['community.feedback'].browse(feedback_id)
        if not feedback.exists() or feedback.partner_id.id != partner.id:
            return request.redirect('/my/feedbacks')

        # Prev/Next
        all_ids = request.env['community.feedback'].search(
            [('partner_id', '=', partner.id)], order='create_date desc'
        ).ids
        idx = all_ids.index(feedback.id) if feedback.id in all_ids else -1
        prev_record = '/my/feedbacks/%d' % all_ids[idx - 1] if idx > 0 else None
        next_record = (
            '/my/feedbacks/%d' % all_ids[idx + 1]
            if 0 <= idx < len(all_ids) - 1 else None
        )

        return request.render(
            'community_base.portal_feedback_detail',
            {
                'feedback': feedback,
                'page_name': 'feedback_detail',
                'prev_record': prev_record,
                'next_record': next_record,
            },
        )
