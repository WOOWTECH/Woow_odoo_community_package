from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CommunityVisitor(models.Model):
    _name = 'community.visitor'
    _description = '訪客主檔'
    _order = 'name'
    _inherit = ['mail.thread']

    name = fields.Char(string='姓名', required=True, tracking=True)
    phone = fields.Char(string='電話', required=True, tracking=True)
    id_last4 = fields.Char(string='證件末4碼', size=4)
    company = fields.Char(string='公司/單位')
    photo = fields.Binary(string='照片', attachment=True)

    # Blacklist
    blacklisted = fields.Boolean(string='黑名單', default=False, tracking=True)
    blacklist_reason = fields.Text(string='黑名單原因')
    blacklist_date = fields.Date(string='加入黑名單日期')

    # Computed
    visit_count = fields.Integer(
        string='來訪次數',
        compute='_compute_visit_stats',
        store=True,
    )
    last_visit = fields.Datetime(
        string='最後來訪',
        compute='_compute_visit_stats',
        store=True,
    )
    visit_ids = fields.One2many(
        'community.visit',
        'visitor_id',
        string='來訪記錄',
    )

    _sql_constraints = [
        (
            'unique_phone',
            'UNIQUE(phone)',
            '此電話號碼已存在！',
        ),
    ]

    @api.depends('visit_ids', 'visit_ids.state')
    def _compute_visit_stats(self):
        for rec in self:
            visits = rec.visit_ids.filtered(
                lambda v: v.state == 'checked_in'
            )
            rec.visit_count = len(visits)
            if visits:
                rec.last_visit = max(visits.mapped('checkin_time') or [False])
            else:
                rec.last_visit = False

    def action_blacklist(self):
        self.ensure_one()
        self.write({
            'blacklisted': True,
            'blacklist_date': fields.Date.today(),
        })

    def action_unblacklist(self):
        self.ensure_one()
        self.write({
            'blacklisted': False,
            'blacklist_reason': False,
            'blacklist_date': False,
        })

    def action_view_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('來訪記錄'),
            'res_model': 'community.visit',
            'view_mode': 'list,form',
            'domain': [('visitor_id', '=', self.id)],
        }
