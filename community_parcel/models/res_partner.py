from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    unit_address = fields.Char(string='戶號', help='社區住戶門牌戶號')
    is_resident = fields.Boolean(string='社區住戶', default=False)
