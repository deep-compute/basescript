from __future__ import absolute_import

import sys
import argparse
import socket

from .log import init_logger
from .utils import Dummy # FIXME: delete this code and use deeputil.Dummy

class BaseScript(object):
    DESC = 'Base script abstraction'
    LOG_LEVEL = 'INFO'
    METRIC_GROUPING_INTERVAL = 1

    def __init__(self, args=None):
        # argparse parser obj
        self.parser = argparse.ArgumentParser(description=self.DESC)
        self.define_baseargs(self.parser)

        self.subcommands = self.parser.add_subparsers(title='commands')
        self.subcommands.dest = 'commands'
        self.define_subcommands(self.subcommands)
        self.subcommand_run = self.subcommands.add_parser('run')
        self.subcommand_run.set_defaults(func=self.run)

        self.define_args(self.subcommand_run)

        self.args = self.parser.parse_args(args=args)

        self.hostname = socket.gethostname()

        self.log = init_logger(
            fmt=self.args.log_format,
            quiet=self.args.quiet,
            level=self.args.log_level,
            fpath=self.args.log_file,
            pre_hooks=self.define_log_pre_format_hooks(),
            post_hooks=self.define_log_post_format_hooks(),
            metric_grouping_interval=self.METRIC_GROUPING_INTERVAL
        ).bind(name=self.args.name)

        self.stats = Dummy()

        args = { n: getattr(self.args, n) for n in vars(self.args) }
        args['func'] = self.args.func.__name__
        self.log.debug("basescript init", **args)

    def start(self):
        '''
        Starts execution of the script
        '''
        # invoke the appropriate sub-command as requested from command-line
        try:
            self.args.func()
        except SystemExit as e:
            if e.code != 0:
                raise
        except KeyboardInterrupt:
            self.log.warning("exited via keyboard interrupt")
            sys.exit(1)
        except:
            self.log.exception("exited start function")
            # set exit code so we know it did not end successfully
            # TODO different exit codes based on signals ?
            sys.exit(1)

        self.log.info("exited successfully")

    @property
    def name(self):
        return '.'.join([x for x in (sys.argv[0].split('.')[0], self.args.name) if x])

    def define_log_pre_format_hooks(self):
        """
        these hooks are called before the log has been rendered, but after
        all necessary filtering by log_processors has taken place.
        they must accept a single argument which is a dictionary.
        """
        return []

    def define_log_post_format_hooks(self):
        """
        these hooks are called after the log has been rendered using
        the log renderer defined in `define_log_renderer`.
        they must accept a single argument which is the output of the
        renderer
        """
        # TODO remove this once structlog supports hooks or handlers
        # these hooks accept a 'msg' and do not return anything
        return []

    def define_subcommands(self, subcommands):
        '''
        Define subcommands (as defined at https://docs.python.org/2/library/argparse.html#sub-commands)

        eg: adding a sub-command called "blah" that invokes a function fn_blah

        blah_command = subcommands.add_parser('blah')
        blah_command.set_defaults(func=fn_blah)
        '''
        pass

    def define_baseargs(self, parser):
        '''
        Define basic command-line arguments required by the script.
        @parser is a parser object created using the `argparse` module.
        returns: None
        '''
        parser.add_argument('--name', default=sys.argv[0],
            help='Name to identify this instance')
        parser.add_argument('--log-level', default=self.LOG_LEVEL,
            help='Logging level as picked from the logging module')
        parser.add_argument('--log-format', default=None,
            # TODO add more formats
            choices=("json", "pretty",),
            help=("Force the format of the logs. By default, if the "
                  "command is from a terminal, print colorful logs. "
                  "Otherwise print json."),
        )
        parser.add_argument('--log-file', default=None,
            help='Writes logs to log file if specified, default: %(default)s',
        )
        parser.add_argument('--quiet', default=False, action="store_true",
            help='if true, does not print logs to stderr, default: %(default)s',
        )

    def define_args(self, parser):
        '''
        Define script specific command-line arguments.
        @parser is a parser object created using the `argparse` module.

        You can add arguments using the `add_argument` of the parser object.
        For more information, you can refer to the documentation of argparse
        module.

        returns: None
        '''
        pass

    def run(self):
        '''
        Override this method to define logic for `run` sub-command
        '''
        pass

