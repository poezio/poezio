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

use std::error::Error as StdError;
use std::fmt;
use std::io;

#[derive(Debug)]
pub(crate) enum Error {
    IOError(io::Error),
    UnableToCreateConfigDir,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::IOError(e) => write!(f, "io error: {}", e),
            Error::UnableToCreateConfigDir => write!(f, "Unable to create config dir"),
        }
    }
}

impl StdError for Error {}

impl From<io::Error> for Error {
    fn from(err: io::Error) -> Error {
        Error::IOError(err)
    }
}
