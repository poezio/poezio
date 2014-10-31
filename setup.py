#!/usr/bin/env python3

try:
    from setuptools import setup, Extension
except ImportError:
    print('Setuptools was not found.\n'
          'This script will use distutils instead, which will NOT'
          ' be able to install a `poezio` executable.\nIf you are '
          'using it to build a package or install poezio, please '
          'install setuptools.\n\nYou will also see a few warnings.\n')
    from distutils.core import setup, Extension

import os

module_poopt = Extension('poezio.poopt',
                    extra_compile_args=['-Wno-declaration-after-statement'],
                    sources = ['src/pooptmodule.c'])


current_dir = os.path.dirname(__file__)

# Create a link to the config file (for packaging purposes)
if not os.path.exists(os.path.join(current_dir, 'src', 'default_config.cfg')):
    os.link(os.path.join(current_dir, 'data', 'default_config.cfg'),
            os.path.join(current_dir, 'src',  'default_config.cfg'))

setup(name="poezio",
       version="0.8.3-dev",
       description="A console XMPP client",
       long_description=
       "Poezio is a Free chat client aiming to reproduce the ease of use of most "
       "IRC clients (e.g. weechat, irssi) while using the XMPP network."
       "\n"
       "Documentation is available at http://doc.poez.io/0.8.",


       ext_modules = [module_poopt],
       url = 'http://poez.io/',
       license = 'zlib',
       download_url = 'https://dev.louiz.org/projects/poezio/files',

       author = 'Florent Le Coz',
       author_email = 'louiz@louiz.org',

       maintainer = 'Mathieu Pasquet',
       maintainer_email = 'mathieui@mathieui.net',

       classifiers = ['Development Status :: 2 - Pre-Alpha',
                       'Topic :: Communications :: Chat',
                       'Environment :: Console :: Curses',
                       'Intended Audience :: End Users/Desktop',
                       'License :: OSI Approved :: zlib/libpng License',
                       'Natural Language :: English',
                       'Operating System :: Unix',
                       'Programming Language :: Python :: 3'
                    ],
       keywords = ['jabber', 'xmpp', 'client', 'chat', 'im', 'console'],
       packages = ['poezio', 'poezio.core', 'poezio.tabs', 'poezio.windows',
                   'poezio_plugins', 'poezio_plugins.gpg', 'poezio_themes'],
       package_dir = {'poezio': 'src', 'poezio_plugins': 'plugins', 'poezio_themes': 'data/themes'},
       package_data = {'poezio': ['default_config.cfg']},
       scripts = ['scripts/poezio_gpg_export'],
       entry_points={ 'console_scripts': [ 'poezio = poezio:main' ] },
       data_files = [('share/man/man1/', ['data/poezio.1'])],

       install_requires = ['sleekxmpp>=1.2.4',
                           'dnspython3>=1.10.0'],
       extras_require = {'OTR plugin': 'python-potr>=1.0',
                         'Screen autoaway plugin': 'pyinotify==0.9.4'}
)

# Remove the link afterwards
if os.path.exists(os.path.join(current_dir, 'src', 'default_config.cfg')):
    os.unlink(os.path.join(current_dir, 'src', 'default_config.cfg'))

