from odoo import fields, models


class CommunityAnnouncementCategory(models.Model):
    _name = 'community.announcement.category'
    _description = '公告分類'
    _order = 'name'

    name = fields.Char(string='分類名稱', required=True)
    color = fields.Integer(string='顏色')
