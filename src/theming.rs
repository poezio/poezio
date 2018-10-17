use std::collections::HashMap;
use std::sync::Mutex;
use std::mem;
use enum_set::{EnumSet, CLike};
use ncurses::{attr_t, A_BOLD, A_ITALIC, A_UNDERLINE, A_BLINK, init_pair, COLOR_PAIR, COLORS};

#[derive(Debug, PartialEq, Clone, Copy)]
#[repr(u32)]
pub enum Attr {
    Bold,
    Italic,
    Underline,
    Blink,
}

impl Attr {
    pub fn get_attron(&self) -> attr_t {
        match *self {
            Attr::Bold => A_BOLD(),
            Attr::Italic => A_ITALIC(),
            Attr::Underline => A_UNDERLINE(),
            Attr::Blink => A_BLINK(),
        }
    }
}

impl CLike for Attr {
    fn to_u32(&self) -> u32 {
        *self as u32
    }

    unsafe fn from_u32(v: u32) -> Self {
        mem::transmute(v)
    }
}

named!(
    pub(crate) parse_attrs<&str, EnumSet<Attr>>,
    do_parse!(
        vec: many0!(alt_complete!(
            tag!("b") => { |_| Attr::Bold } |
            tag!("i") => { |_| Attr::Italic } |
            tag!("u") => { |_| Attr::Underline } |
            tag!("a") => { |_| Attr::Blink }
        )) >>
        ({
            let mut set = EnumSet::new();
            set.extend(vec);
            set
        })
    )
);

lazy_static! {
    // TODO: probably replace that mutex with an atomic.
    static ref NEXT_PAIR: Mutex<i16> = Mutex::new(1);

    /// a dict "color tuple -> color_pair"
    /// Each time we use a color tuple, we check if it has already been used.
    /// If not we create a new color_pair and keep it in that dict, to use it
    /// the next time.
    static ref COLOURS_DICT: Mutex<HashMap<(i16, i16), i16>> = {
        Mutex::new(HashMap::new())
    };

    static ref TABLE_256_TO_16: Vec<u8> = vec![
         0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
         0,  4,  4,  4, 12, 12,  2,  6,  4,  4, 12, 12,  2,  2,  6,  4,
        12, 12,  2,  2,  2,  6, 12, 12, 10, 10, 10, 10, 14, 12, 10, 10,
        10, 10, 10, 14,  1,  5,  4,  4, 12, 12,  3,  8,  4,  4, 12, 12,
         2,  2,  6,  4, 12, 12,  2,  2,  2,  6, 12, 12, 10, 10, 10, 10,
        14, 12, 10, 10, 10, 10, 10, 14,  1,  1,  5,  4, 12, 12,  1,  1,
         5,  4, 12, 12,  3,  3,  8,  4, 12, 12,  2,  2,  2,  6, 12, 12,
        10, 10, 10, 10, 14, 12, 10, 10, 10, 10, 10, 14,  1,  1,  1,  5,
        12, 12,  1,  1,  1,  5, 12, 12,  1,  1,  1,  5, 12, 12,  3,  3,
         3,  7, 12, 12, 10, 10, 10, 10, 14, 12, 10, 10, 10, 10, 10, 14,
         9,  9,  9,  9, 13, 12,  9,  9,  9,  9, 13, 12,  9,  9,  9,  9,
        13, 12,  9,  9,  9,  9, 13, 12, 11, 11, 11, 11,  7, 12, 10, 10,
        10, 10, 10, 14,  9,  9,  9,  9,  9, 13,  9,  9,  9,  9,  9, 13,
         9,  9,  9,  9,  9, 13,  9,  9,  9,  9,  9, 13,  9,  9,  9,  9,
         9, 13, 11, 11, 11, 11, 11, 15,  0,  0,  0,  0,  0,  0,  8,  8,
         8,  8,  8,  8,  7,  7,  7,  7,  7,  7, 15, 15, 15, 15, 15, 15
    ];
}

fn colour_256_to_16(colour: i16) -> i16 {
    if colour == -1 {
        return -1;
    }
    return TABLE_256_TO_16[colour as usize] as i16
}

fn get_pair(colours: (i16, i16)) -> attr_t {
    let mut dict = COLOURS_DICT.lock().unwrap();
    match dict.get(&colours) {
        Some(val) => COLOR_PAIR(*val),
        None => {
            let mut pair_mut = NEXT_PAIR.lock().unwrap();
            let pair = *pair_mut;
            init_pair(pair, colours.0, colours.1);
            dict.insert(colours, pair);
            *pair_mut += 1;
            COLOR_PAIR(pair)
        }
    }
}

/// Takes a color tuple (as defined at the top of this file) and
/// returns a valid curses attr that can be passed directly to attron() or attroff()
pub fn curses_attr(mut colours: (i16, i16), mut attrs: EnumSet<Attr>) -> attr_t {
    if COLORS() < 256 {
        // We are not in a term supporting 256 colors, so we convert
        // colors to numbers between -1 and 8.
        colours = (colour_256_to_16(colours.0), colour_256_to_16(colours.1));
        if colours.0 >= 8 {
            colours.0 -= 8;
            attrs.insert(Attr::Bold);
        }
        if colours.1 >= 8 {
            colours.1 -= 8;
        }
    };
    let mut pair = get_pair(colours);
    for attr in attrs.iter() {
        pair |= attr.get_attron();
    }
    pair
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn none() {
        let attrs = "";
        let expected = EnumSet::new();
        let received = parse_attrs(attrs).unwrap();
        assert_eq!(received.1, expected);
    }

    #[test]
    fn bold_twice() {
        let attrs = "bb";
        let mut expected = EnumSet::new();
        expected.insert(Attr::Bold);
        let received = parse_attrs(attrs).unwrap();
        assert_eq!(received.1, expected);
    }

    #[test]
    fn all() {
        let attrs = "baiu";
        let mut expected = EnumSet::new();
        expected.insert(Attr::Bold);
        expected.insert(Attr::Blink);
        expected.insert(Attr::Italic);
        expected.insert(Attr::Underline);
        let received = parse_attrs(attrs).unwrap();
        assert_eq!(received.1, expected);
    }
}
