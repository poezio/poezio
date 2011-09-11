from distutils.core import setup, Extension

module_poopt = Extension('poopt',
                    sources = ['pooptmodule.c'])

setup (name = 'BuildLines',
       version = '0.0.1',
       description = 'Poezio Optimizations',
       ext_modules = [module_poopt],
       author = 'Florent Le Coz',
       author_email = 'louiz@louiz.org',
       long_description = """
       a python3 module for poezio, used to replace some time-critical
       python functions that are too slow. If compiled, poezio will use this module,
       otherwise it will just use the equivalent python functions.
       """)
