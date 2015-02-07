#!/usr/bin/env python3

try:
    from setuptools import setup, Extension
except ImportError:
    print('\nSetuptools was not found. Install setuptools for python 3.\n')
    import sys
    sys.exit(1)

import os

module_poopt = Extension('poezio.poopt',
                    extra_compile_args=['-Wno-declaration-after-statement'],
                    sources = ['src/pooptmodule.c'])


current_dir = os.path.dirname(__file__)

# Create a link to the config file (for packaging purposes)
if not os.path.exists(os.path.join(current_dir, 'src', 'default_config.cfg')):
    os.link(os.path.join(current_dir, 'data', 'default_config.cfg'),
            os.path.join(current_dir, 'src',  'default_config.cfg'))

# identify the git version
git_dir = os.path.join(current_dir, '.git')
if os.path.exists(git_dir):
    try:
        import subprocess
        result = subprocess.Popen(['git', '--git-dir', git_dir, 'describe'],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        result.wait()
        data = result.stdout.read().decode('utf-8', errors='ignore')
        version = '.dev' + data.split('-')[1]
    except:
        version = '.dev1'
else:
    version = '.dev1'

setup(name="poezio",
       version="0.9" + version,
       description="A console XMPP client",
       long_description=
       "Poezio is a Free chat client aiming to reproduce the ease of use of most "
       "IRC clients (e.g. weechat, irssi) while using the XMPP network."
       "\n"
       "Documentation is available at http://doc.poez.io/.",

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

       install_requires = ['slixmpp',
                           'aiodns'],
       extras_require = {'OTR plugin': 'python-potr>=1.0',
                         'Screen autoaway plugin': 'pyinotify==0.9.4'}
)

# Remove the link afterwards
if os.path.exists(os.path.join(current_dir, 'src', 'default_config.cfg')):
    os.unlink(os.path.join(current_dir, 'src', 'default_config.cfg'))

