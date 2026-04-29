import base64
import secrets
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class CommunityAppointment(models.Model):
    _name = 'community.appointment'
    _description = '預約通行單'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'portal.mixin']

    name = fields.Char(
        string='預約單編號',
        readonly=True,
        copy=False,
        default='/',
    )
    resident_id = fields.Many2one(
        'res.partner',
        string='授權住戶',
        required=True,
    )
    unit_id = fields.Many2one(
        'community.unit',
        string='戶號',
        required=True,
    )
    allowed_resident_ids = fields.Many2many(
        related='unit_id.resident_ids',
    )
    visitor_id = fields.Many2one(
        'community.visitor',
        string='訪客',
        required=True,
        ondelete='restrict',
    )
    valid_from = fields.Datetime(string='有效起始', required=True)
    valid_until = fields.Datetime(string='有效截止', required=True)
    access_token = fields.Char(
        string='驗證碼',
        readonly=True,
        copy=False,
    )
    qr_code = fields.Binary(
        string='QR Code',
        compute='_compute_qr_code',
        store=True,
    )
    appointment_type = fields.Selection(
        [
            ('one_time', '一次性'),
            ('recurring', '週期性'),
        ],
        string='類型',
        required=True,
        default='one_time',
    )
    # Recurring day booleans
    mon = fields.Boolean(string='一')
    tue = fields.Boolean(string='二')
    wed = fields.Boolean(string='三')
    thu = fields.Boolean(string='四')
    fri = fields.Boolean(string='五')
    sat = fields.Boolean(string='六')
    sun = fields.Boolean(string='日')
    recurring_from = fields.Float(string='每日起始時間')
    recurring_until = fields.Float(string='每日截止時間')
    state = fields.Selection(
        [
            ('active', '有效'),
            ('expired', '已過期'),
            ('cancelled', '已撤銷'),
        ],
        string='狀態',
        default='active',
        tracking=True,
    )
    visit_ids = fields.One2many(
        'community.visit',
        'appointment_id',
        string='入場記錄',
    )
    purpose_id = fields.Many2one(
        'community.visit.purpose',
        string='來訪目的',
    )
    description = fields.Text(string='來訪敘述')
    note = fields.Text(string='內部備註')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'community.appointment'
                ) or '/'
            if not vals.get('access_token'):
                vals['access_token'] = secrets.token_hex(3).upper()
        return super().create(vals_list)

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        if self.unit_id and self.resident_id:
            if self.resident_id not in self.unit_id.resident_ids:
                self.resident_id = False

    @api.depends('access_token')
    def _compute_qr_code(self):
        for rec in self:
            if rec.access_token:
                try:
                    barcode_value = rec.access_token
                    qr_png = self.env['ir.actions.report'].barcode(
                        barcode_type='QR',
                        value=barcode_value,
                        width=200,
                        height=200,
                    )
                    rec.qr_code = base64.b64encode(qr_png)
                except Exception:
                    rec.qr_code = False
            else:
                rec.qr_code = False

    @api.constrains('valid_from', 'valid_until')
    def _check_dates(self):
        for rec in self:
            if rec.valid_from and rec.valid_until:
                if rec.valid_from >= rec.valid_until:
                    raise ValidationError(
                        _('有效截止時間必須晚於有效起始時間。')
                    )

    @api.constrains('recurring_from', 'recurring_until')
    def _check_recurring_times(self):
        for rec in self:
            if rec.appointment_type == 'recurring':
                if rec.recurring_from and rec.recurring_until:
                    if rec.recurring_from >= rec.recurring_until:
                        raise ValidationError(
                            _('每日截止時間必須晚於每日起始時間。')
                        )

    def action_validate_appointment(self, code):
        """Validate an appointment access code and create a visit if valid."""
        appointment = self.search([
            ('access_token', '=', code.upper()),
            ('state', '=', 'active'),
        ], limit=1)

        if not appointment:
            return {'success': False, 'error': '無效的驗證碼或預約已失效。'}

        now = fields.Datetime.now()

        # Check date range
        if now < appointment.valid_from or now > appointment.valid_until:
            return {'success': False, 'error': '預約不在有效期間內。'}

        # Check recurring schedule
        if appointment.appointment_type == 'recurring':
            if not appointment._check_recurring_schedule(now):
                return {
                    'success': False,
                    'error': '目前不在授權的時間範圍內。',
                }

        visitor = appointment.visitor_id

        # Check blacklist
        if visitor.blacklisted:
            return {
                'success': False,
                'error': f'訪客 {visitor.name} 已被列入黑名單。',
            }

        # Create visit record
        visit = self.env['community.visit'].create({
            'visitor_id': visitor.id,
            'visit_type': (
                'recurring'
                if appointment.appointment_type == 'recurring'
                else 'pre_registered'
            ),
            'unit_id': appointment.unit_id.id,
            'resident_id': appointment.resident_id.id,
            'purpose_id': appointment.purpose_id.id if appointment.purpose_id else False,
            'description': appointment.description,
            'note': appointment.note,
            'appointment_id': appointment.id,
            'guard_in_id': self.env.user.id,
            'checkin_time': now,
            'state': 'checked_in',
            'office_id': appointment.unit_id.office_id.id,
        })

        # Notify resident
        template = self.env.ref(
            'community_visitor.mail_template_appointment_visitor_arrived',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(visit.id, force_send=False)

        return {
            'success': True,
            'visitor_name': visitor.name,
            'resident_name': appointment.resident_id.name,
            'unit_name': appointment.unit_id.name,
            'visit_id': visit.id,
        }

    def _check_recurring_schedule(self, now):
        """Check if current time falls within recurring schedule."""
        self.ensure_one()

        # Map Python weekday (0=Monday..6=Sunday) to Boolean fields
        day_map = {
            0: self.mon,
            1: self.tue,
            2: self.wed,
            3: self.thu,
            4: self.fri,
            5: self.sat,
            6: self.sun,
        }

        # If no day is checked, allow any day
        if not any(day_map.values()):
            return True

        # Convert to local timezone for day-of-week and time checks
        import pytz
        local_tz = pytz.timezone(
            self.env.user.tz or self.env.context.get('tz') or 'UTC'
        )
        if now.tzinfo is None:
            now = pytz.utc.localize(now)
        local_now = now.astimezone(local_tz)

        if not day_map.get(local_now.weekday(), False):
            return False

        if self.recurring_from and self.recurring_until:
            current_hour = local_now.hour + local_now.minute / 60.0
            if (
                current_hour < self.recurring_from
                or current_hour > self.recurring_until
            ):
                return False

        return True

    @api.model
    def action_check_expiry(self):
        """Cron job: expire appointments past their valid_until date."""
        expired = self.search([
            ('state', '=', 'active'),
            ('valid_until', '<', fields.Datetime.now()),
        ])
        expired.write({'state': 'expired'})

    def action_cancel(self):
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('只有有效的預約單可以撤銷。'))
        self.write({'state': 'cancelled'})

    def _compute_access_url(self):
        for rec in self:
            rec.access_url = f"/my/appointments/{rec.id}"

    def action_view_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('入場記錄'),
            'res_model': 'community.visit',
            'view_mode': 'list,form',
            'domain': [('appointment_id', '=', self.id)],
        }
