from odoo import fields, models


class CommunityFeedbackCategory(models.Model):
    _name = 'community.feedback.category'
    _description = '意見反映分類'
    _order = 'sequence, name'

    name = fields.Char(string='分類名稱', required=True)
    sequence = fields.Integer(string='排序', default=10)
    active = fields.Boolean(string='啟用', default=True)
