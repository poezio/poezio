"""
Test the completions methods on an altered input object.
"""

import string
import pytest
import random

class ConfigShim(object):
    def get(self, *args, **kwargs):
        return ''

from poezio import config
config.config = ConfigShim()

from poezio.windows import Input

@pytest.fixture(scope="function")
def input_obj():
    obj = Input()
    obj.reset_completion()
    obj.resize = lambda: None
    obj.rewrite_text = lambda: None
    obj.refresh = lambda: None
    return obj

@pytest.fixture(scope="module")
def random_unquoted_words():
    letters = string.ascii_lowercase + ((len(string.ascii_lowercase)//4)*' ')
    acc = [random.choice(letters) for _ in range(200)]
    words = ''.join(acc).split()
    return words

@pytest.fixture(scope="module")
def quoted_words():
    words = []
    letters = string.ascii_lowercase + ((len(string.ascii_lowercase)//4)*' ')
    words_by_letter = {}
    for start_letter in string.ascii_lowercase:
        words_by_letter[start_letter] = []
        for _ in range(5):
            size = random.randint(0, 15)
            word = start_letter + ''.join(random.choice(letters) for i in range(size))
            words.append(word)
            words_by_letter[start_letter].append(word)
    return (words, words_by_letter)


def test_new_completion_1_unquoted(input_obj):

    input_obj.text = '/example '
    input_obj.pos = len(input_obj.text) - 1

    input_obj.new_completion(['toto', 'titi'], 1, quotify=False)
    assert input_obj.text == '/example toto'

    input_obj.new_completion(['toto', 'titi'], 1, quotify=False)
    assert input_obj.text == '/example titi'

    input_obj.new_completion(['toto', 'titi'], 1, quotify=False)
    assert input_obj.text == '/example toto'


def test_new_completion_1_quoted_spaces(input_obj):
    input_obj.text = '/example '
    input_obj.pos = len(input_obj.text) - 1

    input_obj.new_completion(['toto toto', 'titi titi'], 1, quotify=True)
    assert input_obj.text == '/example "toto toto"'

    input_obj.new_completion(['toto toto', 'titi titi'], 1, quotify=True)
    assert input_obj.text == '/example "titi titi"'

    input_obj.new_completion(['toto toto', 'titi titi'], 1, quotify=True)
    assert input_obj.text == '/example "toto toto"'

    input_obj.text = '/example '
    input_obj.pos = len(input_obj.text) - 1
    input_obj.reset_completion()

    input_obj.new_completion(['toto toto', 'tata', 'titi titi'], 1, quotify=True)
    assert input_obj.text == '/example "toto toto"'

    input_obj.new_completion(['toto toto', 'tata', 'titi titi'], 1, quotify=True)
    assert input_obj.text == '/example tata'

    input_obj.new_completion(['toto toto', 'tata', 'titi titi'], 1, quotify=True)
    assert input_obj.text == '/example "titi titi"'

def test_new_completion_unquoted_random_override(input_obj, random_unquoted_words):
    """
    Complete completely random words and ensure that the input is
    changed adequately.
    """
    words = random_unquoted_words

    # try the completion on the middle element without affecting the others
    input_obj.text = '/example %s %s %s' % (words[0], words[1], words[2])
    base = len(input_obj.text) - len(words[2]) - 1
    input_obj.pos = base
    def f(n):
        return '/example %s %s' % (words[0], words[n])

    for i in range(len(words)):
        pos = input_obj.get_argument_position(False)
        input_obj.new_completion(words[:], pos, quotify=False, override=True)
        assert f(i) + " " + words[2] == input_obj.text
        assert len(f(i)) == input_obj.pos

    assert input_obj.text == '/example %s %s %s' % (words[0], words[-1], words[2])

    pos = input_obj.get_argument_position(False)
    input_obj.new_completion(words[:], pos, quotify=False, override=True)
    assert input_obj.text == '/example %s %s %s' % (words[0], words[0], words[2])

    input_obj.reset_completion()

    # try the completion on the final element without affecting the others
    input_obj.text = '/example %s %s %s' % (words[0], words[1], words[2])
    base = len(input_obj.text)
    input_obj.pos = base
    def f2(n):
        return '/example %s %s %s' % (words[0], words[1], words[n])

    print(words)
    for i in range(len(words)):
        pos = input_obj.get_argument_position(False)
        input_obj.new_completion(words[:], pos, quotify=False, override=True)
        assert f2(i) == input_obj.text
        assert len(f2(i)) == input_obj.pos

    assert input_obj.text == '/example %s %s %s' % (words[0], words[1], words[-1])


def test_new_completion_quoted_random(input_obj, quoted_words):
    """
    Complete (possibly) quoted words starting with a specific letter.
    And make sure that the quotes only appear when necessary.
    """
    words = quoted_words[0]
    words_l = quoted_words[1]

    letters = ('', 'a', 'b', 'c')

    # generate the text which is supposed to be present in the input
    def f(p, i):
        rep = words_l[letters[p]][i] if ' ' not in words_l[letters[p]][i] else '"'+words_l[letters[p]][i]+'"'
        fst = letters[1] if p != 1 else rep
        snd = letters[2] if p != 2 else rep
        trd = letters[3] if p != 3 else rep
        return '/example %s %s %s' % (fst, snd, trd)

    for pos in range(1, 4):
        input_obj.text = '/example a b c'
        input_obj.reset_completion()
        input_obj.pos = len('/example') + pos * 2

        extra = (3 - pos) * 2
        for i in range(5):
            input_obj.new_completion(words[:], pos, quotify=True)
            assert f(pos, i) == input_obj.text
            assert len(f(pos, i)) - extra == input_obj.pos

