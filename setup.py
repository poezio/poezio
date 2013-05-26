from distutils.core import setup, Extension

module_poopt = Extension('poezio.poopt',
                    sources = ['src/pooptmodule.c'])

setup(name="poezio",
       version="0.8-dev",
       description="A console XMPP client",
       long_description=
       """
       Poezio is a free chat client aiming to reproduce the ease of use of most
       IRC clients (e.g. weechat, irssi) while using the XMPP network.
       """,
       ext_modules = [module_poopt],
       url = 'http://poezio.eu/',
       license = 'zlib',

       author = 'Florent Le Coz',
       author_email = 'louiz@louiz.org',

       maintainer = 'Mathieu Pasquet',
       maintainer_email = 'mathieui@mathieui.net',

       classifiers = ['Development Status :: 4 - Beta',
                       'Environment :: Console :: Curses',
                       'Intended Audience :: End Users/Desktop',
                       'License :: OSI Approved :: zlib/libpng License',
                       'Natural Language :: English',
                       'Operating System :: Unix',
                       'Topic :: Communications :: Chat',
                       'Programming Language :: Python :: 3',
                    ],
       keywords = ['xmpp', 'chat', 'im', 'console'],
       packages = ['poezio', 'poezio_plugins'],
       package_dir = {'poezio': 'src', 'poezio_plugins': 'plugins'},
       scripts = ['scripts/poezio'],
       data_files = [('/etc/poezio/', ['data/default_config.cfg']),
           ('share/poezio/themes/', ['data/themes/dark.py']),
           ('share/man/man1/', ['data/poezio.1'])],
)
