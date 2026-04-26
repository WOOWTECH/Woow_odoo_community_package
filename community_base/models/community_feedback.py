from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CommunityFeedback(models.Model):
    _name = 'community.feedback'
    _description = '意見反映'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(
        string='編號',
        readonly=True,
        copy=False,
        default='/',
    )
    title = fields.Char(string='標題', required=True, tracking=True)
    content = fields.Text(string='內容', required=True)
    category_id = fields.Many2one(
        'community.feedback.category',
        string='意見類別',
        required=True,
        tracking=True,
    )
    unit_id = fields.Many2one(
        'community.unit',
        string='戶號',
        required=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='提交住戶',
        default=lambda self: self.env.user.partner_id,
        readonly=True,
    )
    office_id = fields.Many2one(
        'community.office',
        string='管理室',
        related='unit_id.office_id',
        store=True,
    )
    state = fields.Selection(
        [
            ('pending', '待處理'),
            ('in_progress', '處理中'),
            ('done', '已結案'),
        ],
        string='狀態',
        default='pending',
        tracking=True,
    )
    properties = fields.Properties(
        string='屬性',
        definition='office_id.feedback_properties_definition',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'community.feedback'
                ) or '/'
        return super().create(vals_list)

    def action_accept(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('只有待處理的反映可以接受處理。'))
        self.write({'state': 'in_progress'})

    def action_done(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('只有處理中的反映可以結案。'))
        self.write({'state': 'done'})

    def action_reopen(self):
        for rec in self:
            if rec.state != 'done':
                raise UserError(_('只有已結案的反映可以重新開啟。'))
        self.write({'state': 'in_progress'})
