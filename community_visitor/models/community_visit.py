import secrets
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class CommunityVisit(models.Model):
    _name = 'community.visit'
    _description = '訪問記錄'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='訪問編號',
        readonly=True,
        copy=False,
        default='/',
    )
    visitor_id = fields.Many2one(
        'community.visitor',
        string='訪客',
        required=True,
        ondelete='restrict',
    )
    visit_type = fields.Selection(
        [
            ('walk_in', '臨時訪客'),
            ('pre_registered', '預約訪客'),
            ('recurring', '常態授權'),
        ],
        string='訪問類型',
        required=True,
        default='walk_in',
    )
    unit_id = fields.Many2one(
        'community.unit',
        string='訪問戶號',
        required=True,
    )
    resident_id = fields.Many2one(
        'res.partner',
        string='確認住戶',
        help='實際確認放行的住戶',
    )
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
    appointment_id = fields.Many2one(
        'community.appointment',
        string='預約單',
    )
    guard_in_id = fields.Many2one(
        'res.users',
        string='登記警衛',
        default=lambda self: self.env.user,
    )
    checkin_time = fields.Datetime(string='入場時間')
    state = fields.Selection(
        [
            ('draft', '草稿'),
            ('pending_confirm', '待確認'),
            ('confirmed', '已確認'),
            ('rejected', '已拒絕'),
            ('timeout', '逾時'),
            ('checked_in', '已入場'),
        ],
        string='狀態',
        default='draft',
        tracking=True,
    )
    resident_confirm_time = fields.Datetime(string='住戶確認時間')
    confirm_token = fields.Char(string='確認 Token', copy=False)
    token_expiry = fields.Datetime(string='Token 過期時間')
    badge_number = fields.Char(string='訪客證編號')
    office_id = fields.Many2one(
        'community.office',
        string='管理室',
    )
    note = fields.Text(string='備註')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'community.visit'
                ) or '/'
        return super().create(vals_list)

    def _generate_confirm_token(self):
        """Generate a confirmation token and set expiry (20 minutes)."""
        self.ensure_one()
        token = secrets.token_urlsafe(16)
        self.write({
            'confirm_token': token,
            'token_expiry': fields.Datetime.now() + timedelta(minutes=20),
        })
        return token

    def action_send_confirmation(self):
        """Send confirmation request to all residents of the unit."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('只有草稿狀態的訪問記錄可以發送確認請求。'))

        token = self._generate_confirm_token()
        self.write({'state': 'pending_confirm'})

        # Send notification to all residents of the unit
        residents = self.unit_id.resident_ids.filtered('is_resident')
        if not residents:
            raise UserError(_(
                '戶號 %s 沒有登記住戶，無法發送確認請求。',
                self.unit_id.name,
            ))

        template = self.env.ref(
            'community_visitor.mail_template_visit_confirm_request',
            raise_if_not_found=False,
        )
        if template:
            for resident in residents:
                template.with_context(
                    resident_name=resident.name,
                    confirm_url=self._get_confirm_url(token),
                    reject_url=self._get_reject_url(token),
                ).send_mail(self.id, force_send=False)

    def _get_confirm_url(self, token):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        )
        return f"{base_url}/visitor/confirm/{token}/accept"

    def _get_reject_url(self, token):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        )
        return f"{base_url}/visitor/confirm/{token}/reject"

    def action_confirm(self, token, partner=None):
        """Resident confirms visitor entry."""
        self.ensure_one()
        if self.state != 'pending_confirm':
            raise UserError(_('此訪問記錄不在待確認狀態。'))
        if self.confirm_token != token:
            raise UserError(_('無效的確認碼。'))
        if self.token_expiry and fields.Datetime.now() > self.token_expiry:
            raise UserError(_('確認連結已過期。'))

        vals = {
            'state': 'confirmed',
            'resident_confirm_time': fields.Datetime.now(),
        }
        if partner:
            vals['resident_id'] = partner.id
        self.write(vals)

        # Notify guard via bus.bus
        self._notify_guard('confirmed')

    def action_reject(self, token, partner=None):
        """Resident rejects visitor entry."""
        self.ensure_one()
        if self.state != 'pending_confirm':
            raise UserError(_('此訪問記錄不在待確認狀態。'))
        if self.confirm_token != token:
            raise UserError(_('無效的確認碼。'))

        vals = {'state': 'rejected'}
        if partner:
            vals['resident_id'] = partner.id
        self.write(vals)

        self._notify_guard('rejected')

    def action_checkin(self):
        """Guard confirms visitor has entered."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('只有已確認的訪問記錄可以登記入場。'))
        self.write({
            'state': 'checked_in',
            'checkin_time': fields.Datetime.now(),
        })

    @api.model
    def action_timeout(self):
        """Cron job: timeout visits pending for more than 20 minutes."""
        timeout_visits = self.search([
            ('state', '=', 'pending_confirm'),
            ('token_expiry', '<=', fields.Datetime.now()),
        ])
        for visit in timeout_visits:
            visit.write({'state': 'timeout'})
            visit._notify_guard('timeout')

    def _notify_guard(self, event_type):
        """Send bus.bus notification to the guard who registered the visit."""
        self.ensure_one()
        guard = self.guard_in_id
        if not guard or not guard.partner_id:
            return
        payload = {
            'visit_id': self.id,
            'visit_name': self.name,
            'visitor_name': self.visitor_id.name,
            'unit_name': self.unit_id.name,
            'event': event_type,
        }
        self.env['bus.bus']._sendone(
            guard.partner_id,
            'community_visitor/visit_update',
            payload,
        )
