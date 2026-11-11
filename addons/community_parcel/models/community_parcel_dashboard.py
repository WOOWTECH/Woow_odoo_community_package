from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, tools


class CommunityParcelDashboard(models.Model):
    _name = 'community.parcel.dashboard'
    _description = '包裹管理工作台'
    _auto = False
    _order = 'id'

    name = fields.Char(string='名稱', readonly=True)
    count = fields.Integer(string='數量', compute='_compute_counts')
    target_model = fields.Char(string='目標模型', readonly=True)
    domain_filter = fields.Char(string='篩選條件', readonly=True)
    count_stat1 = fields.Integer(string='統計1數量', compute='_compute_counts')
    stat1_label = fields.Char(string='統計1標籤', readonly=True)
    stat1_filter = fields.Char(string='統計1篩選', readonly=True)
    count_stat2 = fields.Integer(string='統計2數量', compute='_compute_counts')
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
                       0 AS count,
                       'community.parcel' AS target_model,
                       'today_received' AS domain_filter,
                       0 AS count_stat1,
                       '已通知' AS stat1_label,
                       'today_notified' AS stat1_filter,
                       0 AS count_stat2,
                       '逾期' AS stat2_label,
                       'today_overdue' AS stat2_filter,
                       0 AS color

                UNION ALL

                -- 2. 包裹未取件: stat1=逾期
                SELECT 2 AS id,
                       '包裹未取件' AS name,
                       0 AS count,
                       'community.parcel' AS target_model,
                       'uncollected' AS domain_filter,
                       0 AS count_stat1,
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
                       0 AS count,
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
                       0 AS count,
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
                       0 AS count,
                       'community.storage' AS target_model,
                       'storing' AS domain_filter,
                       0 AS count_stat1,
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
                       0 AS count,
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

    @api.depends('domain_filter', 'stat1_filter', 'stat2_filter')
    @api.depends_context('tz', 'uid')
    def _compute_counts(self):
        # Use the same domains and access rules as each drill-down action.
        for card in self:
            for count_field, filter_field in (
                ('count', 'domain_filter'),
                ('count_stat1', 'stat1_filter'),
                ('count_stat2', 'stat2_filter'),
            ):
                config = card._get_domain_config(card[filter_field])
                card[count_field] = (
                    self.env[config[1]].search_count(config[2]) if config else 0
                )

    def _today_received_domain(self):
        local_now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        zone = pytz.timezone(local_now.tzinfo.zone)
        today = local_now.date()
        # Localize both midnights separately: a DST day may be 23 or 25 hours.
        start, end = (
            zone.localize(datetime.combine(day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
            for day in (today, today + timedelta(days=1))
        )
        return [('received_date', '>=', fields.Datetime.to_string(start)),
                ('received_date', '<', fields.Datetime.to_string(end))]

    # ── Domain 定義 ────────────────────────────────────────
    def _get_domain_config(self, filter_key):
        """Return (name, model, domain, search_view_ref) for a given filter key."""
        today_domain = self._today_received_domain()
        config_map = {
            'today_received': (
                '今日到件', 'community.parcel',
                today_domain,
                'community_parcel.community_parcel_view_search',
            ),
            'today_notified': (
                '今日到件（已通知）', 'community.parcel',
                today_domain + [('state', '=', 'notified')],
                'community_parcel.community_parcel_view_search',
            ),
            'today_overdue': (
                '今日到件（逾期）', 'community.parcel',
                today_domain + [('state', '=', 'overdue')],
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
