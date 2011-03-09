#/usr/bin/env python
# -*- encoding: utf-8
"""
 * This is a Python implementation of wcwidth() and wcswidth(), based on the
 * C implementation of the same functions (defined in IEEE Std 1002.1-2001)
 * for Unicode:
 *
 * http://www.opengroup.org/onlinepubs/007904975/functions/wcwidth.html
 * http://www.opengroup.org/onlinepubs/007904975/functions/wcswidth.html
 *
 * In fixed-width output devices, Latin characters all occupy a single
 * "cell" position of equal width, whereas ideographic CJK characters
 * occupy two such cells. Interoperability between terminal-line
 * applications and (teletype-style) character terminals using the
 * UTF-8 encoding requires agreement on which character should advance
 * the cursor by how many cell positions. No established formal
 * standards exist at present on which Unicode character shall occupy
 * how many cell positions on character terminals. These routines are
 * a first attempt of defining such behavior based on simple rules
 * applied to data provided by the Unicode Consortium.
 *
 * For some graphical characters, the Unicode standard explicitly
 * defines a character-cell width via the definition of the East Asian
 * FullWidth (F), Wide (W), Half-width (H), and Narrow (Na) classes.
 * In all these cases, there is no ambiguity about which width a
 * terminal shall use. For characters in the East Asian Ambiguous (A)
 * class, the width choice depends purely on a preference of backward
 * compatibility with either historic CJK or Western practice.
 * Choosing single-width for these characters is easy to justify as
 * the appropriate long-term solution, as the CJK practice of
 * displaying these characters as double-width comes from historic
 * implementation simplicity (8-bit encoded characters were displayed
 * single-width and 16-bit ones double-width, even for Greek,
 * Cyrillic, etc.) and not any typographic considerations.
 *
 * Much less clear is the choice of width for the Not East Asian
 * (Neutral) class. Existing practice does not dictate a width for any
 * of these characters. It would nevertheless make sense
 * typographically to allocate two character cells to characters such
 * as for instance EM SPACE or VOLUME INTEGRAL, which cannot be
 * represented adequately with a single-width glyph. The following
 * routines at present merely assign a single-cell width to all
 * neutral characters, in the interest of simplicity. This is not
 * entirely satisfactory and should be reconsidered before
 * establishing a formal standard in this area. At the moment, the
 * decision which Not East Asian (Neutral) characters should be
 * represented by double-width glyphs cannot yet be answered by
 * applying a simple rule from the Unicode database content. Setting
 * up a proper standard for the behavior of UTF-8 character terminals
 * will require a careful analysis not only of each Unicode character,
 * but also of each presentation form, something the author of these
 * routines has avoided to do so far.
 *
 * http://www.unicode.org/unicode/reports/tr11/
 *
 * Markus Kuhn -- 2007-05-26 (Unicode 5.0)
 * Berteun Damman - 2007-06-28 (Python version)
 *
 * Permission to use, copy, modify, and distribute this software
 * for any purpose and without fee is hereby granted. The author
 * disclaims all warranties with regard to this software.
 *
 * Latest C version: http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
"""

# auxiliary function for binary search in interval table, see below
def bisearch(ucs):
    mn = 0
    mx = len(combining_table) - 1
    if ucs < combining_table[0][0] or ucs > combining_table[mx][1]:
        return False

    while mx >= mn:
        mid = (mn + mx) // 2
        if ucs > combining_table[mid][1]:
            mn = mid + 1
        elif ucs < combining_table[mid][0]:
            mx = mid - 1
        else:
            return True

    return False


"""
 * The following two functions define the column width of an ISO 10646
 * character as follows:
 *
 *    - The null character (U+0000) has a column width of 0.
 *
 *    - Other C0/C1 control characters and DEL will lead to a return
 *      value of -1.
 *
 *    - Non-spacing and enclosing combining characters (general
 *      category code Mn or Me in the Unicode database) have a
 *      column width of 0.
 *
 *    - SOFT HYPHEN (U+00AD) has a column width of 1.
 *
 *    - Other format characters (general category code Cf in the Unicode
 *      database) and ZERO WIDTH SPACE (U+200B) have a column width of 0.
 *
 *    - Hangul Jamo medial vowels and final consonants (U+1160-U+11FF)
 *      have a column width of 0.
 *
 *    - Spacing characters in the East Asian Wide (W) or East Asian
 *      Full-width (F) category as defined in Unicode Technical
 *      Report #11 have a column width of 2.
 *
 *    - All remaining characters (including all printable
 *      ISO 8859-1 and WGL4 characters, Unicode control characters,
 *      etc.) have a column width of 1.
 *
 * This implementation assumes that wchar_t characters are encoded
 * in ISO 10646.
"""
# sorted list of non-overlapping intervals of non-spacing characters
# generated by "uniset +cat=Me +cat=Mn +cat=Cf -00AD +1160-11FF +200B c"
combining_table = [
    ('\u0300', '\u036F'), ('\u0483', '\u0486'), ('\u0488', '\u0489'),
    ('\u0591', '\u05BD'), ('\u05BF', '\u05BF'), ('\u05C1', '\u05C2'),
    ('\u05C4', '\u05C5'), ('\u05C7', '\u05C7'), ('\u0600', '\u0603'),
    ('\u0610', '\u0615'), ('\u064B', '\u065E'), ('\u0670', '\u0670'),
    ('\u06D6', '\u06E4'), ('\u06E7', '\u06E8'), ('\u06EA', '\u06ED'),
    ('\u070F', '\u070F'), ('\u0711', '\u0711'), ('\u0730', '\u074A'),
    ('\u07A6', '\u07B0'), ('\u07EB', '\u07F3'), ('\u0901', '\u0902'),
    ('\u093C', '\u093C'), ('\u0941', '\u0948'), ('\u094D', '\u094D'),
    ('\u0951', '\u0954'), ('\u0962', '\u0963'), ('\u0981', '\u0981'),
    ('\u09BC', '\u09BC'), ('\u09C1', '\u09C4'), ('\u09CD', '\u09CD'),
    ('\u09E2', '\u09E3'), ('\u0A01', '\u0A02'), ('\u0A3C', '\u0A3C'),
    ('\u0A41', '\u0A42'), ('\u0A47', '\u0A48'), ('\u0A4B', '\u0A4D'),
    ('\u0A70', '\u0A71'), ('\u0A81', '\u0A82'), ('\u0ABC', '\u0ABC'),
    ('\u0AC1', '\u0AC5'), ('\u0AC7', '\u0AC8'), ('\u0ACD', '\u0ACD'),
    ('\u0AE2', '\u0AE3'), ('\u0B01', '\u0B01'), ('\u0B3C', '\u0B3C'),
    ('\u0B3F', '\u0B3F'), ('\u0B41', '\u0B43'), ('\u0B4D', '\u0B4D'),
    ('\u0B56', '\u0B56'), ('\u0B82', '\u0B82'), ('\u0BC0', '\u0BC0'),
    ('\u0BCD', '\u0BCD'), ('\u0C3E', '\u0C40'), ('\u0C46', '\u0C48'),
    ('\u0C4A', '\u0C4D'), ('\u0C55', '\u0C56'), ('\u0CBC', '\u0CBC'),
    ('\u0CBF', '\u0CBF'), ('\u0CC6', '\u0CC6'), ('\u0CCC', '\u0CCD'),
    ('\u0CE2', '\u0CE3'), ('\u0D41', '\u0D43'), ('\u0D4D', '\u0D4D'),
    ('\u0DCA', '\u0DCA'), ('\u0DD2', '\u0DD4'), ('\u0DD6', '\u0DD6'),
    ('\u0E31', '\u0E31'), ('\u0E34', '\u0E3A'), ('\u0E47', '\u0E4E'),
    ('\u0EB1', '\u0EB1'), ('\u0EB4', '\u0EB9'), ('\u0EBB', '\u0EBC'),
    ('\u0EC8', '\u0ECD'), ('\u0F18', '\u0F19'), ('\u0F35', '\u0F35'),
    ('\u0F37', '\u0F37'), ('\u0F39', '\u0F39'), ('\u0F71', '\u0F7E'),
    ('\u0F80', '\u0F84'), ('\u0F86', '\u0F87'), ('\u0F90', '\u0F97'),
    ('\u0F99', '\u0FBC'), ('\u0FC6', '\u0FC6'), ('\u102D', '\u1030'),
    ('\u1032', '\u1032'), ('\u1036', '\u1037'), ('\u1039', '\u1039'),
    ('\u1058', '\u1059'), ('\u1160', '\u11FF'), ('\u135F', '\u135F'),
    ('\u1712', '\u1714'), ('\u1732', '\u1734'), ('\u1752', '\u1753'),
    ('\u1772', '\u1773'), ('\u17B4', '\u17B5'), ('\u17B7', '\u17BD'),
    ('\u17C6', '\u17C6'), ('\u17C9', '\u17D3'), ('\u17DD', '\u17DD'),
    ('\u180B', '\u180D'), ('\u18A9', '\u18A9'), ('\u1920', '\u1922'),
    ('\u1927', '\u1928'), ('\u1932', '\u1932'), ('\u1939', '\u193B'),
    ('\u1A17', '\u1A18'), ('\u1B00', '\u1B03'), ('\u1B34', '\u1B34'),
    ('\u1B36', '\u1B3A'), ('\u1B3C', '\u1B3C'), ('\u1B42', '\u1B42'),
    ('\u1B6B', '\u1B73'), ('\u1DC0', '\u1DCA'), ('\u1DFE', '\u1DFF'),
    ('\u200B', '\u200F'), ('\u202A', '\u202E'), ('\u2060', '\u2063'),
    ('\u206A', '\u206F'), ('\u20D0', '\u20EF'), ('\u302A', '\u302F'),
    ('\u3099', '\u309A'), ('\uA806', '\uA806'), ('\uA80B', '\uA80B'),
    ('\uA825', '\uA826'), ('\uFB1E', '\uFB1E'), ('\uFE00', '\uFE0F'),
    ('\uFE20', '\uFE23'), ('\uFEFF', '\uFEFF'), ('\uFFF9', '\uFFFB'),
]

    # XXX: There are some issues with Plane 1 Unicode characters on 32-bit
    # systems. As these use UTF-16 internally they will use surrogate pairs
    # to represent the character. I don't know how this works exactly though,
    # therefore, until I've figured it out, if we're on a 32-bit system,
    # we won't include these, otherwise we will.
if '\U0000FFFF' < '\U00010000':
    combining_table.extend([
        ('\U00010A01', '\U00010A03'), ('\U00010A05', '\U00010A06'),
        ('\U00010A0C', '\U00010A0F'), ('\U00010A38', '\U00010A3A'),
        ('\U00010A3F', '\U00010A3F'), ('\U0001D167', '\U0001D169'),
        ('\U0001D173', '\U0001D182'), ('\U0001D185', '\U0001D18B'),
        ('\U0001D1AA', '\U0001D1AD'), ('\U0001D242', '\U0001D244'),
        ('\U000E0001', '\U000E0001'), ('\U000E0020', '\U000E007F'),
        ('\U000E0100', '\U000E01EF'),
      ])

def wcwidth(ucs):
  if len(ucs) > 1:
    raise TypeError('wcwidth() expected a character, '
        'but string of length %d found' % (len(ucs),))
  # test for 8-bit control characters
  if ucs == '\u0000':
    return 0

  # non-printable chars.
  if ucs < '\u0020' or (ucs >= '\u007f' and ucs < '\u00a0'):
    return -1

  # binary search in table of non-spacing characters
  if bisearch(ucs):
    return 0

  # if we arrive here, ucs is not a combining or C0/C1 control character

  return (1 +
    (ucs >= '\u1100' and
     (ucs <= '\u115f' or                    # Hangul Jamo init. consonants
      ucs == '\u2329' or ucs == '\u232a' or
      (ucs >= '\u2e80' and ucs <= '\ua4cf' and
       ucs != '\u303f') or                  # CJK ... Yi
      (ucs >= '\uac00' and ucs <= '\ud7a3') or # Hangul Syllables
      (ucs >= '\uf900' and ucs <= '\ufaff') or # CJK Comp. Ideographs
      (ucs >= '\ufe10' and ucs <= '\ufe19') or # Vertical forms
      (ucs >= '\ufe30' and ucs <= '\ufe6f') or # CJK Comp. Forms
      (ucs >= '\uff00' and ucs <= '\uff60') or # Fullwidth Forms
      (ucs >= '\uffe0' and ucs <= '\uffe6') or
      # XXX: '\U0000FFFF' < '\U00010000' is only True on 64-bit systems.
      # On 32 bit systems it fails, but hopefully it won't cause chars to be
      # misrepresented. It has to do with surrogate pairs, but I don't know
      # how to fix this.
      (('\U0000FFFF' < '\U00010000') and
      (ucs >= '\U00020000' and ucs <= '\U0002fffd') or
      (ucs >= '\U00030000' and ucs <= '\U0003fffd')))))


def wcswidth(s):
    """
    Return the length of the passed string, using wcwidth on each char
    instead of couting 1 for each one.
    """
    width = 0
    for c in s:
        w = wcwidth(c)
        if w < 0:
            # If s contains a non-printable char, we should return -1.
            # This includes newlines and tabs!
            return -1
        else:
            width += w
    return width

def wcsislonger(s, l):
    """
    Returns the same result than "wcswidth(s) > l" but
    is faster.
    """
    width = 0
    for c in s:
        w = wcwidth(c)
        if w < 0:
            return -1
        else:
            width += w
            if width > l:
                return True
    return False

def widthcut(s, m):
    """
    Return the first characters of s that can be contained in
    a m length
    """
    i = 0
    width = 0
    for c in s:
        w = wcwidth(c)
        if w < 0:
            return None
        else:
            width += w

        i += 1
        if width > m:
            return s[:i-1]
    return s

def ljust(s, max, fillchar=" "):
    """
    Like widthcut but adding chars at the end of the string until
    max is reached
    """
    if wcwidth(fillchar)!=1:
        raise TypeError('widthpad() expected fillchar as a character, '
                        'but string of length %d found' % (len(fillchar),))
    i = 0
    width = 0
    for c in s:
        w = wcwidth(c)
        if w < 0:
            return None
        else:
            width += w

        i += 1
        if width==max:
            return s[:i]
        if width > max:
            return s[:i-1]+fillchar

    return s + fillchar*(max-width)

def rjust(s, max, fillchar=" "):
    if wcwidth(fillchar)!=1:
        raise TypeError('widthpad() expected fillchar as a character, '
                        'but string of length %d found' % (len(fillchar),))
    i = 0
    width = 0
    for c in s:
        w = wcwidth(c)
        if w < 0:
            return None
        else:
            width += w

        i += 1
        if width==max:
            return s[:i]
        if width > max:
            return fillchar+s[:i-1]

    return fillchar*(max-width) + s

if __name__ == '__main__':
    import unicodedata
    test_strings = [
        'Pál Erdős', 'Kurt Gödel', 'Évariste Galois',
        "Guillaume de l'Hôpital",
        'ἄνδρα μοι ἔννεπε, μοῦσα, πολύτροπον, ὃς μάλα πολλὰ πλάγχθη',
    ]
    for s in test_strings:
        # d will be the decomposed version, this one should have the
        # same display width, but it should have more characters.
        d = unicodedata.normalize('NFD', s)
        assert wcswidth(s) == wcswidth(d)
        assert len(s) != len(d)
    assert wcswidth('string with \n char') == -1
    assert wcswidth('string with \t char') == -1
    print('Minor testcase succeeded')
