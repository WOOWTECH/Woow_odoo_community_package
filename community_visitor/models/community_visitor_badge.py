from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CommunityVisitorBadge(models.Model):
    _name = 'community.visitor.badge'
    _description = '訪客證'
    _order = 'name'

    name = fields.Char(string='編號', required=True)
    state = fields.Selection(
        [
            ('available', '可用'),
            ('in_use', '使用中'),
        ],
        string='狀態',
        default='available',
        required=True,
    )
    current_visit_id = fields.Many2one(
        'community.visit',
        string='目前訪問記錄',
        ondelete='set null',
        readonly=True,
    )

    _sql_constraints = [
        ('unique_name', 'UNIQUE(name)', '訪客證編號不可重複！'),
    ]

    def _lock_assignment(self):
        self.check_access_rights('write')
        self.check_access_rule('write')
        self.flush_recordset()
        self.env.cr.execute(
            'SELECT id FROM community_visitor_badge WHERE id IN %s ORDER BY id FOR UPDATE',
            [tuple(self.ids)],
        )
        self.invalidate_recordset(['state', 'current_visit_id'])

    def _release_for_visit(self, visit):
        """Historical visit links must never release a subsequent loan."""
        self._lock_assignment()
        for badge in self:
            if badge.current_visit_id == visit:
                badge.action_release()

    def action_release(self):
        """歸還訪客證；保留訪問紀錄上的歷史證號。"""
        if not self:
            return
        self._lock_assignment()
        self.write({'state': 'available', 'current_visit_id': False})

    def action_assign(self, visit):
        """發放訪客證給訪問記錄；同一借用可安全重試。"""
        self.ensure_one()
        visit.ensure_one()
        self._lock_assignment()
        if self.state == 'in_use' and self.current_visit_id == visit:
            return
        if self.state != 'available':
            raise UserError(_('訪客證 %s 目前使用中，無法發放。', self.name))
        self.write({'state': 'in_use', 'current_visit_id': visit.id})
