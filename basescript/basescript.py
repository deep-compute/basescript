from __future__ import absolute_import

import sys
import logging
import argparse
import socket
import structlog

from .log import LevelLoggerFactory, BoundLevelLogger, StdlibStructlogHandler

class BaseScript(object):
    DESC = 'Base script abstraction'
    LOG_LEVEL = 'INFO'

    # stdlib to structlog handlers should be configured only once.
    _GLOBAL_LOG_CONFIGURED = False

    def __init__(self):
        # argparse parser obj
        self.parser = argparse.ArgumentParser(description=self.DESC)
        self.define_baseargs(self.parser)

        self.subcommands = self.parser.add_subparsers(title='commands')
        self.define_subcommands(self.subcommands)
        self.subcommand_run = self.subcommands.add_parser('run')
        self.subcommand_run.set_defaults(func=self.run)

        self.define_args(self.subcommand_run)

        self.args = self.parser.parse_args()

        self.hostname = socket.gethostname()
        self.log = self.init_logger(self.args.log_level)

        args = { n: getattr(self.args, n) for n in vars(self.args) }
        self.log.debug("basescript init", **args)

    def start(self):
        '''
        Starts execution of the script
        '''
        # invoke the appropriate sub-command as requested from command-line
        self.args.func()

    @property
    def name(self):
        return '.'.join([x for x in (sys.argv[0].split('.')[0], self.args.name) if x])

    def _configure_logger(self, level):
        # NOTE not thread safe. Multiple BaseScripts cannot be instantiated concurrently.
        if self._GLOBAL_LOG_CONFIGURED:
            return

        # a global level struct log config unless otherwise specified.
        structlog.configure(
            processors=[
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=LevelLoggerFactory(level=level),
            wrapper_class=BoundLevelLogger,
            cache_logger_on_first_use=True,
        )

        # TODO take care of removing other handlers
        stdlib_root_log = logging.getLogger()
        stdlib_root_log.addHandler(StdlibStructlogHandler())
        stdlib_root_log.setLevel(level)

        self._GLOBAL_LOG_CONFIGURED = True

    def init_logger(self, levelname):
        level = getattr(logging, levelname.upper())
        self._configure_logger(level)

        # TODO bind relevant things to the basescript here ? name / hostname etc ?
        log = structlog.get_logger()
        log.setLevel(level)

        # TODO functionality to change even the level of global stdlib logger.
        return log

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
        parser.add_argument('--name', default=None,
            help='Name to identify this instance')
        parser.add_argument('--log-level', default=self.LOG_LEVEL,
            help='Logging level as picked from the logging module')

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

