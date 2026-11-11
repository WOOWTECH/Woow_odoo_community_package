"""Preserve legacy executor timezone behavior and repair known mail expressions."""
from odoo import api, SUPERUSER_ID
from odoo.addons.community_visitor.migration_utils import repair_mail_body


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Odoo initially fills a new column using its default. Existing authorizations
    # must instead retain the old guard/context-dependent timezone semantics.
    env['community.appointment'].search([]).write({'schedule_tz': False})

    # These templates are noupdate. Keep customized content and translations;
    # only replace the known broken inline expressions in the HTML body.
    expressions = (
        'object.visitor_id.name', 'object.purpose_id.name', 'object.unit_id.name',
        'object.create_date', 'object.checkin_time', 'object.name', 'object.phone',
        "object.blacklist_reason or '未說明'", 'object.blacklist_date',
    )
    languages = set(env['res.lang'].search([]).mapped('code')) | {'en_US'}
    for name in ('visit_confirm_request', 'appointment_visitor_arrived', 'blacklist_alert'):
        template = env.ref('community_visitor.mail_template_' + name, raise_if_not_found=False)
        if not template:
            continue
        for language in languages:
            localized = template.with_context(lang=language)
            body = localized.body_html or ''
            updated = repair_mail_body(body, expressions=expressions, repair_links=True)
            if updated != body:
                localized.body_html = updated
