from odoo import models, fields, _


class ValidateAppointmentWizard(models.TransientModel):
    _name = 'validate.appointment.wizard'
    _description = '驗證碼查驗'

    access_code = fields.Char(string='驗證碼')
    state = fields.Selection(
        [
            ('input', '輸入'),
            ('success', '成功'),
            ('fail', '失敗'),
        ],
        default='input',
    )
    result_message = fields.Text(string='結果', readonly=True)
    visit_id = fields.Many2one(
        'community.visit',
        string='訪問記錄',
        readonly=True,
    )
    visitor_name = fields.Char(string='訪客姓名', readonly=True)
    unit_name = fields.Char(string='訪問戶號', readonly=True)
    remaining = fields.Char(string='剩餘次數', readonly=True)

    def action_validate(self):
        """驗證預約通行碼"""
        self.ensure_one()
        if not self.access_code:
            self.write({
                'state': 'fail',
                'result_message': '請輸入驗證碼。',
            })
            return self._reopen()

        result = self.env['community.appointment'].action_validate_appointment(
            self.access_code.strip(),
        )

        if result.get('success'):
            self.write({
                'state': 'success',
                'result_message': '驗證成功！訪客已入場。',
                'visit_id': result.get('visit_id'),
                'visitor_name': result.get('visitor_name'),
                'unit_name': result.get('unit_name'),
                'remaining': result.get('remaining'),
            })
        else:
            self.write({
                'state': 'fail',
                'result_message': result.get('error', '驗證失敗。'),
            })

        return self._reopen()

    def action_reset(self):
        """重新輸入"""
        self.ensure_one()
        self.write({
            'state': 'input',
            'access_code': False,
            'result_message': False,
            'visit_id': False,
            'visitor_name': False,
            'unit_name': False,
            'remaining': False,
        })
        return self._reopen()

    def action_open_visit(self):
        """前往訪問記錄"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('訪問記錄'),
            'res_model': 'community.visit',
            'res_id': self.visit_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _reopen(self):
        """重新開啟 wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('驗證碼查驗'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
