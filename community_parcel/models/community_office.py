from odoo import fields, models


class CommunityOffice(models.Model):
    _name = 'community.office'
    _description = '管理室'
    _order = 'name'

    name = fields.Char(string='管理室名稱', required=True)
    building_id = fields.Char(string='棟別', help='所屬棟別名稱')
    responsible_id = fields.Many2one(
        'res.users',
        string='負責人',
        default=lambda self: self.env.uid,
    )
