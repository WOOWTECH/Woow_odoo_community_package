from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .notification import send_resident_notification


class CommunityStorage(models.Model):
    _name = 'community.storage'
    _description = '寄放物品'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deposit_date desc, id desc'
    _mail_post_access = 'read'

    name = fields.Char(
        string='寄放編號',
        required=True,
        readonly=True,
        default='New',
        copy=False,
    )
    unit_id = fields.Many2one(
        'community.unit',
        string='戶號',
        required=True,
        tracking=True,
    )
    recipient_name = fields.Char(
        string='取件人',
        tracking=True,
    )
    type_id = fields.Many2one(
        'community.storage.type',
        string='類型',
        tracking=True,
    )
    office_id = fields.Many2one(
        'community.office',
        string='管理室',
        related='unit_id.office_id',
        store=True,
    )
    storage_location = fields.Char(string='寄放位置/格號')
    deposit_date = fields.Datetime(
        string='寄放時間',
        default=fields.Datetime.now,
        required=True,
    )
    expected_pickup = fields.Date(string='預計取件日')
    actual_pickup = fields.Datetime(string='實際取件時間')
    picked_by = fields.Many2one('res.users', string='交付確認人員', readonly=True, copy=False)
    state = fields.Selection(
        [
            ('pending', '待接收'),
            ('storing', '保管中'),
            ('ready', '待取件'),
            ('done', '已完成'),
            ('scrapped', '已報廢'),
        ],
        string='狀態',
        default='pending',
        required=True,
        tracking=True,
        group_expand='_expand_states',
    )
    item_description = fields.Text(string='物品敘述')
    internal_note = fields.Text(string='內部備註', groups='base.group_user')
    color = fields.Integer(string='Color Index')

    # ── Sequence ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('community.storage')
                    or 'New'
                )
        return super().create(vals_list)

    # ── Kanban group_expand ──────────────────────────────────
    @api.model
    def _expand_states(self, states, domain):
        return [key for key, _val in self._fields['state'].selection]

    # ── State Machine ────────────────────────────────────────
    def action_accept(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('只有「待接收」的物品才能受理。'))
            rec.write({'state': 'storing'})

    def action_ready(self):
        for rec in self:
            if rec.state != 'storing':
                raise UserError(_('只有「保管中」的物品才能標記為待取件。'))
            with self.env.cr.savepoint():
                rec.write({'state': 'ready'})
                send_resident_notification(
                    rec, 'community_parcel.mail_template_storage_ready', required=True,
                )

    def action_pickup_onsite(self):
        """Staff handover without claiming that an email notification was sent."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group(
            'community_parcel.community_parcel_group_office_staff'
        ):
            raise AccessError(_('只有管理室人員可以確認現場取件。'))
        self.check_access_rights('write')
        self.check_access_rule('write')
        if self.state != 'storing':
            raise UserError(_('目前狀態不允許現場取件。'))
        with self.env.cr.savepoint():
            self.write({
                'state': 'done',
                'actual_pickup': fields.Datetime.now(),
                'picked_by': self.env.uid,
            })
            self.message_post(
                body=_('現場取件：管理室已核對身分並交付物品，未發送取件通知郵件。'),
                subtype_xmlid='mail.mt_note',
            )

    def action_done(self):
        for rec in self:
            if rec.state != 'ready':
                raise UserError(_('只有「待取件」的物品才能完成交付。'))
            rec.write({
                'state': 'done',
                'actual_pickup': fields.Datetime.now(),
                'picked_by': self.env.uid,
            })

    def action_scrap(self):
        for rec in self:
            if rec.state not in ('storing', 'ready'):
                raise UserError(
                    _('只有「保管中」或「待取件」的寄放物品才能報廢'
                      '（目前狀態：%s）。') % rec.state
                )
        self.write({'state': 'scrapped'})
