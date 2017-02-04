from __future__ import absolute_import

import sys
import atexit
import logging
import argparse
import socket
import structlog
from datetime import timedelta
from functools import wraps
from threading import Thread

from .log import LevelLoggerFactory, BoundLevelLogger, StdlibStructlogHandler, StderrConsoleRenderer, Stream
from .stats import Stats

class BaseScript(object):
    DESC = 'Base script abstraction'
    LOG_LEVEL = 'INFO'

    # stdlib to structlog handlers should be configured only once.
    _GLOBAL_LOG_CONFIGURED = False

    # acquires and releases locks for every metric captured
    THREAD_SAFE_STATS = True

    # periodic interval to dump stats
    DUMP_STATS_INTERVAL = timedelta(seconds=1)

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
        self.log = self.init_logger()

        args = { n: getattr(self.args, n) for n in vars(self.args) }
        args['func'] = self.args.func.func_name
        self.log.debug("basescript init", **args)

        self.stats = self.init_stats()

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

    def define_log_processors(self):
        """
        log processors that structlog executes before final rendering
        """
        # these processors should accept logger, method_name and event_dict
        # and return a new dictionary which will be passed as event_dict to the next one.

        processors = []

        processors.extend([
            structlog.processors.TimeStamper(fmt="iso"),
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

        if self.args.log_file is not None:
            return structlog.processors.JSONRenderer()

        if sys.stderr.isatty() and not self.args.quiet:
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

    def _configure_logger(self):
        # NOTE not thread safe. Multiple BaseScripts cannot be instantiated concurrently.
        level = getattr(logging, self.args.log_level.upper())

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

        log_renderer = self.define_log_renderer()
        stderr_required = (not self.args.quiet)
        pretty_to_stderr = (
            stderr_required
            and (
                self.args.log_format == "pretty"
                or (self.args.log_format is None and sys.stderr.isatty())
            )
        )

        should_inject_pretty_renderer = (
            pretty_to_stderr
            and not isinstance(log_renderer, structlog.dev.ConsoleRenderer)
        )
        if should_inject_pretty_renderer:
            stderr_required = False
            processors.append(StderrConsoleRenderer())

        processors.append(log_renderer)
        processors.extend(
            [ wrap_hook(h) for h in self.define_log_post_format_hooks() ]
        )

        streams = []
        # we need to use a stream if we are writing to both file and stderr, and both are json
        if stderr_required:
            streams.append(sys.stderr)

        if self.args.log_file is not None:
            # TODO handle creating a directory for this log file ?
            # TODO set mode and encoding appropriately
            streams.append(open(self.args.log_file, 'a'))

        if len(streams) == 0:
            # no logging configured at all
            # TODO what do we do in such cases ?
            return

        stream = streams[0] if len(streams) == 1 else Stream(*streams)
        atexit.register(stream.close)

        # a global level struct log config unless otherwise specified.
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=LevelLoggerFactory(stream, level=level),
            wrapper_class=BoundLevelLogger,
            cache_logger_on_first_use=True,
        )

        # TODO take care of removing other handlers
        stdlib_root_log = logging.getLogger()
        stdlib_root_log.addHandler(StdlibStructlogHandler())
        stdlib_root_log.setLevel(level)

        self._GLOBAL_LOG_CONFIGURED = True

    def init_logger(self):
        self._configure_logger()

        # TODO bind relevant things to the basescript here ? name / hostname etc ?
        log = structlog.get_logger()
        level = getattr(logging, self.args.log_level.upper())
        log.setLevel(level)

        # TODO functionality to change even the level of global stdlib logger.
        return log

    def define_metric_tags(self):
        """
        the tags (dictionary {str: str}) returned by this function
        must be present in every metric that basescript emits.
        """
        return { "host": self.hostname, "name": self.name }

    def init_stats(self):
        basescript_tags = self.define_metric_tags()
        stats = Stats(self.log, thread_safe=self.THREAD_SAFE_STATS, **basescript_tags)

        self.dump_stats_thread = Thread(
            target=stats.dump_stats_periodically,
            kwargs={ 'interval': self.DUMP_STATS_INTERVAL },
        )
        self.dump_stats_thread.daemon = True
        self.dump_stats_thread.start()
        return stats

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

