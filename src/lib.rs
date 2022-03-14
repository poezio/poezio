extern crate pyo3;
#[macro_use]
extern crate nom;
extern crate ncurses;
#[macro_use]
extern crate lazy_static;
extern crate enum_set;

pub mod theming;

use self::theming::{curses_attr, parse_attrs};

use pyo3::{
    conversion::{IntoPy, ToPyObject},
    create_exception,
    marker::Python,
    prelude::{pyfunction, pymodule, wrap_pyfunction, PyErr, PyModule, PyObject, PyResult},
};

create_exception!(libpoezio, LogParseError, pyo3::exceptions::PyException);

#[pymodule]
fn libpoezio(py: Python, m: &PyModule) -> PyResult<()> {
    m.add("LogParseError", py.get_type::<LogParseError>())?;
    m.add_function(wrap_pyfunction!(to_curses_attr, m)?)?;

    Ok(())
}

macro_rules! py_object {
    ($py:ident, $i:expr) => {
        $i.into_py($py).to_object($py)
    };
}

fn nom_to_py_err(py: Python, err: nom::Err<&str>) -> PyErr {
    LogParseError::new_err(py_object!(py, err.into_error_kind().description()))
}

#[pyfunction]
fn to_curses_attr(py: Python, fg: i16, bg: i16, attrs: &str) -> PyResult<PyObject> {
    let attrs = match parse_attrs(attrs) {
        Ok(attrs) => attrs.1,
        Err(err) => return Err(nom_to_py_err(py, err)),
    };
    let result = curses_attr(fg, bg, attrs);
    Ok(py_object!(py, result))
}
