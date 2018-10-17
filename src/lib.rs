#[macro_use]
extern crate cpython;

py_module_initializer!(libpoezio, initlibpoezio, PyInit_libpoezio, |py, m| {
    Ok(())
});
