from odoo import models, fields


class CommunityOffice(models.Model):
    _name = 'community.office'
    _description = '管理室'
    _order = 'name'

    name = fields.Char(string='管理室名稱', required=True)
    building_name = fields.Char(string='棟別名稱')
    responsible_id = fields.Many2one(
        'res.users',
        string='負責人',
    )
