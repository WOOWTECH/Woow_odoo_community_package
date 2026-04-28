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
    visitor_name = fields.Char(string='訪客姓名', required=True)
    visitor_phone = fields.Char(string='訪客電話', required=True)
    valid_from = fields.Datetime(string='有效起始', required=True)
    valid_until = fields.Datetime(string='有效截止', required=True)
    max_entries = fields.Integer(
        string='最大入場次數',
        default=1,
        help='0 表示無限次',
    )
    used_entries = fields.Integer(
        string='已使用次數',
        compute='_compute_used_entries',
        store=True,
    )
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
            ('permanent', '永久'),
        ],
        string='類型',
        required=True,
        default='one_time',
    )
    recurring_days = fields.Char(
        string='授權星期',
        help='以逗號分隔的星期數字（0=週一, 6=週日），例如 0,1,2,3,4',
    )
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
    purpose = fields.Text(string='授權目的')

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

    @api.depends('visit_ids', 'visit_ids.state')
    def _compute_used_entries(self):
        for rec in self:
            rec.used_entries = len(
                rec.visit_ids.filtered(lambda v: v.state == 'checked_in')
            )

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

        # Check remaining entries
        if (
            appointment.max_entries > 0
            and appointment.used_entries >= appointment.max_entries
        ):
            return {'success': False, 'error': '入場次數已用完。'}

        # Find or create visitor
        visitor = self.env['community.visitor'].search([
            ('phone', '=', appointment.visitor_phone),
        ], limit=1)
        if not visitor:
            visitor = self.env['community.visitor'].create({
                'name': appointment.visitor_name,
                'phone': appointment.visitor_phone,
            })

        # Check blacklist
        if visitor.blacklisted:
            return {
                'success': False,
                'error': f'訪客 {visitor.name} 已被列入黑名單。',
            }

        # Find default purpose
        default_purpose = self.env['community.visit.purpose'].search(
            [], limit=1,
        )

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
            'purpose_id': default_purpose.id if default_purpose else False,
            'description': appointment.purpose,
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

        remaining = (
            '無限'
            if appointment.max_entries == 0
            else str(appointment.max_entries - appointment.used_entries)
        )

        return {
            'success': True,
            'visitor_name': visitor.name,
            'resident_name': appointment.resident_id.name,
            'unit_name': appointment.unit_id.name,
            'remaining': remaining,
            'visit_id': visit.id,
        }

    def _check_recurring_schedule(self, now):
        """Check if current time falls within recurring schedule."""
        self.ensure_one()
        if not self.recurring_days:
            return True

        # Convert to local timezone for day-of-week and time checks
        import pytz
        local_tz = pytz.timezone(
            self.env.user.tz or self.env.context.get('tz') or 'UTC'
        )
        if now.tzinfo is None:
            now = pytz.utc.localize(now)
        local_now = now.astimezone(local_tz)

        # Python weekday: 0=Monday, 6=Sunday
        allowed_days = [
            int(d.strip()) for d in self.recurring_days.split(',') if d.strip()
        ]
        if local_now.weekday() not in allowed_days:
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
            ('appointment_type', '!=', 'permanent'),
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
