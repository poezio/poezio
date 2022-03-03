#[macro_use]
extern crate cpython;
#[macro_use]
extern crate nom;
extern crate ncurses;
#[macro_use]
extern crate lazy_static;
extern crate enum_set;

pub mod theming;

use self::theming::{curses_attr, parse_attrs};
use cpython::{PyErr, PyObject, PyResult, Python, PythonObject, ToPyObject};

py_module_initializer!(libpoezio, initlibpoezio, PyInit_libpoezio, |py, m| {
    m.add(
        py,
        "to_curses_attr",
        py_fn!(py, to_curses_attr(fg: i16, bg: i16, attrs: &str)),
    )?;
    Ok(())
});

py_exception!(libpoezio, LogParseError);

macro_rules! py_int {
    ($py:ident, $i:expr) => {
        $i.to_py_object($py).into_object()
    };
}

fn nom_to_py_err(py: Python, err: nom::Err<&str>) -> PyErr {
    PyErr {
        ptype: py.get_type::<LogParseError>().into_object(),
        pvalue: Some(
            LogParseError(
                err.into_error_kind()
                    .description()
                    .to_py_object(py)
                    .into_object(),
            )
            .into_object(),
        ),
        ptraceback: None,
    }
}

fn to_curses_attr(py: Python, fg: i16, bg: i16, attrs: &str) -> PyResult<PyObject> {
    let attrs = match parse_attrs(attrs) {
        Ok(attrs) => attrs.1,
        Err(err) => return Err(nom_to_py_err(py, err)),
    };
    let result = curses_attr(fg, bg, attrs);
    Ok(py_int!(py, result))
}
