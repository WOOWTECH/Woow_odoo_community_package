from odoo import fields, models


class CommunityAnnouncementCategory(models.Model):
    _name = 'community.announcement.category'
    _description = '公告分類'
    _order = 'sequence, name'

    name = fields.Char(string='分類名稱', required=True)
    sequence = fields.Integer(string='排序', default=10)
    active = fields.Boolean(string='啟用', default=True)
