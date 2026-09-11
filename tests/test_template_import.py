import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient
from class_schedule import webapp


class TemplateImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in [('CONFIG_DIR', self.root / 'config'), ('WORK_ROOT', self.root / 'work')]:
            patcher = patch.object(webapp, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(webapp.create_app())
        self.addCleanup(self.client.close)
        self.source = b'Subject,Number,Section,Instructor,Building,Room,Time Slot,Duration,Type,Credits\nMATH,101,001,Alice,Science,10,MWF 9:00am,50,CLAS,3\n'

    def upload(self, files, mode='create', package='EXISTING'):
        return self.client.post('/api/configuration-packages', data={'upload_mode': mode, 'current_package': package}, files=[('config_files', (name, content)) for name, content in files])

    def create(self):
        response = self.upload([('term.csv', self.source)])
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_new_template_and_duplicate_name_are_independent(self):
        body = self.create()
        self.assertEqual(body['package_id'], 'term')
        self.assertEqual(len(body['inferred_files']), 7)
        self.assertTrue(body['template']['present'])
        self.assertEqual(self.create()['package_id'], 'term-2')
        self.assertFalse((self.root / 'config/EXISTING').exists())

    def test_full_config_creates_new_package_and_retargets_headers(self):
        original = self.create()
        files = [(item['name'], item['content'].encode()) for item in original['files']]
        response = self.upload(files)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['package_id'], 'term-2')
        self.assertFalse(body['template']['present'])
        for item in body['files']:
            self.assertIn('# Configuration package: term-2', item['content'])
        response = self.upload(files + [('other.csv', self.source)])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['package_id'], 'term-3')
        self.assertTrue(response.json()['template']['present'])

    def test_replacement_preserves_config_and_previews_xlsx(self):
        original = self.create()
        stream = io.BytesIO()
        pd.read_csv(io.BytesIO(self.source), dtype=str).to_excel(stream, index=False)
        response = self.upload([('replacement.xlsx', stream.getvalue())], 'replace_template', 'term')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([f['content'] for f in original['files']], [f['content'] for f in response.json()['files']])
        preview = self.client.get('/api/configuration-packages/term/template-preview').json()
        self.assertEqual(preview['total'], 1)
        self.assertEqual(preview['rows'][0][preview['columns'].index('Section')], '001')
        self.assertEqual(self.client.get('/api/configuration-packages/term/template-preview?offset=1').json()['rows'], [])
        self.assertEqual(self.client.get('/api/configuration-packages/term/template-preview?limit=0').status_code, 400)

    def test_invalid_replacement_does_not_change_existing_template(self):
        original = self.create()
        response = self.upload([('bad.csv', b'Subject,Number\n"unterminated')], 'replace_template', 'term')
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/configuration-packages/term/template').content, self.source)
        response = self.upload([('courses.toml', original['files'][0]['content'].encode())], 'replace_template', 'term')
        self.assertEqual(response.status_code, 400)

    def test_editor_batch_updates_selected_package_only(self):
        original = self.create()
        before = {item['name']: item['content'] for item in original['files']}
        names = ['preferences.toml', 'constraints.toml']
        files = [(name, (before[name].replace('package: term', 'package: OTHER') + '\n# updated\n').encode()) for name in names]
        response = self.upload(files + [('new.csv', self.source)], 'update', 'term')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['package_id'], 'term')
        self.assertEqual(response.json()['template']['filename'], 'new.csv')
        for item in response.json()['files']:
            expected = before[item['name']] + ('\n# updated\n' if item['name'] in names else '')
            self.assertEqual(item['content'], expected)
        self.assertEqual([p.name for p in (self.root / 'config').iterdir()], ['term'])

    def test_editor_invalid_batch_leaves_every_file_unchanged(self):
        original = self.create()
        before = {item['name']: item['content'] for item in original['files']}
        response = self.upload([
            ('preferences.toml', (before['preferences.toml'] + '\n# updated\n').encode()),
            ('constraints.toml', b'invalid = ['),
            ('replacement.csv', self.source),
        ], 'update', 'term')
        self.assertEqual(response.status_code, 400, response.text)
        after = self.client.get('/api/configuration-files?package=term').json()
        self.assertEqual(before, {item['name']: item['content'] for item in after['files']})
        self.assertEqual(after['template']['filename'], 'term.csv')

    def test_editor_cannot_create_a_package(self):
        response = self.upload([('term.csv', self.source)], 'update', 'missing')
        self.assertEqual(response.status_code, 404, response.text)
        self.assertFalse((self.root / 'config/missing').exists())

if __name__ == '__main__':
    unittest.main()
