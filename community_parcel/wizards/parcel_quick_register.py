from odoo import fields, models


class ParcelQuickRegister(models.TransientModel):
    _name = 'parcel.quick.register'
    _description = '快速包裹登記'

    barcode = fields.Char(string='快遞條碼', required=True)
    resident_id = fields.Many2one(
        'res.partner',
        string='收件住戶',
        required=True,
        domain=[('is_resident', '=', True)],
    )
    parcel_type = fields.Selection(
        [
            ('parcel', '包裹'),
            ('letter', '信件'),
            ('registered', '掛號'),
            ('other', '其他'),
        ],
        string='類型',
        default='parcel',
        required=True,
    )
    office_id = fields.Many2one('community.office', string='管理室')
    image = fields.Binary(string='包裹照片')
    note = fields.Text(string='備註')
    auto_notify = fields.Boolean(string='自動通知住戶', default=True)

    def action_register(self):
        """建立包裹並視需要自動通知。"""
        self.ensure_one()
        parcel = self.env['community.parcel'].create({
            'barcode': self.barcode,
            'resident_id': self.resident_id.id,
            'parcel_type': self.parcel_type,
            'office_id': self.office_id.id if self.office_id else False,
            'image': self.image,
            'note': self.note,
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
        """建立包裹後開啟新的登記視窗（保留管理室設定）。"""
        self.action_register()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'parcel.quick.register',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_office_id': self.office_id.id if self.office_id else False,
                'default_auto_notify': self.auto_notify,
            },
        }
