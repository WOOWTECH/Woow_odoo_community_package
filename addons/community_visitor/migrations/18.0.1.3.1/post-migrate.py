"""Repair known UTC date expressions without replacing customized mail bodies."""
from odoo import api, SUPERUSER_ID
from odoo.addons.community_visitor.migration_utils import repair_mail_body


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    languages = set(env['res.lang'].search([]).mapped('code')) | {'en_US'}
    for name, field in (
        ('visit_confirm_request', 'create_date'),
        ('appointment_visitor_arrived', 'checkin_time'),
    ):
        template = env.ref('community_visitor.mail_template_' + name, raise_if_not_found=False)
        if not template:
            continue
        for language in languages:
            localized = template.with_context(lang=language)
            body = localized.body_html or ''
            updated = repair_mail_body(body, date_fields=(field,))
            if updated != body:
                localized.body_html = updated
