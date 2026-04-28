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
    count_stat1 = fields.Integer(string='統計1數量', readonly=True)
    stat1_label = fields.Char(string='統計1標籤', readonly=True)
    stat1_filter = fields.Char(string='統計1篩選', readonly=True)
    count_stat2 = fields.Integer(string='統計2數量', readonly=True)
    stat2_label = fields.Char(string='統計2標籤', readonly=True)
    stat2_filter = fields.Char(string='統計2篩選', readonly=True)
    color = fields.Integer(string='Color Index')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'community_parcel_dashboard')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW community_parcel_dashboard AS (
                -- 1. 今日到件: stat1=已通知, stat2=逾期
                SELECT 1 AS id,
                       '今日到件' AS name,
                       (SELECT COUNT(*) FROM community_parcel
                        WHERE received_date >= (NOW() AT TIME ZONE 'UTC')::date
                          AND received_date < ((NOW() AT TIME ZONE 'UTC')::date + INTERVAL '1 day')
                       )::integer AS count,
                       'community.parcel' AS target_model,
                       'today_received' AS domain_filter,
                       (SELECT COUNT(*) FROM community_parcel
                        WHERE received_date >= (NOW() AT TIME ZONE 'UTC')::date
                          AND received_date < ((NOW() AT TIME ZONE 'UTC')::date + INTERVAL '1 day')
                          AND state = 'notified'
                       )::integer AS count_stat1,
                       '已通知' AS stat1_label,
                       'today_notified' AS stat1_filter,
                       (SELECT COUNT(*) FROM community_parcel
                        WHERE received_date >= (NOW() AT TIME ZONE 'UTC')::date
                          AND received_date < ((NOW() AT TIME ZONE 'UTC')::date + INTERVAL '1 day')
                          AND state = 'overdue'
                       )::integer AS count_stat2,
                       '逾期' AS stat2_label,
                       'today_overdue' AS stat2_filter,
                       0 AS color

                UNION ALL

                -- 2. 包裹未取件: stat1=逾期
                SELECT 2 AS id,
                       '包裹未取件' AS name,
                       (SELECT COUNT(*) FROM community_parcel
                        WHERE state IN ('draft', 'notified', 'overdue')
                       )::integer AS count,
                       'community.parcel' AS target_model,
                       'uncollected' AS domain_filter,
                       (SELECT COUNT(*) FROM community_parcel
                        WHERE state = 'overdue'
                       )::integer AS count_stat1,
                       '逾期' AS stat1_label,
                       'overdue' AS stat1_filter,
                       0 AS count_stat2,
                       NULL AS stat2_label,
                       NULL AS stat2_filter,
                       0 AS color

                UNION ALL

                -- 3. 包裹逾期: 無右側統計
                SELECT 3 AS id,
                       '包裹逾期' AS name,
                       (SELECT COUNT(*) FROM community_parcel
                        WHERE state = 'overdue'
                       )::integer AS count,
                       'community.parcel' AS target_model,
                       'overdue' AS domain_filter,
                       0 AS count_stat1,
                       NULL AS stat1_label,
                       NULL AS stat1_filter,
                       0 AS count_stat2,
                       NULL AS stat2_label,
                       NULL AS stat2_filter,
                       0 AS color

                UNION ALL

                -- 4. 寄放待接收: 無右側統計
                SELECT 4 AS id,
                       '寄放待接收' AS name,
                       (SELECT COUNT(*) FROM community_storage
                        WHERE state = 'pending'
                       )::integer AS count,
                       'community.storage' AS target_model,
                       'pending' AS domain_filter,
                       0 AS count_stat1,
                       NULL AS stat1_label,
                       NULL AS stat1_filter,
                       0 AS count_stat2,
                       NULL AS stat2_label,
                       NULL AS stat2_filter,
                       0 AS color

                UNION ALL

                -- 5. 寄放保管中: stat1=待取件
                SELECT 5 AS id,
                       '寄放保管中' AS name,
                       (SELECT COUNT(*) FROM community_storage
                        WHERE state = 'storing'
                       )::integer AS count,
                       'community.storage' AS target_model,
                       'storing' AS domain_filter,
                       (SELECT COUNT(*) FROM community_storage
                        WHERE state = 'ready'
                       )::integer AS count_stat1,
                       '待取件' AS stat1_label,
                       'ready' AS stat1_filter,
                       0 AS count_stat2,
                       NULL AS stat2_label,
                       NULL AS stat2_filter,
                       0 AS color

                UNION ALL

                -- 6. 寄放待取件: 無右側統計
                SELECT 6 AS id,
                       '寄放待取件' AS name,
                       (SELECT COUNT(*) FROM community_storage
                        WHERE state = 'ready'
                       )::integer AS count,
                       'community.storage' AS target_model,
                       'ready' AS domain_filter,
                       0 AS count_stat1,
                       NULL AS stat1_label,
                       NULL AS stat1_filter,
                       0 AS count_stat2,
                       NULL AS stat2_label,
                       NULL AS stat2_filter,
                       0 AS color
            )
        """)

    # ── Domain 定義 ────────────────────────────────────────
    def _get_domain_config(self, filter_key):
        """Return (name, model, domain, search_view_ref) for a given filter key."""
        today = fields.Date.context_today(self).strftime('%Y-%m-%d')
        config_map = {
            'today_received': (
                '今日到件', 'community.parcel',
                [('received_date', '>=', f'{today} 00:00:00'),
                 ('received_date', '<=', f'{today} 23:59:59')],
                'community_parcel.community_parcel_view_search',
            ),
            'today_notified': (
                '今日到件（已通知）', 'community.parcel',
                [('received_date', '>=', f'{today} 00:00:00'),
                 ('received_date', '<=', f'{today} 23:59:59'),
                 ('state', '=', 'notified')],
                'community_parcel.community_parcel_view_search',
            ),
            'today_overdue': (
                '今日到件（逾期）', 'community.parcel',
                [('received_date', '>=', f'{today} 00:00:00'),
                 ('received_date', '<=', f'{today} 23:59:59'),
                 ('state', '=', 'overdue')],
                'community_parcel.community_parcel_view_search',
            ),
            'uncollected': (
                '未取件包裹', 'community.parcel',
                [('state', 'in', ('draft', 'notified', 'overdue'))],
                'community_parcel.community_parcel_view_search',
            ),
            'overdue': (
                '逾期包裹', 'community.parcel',
                [('state', '=', 'overdue')],
                'community_parcel.community_parcel_view_search',
            ),
            'pending': (
                '寄放待接收', 'community.storage',
                [('state', '=', 'pending')],
                'community_parcel.community_storage_view_search',
            ),
            'storing': (
                '寄放保管中', 'community.storage',
                [('state', '=', 'storing')],
                'community_parcel.community_storage_view_search',
            ),
            'ready': (
                '寄放待取件', 'community.storage',
                [('state', '=', 'ready')],
                'community_parcel.community_storage_view_search',
            ),
        }
        return config_map.get(filter_key)

    def _build_action(self, filter_key):
        config = self._get_domain_config(filter_key)
        if not config:
            return {}
        name, model, domain, search_ref = config
        search_view = self.env.ref(search_ref, raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'list,kanban,form',
            'domain': domain,
            'search_view_id': search_view.id if search_view else False,
            'target': 'current',
        }

    # ── Action Methods ─────────────────────────────────────
    def action_open(self):
        self.ensure_one()
        return self._build_action(self.domain_filter)

    def action_open_stat1(self):
        self.ensure_one()
        return self._build_action(self.stat1_filter)

    def action_open_stat2(self):
        self.ensure_one()
        return self._build_action(self.stat2_filter)
