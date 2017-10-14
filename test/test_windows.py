import pytest

class ConfigShim(object):
    def get(self, *args, **kwargs):
        return ''

from poezio import config
config.config = ConfigShim()

from poezio.windows import Input, HistoryInput, MessageInput

@pytest.fixture
def input():
    input = Input()
    input.rewrite_text = lambda: None
    return input

class TestInput(object):

    def test_do_command(self, input):

        input.do_command('a')
        assert input.text == 'a'

        for char in 'coucou':
            input.do_command(char)
        assert input.text == 'acoucou'

    def test_empty(self, input):
        assert input.is_empty() == True
        input.do_command('a')
        assert input.is_empty() == False

    def test_key_left(self, input):
        for char in 'this is a line':
            input.do_command(char)
        for i in range(4):
            input.key_left()
        for char in 'long ':
            input.do_command(char)

        assert input.text == 'this is a long line'

    def test_key_right(self, input):
        for char in 'this is a line':
            input.do_command(char)
        for i in range(4):
            input.key_left()
        input.key_right()

        for char in 'iii':
            input.do_command(char)

        assert input.text == 'this is a liiiine'

    def test_key_home(self, input):
        for char in 'this is a line of text':
            input.do_command(char)
        input.do_command('z')
        input.key_home()
        input.do_command('a')

        assert input.text == 'athis is a line of textz'

    def test_key_end(self, input):
        for char in 'this is a line of text':
            input.do_command(char)
        input.key_home()
        input.key_end()
        input.do_command('z')

        assert input.text == 'this is a line of textz'

