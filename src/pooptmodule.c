/* Copyright 2010-2011 Florent Le Coz <louiz@louiz.org> */

/* This file is part of Poezio. */

/* Poezio is free software: you can redistribute it and/or modify */
/* it under the terms of the MIT license. See the COPYING file. */

/** The poopt python3 module
**/

/* This file is a python3 module for poezio, used to replace some time-critical
python functions that are too slow. If compiled, poezio will use this module,
otherwise it will just use the equivalent python functions. */

#define PY_SSIZE_T_CLEAN

#include "Python.h"

PyObject *ErrorObject;
#define DEBUG(...) fprintf(stderr, __VA_ARGS__)

/***
    The module functions
 ***/

/* cut_text: takes a string and returns a tuple of int.
   Each two int tuple is a line, represented by the ending position it (where it should be cut).
   Not that this position is calculed using the position of the python string characters,
   not just the individual bytes.
   For example, poopt_cut_text("vivent les frigidaires", 6);
   will return [(0, 6), (7, 10), (11, 17), (17, 22)], meaning that the lines are
   "vivent", "les", "frigid" and "aires"
*/
PyDoc_STRVAR(poopt_cut_text_doc, "cut_text(width, text)\n\n\nReturn the list of strings, cut according to the given size.");

static PyObject *poopt_cut_text(PyObject *self, PyObject *args)
{
  int length;
  unsigned char *buffer;
  int width;

  if (PyArg_ParseTuple(args, "es#i", NULL, &buffer, &length, &width) == 0)
    return NULL;

  int bpos = 0;			/* the real position in the char* */
  int spos = 0;			/* the position, considering UTF-8 chars */
  int last_space = -1;
  int start_pos = 0;

  PyObject* retlist = PyList_New(0);

  while (bpos < length)
    {
      if (buffer[bpos] == ' ')
	last_space = spos;
      else if (buffer[bpos] == '\n')
	{
	  if (PyList_Append(retlist, Py_BuildValue("ii", start_pos, spos)) == -1)
	    return NULL;
	  start_pos = spos + 1;
	  last_space = -1;
	}
      else if ((spos - start_pos) >= width)
      	{
      	  if (last_space == -1)
      	    {
      	      if (PyList_Append(retlist, Py_BuildValue("ii", start_pos, spos)) == -1)
      	      	return NULL;
      	      start_pos = spos;
	    }
      	  else
      	    {
      	      if (PyList_Append(retlist, Py_BuildValue("ii", start_pos, last_space)) == -1)
      	  	return NULL;
      	      start_pos = last_space + 1;
      	      last_space = -1;
      	    }
      	}
      if (buffer[bpos] == 25)	/* \x19 */
      	{
      	  spos--;
      	  bpos += 1;
      	}
      else if (buffer[bpos] <= 127) /* ASCII char on one byte */
	bpos += 1;
      else if (buffer[bpos] <= 195)
	bpos += 2;
      else if (buffer[bpos] <= 225)
	bpos += 3;
      else
	bpos += 4;
      spos++;
    }
  if (PyList_Append(retlist, Py_BuildValue("(i,i)", start_pos, spos)) == -1)
    return NULL;
  return retlist;
}

/***
    Module initialization. Just taken from the xxmodule.c template from the python sources.
 ***/
static PyTypeObject Str_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "pooptmodule.Str",          /*tp_name*/
    0,                          /*tp_basicsize*/
    0,                          /*tp_itemsize*/
    /* methods */
    0,                          /*tp_dealloc*/
    0,                          /*tp_print*/
    0,                          /*tp_getattr*/
    0,                          /*tp_setattr*/
    0,                          /*tp_reserved*/
    0,                          /*tp_repr*/
    0,                          /*tp_as_number*/
    0,                          /*tp_as_sequence*/
    0,                          /*tp_as_mapping*/
    0,                          /*tp_hash*/
    0,                          /*tp_call*/
    0,                          /*tp_str*/
    0,                          /*tp_getattro*/
    0,                          /*tp_setattro*/
    0,                          /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    0,                          /*tp_doc*/
    0,                          /*tp_traverse*/
    0,                          /*tp_clear*/
    0,                          /*tp_richcompare*/
    0,                          /*tp_weaklistoffset*/
    0,                          /*tp_iter*/
    0,                          /*tp_iternext*/
    0,                          /*tp_methods*/
    0,                          /*tp_members*/
    0,                          /*tp_getset*/
    0, /* see PyInit_xx */      /*tp_base*/
    0,                          /*tp_dict*/
    0,                          /*tp_descr_get*/
    0,                          /*tp_descr_set*/
    0,                          /*tp_dictoffset*/
    0,                          /*tp_init*/
    0,                          /*tp_alloc*/
    0,                          /*tp_new*/
    0,                          /*tp_free*/
    0,                          /*tp_is_gc*/
};

/* ---------- */

static PyObject *
null_richcompare(PyObject *self, PyObject *other, int op)
{
  Py_INCREF(Py_NotImplemented);
  return Py_NotImplemented;
}

static PyTypeObject Null_Type = {
  PyVarObject_HEAD_INIT(NULL, 0)
  "pooptmodule.Null",            /*tp_name*/
  0,                          /*tp_basicsize*/
  0,                          /*tp_itemsize*/
  /* methods */
  0,                          /*tp_dealloc*/
  0,                          /*tp_print*/
  0,                          /*tp_getattr*/
  0,                          /*tp_setattr*/
  0,                          /*tp_reserved*/
  0,                          /*tp_repr*/
  0,                          /*tp_as_number*/
  0,                          /*tp_as_sequence*/
  0,                          /*tp_as_mapping*/
  0,                          /*tp_hash*/
  0,                          /*tp_call*/
  0,                          /*tp_str*/
  0,                          /*tp_getattro*/
  0,                          /*tp_setattro*/
  0,                          /*tp_as_buffer*/
  Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
  0,                          /*tp_doc*/
  0,                          /*tp_traverse*/
  0,                          /*tp_clear*/
  null_richcompare,           /*tp_richcompare*/
  0,                          /*tp_weaklistoffset*/
  0,                          /*tp_iter*/
  0,                          /*tp_iternext*/
  0,                          /*tp_methods*/
  0,                          /*tp_members*/
  0,                          /*tp_getset*/
  0, /* see PyInit_xx */      /*tp_base*/
  0,                          /*tp_dict*/
  0,                          /*tp_descr_get*/
  0,                          /*tp_descr_set*/
  0,                          /*tp_dictoffset*/
  0,                          /*tp_init*/
  0,                          /*tp_alloc*/
  0, /* see PyInit_xx */      /*tp_new*/
  0,                          /*tp_free*/
  0,                          /*tp_is_gc*/
};


/* List of functions defined in the module */

static PyMethodDef poopt_methods[] = {
  {"cut_text",             poopt_cut_text,         METH_VARARGS,
   poopt_cut_text_doc},
  {NULL,              NULL}           /* sentinel */
};

PyDoc_STRVAR(module_doc,
	     "This is a template module just for instruction. And poopt.");

/* Initialization function for the module (*must* be called PyInit_xx) */

static struct PyModuleDef pooptmodule = {
  PyModuleDef_HEAD_INIT,
  "poopt",
  module_doc,
  -1,
  poopt_methods,
  NULL,
  NULL,
  NULL,
  NULL
};

PyMODINIT_FUNC
PyInit_poopt(void)
{
  PyObject *m = NULL;

  /* Due to cross platform compiler issues the slots must be filled
   * here. It's required for portability to Windows without requiring
   * C++. */
  Null_Type.tp_base = &PyBaseObject_Type;
  Null_Type.tp_new = PyType_GenericNew;
  Str_Type.tp_base = &PyUnicode_Type;

  /* Finalize the type object including setting type of the new type
   * object; doing it here is required for portability, too. */
  /* if (PyType_Ready(&Xxo_Type) < 0) */
  /*     goto fail; */

  /* Create the module and add the functions */
  m = PyModule_Create(&pooptmodule);
  if (m == NULL)
    goto fail;

  /* Add some symbolic constants to the module */
  if (ErrorObject == NULL) {
    ErrorObject = PyErr_NewException("poopt.error", NULL, NULL);
    if (ErrorObject == NULL)
      goto fail;
  }
  Py_INCREF(ErrorObject);
  PyModule_AddObject(m, "error", ErrorObject);

  /* Add Str */
  if (PyType_Ready(&Str_Type) < 0)
    goto fail;
  PyModule_AddObject(m, "Str", (PyObject *)&Str_Type);

  /* Add Null */
  if (PyType_Ready(&Null_Type) < 0)
    goto fail;
  PyModule_AddObject(m, "Null", (PyObject *)&Null_Type);
  return m;
 fail:
  Py_XDECREF(m);
  return NULL;
}

/* /\* test function *\/ */
/* int main(void) */
/* { */
/*   char coucou[] = "vive le foutre, le beurre et le caca boudin"; */

/*   cut_text(coucou, 8); */
/* } */
