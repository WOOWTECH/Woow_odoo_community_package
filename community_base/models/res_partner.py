from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    unit_ids = fields.Many2many(
        'community.unit',
        'community_unit_partner_rel',
        'partner_id',
        'unit_id',
        string='戶號',
    )
    is_resident = fields.Boolean(string='社區住戶', default=False)
