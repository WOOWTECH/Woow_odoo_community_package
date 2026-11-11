import logging
from datetime import timedelta

from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .notification import send_resident_notification


_logger = logging.getLogger(__name__)


class CommunityParcel(models.Model):
    _name = 'community.parcel'
    _description = '包裹'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'received_date desc, id desc'
    _mail_post_access = 'read'

    name = fields.Char(
        string='流水編號',
        required=True,
        readonly=True,
        default='New',
        copy=False,
    )
    barcode = fields.Char(string='快遞條碼', index=True, copy=False)
    unit_id = fields.Many2one(
        'community.unit',
        string='戶號',
        required=True,
        tracking=True,
    )
    type_id = fields.Many2one(
        'community.parcel.type',
        string='類型',
        tracking=True,
    )
    office_id = fields.Many2one(
        'community.office',
        string='管理室',
        related='unit_id.office_id',
        store=True,
    )
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
            ('scrapped', '已報廢'),
        ],
        string='狀態',
        default='draft',
        required=True,
        tracking=True,
        group_expand='_expand_states',
    )
    courier = fields.Char(string='快遞業者', tracking=True)
    description = fields.Text(string='物品敘述')
    internal_note = fields.Text(string='內部備註', groups='base.group_user')
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
            if 'barcode' in vals:
                vals['barcode'] = (vals['barcode'] or '').strip() or False
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('community.parcel')
                    or 'New'
                )
        return super().create(vals_list)

    def write(self, vals):
        if 'barcode' in vals:
            vals = dict(vals, barcode=(vals['barcode'] or '').strip() or False)
        return super().write(vals)

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
            with self.env.cr.savepoint():
                rec.write({
                    'state': 'notified',
                    'notified_date': fields.Datetime.now(),
                })
                send_resident_notification(
                    rec, 'community_parcel.mail_template_parcel_arrival', required=True,
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
        if self.state != 'draft':
            raise UserError(_('目前狀態不允許現場取件。'))
        with self.env.cr.savepoint():
            self.write({
                'state': 'picked_up',
                'pickup_date': fields.Datetime.now(),
                'picked_by': self.env.uid,
            })
            self.message_post(
                body=_('現場取件：管理室已核對身分並交付物品，未發送取件通知郵件。'),
                subtype_xmlid='mail.mt_note',
            )

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
            send_resident_notification(
                rec, 'community_parcel.mail_template_parcel_overdue',
            )

    def action_scrap(self):
        for rec in self:
            if rec.state in ('picked_up', 'returned', 'scrapped'):
                raise UserError(
                    _('只有未取件的包裹才能報廢（目前狀態：%s）。')
                    % rec.state
                )
        self.write({'state': 'scrapped'})

    # ── Cron ─────────────────────────────────────────────────
    @api.model
    def _cron_check_overdue(self):
        """每日檢查逾期包裹：通知超過 7 天未取件自動標為逾期。"""
        threshold = fields.Datetime.now() - timedelta(days=7)
        overdue_parcels = self.search([
            ('state', '=', 'notified'),
            ('notified_date', '<=', threshold),
        ])
        for parcel in overdue_parcels:
            try:
                # Roll back both the state and any partially queued mail for
                # this parcel. Failed parcels remain eligible for the next run.
                with self.env.cr.savepoint():
                    parcel.action_overdue()
            except (SerializationFailure, DeadlockDetected):
                # Let Odoo retry the whole transaction with a fresh snapshot.
                raise
            except Exception:
                _logger.exception('Could not mark parcel %s overdue; continuing batch', parcel.id)
