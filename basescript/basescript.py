from gevent import monkey; monkey.patch_all()

import sys
import gc
import time
import threading
import resource
import logging
import logging.handlers
import argparse
import socket

import gevent
import statsd

MAX_LOG_FILE_SIZE = 100 * 1024 * 1024 # 100MB

class StatsCollector(object):
    STATS_FLUSH_INTERVAL = 1

    def __init__(self, prefix, stats_loc):
        self.cache = {}
        self.gauge_cache = {}

        self.stats = None
        if not stats_loc: return

        port = None
        if ':' in stats_loc:
            ip, port = stats_loc.split(':')
            port = int(port)
        else:
            ip = stats_loc

        S = statsd.StatsClient
        self.stats = S(ip, port, prefix) if port is not None else S(ip, prefix=prefix)

        def fn():
            while 1:
                time.sleep(self.STATS_FLUSH_INTERVAL)
                self._collect_ramusage()
                self.send()

        self.stats_thread = gevent.spawn(fn)

    def incr(self, key, n=1):
        if self.stats is None: return
        self.cache[key] = self.cache.get(key, 0) + n

    def decr(self, key, n=1):
        if self.stats is None: return
        self.cache[key] = self.cache.get(key, 0) - n

    def timing(self, key, ms):
        if self.stats is None: return
        return self.stats.timing(key, ms)

    def gauge(self, key, n, delta=False):
        if delta:
            v, _ = self.gauge_cache.get(key, (0, True))
            n += v
        self.gauge_cache[key] = (n, delta)

    def _collect_ramusage(self):
        self.gauge('resource.maxrss',
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

    def send(self):
        if self.stats is None: return
        p = self.stats.pipeline()

        for k, v in self.cache.iteritems():
            p.incr(k, v)

        for k, (v, d) in self.gauge_cache.iteritems():
            p.gauge(k, v, delta=d)

        p.send()
        self.cache = {}
        self.gauge_cache = {}

class BaseScript(object):
    LOG_FORMATTER = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    DESC = 'Base script abstraction'

    def __init__(self):
        # argparse parser obj
        self.parser = argparse.ArgumentParser(description=self.DESC)
        self.define_baseargs(self.parser)
        self.define_args(self.parser)
        self.args = self.parser.parse_args()

        self.hostname = socket.gethostname()

        self.log = self.init_logger(self.args.log, self.args.log_level,\
            quiet=self.args.quiet)

        self.stats = self.create_stats()
        self.log.debug('init: args=%s' % repr(self.args))

        self.init()

    @property
    def name(self):
        return '.'.join([x for x in (sys.argv[0].split('.')[0], self.args.name) if x])

    def create_stats(self):
        stats_prefix = '.'.join([x for x in (self.hostname, self.name) if x])
        return StatsCollector(stats_prefix, self.args.statsd_server)

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

    def dump_stacks(self):
        '''
        Dumps the stack of all threads and greenlets. This function
        is meant for debugging. Useful when a deadlock happens.

        borrowed from: http://blog.ziade.org/2012/05/25/zmq-and-gevent-debugging-nightmares/
        '''

        dump = []

        # threads
        threads = dict([(th.ident, th.name)
                            for th in threading.enumerate()])

        for thread, frame in sys._current_frames().items():
            if thread not in threads: continue
            dump.append('Thread 0x%x (%s)\n' % (thread, threads[thread]))
            dump.append(''.join(traceback.format_stack(frame)))
            dump.append('\n')

        # greenlets
        try:
            from greenlet import greenlet
        except ImportError:
            return ''.join(dump)

        # if greenlet is present, let's dump each greenlet stack
        for ob in gc.get_objects():
            if not isinstance(ob, greenlet):
                continue
            if not ob:
                continue   # not running anymore or not started
            dump.append('Greenlet\n')
            dump.append(''.join(traceback.format_stack(ob.gr_frame)))
            dump.append('\n')

        return ''.join(dump)

    def define_baseargs(self, parser):
        '''
        Define basic command-line arguments required by the script.
        @parser is a parser object created using the `argparse` module.
        returns: None
        '''
        parser.add_argument('--name', default=None,
            help='Name to identify this instance')
        parser.add_argument('--statsd-server', default=None,
            help='Location of StatsD server to send statistics. '
                'Format is ip[:port]. Eg: localhost, localhost:8125')
        parser.add_argument('--log', default=None,
            help='Name of log file')
        parser.add_argument('--log-level', default='WARNING',
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
