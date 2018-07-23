"""
Test the config module
"""

import os
import tempfile
from pathlib import Path

import pytest

from poezio import config

@pytest.yield_fixture(scope="module")
def config_obj():
    file_ = tempfile.NamedTemporaryFile(delete=False)
    conf = config.Config(file_name=Path(file_.name))
    yield conf
    del conf
    os.unlink(file_.name)

class TestConfigSimple(object):
    def test_get_set(self, config_obj):
        config_obj.set_and_save('test', value='coucou')
        config_obj.set_and_save('test2', value='true')
        assert config_obj.get('test') == 'coucou'
        assert config_obj.get('test2') == 'true'
        assert config_obj.get('toto') == ''

    def test_file_content(self, config_obj):
        with open(str(config_obj.file_name), 'r') as fd:
            data = fd.read()
        supposed_content = '[Poezio]\ntest = coucou\ntest2 = true\n'
        assert data == supposed_content

    def test_get_types(self, config_obj):

        config_obj.set_and_save('test_int', '99')
        config_obj.set_and_save('test_int_neg', '-1')
        config_obj.set_and_save('test_bool_t', 'true')
        config_obj.set_and_save('test_bool_f', 'false')
        config_obj.set_and_save('test_float', '1.5')

        assert config_obj.get('test_int', default=0) == 99
        assert config_obj.get('test_int_neg', default=0) == -1
        assert config_obj.get('test_bool_t', default=False) == True
        assert config_obj.get('test_bool_f', default=True) == False
        assert config_obj.get('test_float', default=1.0) == 1.5

    def test_remove(self, config_obj):
        with open(str(config_obj.file_name), 'r') as fd:
            data = fd.read()

        supposed_content = ('[Poezio]\ntest = coucou\ntest2 = true\n'
                            'test_int = 99\ntest_int_neg = -1\ntest_bool_t ='
                            ' true\ntest_bool_f = false\ntest_float = 1.5\n')

        assert data == supposed_content

        config_obj.remove_and_save('test_int')
        config_obj.remove_and_save('test_int_neg')
        config_obj.remove_and_save('test_bool_t')
        config_obj.remove_and_save('test_bool_f')
        config_obj.remove_and_save('test_float')

        with open(str(config_obj.file_name), 'r') as fd:
            data = fd.read()

        supposed_content = '[Poezio]\ntest = coucou\ntest2 = true\n'

        assert data == supposed_content


    def test_toggle(self, config_obj):
        config_obj.set_and_save('test2', value='toggle')
        assert config_obj.get('test2') == 'false'
        config_obj.set_and_save('test2', value='toggle')
        assert config_obj.get('test2') == 'true'

    def test_get_set_default(self, config_obj):
        assert config_obj.get('doesnotexist', 'toto@tata') == 'toto@tata'
        assert config_obj.get('doesnotexist2', '1234') == '1234'

class TestConfigSections(object):
    def test_set_section(self, config_obj):
        config_obj.set_and_save('option1', 'test', section='NotPoezio')
        config_obj.set_and_save('option2', 'test2', section='NotPoezio')

        assert config_obj.get('option1', section='NotPoezio') == 'test'
        assert config_obj.get('option2', section='NotPoezio') == 'test2'

    def test_file_content(self, config_obj):
        with open(str(config_obj.file_name), 'r') as fd:
            data = fd.read()
        supposed_content = ('[Poezio]\ntest = coucou\ntest2 = true\n'
                            '[NotPoezio]\noption1 = test\noption2 = test2\n')
        assert data == supposed_content

class TestTabNames(object):
    def test_get_tabname(self, config_obj):
        config.post_logging_setup()
        config_obj.set_and_save('test', value='value.toto@toto.com',
                                section='toto@toto.com')
        config_obj.set_and_save('test2', value='value2@toto.com',
                                section='@toto.com')

        assert config_obj.get_by_tabname('test', 'toto@toto.com') == 'value.toto@toto.com'
        assert config_obj.get_by_tabname('test2', 'toto@toto.com') == 'value2@toto.com'
        assert config_obj.get_by_tabname('test2', 'toto@toto.com', fallback=False) == 'value2@toto.com'
        assert config_obj.get_by_tabname('test2', 'toto@toto.com', fallback_server=False) == 'true'
        assert config_obj.get_by_tabname('test_int', 'toto@toto.com', fallback=False) == ''


