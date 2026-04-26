from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CommunityAnnouncement(models.Model):
    _name = 'community.announcement'
    _description = '社區公告'
    _inherit = ['mail.thread']
    _order = 'publish_date desc, create_date desc'

    name = fields.Char(string='標題', required=True, tracking=True)
    content = fields.Html(string='公告內容', sanitize_style=True)
    category_id = fields.Many2one(
        'community.announcement.category',
        string='公告分類',
        required=True,
        tracking=True,
    )
    office_id = fields.Many2one(
        'community.office',
        string='發布管理室',
        required=True,
        tracking=True,
    )
    author_id = fields.Many2one(
        'res.users',
        string='發布者',
        default=lambda self: self.env.user,
        readonly=True,
    )
    state = fields.Selection(
        [
            ('draft', '草稿'),
            ('published', '已發布'),
            ('archived', '已下架'),
        ],
        string='狀態',
        default='draft',
        tracking=True,
    )
    publish_date = fields.Datetime(string='發布時間', readonly=True)
    properties = fields.Properties(
        string='屬性',
        definition='office_id.announcement_properties_definition',
    )

    def action_publish(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('只有草稿狀態的公告可以發布。'))
        self.write({
            'state': 'published',
            'publish_date': fields.Datetime.now(),
        })

    def action_archive_announcement(self):
        for rec in self:
            if rec.state != 'published':
                raise UserError(_('只有已發布的公告可以下架。'))
        self.write({'state': 'archived'})

    def action_republish(self):
        for rec in self:
            if rec.state != 'archived':
                raise UserError(_('只有已下架的公告可以重新發布。'))
        self.write({
            'state': 'published',
            'publish_date': fields.Datetime.now(),
        })
