"""Repair Markup-escaped QWeb nodes and URL-encoded legacy confirmation links."""
from odoo import api, SUPERUSER_ID
from odoo.addons.community_visitor.migration_utils import repair_visitor_mail_templates


def migrate(cr, version):
    repair_visitor_mail_templates(api.Environment(cr, SUPERUSER_ID, {}))
