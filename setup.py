from distutils.core import setup, Extension
import os, sys

module_poopt = Extension('poezio.poopt',
                    sources = ['src/pooptmodule.c'])


current_dir = os.path.dirname(__file__)

# Create a link to the config file (for packaging purposes)
if not os.path.exists(os.path.join(current_dir, 'src', 'default_config.cfg')):
    os.link(os.path.join(current_dir, 'data', 'default_config.cfg'),
            os.path.join(current_dir, 'src',  'default_config.cfg'))

setup(name="poezio",
       version="0.8",
       description="A console XMPP client",
       long_description=
       """
       Poezio is a Free chat client aiming to reproduce the ease of use of most
       IRC clients (e.g. weechat, irssi) while using the XMPP network.
       """,
       ext_modules = [module_poopt],
       url = 'http://poezio.eu/',
       license = 'zlib',

       author = 'Florent Le Coz',
       author_email = 'louiz@louiz.org',

       maintainer = 'Mathieu Pasquet',
       maintainer_email = 'mathieui@mathieui.net',

       classifiers = ['Development Status :: 5 - Production/Stable',
                       'Environment :: Console :: Curses',
                       'Intended Audience :: End Users/Desktop',
                       'License :: OSI Approved :: zlib/libpng License',
                       'Natural Language :: English',
                       'Operating System :: Unix',
                       'Topic :: Communications :: Chat',
                       'Programming Language :: Python :: 3',
                    ],
       keywords = ['jabber', 'xmpp', 'client', 'chat', 'im', 'console'],
       packages = ['poezio', 'poezio_plugins', 'poezio_plugins.gpg', 'poezio_themes'],
       package_dir = {'poezio': 'src', 'poezio_plugins': 'plugins', 'poezio_themes': 'data/themes'},
       package_data = {'poezio': ['default_config.cfg']},
       scripts = ['scripts/poezio'],
       data_files = [('share/poezio/themes/', ['data/themes/dark.py']),
           ('share/man/man1/', ['data/poezio.1'])],
)

# Remove the link afterwards
if os.path.exists(os.path.join(current_dir, 'src', 'default_config.cfg')):
    os.unlink(os.path.join(current_dir, 'src', 'default_config.cfg'))

