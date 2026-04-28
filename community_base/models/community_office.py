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
    unit_ids = fields.One2many(
        'community.unit',
        'office_id',
        string='轄下戶號',
    )
    internal_note = fields.Text(string='內部備註')
    announcement_properties_definition = fields.PropertiesDefinition(
        string='公告屬性定義',
    )
    feedback_properties_definition = fields.PropertiesDefinition(
        string='意見屬性定義',
    )
    unit_properties_definition = fields.PropertiesDefinition(
        string='戶號屬性定義',
    )
