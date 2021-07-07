from __future__ import absolute_import

import sys
import argparse
import socket

from .log import init_logger, pretty_print
from deeputil import Dummy


class BaseScript(object):
    DESC = "Base script abstraction"
    METRIC_GROUPING_INTERVAL = 1

    def __init__(self, args=None):
        # argparse parser obj
        self.parser = argparse.ArgumentParser(description=self.DESC)
        self.define_baseargs(self.parser)

        self.subcommands = self.parser.add_subparsers(title="commands")
        self.subcommands.dest = "commands"
        self.subcommands.required = True
        self.define_subcommands(self.subcommands)
        self.subcommand_run = self.subcommands.add_parser("run")
        self.subcommand_run.set_defaults(func=self.run)

        self.define_args(self.subcommand_run)

        self.args = self.parser.parse_args(args=args)

        self.hostname = socket.gethostname()

        if self.args.metric_grouping_interval:
            self.METRIC_GROUPING_INTERVAL = self.args.metric_grouping_interval

        if self.args.debug:
            if self.args.log_level is None:
                self.args.log_level = "debug"
            if self.args.metric_grouping_interval is None:
                self.args.metric_grouping_interval = 0

        if not self.args.log_level:
            self.args.log_level = "info"
            self.args.metric_grouping_interval = self.METRIC_GROUPING_INTERVAL

        if self.args.metric_grouping_interval is None:
            self.args.metric_grouping_interval = self.METRIC_GROUPING_INTERVAL

        log = init_logger(
            fmt=self.args.log_format,
            quiet=self.args.quiet,
            level=self.args.log_level,
            fpath=self.args.log_file,
            processors=self.define_log_processors(),
            metric_grouping_interval=self.args.metric_grouping_interval,
            minimal=self.args.minimal,
        )

        self._flush_metrics_q = log._force_flush_q
        self.log = log.bind(name=self.args.name)

        self.stats = Dummy()

        args = {n: getattr(self.args, n) for n in vars(self.args)}
        args["func"] = self.args.func.__name__
        self.log.debug("basescript init", **args)

    def start(self):
        """
        Starts execution of the script
        """
        # invoke the appropriate sub-command as requested from command-line
        try:
            self.args.func()
        except SystemExit as e:
            if e.code != 0:
                raise
        except KeyboardInterrupt:
            self.log.warning("exited via keyboard interrupt")
        except Exception as e:
            self.log.error("exited start function")
            raise
        finally:
            self._flush_metrics_q.put(None, block=True)
            self._flush_metrics_q.put(None, block=True, timeout=1)

        self.log.debug("exited_successfully")

    @property
    def name(self):
        return ".".join([x for x in (sys.argv[0].split(".")[0], self.args.name) if x])

    def define_log_processors(self):
        """
        These processors are called before a log is rendered but after
        all necessary filtering by the default log processors has taken
        place. They must have the function signature required by `structlog`
        """
        return []

    def define_subcommands(self, subcommands):
        """
        Define subcommands (as defined at https://docs.python.org/2/library/argparse.html#sub-commands)

        eg: adding a sub-command called "blah" that invokes a function fn_blah

        blah_command = subcommands.add_parser('blah')
        blah_command.set_defaults(func=fn_blah)
        """
        pretty_cmd = subcommands.add_parser("pretty")
        pretty_cmd.add_argument(
            "-c",
            "--no-colors",
            action="store_true",
            default=False,
            help="Do not emit colored output",
        )

        pretty_cmd.set_defaults(
            func=lambda: pretty_print(colors=not self.args.no_colors)
        )

    def define_baseargs(self, parser):
        """
        Define basic command-line arguments required by the script.
        @parser is a parser object created using the `argparse` module.
        returns: None
        """
        parser.add_argument(
            "--name", default=sys.argv[0], help="Name to identify this instance"
        )
        parser.add_argument(
            "--log-level",
            default=None,
            help="Logging level as picked from the logging module",
        )
        parser.add_argument(
            "--log-format",
            default=None,
            # TODO add more formats
            choices=("json", "pretty"),
            help=(
                "Force the format of the logs. By default, if the "
                "command is from a terminal, print colorful logs. "
                "Otherwise print json."
            ),
        )
        parser.add_argument(
            "--log-file",
            default=None,
            help="Writes logs to log file if specified, default: %(default)s",
        )
        parser.add_argument(
            "--quiet",
            default=False,
            action="store_true",
            help="if true, does not print logs to stderr, default: %(default)s",
        )
        parser.add_argument(
            "--metric-grouping-interval",
            default=None,
            type=int,
            help="To group metrics based on time interval ex:10 i.e;(10 sec)",
        )
        parser.add_argument(
            "--debug",
            default=False,
            action="store_true",
            help="To run the code in debug mode",
        )
        parser.add_argument(
            "--minimal",
            default=False,
            action="store_true",
            help="Hide log keys such as id, host",
        )

    def define_args(self, parser):
        """
        Define script specific command-line arguments.
        @parser is a parser object created using the `argparse` module.

        You can add arguments using the `add_argument` of the parser object.
        For more information, you can refer to the documentation of argparse
        module.

        returns: None
        """
        pass

    def run(self):
        """
        Override this method to define logic for `run` sub-command
        """
        pass


def main():
    BaseScript().start()
