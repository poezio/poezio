// Copyright (C) 2022 Maxime “pep” Buquet <pep@bouah.net>
//
// This program is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by the
// Free Software Foundation, either version 3 of the License, or (at your
// option) any later version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
// FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
// for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

use crate::error::Error;
use crate::xdg::PROJECT;

use std::cell::LazyCell;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

use clap::Parser;
use pyo3::{
    marker::Python,
    prelude::{pyclass, pymethods, PyObject, PyResult},
};

const VERSION: &'static str = "v0.14.0";
const CONFIG_FILE: LazyCell<PathBuf> =
    LazyCell::new(|| PROJECT.config_dir().to_path_buf().join("poezio.cfg"));

#[pyclass]
#[derive(Parser, Debug)]
#[clap(author, version = VERSION, about, long_about = None)]
pub(crate) struct Args {
    /// Check the config file
    #[pyo3(get)]
    #[clap(short, long, action)]
    pub(crate) check_config: bool,

    /// The file where debug will be written
    #[clap(short, long, value_name = "DEBUG_FILE")]
    pub(crate) debug: Option<PathBuf>,

    /// The config file to use
    #[clap(short, long = "file", value_name = "CONFIG_FILE", default_value_os_t = CONFIG_FILE.to_path_buf())]
    pub(crate) filename: PathBuf,

    /// Custom version passed to Poezio
    #[pyo3(get)]
    #[clap(long, help = None, default_value_t = VERSION.to_string())]
    pub(crate) custom_version: String,
}

#[pymethods]
impl Args {
    #[getter]
    fn debug(&self, py: Python<'_>) -> PyResult<PyObject> {
        // TODO: Stop importing pathlib all the time
        let pathlib = py.import("pathlib")?;
        let path: PyObject = pathlib.getattr("Path")?.extract()?;
        if let Some(ref debug) = self.debug {
            Ok(path.call1(py, (debug.clone(),))?)
        } else {
            Ok(py.None())
        }
    }

    #[getter]
    fn filename(&self, py: Python<'_>) -> PyResult<PyObject> {
        // TODO: Stop importing pathlib all the time
        let pathlib = py.import("pathlib")?;
        let path: PyObject = pathlib.getattr("Path")?.extract()?;
        Ok(path.call1(py, (self.filename.clone(),))?)
    }
}

/// Parse command line arguments and return whether it's our firstrun alongside Args
pub(crate) fn parse_args(argv: Vec<String>) -> Result<(Args, bool), Error> {
    let args = Args::parse_from(argv);

    if args.filename.exists() {
        return Ok((args, false));
    };

    let parent = args
        .filename
        .parent()
        .ok_or(Error::UnableToCreateConfigDir)?;
    fs::create_dir_all(parent).map_err(|_| Error::UnableToCreateConfigDir)?;
    let default = include_bytes!("../data/default_config.cfg");
    let mut file = fs::File::create(args.filename.clone())?;
    file.write_all(default)?;
    Ok((args, true))
}
