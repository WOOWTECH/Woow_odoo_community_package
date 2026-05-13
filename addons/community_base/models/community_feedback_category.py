from odoo import fields, models


class CommunityFeedbackCategory(models.Model):
    _name = 'community.feedback.category'
    _description = '意見反映分類'
    _order = 'name'

    name = fields.Char(string='分類名稱', required=True)
    color = fields.Integer(string='顏色')
