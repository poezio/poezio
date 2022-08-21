// Copyright (C) 2022 Maxime “pep” Buquet <pep@bouah.net>
//
// This program is free software: you can redistribute it and/or modify it
// under the terms of the GNU Affero General Public License as published by the
// Free Software Foundation, either version 3 of the License, or (at your
// option) any later version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
// FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License
// for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

use std::cell::LazyCell;

use directories::ProjectDirs;
use pyo3::{
    marker::Python,
    prelude::{pyclass, pymethods, PyObject, PyResult},
    IntoPy,
};

/// Project qualifier
pub const QUALIFIER: &'static str = "io";
/// Project organization
pub const ORGANIZATION: &'static str = "poez";
/// Project appname
pub const APPNAME: &'static str = "Poezio";

/// Project directories
pub const PROJECT: LazyCell<ProjectDirs> = LazyCell::new(|| {
    ProjectDirs::from(QUALIFIER, ORGANIZATION, APPNAME).expect("HOME dir should be available.")
});

#[pyclass(name = "XDG")]
pub struct PyProject(ProjectDirs);

fn get_path(py: Python<'_>) -> PyResult<PyObject> {
    // TODO: Stop importing pathlib all the time
    let pathlib = py.import("pathlib")?;
    let path = pathlib.getattr("Path")?;
    Ok(path.into_py(py))
}

impl PyProject {
    pub fn new(dirs: ProjectDirs) -> Self {
        PyProject(dirs)
    }
}

#[pymethods]
impl PyProject {
    #[getter]
    pub fn cache_dir(&self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(get_path(py)?.call1(py, (self.0.cache_dir(),))?)
    }

    #[getter]
    pub fn config_dir(&self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(get_path(py)?.call1(py, (self.0.config_dir(),))?)
    }

    #[getter]
    pub fn data_dir(&self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(get_path(py)?.call1(py, (self.0.data_dir(),))?)
    }
}
