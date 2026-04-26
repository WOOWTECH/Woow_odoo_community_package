from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VisitorRegisterWizard(models.TransientModel):
    _name = 'visitor.register.wizard'
    _description = '訪客快速登記'

    unit_id = fields.Many2one(
        'community.unit',
        string='訪問戶號',
        required=True,
    )
    visitor_phone = fields.Char(string='訪客電話', required=True)
    visitor_name = fields.Char(string='訪客姓名', required=True)
    id_last4 = fields.Char(string='證件末4碼', size=4)
    purpose = fields.Selection(
        [
            ('visit', '探訪'),
            ('delivery', '送貨'),
            ('repair', '維修'),
            ('business', '商務'),
            ('other', '其他'),
        ],
        string='來訪目的',
        required=True,
        default='visit',
    )
    purpose_note = fields.Text(string='目的說明')
    existing_visitor_id = fields.Many2one(
        'community.visitor',
        string='已知訪客',
        readonly=True,
    )
    is_blacklisted = fields.Boolean(
        string='黑名單',
        related='existing_visitor_id.blacklisted',
    )
    blacklist_reason = fields.Text(
        string='黑名單原因',
        related='existing_visitor_id.blacklist_reason',
    )
    office_id = fields.Many2one(
        'community.office',
        string='管理室',
    )

    # Appointment verification
    access_code = fields.Char(string='預約驗證碼')

    @api.onchange('visitor_phone')
    def _onchange_visitor_phone(self):
        if self.visitor_phone:
            visitor = self.env['community.visitor'].search([
                ('phone', '=', self.visitor_phone),
            ], limit=1)
            if visitor:
                self.existing_visitor_id = visitor.id
                self.visitor_name = visitor.name
                self.id_last4 = visitor.id_last4
            else:
                self.existing_visitor_id = False

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        if self.unit_id and self.unit_id.office_id:
            self.office_id = self.unit_id.office_id.id

    def action_register(self):
        """Register a walk-in visitor."""
        self.ensure_one()

        # Find or create visitor
        visitor = self.existing_visitor_id
        if not visitor:
            visitor = self.env['community.visitor'].create({
                'name': self.visitor_name,
                'phone': self.visitor_phone,
                'id_last4': self.id_last4,
            })
        else:
            # Update id_last4 if provided
            if self.id_last4 and not visitor.id_last4:
                visitor.write({'id_last4': self.id_last4})

        # Check blacklist
        if visitor.blacklisted:
            # Notify office manager
            if self.office_id and self.office_id.responsible_id:
                template = self.env.ref(
                    'community_visitor.mail_template_blacklist_alert',
                    raise_if_not_found=False,
                )
                if template:
                    template.send_mail(visitor.id, force_send=False)

            raise UserError(_(
                '警告：訪客 %s 已被列入黑名單！\n原因：%s\n請通報社區主任。',
                visitor.name,
                visitor.blacklist_reason or '未說明',
            ))

        # Create visit record
        visit = self.env['community.visit'].create({
            'visitor_id': visitor.id,
            'visit_type': 'walk_in',
            'unit_id': self.unit_id.id,
            'purpose': self.purpose,
            'purpose_note': self.purpose_note,
            'guard_in_id': self.env.user.id,
            'office_id': self.office_id.id if self.office_id else False,
        })

        # Send confirmation to residents
        visit.action_send_confirmation()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'community.visit',
            'res_id': visit.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_verify_code(self):
        """Verify an appointment access code."""
        self.ensure_one()
        if not self.access_code:
            raise UserError(_('請輸入預約驗證碼。'))

        result = self.env['community.appointment'].action_validate_appointment(
            self.access_code,
        )

        if not result.get('success'):
            raise UserError(result.get('error', '驗證失敗'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'community.visit',
            'res_id': result['visit_id'],
            'view_mode': 'form',
            'target': 'current',
        }
