#!/usr/bin/env python3

try:
    from setuptools import setup, Extension
except ImportError:
    print('\nSetuptools was not found. Install setuptools for python 3.\n')
    import sys
    sys.exit(1)

from os.path import basename, dirname, exists, join
from os import link, walk, unlink

current_dir = dirname(__file__)

def get_relative_dir(folder, stopper):
    """
    Find the path from a directory to a pseudo-root in order to recreate
    the filetree.
    """
    acc = []
    last = basename(folder)
    while last != stopper:
        acc.append(last)
        folder = dirname(folder)
        last = basename(folder)
    return join(*acc[::-1]) if acc else ''

def find_doc(before, path):
    _files = []
    stop = basename(path)
    for root, dirs, files in walk(join(current_dir, 'doc', path)):
        files_path = []
        relative_root = get_relative_dir(root, stop)
        for name in files:
            files_path.append(join(root, name))
        _files.append((join(before, relative_root), files_path))
    return _files

def check_include(library_name, header):
    command = [os.environ.get('PKG_CONFIG', 'pkg-config'), '--cflags', library_name]
    try:
        cflags = check_output(command).decode('utf-8').split()
    except FileNotFoundError:
        print('pkg-config not found.')
        return False
    except CalledProcessError:
        # pkg-config already prints the missing libraries on stderr.
        return False
    command = [os.environ.get('CC', 'cc')] + cflags + ['-E', '-']
    with TemporaryFile('w+') as c_file:
        c_file.write('#include <%s>' % header)
        c_file.seek(0)
        try:
            return call(command, stdin=c_file, stdout=DEVNULL, stderr=DEVNULL) == 0
        except FileNotFoundError:
            print('%s headers not found.' % library_name)
            return False

if not check_include('python3', 'Python.h'):
    import sys
    sys.exit(2)

module_poopt = Extension('poezio.poopt',
                    extra_compile_args=['-Wno-declaration-after-statement'],
                    sources=['poezio/pooptmodule.c'])

# Create a link to the config file (for packaging purposes)
if not exists(join(current_dir, 'poezio', 'default_config.cfg')):
    link(join(current_dir, 'data', 'default_config.cfg'),
         join(current_dir, 'poezio', 'default_config.cfg'))

# identify the git version
git_dir = join(current_dir, '.git')
if exists(git_dir):
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

with open('README.rst', encoding='utf-8') as readme_fd:
    LONG_DESCRIPTION = readme_fd.read()

setup(name="poezio",
      version="1.0" + version,
      description="A console XMPP client",
      long_description=LONG_DESCRIPTION,
      ext_modules=[module_poopt],
      url='https://poez.io/',
      license='zlib',
      download_url='https://dev.louiz.org/projects/poezio/files',

      author='Florent Le Coz',
      author_email='louiz@louiz.org',

      maintainer='Mathieu Pasquet',
      maintainer_email='mathieui@mathieui.net',

      classifiers=['Development Status :: 5 - Production/Stable',
                   'Topic :: Communications :: Chat',
                   'Topic :: Internet :: XMPP',
                   'Environment :: Console :: Curses',
                   'Intended Audience :: End Users/Desktop',
                   'License :: OSI Approved :: zlib/libpng License',
                   'Natural Language :: English',
                   'Operating System :: Unix',
                   'Programming Language :: Python :: 3.6',
                   'Programming Language :: Python :: 3.5',
                   'Programming Language :: Python :: 3.4',
                   'Programming Language :: Python :: 3 :: Only'],
      keywords=['jabber', 'xmpp', 'client', 'chat', 'im', 'console'],
      packages=['poezio', 'poezio.core', 'poezio.tabs', 'poezio.windows',
                'poezio_plugins', 'poezio_plugins.gpg', 'poezio_themes'],
      package_dir={'poezio': 'poezio',
                   'poezio_plugins': 'plugins',
                   'poezio_themes': 'data/themes'},
      package_data={'poezio': ['default_config.cfg']},
      scripts=['scripts/poezio_gpg_export', 'scripts/poezio_logs'],
      entry_points={'console_scripts': ['poezio = poezio.__main__:run']},
      data_files=([('share/man/man1/', ['data/poezio.1',
                                        'data/poezio_gpg_export.1',
                                        'data/poezio_logs.1']),
                   ('share/poezio/', ['README.rst', 'COPYING', 'CHANGELOG'])]
                  + find_doc('share/doc/poezio/source', 'source')
                  + find_doc('share/doc/poezio/html', 'build/html')),
      install_requires=['slixmpp>=1.3.0', 'aiodns', 'pyasn1_modules', 'pyasn1'],
      extras_require={'OTR plugin': 'python-potr>=1.0',
                      'Screen autoaway plugin': 'pyinotify==0.9.4',
                      'Avoiding cython': 'cffi'})

# Remove the link afterwards
if (exists(join(current_dir, 'poezio', 'default_config.cfg')) and
        exists(join(current_dir, 'data', 'default_config.cfg'))):

    unlink(join(current_dir, 'poezio', 'default_config.cfg'))

