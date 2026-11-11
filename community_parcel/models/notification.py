from odoo import _, tools
from odoo.exceptions import UserError


def send_resident_notification(record, template_xmlid, required=False):
    """Queue native Odoo mail for active residents of this unit only."""
    record.ensure_one()
    record.check_access_rights('write')
    record.check_access_rule('write')
    residents = record.unit_id.resident_ids.filtered(
        lambda partner: partner.active and tools.email_normalize(partner.email)
    )
    template = record.env.ref(template_xmlid, raise_if_not_found=False)
    if not residents or not template:
        if required:
            raise UserError(_('無法通知：請確認戶號有啟用且電子郵件有效的住戶，並已設定通知範本。'))
        return False
    return template.send_mail(record.id, force_send=False, email_values={
        'email_to': False,
        'email_cc': False,
        'recipient_ids': [(6, 0, residents.ids)],
    })
