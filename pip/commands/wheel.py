# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import sys
from pip.basecommand import Command
from pip.index import PackageFinder
from pip.log import logger
from pip.exceptions import CommandError
from pip.req import InstallRequirement, RequirementSet, parse_requirements
from pip.util import normalize_path
from pip.wheel import WheelBuilder
from pip import cmdoptions

DEFAULT_WHEEL_DIR = os.path.join(normalize_path(os.curdir), 'wheelhouse')

class WheelCommand(Command):
    """
    Build wheel archives from your requirements using "setup.py bdist_wheel".

    Requirements: Distribute>=0.6.28 (not Setuptools), wheel, and markerlib.

    Wheel is a built-package format, and offers the advantage of not recompiling your software during every install.
    For more details, see the wheel docs: http://wheel.readthedocs.org/en/latest.
    """

    name = 'wheel'
    usage = """
      %prog [options] <requirement specifier> ...
      %prog [options] -r <requirements file> ..."""

    summary = 'Build wheels from your requirements.'

    def __init__(self, *args, **kw):
        super(WheelCommand, self).__init__(*args, **kw)

        cmd_opts = self.cmd_opts

        cmd_opts.add_option(
            '-w', '--wheel-dir',
            dest='wheel_dir',
            metavar='dir',
            default=DEFAULT_WHEEL_DIR,
            help="Build wheels into <dir>, where the default is '<cwd>/wheelhouse'.")
        cmd_opts.add_option(cmdoptions.use_wheel)
        cmd_opts.add_option(
            '--unpack-only',
            dest='unpack_only',
            action='store_true',
            default=False,
            help="Only unpack packages into the build dir. Don't build wheels.")
        cmd_opts.add_option(
            '--build-option',
            dest='build_options',
            metavar='options',
            action='append',
            help="Extra arguments to be supplied to 'setup.py bdist_wheel'.")
        cmd_opts.add_option(cmdoptions.requirements)
        cmd_opts.add_option(cmdoptions.download_cache)
        cmd_opts.add_option(cmdoptions.no_deps)
        cmd_opts.add_option(cmdoptions.build_dir)

        cmd_opts.add_option(
            '--global-option',
            dest='global_options',
            action='append',
            metavar='options',
            help="Extra global options to be supplied to the setup.py "
            "call before the 'bdist_wheel' command.")

        index_opts = cmdoptions.make_option_group(cmdoptions.index_group, self.parser)

        self.parser.insert_option_group(0, index_opts)
        self.parser.insert_option_group(0, cmd_opts)

    def run(self, options, args):

        if sys.version_info < (2, 6):
            raise CommandError("'pip wheel' requires Python 2.6 or greater.")

        try:
            import wheel.bdist_wheel
        except ImportError:
            raise CommandError("'pip wheel' requires bdist_wheel from the 'wheel' distribution.")

        index_urls = [options.index_url] + options.extra_index_urls
        if options.no_index:
            logger.notify('Ignoring indexes: %s' % ','.join(index_urls))
            index_urls = []

        finder = PackageFinder(find_links=options.find_links,
                               index_urls=index_urls,
                               use_mirrors=options.use_mirrors,
                               mirrors=options.mirrors,
                               use_wheel=options.use_wheel)

        options.build_dir = os.path.abspath(options.build_dir)
        requirement_set = RequirementSet(
            build_dir=options.build_dir,
            src_dir=None,
            download_dir=None,
            download_cache=options.download_cache,
            ignore_dependencies=options.ignore_dependencies,
            ignore_installed=True)

        #parse args and/or requirements files
        for name in args:
            if name.endswith(".whl"):
                logger.notify("ignoring %s" % name)
                continue
            requirement_set.add_requirement(
                InstallRequirement.from_line(name, None))

        for filename in options.requirements:
            for req in parse_requirements(filename, finder=finder, options=options):
                if req.editable or (req.name is None and req.url.endswith(".whl")):
                    logger.notify("ignoring %s" % req.url)
                    continue
                requirement_set.add_requirement(req)

        #fail if no requirements
        if not requirement_set.has_requirements:
            opts = {'name': self.name}
            msg = ('You must give at least one requirement '
                   'to %(name)s (see "pip help %(name)s")' % opts)
            logger.error(msg)
            return

        #if unpack-only, just prepare and return
        #'pip wheel' probably shouldn't be offering this? 'pip unpack'?
        if options.unpack_only:
            requirement_set.prepare_files(finder)
            return

        #build wheels
        wb = WheelBuilder(
            requirement_set,
            finder,
            options.wheel_dir,
            build_options = options.build_options or [],
            global_options = options.global_options or []
            )
        wb.build()

        requirement_set.cleanup_files()

