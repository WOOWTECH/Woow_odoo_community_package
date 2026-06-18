from odoo import fields, models


class CommunityParcelType(models.Model):
    _name = 'community.parcel.type'
    _description = '包裹類型'
    _order = 'name'

    name = fields.Char(string='類型名稱', required=True)
    color = fields.Integer(string='顏色')
