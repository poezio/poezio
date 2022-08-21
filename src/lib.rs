#![feature(once_cell)]

pub mod args;
pub mod error;
pub mod logger;
pub mod theming;
mod xdg;

use crate::args::parse_args;
use crate::logger::LogItem;
use crate::theming::{curses_attr, parse_attrs};

use chrono::{Datelike, Timelike};
use pyo3::{
    conversion::{IntoPy, ToPyObject},
    create_exception,
    exceptions::PyIOError,
    marker::Python,
    prelude::{pyfunction, pymodule, wrap_pyfunction, PyErr, PyModule, PyObject, PyResult},
    types::{PyDateTime, PyDict},
};

create_exception!(libpoezio, LogParseError, pyo3::exceptions::PyException);

#[pymodule]
fn libpoezio(py: Python, m: &PyModule) -> PyResult<()> {
    m.add("LogParseError", py.get_type::<LogParseError>())?;
    m.add_function(wrap_pyfunction!(to_curses_attr, m)?)?;
    m.add_function(wrap_pyfunction!(parse_logs, m)?)?;
    m.add_function(wrap_pyfunction!(run_cmdline_args, m)?)?;
    m.add("XDG", xdg::PyProject::new(xdg::PROJECT.clone()))?;

    Ok(())
}

macro_rules! py_object {
    ($py:ident, $i:expr) => {
        $i.into_py($py).to_object($py)
    };
}

fn nom_to_py_err(py: Python, err: nom::Err<nom::error::Error<&str>>) -> PyErr {
    LogParseError::new_err(py_object!(py, err.to_string()))
}

#[pyfunction]
fn to_curses_attr(py: Python, fg: i16, bg: i16, attrs: &str) -> PyResult<PyObject> {
    let attrs = match parse_attrs(attrs) {
        Ok(attrs) => attrs,
        Err(err) => return Err(nom_to_py_err(py, err)),
    };
    let result = curses_attr(fg, bg, attrs);
    Ok(py_object!(py, result))
}

fn chrono_to_datetime(py: Python, chrono: &chrono::DateTime<chrono::Utc>) -> PyResult<PyObject> {
    let datetime = PyDateTime::new(
        py,
        chrono.year(),
        chrono.month() as u8,
        chrono.day() as u8,
        chrono.hour() as u8,
        chrono.minute() as u8,
        chrono.second() as u8,
        0,
        None,
    )?;
    Ok(datetime.to_object(py))
}

#[pyfunction]
fn parse_logs(py: Python, input: &str) -> PyResult<PyObject> {
    let logs = match logger::parse_logs(input) {
        Ok((_, logs)) => logs,
        Err(err) => return Err(nom_to_py_err(py, err)),
    };
    let mut items = Vec::new();
    for item in logs {
        let dict = PyDict::new(py);
        let (time, txt) = match item {
            logger::Item::Message(message) => {
                let time = chrono_to_datetime(py, message.get_time())?;
                dict.set_item("nickname", message.get_nick())?;
                (time, message.get_message())
            }
            logger::Item::Info(info) => {
                let time = chrono_to_datetime(py, info.get_time())?;
                (time, info.get_message())
            }
        };
        dict.set_item("history", true)?;
        dict.set_item("time", time)?;
        dict.set_item("txt", txt)?;
        items.push(dict);
    }
    Ok(items.into_py(py).to_object(py))
}

#[pyfunction]
fn run_cmdline_args(py: Python, argv: Vec<String>) -> PyResult<(PyObject, bool)> {
    let (args, firstrun) = parse_args(argv).map_err(|err| PyIOError::new_err(err.to_string()))?;
    Ok((args.into_py(py), firstrun))
}
