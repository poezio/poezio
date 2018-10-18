#[macro_use]
extern crate cpython;
#[macro_use]
extern crate nom;
extern crate chrono;
extern crate ncurses;
#[macro_use]
extern crate lazy_static;
extern crate enum_set;

pub mod logger;
pub mod strings;
pub mod theming;

use std::ffi::c_void;
use cpython::{Python, PyResult, PyErr, PyList, PyDict, PyTuple, PyString, PyObject, ToPyObject, PythonObject, ObjectProtocol};
use self::logger::LogItem;
use chrono::{DateTime, Utc, Local, Datelike, Timelike};
use self::theming::{curses_attr, parse_attrs};
use self::strings::{parse_string, print_string, finish_line as finish_line_, truncate_nick as truncate_nick_};
use ncurses::{WINDOW};

py_module_initializer!(libpoezio, initlibpoezio, PyInit_libpoezio, |py, m| {
    m.add(py, "parse_logs", py_fn!(py, parse_logs(input: &str)))?;
    m.add(py, "to_curses_attr", py_fn!(py, to_curses_attr(fg: i16, bg: i16, attrs: &str)))?;
    m.add(py, "printw", py_fn!(py, printw(window: PyObject, text: &str)))?;
    m.add(py, "finish_line", py_fn!(py, finish_line(window: PyObject, width: i32, color: Option<(i16, i16)>)))?;
    m.add(py, "truncate_nick", py_fn!(py, truncate_nick(nick: &str, size: usize)))?;
    Ok(())
});

py_exception!(libpoezio, LogParseError);

macro_rules! py_int {
    ($py:ident, $i:expr) => ($i.to_py_object($py).into_object())
}

fn chrono_to_datetime(py: Python, chrono: &DateTime<Utc>) -> PyResult<PyObject> {
    let chrono = chrono.with_timezone(&Local);
    let datetime = py.import("datetime")?;
    let datetime = datetime.get(py, "datetime")?;
    let datetime = datetime.call(py, PyTuple::new(py, &[
        py_int!(py, chrono.year()),
        py_int!(py, chrono.month()),
        py_int!(py, chrono.day()),
        py_int!(py, chrono.hour()),
        py_int!(py, chrono.minute()),
        py_int!(py, chrono.second()),
        py_int!(py, chrono.second()),
    ]), None)?;
    Ok(datetime)
}

fn nom_to_py_err<T>(py: Python, err: nom::Err<T>) -> PyErr {
    PyErr {
        ptype: py.get_type::<LogParseError>().into_object(),
        pvalue: Some(LogParseError(err.into_error_kind().description().to_py_object(py).into_object()).into_object()),
        ptraceback: None,
    }
}

unsafe fn get_window_from_python(window: PyObject) -> WINDOW {
    let py_win = window.as_ptr() as *const c_void;
    let win: *const WINDOW = std::mem::transmute(py_win.offset(16));
    *win
}

fn printw(py: Python, window: PyObject, text: &str) -> PyResult<PyObject> {
    let items = match parse_string(text) {
        Ok(items) => items.1,
        Err(err) => return Err(nom_to_py_err(py, err)),
    };
    let win = unsafe { get_window_from_python(window) };
    print_string(win, items);
    Ok(py.None())
}

fn finish_line(py: Python, window: PyObject, width: i32, colour: Option<(i16, i16)>) -> PyResult<PyObject> {
    let win = unsafe { get_window_from_python(window) };
    finish_line_(win, width, colour);
    Ok(py.None())
}

fn truncate_nick(py: Python, nick: &str, size: usize) -> PyResult<PyString> {
    let string = truncate_nick_(nick, size);
    Ok(PyString::new(py, &string))
}

fn to_curses_attr(py: Python, fg: i16, bg: i16, attrs: &str) -> PyResult<PyObject> {
    let attrs = match parse_attrs(attrs) {
        Ok(attrs) => attrs.1,
        Err(err) => return Err(nom_to_py_err(py, err)),
    };
    let result = curses_attr(fg, bg, attrs);
    Ok(py_int!(py, result))
}

fn parse_logs(py: Python, input: &str) -> PyResult<PyList> {
    let logs = match logger::parse_logs(&input) {
        Ok(logs) => logs,
        Err(err) => return Err(nom_to_py_err(py, err)),
    };
    let mut items = vec!();
    for item in logs {
        let dict = PyDict::new(py);
        dict.set_item(py, "history", py.True())?;
        let (time, txt) = match item {
            logger::Item::Message(message) => {
                let time = chrono_to_datetime(py, message.get_time())?;
                dict.set_item(py, "nickname", message.get_nick())?;
                (time, message.get_message())
            },
            logger::Item::Info(info) => {
                let time = chrono_to_datetime(py, info.get_time())?;
                (time, info.get_message())
            },
        };
        dict.set_item(py, "time", time)?;
        dict.set_item(py, "txt", txt)?;
        items.push(dict.into_object());
    }
    let items = PyList::new(py, &items);
    Ok(items)
}
