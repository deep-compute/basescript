import sys
import logging
import logging.handlers
import argparse
import socket

MAX_LOG_FILE_SIZE = 100 * 1024 * 1024 # 100MB

class BaseScript(object):
    LOG_FORMATTER = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    DESC = 'Base script abstraction'
    LOG_LEVEL = 'INFO'

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

        self.log = self.init_logger(self.args.log, self.args.log_level,\
            quiet=self.args.quiet)

        self.log.debug('init: args=%s' % repr(self.args))

        self.init()
        self.args.func()

    @property
    def name(self):
        return '.'.join([x for x in (sys.argv[0].split('.')[0], self.args.name) if x])

    def init_logger(self, fname, log_level, quiet=False):
        if not fname:
            fname = '%s.log' % self.name

        log = logging.getLogger('')

        stderr_hdlr = logging.StreamHandler(sys.stderr)
        rofile_hdlr = logging.handlers.RotatingFileHandler(fname,
            maxBytes=MAX_LOG_FILE_SIZE, backupCount=10)
        hdlrs = (stderr_hdlr, rofile_hdlr)

        for hdlr in hdlrs:
            hdlr.setFormatter(self.LOG_FORMATTER)
            log.addHandler(hdlr)

        log.addHandler(rofile_hdlr)
        if not quiet: log.addHandler(stderr_hdlr)

        log.setLevel(getattr(logging, log_level.upper()))

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
        parser.add_argument('--log', default=None,
            help='Name of log file')
        parser.add_argument('--log-level', default=self.LOG_LEVEL,
            help='Logging level as picked from the logging module')
        parser.add_argument('--quiet', action='store_true')

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

    def init(self):
        '''
        Override this method to put any initialization logic for your script.
        It is recommended that you use this instead of subclassing __init__.
        '''
        pass

    def run(self):
        '''
        Override this method to define logic for the scripts functionality.
        It is recommended that you use this instead of subclassing __init__.
        '''
        pass
