from odoo import fields, models


class ParcelQuickRegister(models.TransientModel):
    _name = 'parcel.quick.register'
    _description = '快速包裹登記'

    barcode = fields.Char(string='快遞條碼', required=True)
    unit_id = fields.Many2one(
        'community.unit',
        string='戶號',
        required=True,
    )
    type_id = fields.Many2one(
        'community.parcel.type',
        string='類型',
    )
    description = fields.Text(string='物品敘述')
    auto_notify = fields.Boolean(string='自動通知住戶', default=True)

    def action_register(self):
        """建立包裹並視需要自動通知。"""
        self.ensure_one()
        parcel = self.env['community.parcel'].create({
            'barcode': self.barcode,
            'unit_id': self.unit_id.id,
            'type_id': self.type_id.id if self.type_id else False,
            'description': self.description,
        })
        if self.auto_notify:
            parcel.action_notify()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'community.parcel',
            'res_id': parcel.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_register_and_new(self):
        """建立包裹後開啟新的登記視窗。"""
        self.action_register()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'parcel.quick.register',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_auto_notify': self.auto_notify,
            },
        }
