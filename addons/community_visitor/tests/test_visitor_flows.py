from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import urlsplit

import pytz
from lxml import html
from markupsafe import Markup

from odoo import fields
from odoo.tools import format_datetime
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.community_visitor.controllers.portal import VisitorPortal
from odoo.addons.community_visitor.migration_utils import repair_mail_body, repair_visitor_mail_templates


class VisitorFlowFixtures:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resident = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Visitor flow resident', 'login': 'visitor-flow@example.test',
            'password': 'visitor-flow-password', 'tz': 'Asia/Taipei',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.unit = cls.env['community.unit'].create({
            'building': 'Visitor flow', 'floor': '1', 'number': '1',
            'resident_ids': [(4, cls.resident.partner_id.id)],
        })
        cls.visitor = cls.env['community.visitor'].create({
            'name': 'Flow guest', 'phone': '0912345678',
        })
        cls.purpose = cls.env['community.visit.purpose'].create({'name': 'Flow purpose'})

    def _visit(self, **values):
        return self.env['community.visit'].create({
            'visitor_id': self.visitor.id, 'unit_id': self.unit.id,
            'purpose_id': self.purpose.id, **values,
        })

    def _appointment(self, **values):
        return self.env['community.appointment'].create({
            'resident_id': self.resident.partner_id.id, 'unit_id': self.unit.id,
            'visitor_name': self.visitor.name, 'visitor_phone': self.visitor.phone,
            'valid_from': fields.Datetime.now() - timedelta(hours=1),
            'valid_until': fields.Datetime.now() + timedelta(days=1),
            **values,
        })


@tagged('community_visitor_flow')
class TestVisitorFlows(VisitorFlowFixtures, TransactionCase):
    def test_local_datetime_and_dst(self):
        parse = VisitorPortal._local_datetime_to_utc
        self.assertEqual(parse('2030-01-02T09:30', 'Asia/Taipei'), datetime(2030, 1, 2, 1, 30))
        with self.assertRaises(pytz.NonExistentTimeError):
            parse('2030-03-10T02:30', 'America/New_York')
        with self.assertRaises(pytz.AmbiguousTimeError):
            parse('2030-11-03T01:30', 'America/New_York')
        with self.assertRaises(ValueError):
            VisitorPortal._parse_time_to_float('12:99')

    def test_recurring_midnight_without_days_uses_pinned_timezone(self):
        appointment = self._appointment(
            appointment_type='recurring', schedule_tz='Asia/Taipei',
            recurring_from=0, recurring_until=1, recurring_days=False,
        )
        appointment = appointment.with_context(tz='America/New_York')
        self.assertTrue(appointment._check_recurring_schedule(datetime(2030, 1, 1, 16, 30)))
        self.assertFalse(appointment._check_recurring_schedule(datetime(2030, 1, 1, 17)))
        self.assertFalse(appointment._check_recurring_schedule(datetime(2030, 1, 1, 15, 30)))
        appointment.recurring_days = '2'  # Wednesday Jan 2 in Taipei, Tuesday in UTC
        self.assertTrue(appointment._check_recurring_schedule(datetime(2030, 1, 1, 16, 30)))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            appointment.write({'recurring_from': 25, 'recurring_until': 26})

    def test_legacy_recurring_schedule_preserves_executor_timezone_precedence(self):
        guards = self.env['res.users'].with_context(no_reset_password=True).create([
            {'name': 'Timezone guard ' + suffix, 'login': 'visitor-tz-' + suffix + '@example.test',
             'tz': timezone,
             'groups_id': [(6, 0, [self.env.ref('community_visitor.group_guard').id])]}
            for suffix, timezone in (('taipei', 'Asia/Taipei'), ('utc', 'UTC'), ('unset', False))
        ])
        appointment = self._appointment(
            appointment_type='recurring', schedule_tz=False, recurring_days='2',
            recurring_from=0, recurring_until=1,
        )
        now = datetime(2030, 1, 1, 16, 30)  # Wednesday 00:30 in Taipei, Tuesday UTC.
        self.assertTrue(appointment.with_user(guards[0]).with_context(tz='UTC')._check_recurring_schedule(now))
        self.assertFalse(appointment.with_user(guards[1]).with_context(tz='Asia/Taipei')._check_recurring_schedule(now))
        self.assertTrue(appointment.with_user(guards[2]).with_context(tz='Asia/Taipei')._check_recurring_schedule(now))
        self.assertFalse(appointment.with_user(guards[2]).with_context(tz=False)._check_recurring_schedule(now))
        appointment.schedule_tz = 'Asia/Taipei'
        self.assertTrue(appointment.with_user(guards[1]).with_context(tz='UTC')._check_recurring_schedule(now))
        self.env.user.tz = 'Asia/Taipei'
        created = self._appointment(appointment_type='recurring')
        self.assertEqual(created.schedule_tz, 'Asia/Taipei')
        self.env.user.tz = 'UTC'
        self.assertEqual(created.schedule_tz, 'Asia/Taipei')

    def test_code_redemption_and_reentry(self):
        appointment = self._appointment(max_entries=2)
        redeem = self.env['community.appointment'].action_validate_appointment
        self.assertFalse(redeem(False)['success'])
        self.assertFalse(redeem('   ')['success'])
        result = redeem(' ' + appointment.access_token.lower() + '\n')
        self.assertTrue(result['success'])
        self.assertFalse(redeem(appointment.access_token)['success'])
        visit = self.env['community.visit'].browse(result['visit_id'])
        visit.action_checkout()
        self.assertTrue(redeem(appointment.access_token)['success'])
        appointment.visit_ids.filtered(lambda v: v.state == 'checked_in').action_checkout()
        self.assertFalse(redeem(appointment.access_token)['success'])
        self.assertEqual(appointment.used_entries, 2)
        with self.assertRaises(AccessError):
            self.env['community.appointment'].with_user(self.resident).action_validate_appointment(
                appointment.access_token,
            )

    def test_all_types_keep_explicit_unlimited_entries_and_wizard_retry(self):
        for kind in ('one_time', 'recurring', 'permanent'):
            appointment = self._appointment(appointment_type=kind, max_entries=0)
            wizard = self.env['validate.appointment.wizard'].create({'access_code': appointment.access_token})
            wizard.action_validate()
            self.assertEqual(wizard.state, 'success')
            original_visit = wizard.visit_id
            wizard.action_validate()
            self.assertEqual(wizard.visit_id, original_visit)
            self.assertEqual(appointment.used_entries, 1)
            original_visit.action_checkout()
            wizard.action_reset()
            wizard.access_code = appointment.access_token
            wizard.action_validate()
            self.assertEqual(wizard.state, 'success')
            self.assertEqual(appointment.used_entries, 2)

    def test_guard_expired_code_returns_feedback_without_write_acl(self):
        guard = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Flow guard', 'login': 'flow-guard@example.test',
            'groups_id': [(6, 0, [self.env.ref('community_visitor.group_guard').id])],
        })
        appointment = self._appointment()
        with patch.object(fields.Datetime, 'now', return_value=appointment.valid_until + timedelta(seconds=1)):
            result = self.env['community.appointment'].with_user(guard).action_validate_appointment(
                appointment.access_token,
            )
        self.assertFalse(result['success'])
        self.assertEqual(appointment.state, 'active')

    def test_missing_purpose_does_not_create_partial_visit(self):
        appointment = self._appointment()
        with patch.object(type(self.purpose), 'search', return_value=self.purpose.browse()):
            result = self.env['community.appointment'].action_validate_appointment(appointment.access_token)
        self.assertFalse(result['success'])
        self.assertFalse(appointment.visit_ids)

    def test_badge_reuse_historical_checkout_and_reassignment(self):
        badge = self.env['community.visitor.badge'].create({'name': 'FLOW-01'})
        first = self._visit(state='checked_in', badge_id=badge.id)
        badge.action_assign(first)  # A duplicate call must not fail or reassign.
        badge.action_release()
        second = self._visit(state='checked_in', badge_id=badge.id)
        first.action_checkout()  # Its historical badge now belongs to second.
        self.assertEqual(badge.current_visit_id, second)
        first.badge_id = False
        self.assertEqual(badge.current_visit_id, second)
        with self.assertRaises(UserError), self.cr.savepoint():
            self._visit(badge_id=badge.id)
        second.action_checkout()
        self.assertEqual(badge.state, 'available')
        with self.assertRaises(UserError):
            second.action_checkout()

    def test_reject_and_timeout_release_badges_and_cannot_be_replayed(self):
        for action in ('reject', 'timeout'):
            badge = self.env['community.visitor.badge'].create({'name': 'FLOW-' + action})
            visit = self._visit(
                state='pending_confirm', badge_id=badge.id, confirm_token='flow-' + action,
                token_expiry=fields.Datetime.now() + timedelta(minutes=20),
            )
            if action == 'reject':
                visit.action_reject(visit.confirm_token, partner=self.resident.partner_id)
                self.assertTrue(visit.resident_confirm_time)
                self.assertEqual(visit.resident_id, self.resident.partner_id)
            else:
                visit.token_expiry = fields.Datetime.now() - timedelta(seconds=1)
                visit.action_timeout()
            self.assertEqual(badge.state, 'available')
            with self.assertRaises(UserError):
                visit.action_confirm(visit.confirm_token)
            with self.assertRaises(UserError):
                visit.action_checkin()

    def test_confirm_checkin_and_empty_token(self):
        visit = self._visit(state='pending_confirm')
        with self.assertRaises(UserError):
            visit.action_confirm(False)
        token = visit._generate_confirm_token()
        visit.action_confirm(token, partner=self.resident.partner_id)
        visit.action_checkin()
        original_time = visit.checkin_time
        with self.assertRaises(UserError):
            visit.action_checkin()
        self.assertEqual(visit.checkin_time, original_time)

    def test_confirmation_without_valid_recipient_keeps_draft(self):
        partner = self.env['res.partner'].create({'name': 'Recipient eligibility fixture'})
        self.unit.resident_ids = partner
        for values in ({'is_resident': True, 'email': False},
                       {'email': 'invalid'},
                       {'email': 'resident@example.test', 'active': False},
                       {'active': True, 'is_resident': False}):
            partner.write(values)
            visit = self._visit()
            with self.assertRaises(UserError):
                visit.action_send_confirmation()
            self.assertEqual(visit.state, 'draft')
            self.assertFalse(visit.confirm_token)
            self.assertFalse(visit.token_expiry)
            self.assertFalse(self.env['mail.mail'].search([
                ('model', '=', visit._name), ('res_id', '=', visit.id),
            ]))

    def test_confirmation_queues_one_native_mail_per_valid_resident(self):
        self.resident.partner_id.write({'is_resident': True, 'email': 'first@example.test'})
        second = self.env['res.partner'].create({
            'name': 'Second resident', 'is_resident': True, 'email': 'second@example.test',
        })
        invalid = self.env['res.partner'].create({
            'name': 'Invalid email', 'is_resident': True, 'email': 'invalid',
        })
        self.unit.write({'resident_ids': [(4, second.id), (4, invalid.id)]})
        visit = self._visit()
        visit.action_send_confirmation()
        self.assertEqual(visit.state, 'pending_confirm')
        mails = self.env['mail.mail'].search([('model', '=', visit._name), ('res_id', '=', visit.id)])
        self.assertEqual(len(mails), 2)
        self.assertEqual(set(mails.mapped('recipient_ids').ids), {self.resident.partner_id.id, second.id})
        for mail in mails:
            self.assertEqual(mail.state, 'outgoing')
            self.assertEqual(len(mail.recipient_ids), 1)
            self.assertFalse(mail.email_to)
            self.assertFalse(mail.email_cc)
            self.assertNotIn('{{', mail.body_html)
            self.assertNotIn('}}', mail.body_html)
            self.assertIn(self.visitor.name, mail.body_html)
            links = html.fromstring(mail.body_html).xpath('//a/@href')
            self.assertEqual(len(links), 2)
            self.assertTrue(all(urlsplit(link).path == '/visitor/confirm/' + visit.confirm_token for link in links))

    def test_mail_migration_preserves_qweb_attributes_and_custom_markup(self):
        body = """<div data-label="{{ object.visitor_id.name }}">
<a t-attf-href="/custom/{{ object.id }}?name={{ object.visitor_id.name }}">{{ object.visitor_id.name }}</a>
<a t-attf-href="{{ ctx.get('confirm_url', '#') }}">Custom link</a>
<a href="{{ ctx.get('reject_url', '#') }}">Reject</a>
<span title="{{ object.create_date }}">{{ object.create_date }}</span>
<t t-out="object.checkin_time"/>
<!-- {{ object.visitor_id.name }} -->
<script>var text = "{{ object.visitor_id.name }}";</script></div>"""
        def upgrade(value):
            value = repair_mail_body(value, expressions=('object.visitor_id.name', 'object.create_date'), repair_links=True)
            return repair_mail_body(value, date_fields=('create_date', 'checkin_time'))
        updated = upgrade(Markup(body))
        self.assertEqual(upgrade(updated), updated)
        document = html.fromstring(updated)
        self.assertEqual(document.get('data-label'), '{{ object.visitor_id.name }}')
        self.assertEqual(document.xpath('//a')[0].get('t-attf-href'), '/custom/{{ object.id }}?name={{ object.visitor_id.name }}')
        self.assertEqual(document.xpath('//a')[1].get('t-attf-href'), "{{ ctx.get('confirm_url', '#') }}")
        self.assertEqual(document.xpath('//a')[2].get('t-att-href'), "ctx.get('reject_url', '#')")
        self.assertEqual(document.xpath('//span')[0].get('title'), '{{ object.create_date }}')
        self.assertIn('<!-- {{ object.visitor_id.name }} -->', updated)
        self.assertIn('var text = "{{ object.visitor_id.name }}";', updated)
        self.assertEqual(len(document.xpath('//t[starts-with(@t-out, "format_datetime(")]')), 2)

    def test_migrated_custom_mail_renders_link_and_local_date(self):
        visit = self._visit(checkin_time=datetime(2035, 1, 2, 1, 30))
        template = self.env.ref('community_visitor.mail_template_visit_confirm_request').with_context(lang='en_US', tz='Asia/Taipei')
        body = '<div><a t-attf-href="/custom/{{ object.id }}">{{ object.visitor_id.name }}</a><p>{{ object.checkin_time }}</p></div>'
        template.body_html = repair_mail_body(body, expressions=('object.visitor_id.name',), date_fields=('checkin_time',))
        rendered = template._render_field('body_html', [visit.id])[visit.id]
        document = html.fromstring(rendered)
        self.assertEqual([urlsplit(link).path for link in document.xpath('//a/@href')], [f'/custom/{visit.id}'])
        self.assertIn(format_datetime(self.env, visit.checkin_time, tz='Asia/Taipei', lang_code='en_US', dt_format=False), document.text_content())
        self.assertNotIn('{{', rendered)

    def test_mail_upgrade_repairs_stored_escaped_nodes_and_encoded_links(self):
        template = self.env.ref('community_visitor.mail_template_visit_confirm_request')
        self.env['res.lang']._activate_lang('zh_TW')
        broken = Markup("""<div><p>LOCAL_LABEL &lt;t t-out="object.visitor_id.name"/&gt;</p>
<p>&lt;t t-out=&#34;object.create_date&#34;/&gt;</p>
<a href="%7B%7B%20ctx.get('confirm_url',%20'#')%20%7D%7D">Confirm</a>
<a t-attf-href="/custom/{{ object.id }}">Custom</a>
<span title="{{ object.visitor_id.name }}">&lt;script&gt;custom text&lt;/script&gt;</span></div>""")
        for language, label in (('en_US', 'English label'), ('zh_TW', '中文標記')):
            template.with_context(lang=language).body_html = broken.replace('LOCAL_LABEL', label)
        repair_visitor_mail_templates(self.env)
        snapshot = {lang: template.with_context(lang=lang).body_html for lang in ('en_US', 'zh_TW')}
        repair_visitor_mail_templates(self.env)
        visit = self._visit()
        for language, label in (('en_US', 'English label'), ('zh_TW', '中文標記')):
            localized = template.with_context(lang=language, tz='Asia/Taipei', confirm_url='/visitor/confirm/migration-test')
            self.assertEqual(localized.body_html, snapshot[language])
            document = html.fromstring(str(localized.body_html))
            self.assertEqual(document.xpath('//span/@title'), ['{{ object.visitor_id.name }}'])
            self.assertFalse(document.xpath('//script'))
            rendered = localized._render_field('body_html', [visit.id])[visit.id]
            document = html.fromstring(rendered)
            self.assertIn(label, document.text_content())
            self.assertIn(self.visitor.name, document.text_content())
            self.assertNotIn('<t t-out=', document.text_content())
            self.assertEqual([urlsplit(link).path for link in document.xpath('//a/@href')],
                             ['/visitor/confirm/migration-test', f'/custom/{visit.id}'])
            expected = format_datetime(self.env, visit.create_date, tz='Asia/Taipei', lang_code=language, dt_format=False)
            self.assertIn(expected, document.text_content())

    def test_queued_mail_dates_use_resident_timezone(self):
        resident = self.resident.partner_id
        resident.write({'is_resident': True, 'email': 'time@example.test',
                        'tz': 'Asia/Taipei', 'lang': 'en_US'})
        visit = self._visit()
        visit.action_send_confirmation()
        mail = self.env['mail.mail'].search([('model', '=', visit._name), ('res_id', '=', visit.id)])
        expected = format_datetime(self.env, visit.create_date, tz='Asia/Taipei', lang_code='en_US', dt_format=False)
        utc = format_datetime(self.env, visit.create_date, tz='UTC', lang_code='en_US', dt_format=False)
        self.assertIn(expected, html.fromstring(mail.body_html).text_content())
        self.assertNotIn(utc, html.fromstring(mail.body_html).text_content())

        # Cover the separate appointment-arrival notification path as well.
        appointment = self._appointment()
        result = self.env['community.appointment'].action_validate_appointment(appointment.access_token)
        self.assertTrue(result['success'])
        arrival = self.env['community.visit'].browse(result['visit_id'])
        mail = self.env['mail.mail'].search([('model', '=', arrival._name), ('res_id', '=', arrival.id)])
        expected = format_datetime(self.env, arrival.checkin_time, tz='Asia/Taipei', lang_code='en_US', dt_format=False)
        utc = format_datetime(self.env, arrival.checkin_time, tz='UTC', lang_code='en_US', dt_format=False)
        self.assertIn(expected, html.fromstring(mail.body_html).text_content())
        self.assertNotIn(utc, html.fromstring(mail.body_html).text_content())
        self.assertNotIn('{{', mail.body_html)

    def test_portal_confirmation_request_requires_staff_and_active_portal_resident(self):
        self.resident.partner_id.is_resident = True
        visit = self._visit()
        with self.assertRaises(AccessError):
            visit.with_user(self.resident).action_request_portal_confirmation()
        self.assertEqual(visit.state, 'draft')
        self.assertFalse(visit.confirm_token)
        self.resident.active = False
        with self.assertRaises(UserError):
            visit.action_request_portal_confirmation()
        self.assertEqual(visit.state, 'draft')
        self.assertFalse(visit.confirm_token)
        self.resident.active = True
        self.resident.partner_id.is_resident = False
        with self.assertRaises(UserError):
            visit.action_request_portal_confirmation()
        self.resident.partner_id.is_resident = True
        visit.action_request_portal_confirmation()
        self.assertEqual(visit.state, 'pending_confirm')
        self.assertFalse(visit.checkin_time)
        with self.assertRaises(UserError):
            visit.action_request_portal_confirmation()
        with self.assertRaises(UserError):
            visit.action_checkin()

    def test_native_qr_and_mail_rendering(self):
        appointment = self._appointment()
        self.assertTrue(appointment.qr_code)
        visit = self._visit(state='pending_confirm', confirm_token='flow-mail')
        template = self.env.ref('community_visitor.mail_template_visit_confirm_request').with_context(
            confirm_url=visit._get_confirm_url('flow-mail'),
            reject_url=visit._get_reject_url('flow-mail'),
        )
        body = template._render_field('body_html', [visit.id])[visit.id]
        self.assertIn(self.visitor.name, body)
        self.assertNotIn('{{', body)
        links = html.fromstring(body).xpath('//a/@href')
        self.assertEqual(len(links), 2)
        self.assertTrue(all(link.endswith('/visitor/confirm/flow-mail') for link in links))


@tagged('community_visitor_flow', 'post_install', '-at_install')
class TestVisitorPortalFlow(VisitorFlowFixtures, HttpCase):
    def _form_post(self, **values):
        page = self.url_open('/my/appointments/new')
        self.assertEqual(page.status_code, 200)
        token = html.fromstring(page.text).xpath('//input[@name="csrf_token"]/@value')[0]
        return self.url_open('/my/appointments/create', data={
            'csrf_token': token, 'unit_id': str(self.unit.id),
            'visitor_name': 'Portal time guest', 'visitor_phone': '0912999999',
            'valid_from': '2035-01-02T09:30', 'valid_until': '2035-01-02T10:30',
            'appointment_type': 'one_time', 'max_entries': '1', **values,
        })

    def test_create_uses_local_time_and_errors_keep_values_without_records(self):
        self.authenticate(self.resident.login, 'visitor-flow-password')
        response = self._form_post()
        self.assertEqual(response.status_code, 200)
        appointment = self.env['community.appointment'].search([('visitor_phone', '=', '0912999999')])
        self.assertEqual(len(appointment), 1)
        self.assertEqual(appointment.valid_from, datetime(2035, 1, 2, 1, 30))
        self.assertEqual(appointment.schedule_tz, 'Asia/Taipei')
        for invalid in ({'visitor_phone': 'bad-phone'}, {'valid_from': 'bad-date'},
                        {'max_entries': '-1'}, {'appointment_type': 'invalid'},
                        {'appointment_type': 'recurring', 'recurring_from': '12:99'}):
            response = self._form_post(**invalid)
            self.assertEqual(response.status_code, 200)
            self.assertIn('alert-danger', response.text)
            self.assertIn('Portal time guest', response.text)
            self.assertIn('Asia/Taipei', response.text)
            document = html.fromstring(response.text)
            self.assertEqual(document.xpath('//input[@name="valid_until"]/@value'), ['2035-01-02T10:30'])
        self.assertEqual(self.env['community.appointment'].search_count([
            ('resident_id', '=', self.resident.partner_id.id),
        ]), 1)

    def test_public_reject_link_get_then_post_and_replay(self):
        self.resident.partner_id.write({'is_resident': True, 'email': 'flow@example.test'})
        visit = self._visit()
        visit.action_send_confirmation()
        token = visit.confirm_token
        mail = self.env['mail.mail'].search([('model', '=', visit._name), ('res_id', '=', visit.id)])
        self.assertEqual(len(mail), 1)
        self.assertNotIn('{{', mail.body_html)
        language_codes = self.env['res.lang'].search([]).mapped('url_code')

        def confirmation_forms(response):
            self.assertEqual(response.status_code, 200)
            document = html.fromstring(response.text)
            self.assertIn(self.visitor.name, document.text_content())
            result = {}
            for action in ('accept', 'reject'):
                path = f'/visitor/confirm/{token}/{action}'
                allowed_paths = {path} | {'/' + code + path for code in language_codes if code}
                matches = [form for form in document.xpath('//form[@action]')
                           if urlsplit(form.get('action')).path in allowed_paths]
                self.assertEqual(len(matches), 1, 'Expected exactly one confirmation form per action')
                form = matches[0]
                self.assertEqual(form.get('method', '').lower(), 'post')
                self.assertEqual(len(form.xpath('./button[@type="submit"]')), 1)
                target = form.get('action')
                parsed = urlsplit(target)
                self.assertFalse(parsed.query)
                self.assertFalse(parsed.fragment)
                self.assertIn(parsed.scheme, ('', 'http', 'https'))
                self.assertTrue(not parsed.netloc or parsed.netloc == urlsplit(response.url).netloc,
                                'Confirmation action must remain on the current origin')
                csrf = form.xpath('./input[@name="csrf_token"]/@value')
                self.assertEqual(len(csrf), 1)
                self.assertTrue(csrf[0])
                result[action] = (target, csrf[0])
            return result

        links = html.fromstring(mail.body_html).xpath('//a/@href')
        self.assertEqual(len(links), 2)
        for link in links:
            response = self.url_open(urlsplit(link).path)
            confirmation_forms(response)
        response = self.url_open('/visitor/confirm/' + token + '/reject')
        forms = confirmation_forms(response)
        visit.invalidate_recordset()
        self.assertEqual(visit.state, 'pending_confirm')
        reject_url, reject_csrf = forms['reject']
        response = self.url_open(reject_url, data={'csrf_token': reject_csrf})
        self.assertEqual(response.status_code, 200)
        visit.invalidate_recordset()
        self.assertEqual(visit.state, 'rejected')
        accept_url, accept_csrf = forms['accept']
        response = self.url_open(accept_url, data={'csrf_token': accept_csrf})
        self.assertEqual(response.status_code, 200)
        visit.invalidate_recordset()
        self.assertEqual(visit.state, 'rejected')
        self.assertFalse(visit.checkin_time)

    def test_resident_can_confirm_from_portal_without_email(self):
        self.resident.partner_id.write({'is_resident': True, 'email': False})
        visit = self._visit()
        visit.action_request_portal_confirmation()
        token = visit.confirm_token
        self.assertEqual(visit.state, 'pending_confirm')
        self.assertFalse(visit.checkin_time)
        self.assertFalse(self.env['mail.mail'].search([('model', '=', visit._name), ('res_id', '=', visit.id)]))
        self.authenticate(self.resident.login, 'visitor-flow-password')
        response = self.url_open(f'/my/visitors/{visit.id}')
        self.assertEqual(response.status_code, 200)
        document = html.fromstring(response.text)
        accept = f'/visitor/confirm/{token}/accept'
        reject = f'/visitor/confirm/{token}/reject'
        self.assertTrue(document.xpath('//form[@action=$url]/button', url=accept))
        self.assertTrue(document.xpath('//form[@action=$url]/button', url=reject))
        csrf = document.xpath('//form[@action=$url]/input[@name="csrf_token"]/@value', url=accept)[0]
        response = self.url_open(accept, data={'csrf_token': csrf})
        self.assertEqual(response.status_code, 200)
        visit.invalidate_recordset()
        self.assertEqual(visit.state, 'confirmed')
        self.assertEqual(visit.resident_id, self.resident.partner_id)

    def test_draft_list_has_status_and_pending_list_has_buttons(self):
        draft = self._visit()
        pending = self._visit(state='pending_confirm')
        token = pending._generate_confirm_token()
        self.authenticate(self.resident.login, 'visitor-flow-password')
        response = self.url_open('/my/visitors')
        self.assertEqual(response.status_code, 200)
        document = html.fromstring(response.text)
        row = document.xpath('//tr[td/a[@href=$url]]', url=f'/my/visitors/{draft.id}')[0]
        self.assertIn('登記中', row.text_content())
        self.assertIn('等待管理室送出確認', row.text_content())
        for action in ('accept', 'reject'):
            self.assertTrue(document.xpath('//form[@action=$url]/button', url=f'/visitor/confirm/{token}/{action}'))
