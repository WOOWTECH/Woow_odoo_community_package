import secrets
from datetime import timedelta

from odoo import models, fields, api, tools, _
from odoo.exceptions import AccessError, UserError


class CommunityVisit(models.Model):
    _name = 'community.visit'
    _description = '訪問記錄'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'

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
        readonly=True,
        help='透過確認連結自動記錄',
    )
    purpose_id = fields.Many2one(
        'community.visit.purpose',
        string='來訪目的',
        required=True,
    )
    appointment_id = fields.Many2one(
        'community.appointment',
        string='預約單',
    )
    guard_in_id = fields.Many2one(
        'res.users',
        string='登記警衛',
        default=lambda self: self.env.user,
    )
    guard_out_id = fields.Many2one(
        'res.users',
        string='離場警衛',
        readonly=True,
    )
    checkin_time = fields.Datetime(string='入場時間')
    checkout_time = fields.Datetime(string='離場時間', readonly=True)
    state = fields.Selection(
        [
            ('draft', '草稿'),
            ('pending_confirm', '待確認'),
            ('confirmed', '已確認'),
            ('rejected', '已拒絕'),
            ('timeout', '逾時'),
            ('checked_in', '已入場'),
            ('checked_out', '已離場'),
        ],
        string='狀態',
        default='draft',
        tracking=True,
    )
    resident_confirm_time = fields.Datetime(string='住戶確認時間')
    confirm_token = fields.Char(string='確認 Token', copy=False)
    token_expiry = fields.Datetime(string='Token 過期時間')
    badge_id = fields.Many2one(
        'community.visitor.badge',
        string='訪客證',
        domain=[('state', '=', 'available')],
    )
    office_id = fields.Many2one(
        'community.office',
        string='管理室',
    )
    vehicle_plate = fields.Char(string='車牌號碼')
    description = fields.Text(string='訪問敘述')
    note = fields.Text(string='內部備註', groups='base.group_user')
    properties = fields.Properties(
        string='屬性',
        definition='office_id.visit_properties_definition',
    )

    # ── CRUD ──────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'community.visit'
                ) or '/'
        # Lock before INSERT obtains FK key-share locks; concurrent creates
        # must not both hold key-share and then try to upgrade to FOR UPDATE.
        badge_ids = sorted({vals['badge_id'] for vals in vals_list if vals.get('badge_id')})
        if badge_ids:
            self.env['community.visitor.badge'].browse(badge_ids)._lock_assignment()
        records = super().create(vals_list)
        for rec in records:
            if rec.badge_id and rec.state not in ('checked_out', 'rejected', 'timeout'):
                rec.badge_id.action_assign(rec)
        return records

    def _lock_for_transition(self):
        self.check_access_rights('write')
        self.check_access_rule('write')
        self.flush_recordset()
        self.env.cr.execute(
            'SELECT id FROM community_visit WHERE id IN %s ORDER BY id FOR UPDATE',
            [tuple(self.ids)],
        )
        self.invalidate_recordset()

    def write(self, vals):
        old_badges = {}
        if 'badge_id' in vals and self:
            self._lock_for_transition()
            old_badges = {rec.id: rec.badge_id for rec in self}
        res = super().write(vals)
        if 'badge_id' in vals:
            for rec in self:
                old_badge = old_badges.get(rec.id)
                if old_badge and old_badge != rec.badge_id:
                    old_badge._release_for_visit(rec)
                if rec.badge_id and rec.state not in ('checked_out', 'rejected', 'timeout'):
                    rec.badge_id.action_assign(rec)
        return res

    # ── Token ─────────────────────────────────────────────

    def _generate_confirm_token(self):
        self.ensure_one()
        token = secrets.token_urlsafe(16)
        self.write({
            'confirm_token': token,
            'token_expiry': fields.Datetime.now() + timedelta(minutes=20),
        })
        return token

    # ── Actions ───────────────────────────────────────────

    def action_send_confirmation(self):
        """發送確認請求給戶號內所有住戶"""
        self.ensure_one()
        self._lock_for_transition()
        if self.state != 'draft':
            raise UserError(_('只有草稿狀態的訪問記錄可以發送確認請求。'))

        residents = self.unit_id.resident_ids.filtered(
            lambda resident: resident.active and resident.is_resident
            and tools.email_normalize(resident.email)
        )
        if not residents:
            raise UserError(_(
                '戶號 %s 沒有已啟用且具有效電子郵件的住戶，請先補齊住戶資料後再發送確認。',
                self.unit_id.name,
            ))
        template = self.env.ref(
            'community_visitor.mail_template_visit_confirm_request',
            raise_if_not_found=False,
        )
        if not template:
            raise UserError(_('找不到訪客確認郵件範本，請聯絡管理員。'))

        with self.env.cr.savepoint():
            token = self._generate_confirm_token()
            self.write({'state': 'pending_confirm'})
            for resident in residents:
                template.with_context(
                    tz=resident.tz or self.env.user.tz or 'UTC',
                    lang=resident.lang or self.env.lang or 'en_US',
                    resident_name=resident.name,
                    resident_email=resident.email,
                    confirm_url=self._get_confirm_url(token),
                    reject_url=self._get_reject_url(token),
                ).send_mail(self.id, force_send=False, email_values={
                    'email_to': False,
                    'email_cc': False,
                    'recipient_ids': [(6, 0, resident.ids)],
                })

    def action_request_portal_confirmation(self):
        """Ask an eligible portal resident to decide; never grant entry here."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group('community_visitor.group_guard'):
            raise AccessError(_('只有警衛或管理員可以送出住戶入口確認。'))
        self._lock_for_transition()
        if self.state != 'draft':
            raise UserError(_('只有草稿狀態的訪問記錄可以發送確認請求。'))
        residents = self.unit_id.resident_ids.sudo().filtered(
            lambda resident: resident.active and resident.is_resident
            and any(user.active and user.has_group('base.group_portal') for user in resident.user_ids)
        )
        if not residents:
            raise UserError(_('戶號內沒有已啟用且具住戶入口帳號的住戶，無法送出入口確認。'))
        with self.env.cr.savepoint():
            self._generate_confirm_token()
            self.write({'state': 'pending_confirm'})
            self.message_post(
                body=_('已送出住戶入口確認，未寄送電子郵件。請住戶登入入口確認或拒絕；尚未授權入場。'),
                subtype_xmlid='mail.mt_note',
            )

    def _get_confirm_url(self, token):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        )
        return f"{base_url}/visitor/confirm/{token}"

    def _get_reject_url(self, token):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        )
        return f"{base_url}/visitor/confirm/{token}"

    def action_confirm(self, token, partner=None):
        """住戶確認訪客入場"""
        self.ensure_one()
        self.env.cr.execute(
            'SELECT id FROM community_visit WHERE id = %s FOR UPDATE',
            [self.id],
        )
        self.invalidate_recordset(['state', 'confirm_token', 'token_expiry'])
        if self.state != 'pending_confirm':
            raise UserError(_('此訪問記錄不在待確認狀態。'))
        if not token or not self.confirm_token or self.confirm_token != token:
            raise UserError(_('無效的確認碼。'))
        if self.token_expiry and fields.Datetime.now() > self.token_expiry:
            raise UserError(_('確認連結已過期。'))

        vals = {
            'state': 'confirmed',
            'resident_confirm_time': fields.Datetime.now(),
        }
        if partner and partner.id in self.unit_id.resident_ids.ids:
            vals['resident_id'] = partner.id
        self.write(vals)
        self._notify_guard('confirmed')

    def action_reject(self, token, partner=None):
        """住戶拒絕訪客入場"""
        self.ensure_one()
        self.env.cr.execute(
            'SELECT id FROM community_visit WHERE id = %s FOR UPDATE',
            [self.id],
        )
        self.invalidate_recordset(['state', 'confirm_token', 'token_expiry'])
        if self.state != 'pending_confirm':
            raise UserError(_('此訪問記錄不在待確認狀態。'))
        if not token or not self.confirm_token or self.confirm_token != token:
            raise UserError(_('無效的確認碼。'))
        if self.token_expiry and fields.Datetime.now() > self.token_expiry:
            raise UserError(_('確認連結已過期。'))

        vals = {'state': 'rejected', 'resident_confirm_time': fields.Datetime.now()}
        if partner and partner.id in self.unit_id.resident_ids.ids:
            vals['resident_id'] = partner.id
        self.write(vals)
        if self.badge_id:
            self.badge_id._release_for_visit(self)
        self._notify_guard('rejected')

    def action_checkin(self):
        """警衛確認訪客已入場"""
        self.ensure_one()
        self._lock_for_transition()
        if self.state != 'confirmed':
            raise UserError(_('只有已確認的訪問記錄可以登記入場。'))
        # Check blacklist before allowing entry
        if self.visitor_id.blacklisted:
            raise UserError(
                _('訪客 %s 已被列入黑名單，無法入場。') % self.visitor_id.name
            )
        if self.badge_id:
            self.badge_id.action_assign(self)
        self.write({
            'state': 'checked_in',
            'checkin_time': fields.Datetime.now(),
        })

    def action_checkout(self):
        """離場登記，自動歸還訪客證"""
        self.ensure_one()
        self._lock_for_transition()
        if self.state != 'checked_in':
            raise UserError(_('只有已入場的訪問記錄可以登記離場。'))
        self.write({
            'state': 'checked_out',
            'checkout_time': fields.Datetime.now(),
            'guard_out_id': self.env.user.id,
        })
        if self.badge_id:
            self.badge_id._release_for_visit(self)

    # ── Cron ──────────────────────────────────────────────

    @api.model
    def action_timeout(self):
        timeout_visits = self.search([
            ('state', '=', 'pending_confirm'),
            ('token_expiry', '<=', fields.Datetime.now()),
        ])
        for visit in timeout_visits:
            visit._lock_for_transition()
            if visit.state != 'pending_confirm' or not visit.token_expiry or visit.token_expiry > fields.Datetime.now():
                continue
            visit.write({'state': 'timeout'})
            if visit.badge_id:
                visit.badge_id._release_for_visit(visit)
            visit._notify_guard('timeout')

    # ── Notification ──────────────────────────────────────

    def _notify_guard(self, event_type):
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
