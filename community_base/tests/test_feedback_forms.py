from lxml import html

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged('-at_install', 'post_install')
class TestFeedbackForms(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resident = new_test_user(
            cls.env, login='feedback-form-resident', password='feedback-form-resident',
            groups='base.group_portal',
        )
        cls.unit = cls.env['community.unit'].create({
            'building': 'Feedback form', 'floor': '1', 'number': '1',
            'resident_ids': [(4, cls.resident.partner_id.id)],
        })
        cls.category = cls.env['community.feedback.category'].create({'name': 'Maintenance'})

    def test_invalid_input_is_preserved_and_cannot_create_blank_feedback(self):
        self.authenticate('feedback-form-resident', 'feedback-form-resident')
        response = self.url_open('/my/feedbacks/new')
        token = html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]
        count = self.env['community.feedback'].search_count([])
        for invalid in ({'title': '   '}, {'content': '   '},
                        {'category_id': 'bad'}, {'unit_id': '2147483647'}):
            data = dict(csrf_token=token, unit_id=str(self.unit.id),
                        category_id=str(self.category.id), title='Keep my title',
                        content='Keep my details')
            data.update(invalid)
            response = self.url_open('/my/feedbacks/create', data=data)
            self.assertEqual(response.status_code, 200)
            self.assertIn('alert-danger', response.text)
            tree = html.fromstring(response.content)
            self.assertEqual(tree.xpath('//input[@name="title"]/@value'), [data['title']])
            self.assertEqual(tree.xpath('string(//textarea[@name="content"])'), data['content'])
        self.assertEqual(self.env['community.feedback'].search_count([]), count)

    def test_valid_feedback_starts_pending_and_is_owned_by_resident(self):
        self.authenticate('feedback-form-resident', 'feedback-form-resident')
        response = self.url_open('/my/feedbacks/new')
        token = html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]
        response = self.url_open('/my/feedbacks/create', data={
            'csrf_token': token, 'unit_id': self.unit.id, 'category_id': self.category.id,
            'title': ' UX repair ', 'content': ' Broken light ', 'state': 'done',
            'partner_id': self.env.ref('base.partner_admin').id,
        })
        self.assertEqual(response.status_code, 200)
        record = self.env['community.feedback'].search([('unit_id', '=', self.unit.id)])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.title, 'UX repair')
        self.assertEqual(record.partner_id, self.resident.partner_id)
        self.assertEqual(record.state, 'pending')
