from datetime import datetime, timedelta
from unittest.mock import patch

from psycopg2.errors import SerializationFailure

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


class TestParcelWorkflows(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resident = cls.env['res.partner'].create({
            'name': 'Resident', 'email': 'resident@example.test',
        })
        cls.unit = cls.env['community.unit'].create({
            'building': 'Workflow', 'floor': '1', 'number': '1',
            'resident_ids': [(6, 0, cls.resident.ids)],
        })
        cls.staff = new_test_user(
            cls.env, login='parcel-workflow-staff', email='staff@example.test',
            groups='community_parcel.community_parcel_group_office_staff',
        )

    def test_arrival_mail_and_pickup_audit(self):
        other = self.env['res.partner'].create({
            'name': 'Other unit', 'email': 'other@example.test',
        })
        invalid = self.env['res.partner'].create({
            'name': 'Invalid email', 'email': 'not-an-email',
        })
        inactive = self.env['res.partner'].create({
            'name': 'Inactive resident', 'email': 'inactive@example.test', 'active': False,
        })
        self.unit.resident_ids = [(4, invalid.id), (4, inactive.id)]
        parcel = self.env['community.parcel'].create({'unit_id': self.unit.id})
        parcel.message_subscribe(other.ids)
        parcel.with_user(self.staff).action_notify()
        mail = self.env['mail.mail'].search([
            ('model', '=', parcel._name), ('res_id', '=', parcel.id),
            ('subject', 'ilike', '您有包裹到件'),
        ])
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.recipient_ids, self.resident)
        self.assertFalse(mail.email_to)
        self.assertIn(parcel.name, mail.body_html)
        self.assertNotIn('{{', mail.body_html)
        self.assertEqual(parcel.state, 'notified')
        self.assertTrue(parcel.notified_date)
        parcel.with_user(self.staff).action_pickup()
        self.assertEqual(parcel.picked_by, self.staff)
        self.assertTrue(parcel.pickup_date)
        with self.assertRaises(UserError):
            parcel.action_pickup()
        with self.assertRaises(UserError):
            parcel.action_return()

    def test_scanner_whitespace_and_empty_barcodes(self):
        parcel = self.env['community.parcel'].create({
            'unit_id': self.unit.id, 'barcode': '  SCAN-123\r\n',
        })
        self.assertEqual(parcel.barcode, 'SCAN-123')
        parcel.barcode = '  SCAN-456\n'
        self.assertEqual(parcel.barcode, 'SCAN-456')
        empty = self.env['community.parcel'].create([
            {'unit_id': self.unit.id, 'barcode': '  '},
            {'unit_id': self.unit.id, 'barcode': ''},
        ])
        self.assertFalse(any(empty.mapped('barcode')))

    def test_no_email_does_not_mark_notified_or_ready(self):
        self.resident.email = False
        parcel = self.env['community.parcel'].create({'unit_id': self.unit.id})
        with self.assertRaises(UserError):
            parcel.action_notify()
        self.assertEqual(parcel.state, 'draft')
        self.assertFalse(parcel.notified_date)
        storage = self.env['community.storage'].create({'unit_id': self.unit.id})
        storage.action_accept()
        with self.assertRaises(UserError):
            storage.action_ready()
        self.assertEqual(storage.state, 'storing')

    def test_cron_overdue_once_and_return(self):
        parcel = self.env['community.parcel'].create({'unit_id': self.unit.id})
        parcel.action_notify()
        parcel.notified_date = fields.Datetime.now() - timedelta(days=8)
        self.env['community.parcel']._cron_check_overdue()
        self.assertEqual(parcel.state, 'overdue')
        domain = [('model', '=', parcel._name), ('res_id', '=', parcel.id),
                  ('subject', 'ilike', '逾期')]
        self.assertEqual(self.env['mail.mail'].search_count(domain), 1)
        self.env['community.parcel']._cron_check_overdue()
        self.assertEqual(self.env['mail.mail'].search_count(domain), 1)
        parcel.action_return()
        self.assertEqual(parcel.state, 'returned')
        self.assertFalse(parcel.pickup_date)

    def test_onsite_handover_without_email_keeps_audit_and_portal_readonly(self):
        self.resident.email = False
        portal = new_test_user(self.env, login='onsite-resident', groups='base.group_portal')
        self.unit.resident_ids = [(4, portal.partner_id.id)]
        for model, initial, final, date_field in (
            ('community.parcel', 'draft', 'picked_up', 'pickup_date'),
            ('community.storage', 'storing', 'done', 'actual_pickup'),
        ):
            record = self.env[model].create({'unit_id': self.unit.id, 'state': initial})
            with self.assertRaises(AccessError):
                record.with_user(portal).action_pickup_onsite()
            self.assertEqual(record.state, initial)
            record.with_user(self.staff).action_pickup_onsite()
            self.assertEqual(record.state, final)
            self.assertEqual(record.picked_by, self.staff)
            self.assertTrue(record[date_field])
            if model == 'community.parcel':
                self.assertFalse(record.notified_date)
            notes = record.message_ids.filtered(lambda message: '現場取件：' in (message.body or ''))
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes.author_id, self.staff.partner_id)
            self.assertEqual(notes.subtype_id, self.env.ref('mail.mt_note'))
            self.assertFalse(self.env['mail.mail'].search([
                ('model', '=', model), ('res_id', '=', record.id),
            ]))
            with self.assertRaises(UserError):
                record.with_user(self.staff).action_pickup_onsite()

    def test_custom_templates_see_updated_state_and_notification_date(self):
        for model, template_name, action, initial, expected in (
            ('community.parcel', 'parcel_arrival', 'action_notify', 'draft', 'notified'),
            ('community.storage', 'storage_ready', 'action_ready', 'storing', 'ready'),
        ):
            template = self.env.ref('community_parcel.mail_template_' + template_name)
            template.body_html = '<div>State: <t t-out="object.state"/></div>'
            if model == 'community.parcel':
                template.body_html = '<div>State: <t t-out="object.state"/> Date: <t t-out="object.notified_date"/></div>'
            record = self.env[model].create({'unit_id': self.unit.id, 'state': initial})
            getattr(record.with_user(self.staff), action)()
            mail = self.env['mail.mail'].search([
                ('model', '=', model), ('res_id', '=', record.id),
            ])
            self.assertEqual(len(mail), 1)
            self.assertIn(expected, mail.body_html)
            if model == 'community.parcel':
                self.assertIn(fields.Datetime.to_string(record.notified_date), mail.body_html)

    def test_notification_error_rolls_back_state_and_partial_mail(self):
        for model, action, initial in (
            ('community.parcel', 'action_notify', 'draft'),
            ('community.storage', 'action_ready', 'storing'),
        ):
            record = self.env[model].create({'unit_id': self.unit.id, 'state': initial})

            def queue_then_error(*args, **kwargs):
                self.env['mail.mail'].create({
                    'subject': 'Partial notification', 'body_html': '<p>Partial</p>',
                    'email_from': 'staff@example.test', 'email_to': 'resident@example.test',
                    'model': model, 'res_id': record.id,
                })
                raise UserError('Mail template failure')

            with patch.object(type(self.env['mail.template']), 'send_mail', side_effect=queue_then_error):
                with self.assertRaises(UserError):
                    getattr(record.with_user(self.staff), action)()
            self.assertEqual(record.state, initial)
            if model == 'community.parcel':
                self.assertFalse(record.notified_date)
            self.assertFalse(self.env['mail.mail'].search([
                ('model', '=', model), ('res_id', '=', record.id), ('subject', '=', 'Partial notification'),
            ]))

    def test_mail_dates_use_native_timezone_formatting(self):
        language = self.env['res.lang'].search([('code', '=', 'en_US')], limit=1)
        native_pattern = language.date_format + ' ' + language.time_format

        moment = datetime(2035, 1, 1, 18, 30)
        parcel = self.env['community.parcel'].create({
            'unit_id': self.unit.id, 'received_date': moment, 'notified_date': moment,
        })
        storage = self.env['community.storage'].create({'unit_id': self.unit.id, 'deposit_date': moment})
        for name, record in (
            ('parcel_arrival', parcel), ('parcel_overdue', parcel), ('storage_ready', storage),
        ):
            template = self.env.ref('community_parcel.mail_template_' + name).with_user(self.staff)
            for zone, local_moment in (
                ('Asia/Taipei', datetime(2035, 1, 2, 2, 30)),
                ('UTC', datetime(2035, 1, 1, 18, 30)),
            ):
                localized = template.with_context(tz=zone, lang='en_US')
                body = localized._render_field('body_html', [record.id])[record.id]
                # Mail's helper defaults dt_format=False (res.lang formats),
                # unlike tools.format_datetime's Babel 'medium' default.
                formatter = localized._render_eval_context()['format_datetime']
                expected = formatter(moment, tz=zone, lang_code='en_US')
                self.assertEqual(expected, local_moment.strftime(native_pattern))
                self.assertIn(expected, body)
            self.staff.tz = 'Asia/Taipei'
            fallback = template.with_context(tz=False, lang='en_US')
            body = fallback._render_field('body_html', [record.id])[record.id]
            formatter = fallback._render_eval_context()['format_datetime']
            expected = formatter(moment, tz='Asia/Taipei', lang_code='en_US')
            self.assertEqual(expected, datetime(2035, 1, 2, 2, 30).strftime(native_pattern))
            self.assertIn(expected, body)

    def test_mail_migration_preserves_attributes_custom_text_and_translations(self):
        import importlib.util
        from pathlib import Path
        from lxml import html

        path = Path(__file__).resolve().parents[1] / 'migrations/18.0.1.0.2/post-migrate.py'
        spec = importlib.util.spec_from_file_location('parcel_mail_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        template = self.env.ref('community_parcel.mail_template_parcel_arrival')
        self.env['res.lang']._activate_lang('zh_TW')
        body = (
            '<div><p>Custom arrival {{ object.name }}</p>'
            '<a t-attf-href="/my/parcels/{{ object.id }}" title="{{ object.name }}">Custom link</a>'
            '<p>{{ object.received_date }}</p>'
            '<p><t t-out="object.notified_date"/> Tail {{ object.name }}</p></div>'
        )
        template.with_context(lang='en_US').body_html = body
        template.with_context(lang='zh_TW').body_html = body.replace('Custom arrival', '自訂到件').replace('Custom link', '自訂連結')
        before = {lang: template.with_context(lang=lang).body_html for lang in ('en_US', 'zh_TW')}
        migration.migrate(self.env.cr, '18.0.1.0.1')
        for lang, original in before.items():
            repaired = template.with_context(lang=lang).body_html
            old = html.fromstring(original)
            new = html.fromstring(repaired)
            self.assertEqual(new.xpath('//a/@t-attf-href'), old.xpath('//a/@t-attf-href'))
            self.assertEqual(new.xpath('//a/@title'), old.xpath('//a/@title'))
            self.assertEqual(new.xpath('//a/text()'), old.xpath('//a/text()'))
            self.assertTrue(new.xpath('//t[@t-out="object.name"]'))
            dates = [value for value in new.xpath('//t/@t-out') if value.startswith('format_datetime(')]
            self.assertEqual(len(dates), 2)
            self.assertIn('自訂到件' if lang == 'zh_TW' else 'Custom arrival', repaired)
            self.assertEqual(migration._repair_body(repaired), repaired)

    def test_dashboard_today_taipei_midnight_and_drilldown(self):
        dashboard = self.env['community.parcel.dashboard'].with_user(self.staff).with_context(tz='Asia/Taipei')
        card = dashboard.browse(1)
        with patch.object(fields.Datetime, 'now', return_value=datetime(2035, 1, 1, 18)):
            expected_domain = [
                ('received_date', '>=', '2035-01-01 16:00:00'),
                ('received_date', '<', '2035-01-02 16:00:00'),
            ]
            self.assertEqual(card.action_open()['domain'], expected_domain)
            baseline = self.env['community.parcel'].with_user(self.staff).search_count(expected_domain)
            parcels = self.env['community.parcel'].create([
                {'unit_id': self.unit.id, 'received_date': date, 'state': state}
                for date, state in (
                    ('2035-01-01 15:59:59', 'draft'),  # Previous local day.
                    ('2035-01-01 16:00:00', 'draft'),  # Inclusive local midnight.
                    ('2035-01-02 00:00:00', 'notified'),
                    ('2035-01-02 15:59:59', 'overdue'),
                    ('2035-01-02 16:00:00', 'draft'),  # Exclusive next midnight.
                )
            ])
            selected = self.env['community.parcel'].search(expected_domain) & parcels
            self.assertEqual(set(selected.ids), set(parcels[1:4].ids))
            self.assertEqual(card.count, baseline + 3)
            for action, count in (
                (card.action_open(), card.count),
                (card.action_open_stat1(), card.count_stat1),
                (card.action_open_stat2(), card.count_stat2),
            ):
                self.assertEqual(
                    self.env[action['res_model']].with_user(self.staff).search_count(action['domain']), count,
                )
            # Same record in a different context must not reuse Taipei's count.
            utc_card = card.with_context(tz='UTC')
            self.assertEqual(utc_card.action_open()['domain'], [
                ('received_date', '>=', '2035-01-01 00:00:00'),
                ('received_date', '<', '2035-01-02 00:00:00'),
            ])
            self.assertEqual(utc_card.count, self.env['community.parcel'].with_user(self.staff).search_count(
                utc_card.action_open()['domain'],
            ))

    def test_dashboard_local_day_respects_dst(self):
        dashboard = self.env['community.parcel.dashboard'].with_context(tz='America/New_York')
        for now, start, end in (
            (datetime(2030, 3, 10, 12), '2030-03-10 05:00:00', '2030-03-11 04:00:00'),
            (datetime(2030, 11, 3, 12), '2030-11-03 04:00:00', '2030-11-04 05:00:00'),
        ):
            with patch.object(fields.Datetime, 'now', return_value=now):
                self.assertEqual(dashboard._today_received_domain(), [
                    ('received_date', '>=', start), ('received_date', '<', end),
                ])

    def test_dashboard_all_counts_match_actions(self):
        cards = self.env['community.parcel.dashboard'].with_user(self.staff).with_context(tz='Asia/Taipei').search([])
        self.assertEqual(len(cards), 6)
        for card in cards:
            for action, count in (
                (card.action_open(), card.count),
                (card.action_open_stat1(), card.count_stat1),
                (card.action_open_stat2(), card.count_stat2),
            ):
                if action:
                    self.assertEqual(count, self.env[action['res_model']].with_user(self.staff).search_count(
                        action['domain'],
                    ))
                else:
                    self.assertEqual(count, 0)

    def _overdue_candidate(self, unit=None):
        return self.env['community.parcel'].create({
            'unit_id': (unit or self.unit).id,
            'state': 'notified',
            'notified_date': fields.Datetime.now() - timedelta(days=8),
        })

    def test_cron_missing_email_does_not_stop_other_units(self):
        healthy = self._overdue_candidate()
        no_email_unit = self.env['community.unit'].create({
            'building': 'No email', 'floor': '1', 'number': '1',
        })
        missing = self._overdue_candidate(no_email_unit)
        self.env['community.parcel']._cron_check_overdue()
        self.assertEqual(missing.state, 'overdue')
        self.assertEqual(healthy.state, 'overdue')
        mail = self.env['mail.mail'].search([
            ('model', '=', healthy._name), ('res_id', 'in', (missing | healthy).ids),
            ('subject', 'ilike', '逾期'),
        ])
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.res_id, healthy.id)

    @mute_logger('odoo.sql_db')
    def test_cron_rolls_back_failed_mail_and_continues_then_retries(self):
        from odoo.addons.community_parcel.models.community_parcel import send_resident_notification

        healthy = self._overdue_candidate()
        failing = self._overdue_candidate()
        calls = []

        def queue_then_fail(record, *args, **kwargs):
            calls.append(record.id)
            result = send_resident_notification(record, *args, **kwargs)
            if record == failing:
                # Exercise a genuinely aborted PostgreSQL transaction after
                # mail creation, not only a Python validation exception.
                record.env.cr.execute('SELECT 1 / 0')
            return result

        with patch(
            'odoo.addons.community_parcel.models.community_parcel.send_resident_notification',
            side_effect=queue_then_fail,
        ), self.assertLogs('odoo.addons.community_parcel.models.community_parcel', level='ERROR'):
            self.env['community.parcel']._cron_check_overdue()
        self.assertLess(calls.index(failing.id), calls.index(healthy.id))
        self.assertEqual(failing.state, 'notified')
        self.assertEqual(healthy.state, 'overdue')
        mail_domain = [('model', '=', failing._name), ('res_id', '=', failing.id),
                       ('subject', 'ilike', '逾期')]
        self.assertFalse(self.env['mail.mail'].search(mail_domain))
        self.env['community.parcel']._cron_check_overdue()
        self.assertEqual(failing.state, 'overdue')
        self.assertEqual(self.env['mail.mail'].search_count(mail_domain), 1)
        self.assertEqual(self.env['mail.mail'].search_count([
            ('model', '=', healthy._name), ('res_id', '=', healthy.id),
            ('subject', 'ilike', '逾期'),
        ]), 1)

    def test_cron_serialization_failure_is_left_to_odoo_retry(self):
        parcel = self._overdue_candidate()
        with patch(
            'odoo.addons.community_parcel.models.community_parcel.send_resident_notification',
            side_effect=SerializationFailure('retry transaction'),
        ), self.assertRaises(SerializationFailure):
            self.env['community.parcel']._cron_check_overdue()
        self.assertEqual(parcel.state, 'notified')

    def test_storage_delivery_and_portal_cannot_confirm(self):
        portal = new_test_user(self.env, login='parcel-readonly', groups='base.group_portal')
        self.unit.resident_ids = [(4, portal.partner_id.id)]
        storage = self.env['community.storage'].create({'unit_id': self.unit.id})
        with self.assertRaises(UserError):
            storage.action_done()
        storage.action_accept()
        with self.assertRaises(AccessError):
            storage.with_user(portal).action_ready()
        storage.action_ready()
        with self.assertRaises(AccessError):
            storage.with_user(portal).action_done()
        storage.with_user(self.staff).action_done()
        self.assertTrue(storage.actual_pickup)
        self.assertEqual(storage.picked_by, self.staff)
        with self.assertRaises(UserError):
            storage.action_scrap()


@tagged('-at_install', 'post_install')
class TestParcelPortalForms(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal = new_test_user(
            cls.env, login='parcel-form-resident', password='parcel-form-resident',
            groups='base.group_portal',
        )
        cls.unit = cls.env['community.unit'].create({
            'building': 'Portal form', 'floor': '1', 'number': '1',
            'resident_ids': [(6, 0, cls.portal.partner_id.ids)],
        })
        cls.other_unit = cls.env['community.unit'].create({
            'building': 'Portal form', 'floor': '1', 'number': '2',
        })

    def test_invalid_storage_forms_preserve_input_and_create_nothing(self):
        from lxml import html
        self.authenticate('parcel-form-resident', 'parcel-form-resident')
        response = self.url_open('/my/storage/new')
        self.assertEqual(response.status_code, 200)
        token = html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]
        count = self.env['community.storage'].search_count([])
        for invalid in (
            {'unit_id': 'not-an-id'},
            {'unit_id': str(self.other_unit.id)},
            {'type_id': 'invalid'},
            {'type_id': '2147483647'},
            {'expected_pickup': 'not-a-date'},
            {'expected_pickup': '2026-02-30'},
            {'item_description': '   '},
        ):
            data = dict(csrf_token=token, unit_id=str(self.unit.id),
                        item_description='Keep this description', recipient_name='Recipient')
            data.update(invalid)
            response = self.url_open('/my/storage/create', data=data)
            self.assertEqual(response.status_code, 200)
            self.assertIn('alert-danger', response.text)
            self.assertIn('Recipient', response.text)
        self.assertEqual(self.env['community.storage'].search_count([]), count)
        response = self.url_open('/my/storage/create', data={
            'csrf_token': token, 'unit_id': str(self.unit.id),
            'item_description': 'Valid request', 'recipient_name': 'Recipient',
            'state': 'done', 'internal_note': 'must not be accepted',
        })
        self.assertEqual(response.status_code, 200)
        storage = self.env['community.storage'].search([('unit_id', '=', self.unit.id)])
        self.assertEqual(len(storage), 1)
        self.assertEqual(storage.state, 'pending')
        self.assertEqual(storage.recipient_name, 'Recipient')
        self.assertFalse(storage.internal_note)

    def test_foreign_and_missing_details_redirect_without_access_error(self):
        self.authenticate('parcel-form-resident', 'parcel-form-resident')
        for model, route in [('community.parcel', 'parcels'), ('community.storage', 'storage')]:
            foreign = self.env[model].create({'unit_id': self.other_unit.id})
            for record_id in (foreign.id, 2147483647):
                response = self.url_open(f'/my/{route}/{record_id}', allow_redirects=False)
                self.assertEqual(response.status_code, 303)
                self.assertTrue(response.headers['Location'].endswith('/my/' + route))
