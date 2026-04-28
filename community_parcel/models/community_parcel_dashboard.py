from odoo import api, fields, models, tools


class CommunityParcelDashboard(models.Model):
    _name = 'community.parcel.dashboard'
    _description = '包裹管理工作台'
    _auto = False
    _order = 'id'

    name = fields.Char(string='名稱', readonly=True)
    count = fields.Integer(string='數量', readonly=True)
    target_model = fields.Char(string='目標模型', readonly=True)
    domain_filter = fields.Char(string='篩選條件', readonly=True)
    color = fields.Integer(string='Color Index')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'community_parcel_dashboard')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW community_parcel_dashboard AS (
                SELECT 1 AS id,
                       '今日到件' AS name,
                       COALESCE(COUNT(*), 0)::integer AS count,
                       'community.parcel' AS target_model,
                       'today_received' AS domain_filter,
                       0 AS color
                FROM community_parcel
                WHERE received_date >= (NOW() AT TIME ZONE 'UTC')::date
                  AND received_date < ((NOW() AT TIME ZONE 'UTC')::date + INTERVAL '1 day')

                UNION ALL

                SELECT 2 AS id,
                       '包裹未取件' AS name,
                       COALESCE(COUNT(*), 0)::integer AS count,
                       'community.parcel' AS target_model,
                       'uncollected' AS domain_filter,
                       0 AS color
                FROM community_parcel
                WHERE state IN ('draft', 'notified', 'overdue')

                UNION ALL

                SELECT 3 AS id,
                       '包裹逾期' AS name,
                       COALESCE(COUNT(*), 0)::integer AS count,
                       'community.parcel' AS target_model,
                       'overdue' AS domain_filter,
                       0 AS color
                FROM community_parcel
                WHERE state = 'overdue'

                UNION ALL

                SELECT 4 AS id,
                       '寄放待接收' AS name,
                       COALESCE(COUNT(*), 0)::integer AS count,
                       'community.storage' AS target_model,
                       'pending' AS domain_filter,
                       0 AS color
                FROM community_storage
                WHERE state = 'pending'

                UNION ALL

                SELECT 5 AS id,
                       '寄放保管中' AS name,
                       COALESCE(COUNT(*), 0)::integer AS count,
                       'community.storage' AS target_model,
                       'storing' AS domain_filter,
                       0 AS color
                FROM community_storage
                WHERE state = 'storing'

                UNION ALL

                SELECT 6 AS id,
                       '寄放待取件' AS name,
                       COALESCE(COUNT(*), 0)::integer AS count,
                       'community.storage' AS target_model,
                       'ready' AS domain_filter,
                       0 AS color
                FROM community_storage
                WHERE state = 'ready'
            )
        """)

    def action_open(self):
        """Open the target model list view with the appropriate domain."""
        self.ensure_one()
        domain_map = {
            'today_received': {
                'name': '今日到件',
                'model': 'community.parcel',
                'domain': [
                    ('received_date', '>=',
                     fields.Date.context_today(self).strftime('%Y-%m-%d 00:00:00')),
                    ('received_date', '<=',
                     fields.Date.context_today(self).strftime('%Y-%m-%d 23:59:59')),
                ],
                'search_view_ref': 'community_parcel.community_parcel_view_search',
            },
            'uncollected': {
                'name': '未取件包裹',
                'model': 'community.parcel',
                'domain': [('state', 'in', ('draft', 'notified', 'overdue'))],
                'search_view_ref': 'community_parcel.community_parcel_view_search',
            },
            'overdue': {
                'name': '逾期包裹',
                'model': 'community.parcel',
                'domain': [('state', '=', 'overdue')],
                'search_view_ref': 'community_parcel.community_parcel_view_search',
            },
            'pending': {
                'name': '寄放待接收',
                'model': 'community.storage',
                'domain': [('state', '=', 'pending')],
                'search_view_ref': 'community_parcel.community_storage_view_search',
            },
            'storing': {
                'name': '寄放保管中',
                'model': 'community.storage',
                'domain': [('state', '=', 'storing')],
                'search_view_ref': 'community_parcel.community_storage_view_search',
            },
            'ready': {
                'name': '寄放待取件',
                'model': 'community.storage',
                'domain': [('state', '=', 'ready')],
                'search_view_ref': 'community_parcel.community_storage_view_search',
            },
        }
        config = domain_map.get(self.domain_filter, {})
        if not config:
            return {}

        search_view = self.env.ref(
            config['search_view_ref'], raise_if_not_found=False
        )
        return {
            'type': 'ir.actions.act_window',
            'name': config['name'],
            'res_model': config['model'],
            'view_mode': 'list,kanban,form',
            'domain': config['domain'],
            'search_view_id': search_view.id if search_view else False,
            'target': 'current',
        }
