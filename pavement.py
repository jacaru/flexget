import os
import re
from paver.easy import *
import paver.virtual
import paver.setuputils
from paver import svn
from paver.setuputils import setup, find_package_data, find_packages

sphinxcontrib = False
try:
    from sphinxcontrib import paverutils
    sphinxcontrib = True
except ImportError:
    pass

sys.path.insert(0, '')

options = environment.options
install_requires = ['FeedParser>=5.1.2', 'SQLAlchemy >=0.7, <0.7.99', 'PyYAML', 'BeautifulSoup>=3.2, <3.3',
                    'beautifulsoup4>=4.1, <4.2', 'html5lib>=0.11', 'PyRSS2Gen', 'pynzb', 'progressbar', 'jinja2',
                    'flask', 'cherrypy', 'requests>=0.14, <0.15', 'python-dateutil!=2.0']
if sys.version_info < (2, 7):
    # argparse is part of the standard library in python 2.7+
    install_requires.append('argparse')

entry_points = {
    'console_scripts': ['flexget = flexget:main'],
    'gui_scripts': ['flexget-webui = flexget.ui:main']}

# Provide an alternate exe on windows which does not cause a pop-up when scheduled
if sys.platform.startswith('win'):
    entry_points['gui_scripts'].append('flexget-headless = flexget:main')

setup(
    name='FlexGet',
    version='1.0', # our tasks append the r1234 (current svn revision) to the version number
    description='FlexGet is a program aimed to automate downloading or processing content (torrents, podcasts, etc.) from different sources like RSS-feeds, html-pages, various sites and more.',
    author='Marko Koivusalo',
    author_email='marko.koivusalo@gmail.com',
    license='MIT',
    url='http://flexget.com',
    install_requires=install_requires,
    packages=find_packages(exclude=['tests']),
    package_data=find_package_data('flexget', package='flexget',
                                   exclude=['FlexGet.egg-info', '*.pyc'],
                                   only_in_packages=False), # NOTE: the exclude does not seem to work
    zip_safe=False,
    test_suite='nose.collector',
    extras_require={
        'memusage':     ['guppy'],
        'NZB':          ['pynzb'],
        'TaskTray':     ['pywin32'],
    },
    entry_points=entry_points
)

options(
    minilib=Bunch(
        extra_files=['virtual', 'svn']
    ),
    virtualenv=Bunch(
        paver_command_line='develop',
        unzip_setuptools=True,
        distribute=True
    ),
    # sphinxcontrib.paverutils
    sphinx=Bunch(
        docroot='docs',
        builddir='build',
        builder='html',
        confdir='docs'
    ),
)

def freplace(name, what_str, with_str):
    """Replaces a :what_str: with :with_str: in file :name:"""
    import fileinput
    for line in fileinput.FileInput(name, inplace=1):
        if what_str in line:
            line = line.replace(what_str, with_str)
        print line,

def set_init_version(ver):
    """Replaces the version with :ver: in __init__.py"""
    import fileinput
    for line in fileinput.FileInput('flexget/__init__.py', inplace=1):
        if line.startswith('__version__ = '):
            line = "__version__ = '%s'\n" % ver
        print line,


@task
@cmdopts([
    ('online', None, 'Run online tests')
])
def test(options):
    """Run FlexGet unit tests"""
    options.setdefault('test', Bunch())
    import nose
    from nose.plugins.manager import DefaultPluginManager

    cfg = nose.config.Config(plugins=DefaultPluginManager(), verbosity=2)

    args = []
    # Adding the -v flag makes the tests fail in python 2.7
    #args.append('-v')
    args.append('--processes=4')
    args.append('-x')
    if not options.test.get('online'):
        args.append('--attr=!online')
    args.append('--where=tests')

    # Store current path since --where changes it, restore when leaving
    cwd = os.getcwd()
    try:
        return nose.run(argv=args, config=cfg)
    finally:
        os.chdir(cwd)


@task
def clean():
    """Cleans up the virtualenv"""
    import os, glob

    for p in ('bin', 'Scripts', 'build', 'dist', 'include', 'lib', 'man',
              'share', 'FlexGet.egg-info', 'paver-minilib.zip', 'setup.py'):
        pth = path(p)
        if pth.isdir():
            pth.rmtree()
        elif pth.isfile():
            pth.remove()

    for pkg in set(options.setup.packages) | set(('tests',)):
        for filename in glob.glob(pkg.replace('.', os.sep) + "/*.py[oc~]"):
            path(filename).remove()


@task
@cmdopts([
    ('dist-dir=', 'd', 'directory to put final built distributions in')
], share_with=['make_egg'])
def sdist(options):
    """Build tar.gz distribution package"""

    revision = svn.info().get('last_changed_rev')

    print 'Revision: %s' % revision

    # clean previous build
    print 'Cleaning build...'
    for p in ['build']:
        pth = path(p)
        if pth.isdir():
            pth.rmtree()
        elif pth.isfile():
            pth.remove()
        else:
            print 'Unable to remove %s' % pth

    # remove pre-compiled pycs from tests, I don't know why paver even tries to include them ...
    # seems to happen only with sdist though
    for pyc in path('tests/').files('*.pyc'):
        pyc.remove()

    ver = '%sr%s' % (options['version'], revision)

    print 'Building %s' % ver

    # replace version number
    set_init_version(ver)

    # hack version number into setup( ... options='1.0' ...)
    from paver import tasks
    setup_section = tasks.environment.options.setdefault("setup", Bunch())
    setup_section.update(version=ver)

    for t in ['minilib', 'generate_setup', 'setuptools.command.sdist']:
        call_task(t)

    # restore version ...
    set_init_version('{subversion}')


@task
@cmdopts([
    ('dist-dir=', 'd', 'directory to put final built distributions in')
], share_with=['sdist'])
def make_egg(options):
    # naming this task to bdist_egg will make egg installation fail

    revision = svn.info().get('last_changed_rev')
    ver = '%sr%s' % (options['version'], revision)

    # hack version number into setup( ... options='1.0-svn' ...)
    from paver import tasks
    setup_section = tasks.environment.options.setdefault("setup", Bunch())
    setup_section.update(version=ver)

    # replace version number
    set_init_version(ver)

    print 'Making egg release'
    import shutil
    shutil.copytree('FlexGet.egg-info', 'FlexGet.egg-info-backup')

    options.setdefault('bdist_egg', Bunch())['dist_dir'] = options.make_egg.get('dist_dir')

    for t in ["minilib", "generate_setup", "setuptools.command.bdist_egg"]:
        call_task(t)

    # restore version ...
    set_init_version('{subversion}')

    # restore egg info from backup
    print 'Removing FlexGet.egg-info ...'
    shutil.rmtree('FlexGet.egg-info')
    print 'Restoring FlexGet.egg-info'
    shutil.move('FlexGet.egg-info-backup', 'FlexGet.egg-info')


@task
def coverage():
    """Make coverage.flexget.com"""
    # --with-coverage --cover-package=flexget --cover-html --cover-html-dir /var/www/flexget_coverage/
    import nose
    from nose.plugins.manager import DefaultPluginManager

    cfg = nose.config.Config(plugins=DefaultPluginManager(), verbosity=2)
    argv = ['bin/paver']
    argv.extend(['--attr=!online'])
    argv.append('--with-coverage')
    argv.append('--cover-html')
    argv.extend(['--cover-package', 'flexget'])
    argv.extend(['--cover-html-dir', '/var/www/flexget_coverage/'])
    nose.run(argv=argv, config=cfg)
    print 'Coverage generated'


@task
@cmdopts([
    ('docs-dir=', 'd', 'directory to put the documetation in')
])
def docs():
    if not sphinxcontrib:
        print 'ERROR: requires sphinxcontrib-paverutils'
        sys.exit(1)
    from paver import tasks
    setup_section = tasks.environment.options.setdefault("sphinx", Bunch())
    setup_section.update(outdir=options.docs.get('docs_dir', 'build/sphinx'))
    call_task('html')


@task
@might_call('test', 'sdist', 'make_egg')
@cmdopts([
    ('no-tests', None, 'skips unit tests'),
    ('type=', None, 'type of release (src | egg)')
])
def release(options):
    """Make a FlexGet release. Same as bdist_egg but adds version information."""

    if options.release.get('type') not in ['src', 'egg']:
        print 'Invalid --type, must be src or egg'
        return

    print 'Cleaning build...'
    for p in ['build']:
        pth = path(p)
        if pth.isdir():
            pth.rmtree()
        elif pth.isfile():
            pth.remove()
        else:
            print 'Unable to remove %s' % pth

    # run unit tests
    if not options.release.get('no_tests'):
        if not test():
            print 'Unit tests did not pass'
            import sys
            sys.exit(1)

    if options.release.get('type') == 'egg':
        print 'Making egg release'
        make_egg()
    else:
        print 'Making src release'
        sdist()


@task
def install_tools():
    """Install development / jenkins tools and dependencies"""

    try:
        import pip
    except:
        print 'FATAL: Unable to import pip, please install it and run this again!'
        return

    try:
        import sphinxcontrib
        print 'sphinxcontrib INSTALLED'
    except:
        pip.main(['install', 'sphinxcontrib-paverutils'])

    pip.main(['install', '-r', 'jenkins-requirements.txt'])


@task
def clean_compiled():
    for root, dirs, files in os.walk('flexget'):
        for name in files:
            fqn = os.path.join(root, name)
            if fqn[-3:] == 'pyc' or fqn[-3:] == 'pyo' or fqn[-5:] == 'cover':
                print 'Deleting %s' % fqn
                os.remove(fqn)


@task
@consume_args
def pep8(args):
    try:
        import pep8
    except:
        print 'Run bin/paver install_tools'
        return

    # Ignoring certain errors
    ignore = [
        'E711', 'E712', # These are comparisons to singletons i.e. == False, and == None. We need these for sqlalchemy.
        'W291', 'W293', 'E261'
    ]
    styleguide = pep8.StyleGuide(show_source=True, ignore=ignore, repeat=1, max_line_length=120,
        parse_argv=args)
    styleguide.input_dir('flexget')


@task
def bootstrap():
    """
    Current paver bootstrap task ignores the distribute option, do some hackery to fix that.
    This should not be needed after next release of paver (>1.1.1)
    """
    import textwrap
    vopts = options.virtualenv
    more_text = ""
    if vopts.get('distribute') is not None:
        more_text = textwrap.dedent("""
        def more_adjust_options(orig_adjust_options):
            def adjust_options(options, args):
                orig_adjust_options(options, args)
                options.use_distribute = %s
            return adjust_options
        adjust_options = more_adjust_options(adjust_options)
        """ % bool(vopts.get('distribute')))

    paver.virtual._create_bootstrap(vopts.get("script_name", "bootstrap.py"),
        vopts.get("packages_to_install", []),
        vopts.get("paver_command_line", None),
        dest_dir=vopts.get("dest_dir", '.'),
        no_site_packages=vopts.get("no_site_packages", False),
        unzip_setuptools=vopts.get("unzip_setuptools", False),
        more_text=more_text)
