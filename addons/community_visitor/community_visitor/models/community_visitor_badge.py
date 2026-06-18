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

    def action_release(self):
        """歸還訪客證"""
        for rec in self:
            rec.write({
                'state': 'available',
                'current_visit_id': False,
            })

    def action_assign(self, visit):
        """發放訪客證給訪問記錄"""
        self.ensure_one()
        if self.state != 'available':
            raise UserError(
                _('訪客證 %s 目前使用中，無法發放。', self.name)
            )
        self.write({
            'state': 'in_use',
            'current_visit_id': visit.id,
        })
