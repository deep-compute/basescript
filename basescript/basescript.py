from __future__ import absolute_import

import sys
import logging
import argparse
import socket
import structlog
from functools import wraps

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

    def define_log_processors(self):
        """
        log processors that structlog executes before final rendering
        """
        # these processors should accept logger, method_name and event_dict
        # and return a new dictionary which will be passed as event_dict to the next one.

        # NOTE if we are using a tty, then we must add our own timestamp.
        processors = []

        if sys.stderr.isatty():
            processors.append(structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M%S"))

        processors.extend([
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ])

        return processors

    def define_log_renderer(self):
        """
        the final log processor that structlog requires to render.
        """
        # it must accept a logger, method_name and event_dict (just like processors)
        # but must return the rendered string, not a dictionary.
        # TODO tty logic
        if self.args.log_format == "json":
            return structlog.processors.JSONRenderer()

        if self.args.log_format == "pretty":
            return structlog.dev.ConsoleRenderer()

        # log format is None, we need to guess from the tty
        if sys.stderr.isatty():
            return structlog.dev.ConsoleRenderer()

        return structlog.processors.JSONRenderer()

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

    def _configure_logger(self, level):
        # NOTE not thread safe. Multiple BaseScripts cannot be instantiated concurrently.
        if self._GLOBAL_LOG_CONFIGURED:
            return

        # TODO different processors for different basescripts ?
        # TODO dynamically inject processors ?

        # since the hooks need to run through structlog, need to wrap them like processors
        def wrap_hook(fn):
            @wraps(fn)
            def processor(logger, method_name, event_dict):
                fn(event_dict)
                return event_dict

            return processor

        processors = self.define_log_processors()
        processors.extend(
            [ wrap_hook(h) for h in self.define_log_pre_format_hooks() ]
        )
        processors.append(self.define_log_renderer())
        processors.extend(
            [ wrap_hook(h) for h in self.define_log_post_format_hooks() ]
        )

        # a global level struct log config unless otherwise specified.
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=LevelLoggerFactory(stream=sys.stderr, level=level),
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
        parser.add_argument('--log-format', default=None,
            # TODO add more formats
            choices=("json", "pretty",),
            help=("Force the format of the logs. By default, if the "
                  "command is from a terminal, print colorful logs. "
                  "Otherwise print json."),
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

