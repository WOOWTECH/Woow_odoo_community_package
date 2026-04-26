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
    announcement_properties_definition = fields.PropertiesDefinition(
        string='公告屬性定義',
    )
    feedback_properties_definition = fields.PropertiesDefinition(
        string='意見屬性定義',
    )
