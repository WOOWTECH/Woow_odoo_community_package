from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CommunityParcel(models.Model):
    _name = 'community.parcel'
    _description = '包裹'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'received_date desc, id desc'

    name = fields.Char(
        string='流水編號',
        required=True,
        readonly=True,
        default='New',
        copy=False,
    )
    barcode = fields.Char(string='快遞條碼', index=True)
    resident_id = fields.Many2one(
        'res.partner',
        string='收件住戶',
        required=True,
        domain=[('is_resident', '=', True)],
        tracking=True,
    )
    unit_address = fields.Char(
        string='戶號',
        compute='_compute_unit_address',
        store=True,
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
        tracking=True,
    )
    image = fields.Binary(string='包裹照片', attachment=True)
    received_date = fields.Datetime(
        string='收件時間',
        default=fields.Datetime.now,
        required=True,
    )
    notified_date = fields.Datetime(string='通知時間')
    pickup_date = fields.Datetime(string='取件時間')
    picked_by = fields.Many2one(
        'res.users',
        string='取件確認人員',
    )
    state = fields.Selection(
        [
            ('draft', '待通知'),
            ('notified', '已通知'),
            ('picked_up', '已取件'),
            ('returned', '已退回'),
            ('overdue', '逾期'),
        ],
        string='狀態',
        default='draft',
        required=True,
        tracking=True,
        group_expand='_expand_states',
    )
    note = fields.Text(string='備註')
    office_id = fields.Many2one('community.office', string='管理室')
    color = fields.Integer(string='Color Index')
    is_overdue = fields.Boolean(
        string='逾期',
        compute='_compute_is_overdue',
    )

    _sql_constraints = [
        (
            'unique_barcode',
            'UNIQUE(barcode)',
            '此快遞條碼已存在！',
        ),
    ]

    # ── Sequence ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('community.parcel')
                    or 'New'
                )
        return super().create(vals_list)

    # ── Computed: unit_address ─────────────────────────────────
    @api.depends('resident_id', 'resident_id.unit_ids')
    def _compute_unit_address(self):
        for rec in self:
            if rec.resident_id and rec.resident_id.unit_ids:
                rec.unit_address = ', '.join(
                    rec.resident_id.unit_ids.mapped('name')
                )
            else:
                rec.unit_address = False

    # ── Kanban group_expand ──────────────────────────────────
    @api.model
    def _expand_states(self, states, domain):
        return [key for key, _val in self._fields['state'].selection]

    # ── Computed ─────────────────────────────────────────────
    @api.depends('state', 'notified_date')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state == 'overdue':
                rec.is_overdue = True
            elif rec.state == 'notified' and rec.notified_date:
                delta = now - rec.notified_date
                rec.is_overdue = delta.days >= 7
            else:
                rec.is_overdue = False

    # ── State Machine ────────────────────────────────────────
    def action_notify(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('只有「待通知」的包裹才能發送通知。'))
            rec.write({
                'state': 'notified',
                'notified_date': fields.Datetime.now(),
            })
            template = self.env.ref(
                'community_parcel.mail_template_parcel_arrival',
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(rec.id, force_send=False)

    def action_pickup(self):
        for rec in self:
            if rec.state not in ('notified', 'overdue'):
                raise UserError(_('只有「已通知」或「逾期」的包裹才能確認取件。'))
            rec.write({
                'state': 'picked_up',
                'pickup_date': fields.Datetime.now(),
                'picked_by': self.env.uid,
            })

    def action_return(self):
        for rec in self:
            if rec.state not in ('notified', 'overdue'):
                raise UserError(_('只有「已通知」或「逾期」的包裹才能退回。'))
            rec.write({'state': 'returned'})

    def action_overdue(self):
        for rec in self:
            if rec.state != 'notified':
                raise UserError(_('只有「已通知」的包裹才能標記逾期。'))
            rec.write({'state': 'overdue'})
            template = self.env.ref(
                'community_parcel.mail_template_parcel_overdue',
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(rec.id, force_send=False)

    # ── Cron ─────────────────────────────────────────────────
    @api.model
    def _cron_check_overdue(self):
        """每日檢查逾期包裹：通知超過 7 天未取件自動標為逾期。"""
        threshold = fields.Datetime.now() - timedelta(days=7)
        overdue_parcels = self.search([
            ('state', '=', 'notified'),
            ('notified_date', '<=', threshold),
        ])
        if overdue_parcels:
            overdue_parcels.write({'state': 'overdue'})
            template = self.env.ref(
                'community_parcel.mail_template_parcel_overdue',
                raise_if_not_found=False,
            )
            if template:
                for parcel in overdue_parcels:
                    template.send_mail(parcel.id, force_send=False)
