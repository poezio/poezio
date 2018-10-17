use std::str::FromStr;
use std::mem;
use enum_set::EnumSet;
use crate::theming::{Attr, curses_attr, parse_attrs};
use ncurses::{WINDOW, waddstr, wattrset, wattron, getyx};

#[derive(Debug, PartialEq)]
pub enum Item<'a> {
    AttrSet0,
    AttrOn(Attr),
    ColourOn(i16, i16),
    AttrOnEx(i16, i16, EnumSet<Attr>),
    Text(&'a str),
}

impl<'a> Item<'a> {
    fn print_window(&self, window: WINDOW) {
        // TODO: handle wattroff() too, or at least figure out what it breaks not to do it.
        match *self {
            Item::AttrSet0 => wattrset(window, 0),
            Item::AttrOn(attr) => wattron(window, attr.get_attron()),
            Item::ColourOn(fg, bg) => wattron(window, curses_attr(fg, bg, EnumSet::new())),
            Item::AttrOnEx(fg, bg, attrs) => wattron(window, curses_attr(fg, bg, attrs)),
            Item::Text(text) => waddstr(window, text),
        };
    }
}

named!(
    tag_value<&str, Item>,
    alt_complete!(
        tag!("o") => { |_| Item::AttrSet0 } |
        tag!("b") => { |_| Item::AttrOn(Attr::Bold) } |
        tag!("i") => { |_| Item::AttrOn(Attr::Italic) } |
        tag!("u") => { |_| Item::AttrOn(Attr::Underline) } |
        tag!("a") => { |_| Item::AttrOn(Attr::Blink) } |
        do_parse!(
            fg: map_res!(take_till1!(|c| c == '}'), i16::from_str) >>
            tag!("}") >>
            (fg)) => { |fg| Item::ColourOn(fg, -1) } |
        do_parse!(
            fg: map_res!(take_till1!(|c| c == ','), i16::from_str) >>
            tag!(",") >>
            bg: map_res!(take_till1!(|c| c == '}'), i16::from_str) >>
            tag!("}") >>
            (fg, bg)) => { |(fg, bg)| Item::ColourOn(fg, bg) } |
        do_parse!(
            fg: map_res!(take_till1!(|c| c == ','), i16::from_str) >>
            tag!(",") >>
            bg: map_res!(take_till1!(|c| c == ','), i16::from_str) >>
            tag!(",") >>
            attrs: map_res!(take_till1!(|c| c == '}'), parse_attrs) >>
            tag!("}") >>
            (fg, bg, attrs.1)) => { |(fg, bg, attrs)| Item::AttrOnEx(fg, bg, attrs) }
    )
);

fn is_string_character(ch: char) -> bool {
    ch != '\x19'
}

named!(
    parse_string_item<&str, Item>,
    alt_complete!(
        do_parse!(tag!("\x19") >> item: tag_value >> (item)) => { |item| item } |
        take_while!(is_string_character) => { |text| Item::Text(text) }
    )
);

named!(
    pub parse_string<&str, Vec<Item>>,
    many0!(
        parse_string_item
    )
);

pub(crate) fn print_string(window: WINDOW, string: Vec<Item>) {
    for item in string {
        item.print_window(window);
    }
}

pub(crate) fn finish_line(window: WINDOW, width: i32, colour: Option<(i16, i16)>) {
    let mut y: i32 = unsafe { mem::uninitialized() };
    let mut x: i32 = unsafe { mem::uninitialized() };
    getyx(window, &mut y, &mut x);
    let spaces = [' '].iter().cycle().take((width - x) as usize).collect::<String>();
    if let Some(colour) = colour {
        Item::ColourOn(colour.0, colour.1).print_window(window);
    }
    Item::Text(&spaces).print_window(window);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_tag() {
        assert_eq!(tag_value("1,-1,u}").unwrap().1, Item::AttrOnEx(1, -1, { let mut set = EnumSet::new(); set.insert(Attr::Underline); set }));
        assert_eq!(tag_value("1,2}").unwrap().1, Item::ColourOn(1, 2));
        tag_value("toto").unwrap_err();
    }

    #[test]
    fn single_tags() {
        assert_eq!(parse_string_item("\x19o").unwrap().1, Item::AttrSet0);
        assert_eq!(parse_string_item("\x19b").unwrap().1, Item::AttrOn(Attr::Bold));
        assert_eq!(parse_string_item("\x19i").unwrap().1, Item::AttrOn(Attr::Italic));
        assert_eq!(parse_string_item("\x19u").unwrap().1, Item::AttrOn(Attr::Underline));
        assert_eq!(parse_string_item("\x19a").unwrap().1, Item::AttrOn(Attr::Blink));
        assert_eq!(parse_string_item("\x191}").unwrap().1, Item::ColourOn(1, -1));
        assert_eq!(parse_string_item("\x1933,41}").unwrap().1, Item::ColourOn(33, 41));
        assert_eq!(parse_string_item("\x1933,41,bu}").unwrap().1, Item::AttrOnEx(33, 41, { let mut set = EnumSet::new(); set.insert(Attr::Bold); set.insert(Attr::Underline); set }));
    }

    #[test]
    fn single_string() {
        assert_eq!(parse_string_item("Hello world!\x19o").unwrap().1, Item::Text("Hello world!"));
    }

    #[test]
    fn bold_string() {
        assert_eq!(parse_string("\x19bHello world!\x19o").unwrap().1, &[Item::AttrOn(Attr::Bold), Item::Text("Hello world!"), Item::AttrSet0]);
    }
}
