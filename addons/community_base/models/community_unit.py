from odoo import models, fields, api


class CommunityUnit(models.Model):
    _name = 'community.unit'
    _description = '社區戶號'
    _order = 'building, floor, number'

    name = fields.Char(
        string='戶號',
        compute='_compute_name',
        store=True,
    )
    building = fields.Char(string='棟別', required=True)
    floor = fields.Char(string='樓層', required=True)
    number = fields.Char(string='門牌號', required=True)
    resident_ids = fields.Many2many(
        'res.partner',
        'community_unit_partner_rel',
        'unit_id',
        'partner_id',
        string='住戶',
    )
    office_id = fields.Many2one(
        'community.office',
        string='所屬管理室',
    )
    active = fields.Boolean(string='啟用', default=True)

    _sql_constraints = [
        (
            'unique_unit',
            'UNIQUE(building, floor, number)',
            '同一棟別、樓層、門牌號不可重複！',
        ),
    ]

    @api.depends('building', 'floor', 'number')
    def _compute_name(self):
        for rec in self:
            parts = [rec.building or '', rec.floor or '']
            name = ''.join(parts)
            if rec.number:
                name = f"{name}-{rec.number}"
            rec.name = name
