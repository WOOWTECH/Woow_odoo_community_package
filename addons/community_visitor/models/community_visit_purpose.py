from odoo import fields, models


class CommunityVisitPurpose(models.Model):
    _name = 'community.visit.purpose'
    _description = '來訪目的'
    _order = 'name'

    name = fields.Char(string='目的名稱', required=True)
    color = fields.Integer(string='顏色')
