#[macro_use]
extern crate cpython;
#[macro_use]
extern crate nom;
extern crate chrono;

pub mod logger;

use cpython::{Python, PyResult, PyErr, PyList, PyDict, PyTuple, PyObject, ToPyObject, PythonObject, ObjectProtocol};
use self::logger::LogItem;
use chrono::{DateTime, Utc, Local, Datelike, Timelike};

py_module_initializer!(libpoezio, initlibpoezio, PyInit_libpoezio, |py, m| {
    m.add(py, "parse_logs", py_fn!(py, parse_logs(input: &str)))?;
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

fn parse_logs(py: Python, input: &str) -> PyResult<PyList> {
    let logs = match logger::parse_logs(&input) {
        Ok(logs) => logs,
        Err(err) => {
            println!("{}", err);
            return Err(PyErr {
                ptype: py.get_type::<LogParseError>().into_object(),
                pvalue: Some(LogParseError(err.into_error_kind().description().to_py_object(py).into_object()).into_object()),
                ptraceback: None,
            });
        }
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
