"""Language changes must preserve science inputs and export choices."""
import unittest
from unittest.mock import Mock
from occultation_media.desktop_app import App
from occultation_media.ui_text import text
from occultation_media.desktop_job import prepare_job


class Variable:
    def __init__(self,value):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value


class LanguageTests(unittest.TestCase):
    def test_switch_keeps_export_language_and_status(self):
        app=App.__new__(App)
        app.ui_language=Variable('English');app.status=Variable('');app.status_key='running'
        app.root=Mock();label=Mock();combo=Mock()
        output_language=Variable('zh');display=Variable('中文')
        app.labels=[(label,'generate')];app.combos=[(combo,display,output_language,('both','zh','en'))]
        app.fields={'asteroid':Variable('YB35'),'language':output_language}
        app.change_language()
        self.assertEqual(output_language.get(),'zh')
        self.assertEqual(display.get(),'Chinese')
        self.assertEqual(app.fields['asteroid'].get(),'YB35')
        self.assertEqual(app.status.get(),text('running','en'))
        app.ui_language.set('中文');app.change_language()
        self.assertEqual(display.get(),'中文')
        self.assertEqual(output_language.get(),'zh')
        self.assertEqual(app.status.get(),text('running','zh'))

    def test_numeric_errors_are_translatable(self):
        with self.assertRaisesRegex(ValueError,'^err_number$'):
            prepare_job({'exposure':'','uncertainty':'0.7','margin':'5'})
        self.assertIn('finite',text('err_number','en'))


if __name__=='__main__':unittest.main()
