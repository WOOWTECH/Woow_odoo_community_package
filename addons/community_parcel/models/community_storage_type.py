from odoo import fields, models


class CommunityStorageType(models.Model):
    _name = 'community.storage.type'
    _description = '寄放類型'
    _order = 'name'

    name = fields.Char(string='類型名稱', required=True)
    color = fields.Integer(string='顏色')
