import sys
import json
import time
import uuid
import atexit
import socket
import logging
import numbers
from six.moves import queue
from threading import Thread, Lock
from datetime import datetime
from functools import wraps

from deeputil import Dummy, keeprunning
import structlog

# stdlib to structlog handlers should be configured only once.
_GLOBAL_LOG_CONFIGURED = False

FORCE_FLUSH_Q_SIZE = 1
HOSTNAME = socket.gethostname()
METRICS_STATE = {}
METRICS_STATE_LOCK = Lock()

LOG = None


class Stream(object):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()

    def close(self):
        for s in self.streams:
            s.close()


class StderrConsoleRenderer(object):
    BACKUP_KEYS = ("timestamp", "level", "event", "logger", "stack", "exception")

    def __init__(self):
        # TODO allow parameters to configure this
        self.cr = structlog.dev.ConsoleRenderer()
        self.pl = structlog.PrintLogger(file=sys.stderr)

    def __call__(self, logger, method_name, event_dict):
        # based on https://github.com/hynek/structlog/blob/master/src/structlog/dev.py
        # since it pops data from event_dict, we need to add it back
        backup = {}
        for k in self.BACKUP_KEYS:
            v = event_dict.get(k, None)
            if v is None:
                continue
            backup[k] = v

        msg = self.cr(logger, method_name, event_dict)
        self.pl.msg(msg)

        event_dict.update(backup)
        return event_dict


class StdlibStructlogHandler(logging.Handler):
    def __init__(self):
        super(StdlibStructlogHandler, self).__init__()
        self._log = structlog.get_logger()

    def emit(self, record):
        kw = {}
        levelname = record.levelname.lower()

        if record.exc_info is not None:
            kw["exc_info"] = record.exc_info
            levelname = "exception"

        fn = getattr(self._log, levelname)
        event = record.msg
        args = record.args or []

        # If the received event is a class instance
        # we are checking for message and taking message as event
        if not isinstance(event, str) and getattr(event, "message", None):
            event = event.message

        fn(event, *args, **kw)


# Logger with an interface similar to python's standard library logger
# to be used with structlog.PrintLoggerFactory
class LevelLogger(structlog.PrintLogger):
    def __init__(self, fp, level=None):
        """
        Creates a leveled logger with defaults
        level=logging.WARNING
        """
        super(LevelLogger, self).__init__(file=fp)

        self.level = level or logging.WARNING
        assert isinstance(self.level, int), "expected int but got %r" % level

    def setLevel(self, level):
        assert isinstance(level, int), "expected int but got %r" % level
        self.level = level

    def isEnabledFor(self, level):
        return level >= self.level


class LevelLoggerFactory(object):
    def __init__(self, fp, level=None):
        self.fp = fp
        self.level = level

    def __call__(self, *args):
        return LevelLogger(self.fp, level=self.level)


class BoundLevelLogger(structlog.BoundLoggerBase):
    """
    Python Standard Library "like" version.
    Assumes that the factory is LevelLogger i.e. _logger is a LevelLogger.
    """

    def _add_base_info(self, event_dict):
        """
        Instead of using a processor, adding basic information like caller, filename etc
        here.
        """
        f = sys._getframe()
        level_method_frame = f.f_back
        caller_frame = level_method_frame.f_back
        return event_dict

    def debug(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.debug` with the result.
        """
        if not self._logger.isEnabledFor(logging.DEBUG):
            return

        kw = self._add_base_info(kw)
        kw["level"] = "debug"
        return self._proxy_to_logger("debug", event, *args, **kw)

    def info(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.info` with the result.
        """
        if not self._logger.isEnabledFor(logging.INFO):
            return

        kw = self._add_base_info(kw)
        kw["level"] = "info"
        return self._proxy_to_logger("info", event, *args, **kw)

    def warning(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.warning` with the result.
        """
        if not self._logger.isEnabledFor(logging.WARNING):
            return

        kw = self._add_base_info(kw)
        kw["level"] = "warning"
        return self._proxy_to_logger("warning", event, *args, **kw)

    warn = warning

    def error(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.error` with the result.
        """
        if not self._logger.isEnabledFor(logging.ERROR):
            return

        kw = self._add_base_info(kw)
        kw["level"] = "error"
        return self._proxy_to_logger("error", event, *args, **kw)

    def critical(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.critical` with the result.
        """
        if not self._logger.isEnabledFor(logging.CRITICAL):
            return

        kw = self._add_base_info(kw)
        kw["level"] = "critical"
        return self._proxy_to_logger("critical", event, *args, **kw)

    def exception(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.error` with the result,
        after setting ``exc_info`` to `True`.
        """
        if not self._logger.isEnabledFor(logging.ERROR):
            return

        kw = self._add_base_info(kw)
        kw["level"] = "exception"
        kw.setdefault("exc_info", True)
        return self.error(event, *args, **kw)

    def _dump_stats(self, metric):
        """
        Dumps metrics irrespective of log level
        """
        # TODO have a feature to silence metrics as well
        # TODO if dumping to console, we shouldn't club metrics. It should be sent one by one on each line.
        return self._proxy_to_logger("msg", metric, type="metric", level="info")

    fatal = critical

    def _proxy_to_logger(self, method_name, event, *event_args, **event_kw):
        """
        Propagate a method call to the wrapped logger.

        This is the same as the superclass implementation, except that
        it also preserves positional arguments in the `event_dict` so
        that the stdblib's support for format strings can be used.
        """

        if isinstance(event, bytes):
            event = event.decode("utf-8")

        if event_args:
            event_kw["positional_args"] = event_args

        return super(BoundLevelLogger, self)._proxy_to_logger(
            method_name, event=event, **event_kw
        )

    # Pass-through methods to mimick the stdlib's logger interface.

    def setLevel(self, level):
        """
        Calls :meth:`logging.Logger.setLevel` with unmodified arguments.
        """
        self._logger.setLevel(level)


def _structlog_default_keys_processor(logger_class, log_method, event):
    """ Add unique id, type and hostname """
    global HOSTNAME

    if "id" not in event:
        event["id"] = "%s_%s" % (
            datetime.utcnow().strftime("%Y%m%dT%H%M%S"),
            uuid.uuid1().hex,
        )

    if "type" not in event:
        event["type"] = "log"

    event["host"] = HOSTNAME

    return event


def _structlog_minimal_processor(logger_class, log_method, event):
    for key in ("host", "id", "type"):
        if key in event:
            event.pop(key)

    return event


@keeprunning()
def dump_metrics(log, interval):
    global METRICS_STATE

    terminate = False

    while True:
        try:
            log._force_flush_q.get(block=True, timeout=interval)
            terminate = True
        except queue.Empty:
            pass

        METRICS_STATE_LOCK.acquire()
        m = METRICS_STATE
        METRICS_STATE = {}
        METRICS_STATE_LOCK.release()

        for (k, _), v in m.items():
            n = v["num"]
            d = dict(k)
            d.update(v["fields"])

            level = d.pop("level")
            event = d.pop("event")

            fn = getattr(log, level)
            fn(event, type="metric", __grouped__=True, num=n, **d)

        if terminate:
            break


def metrics_grouping_processor(logger_class, log_method, event):
    if event.get("type") == "logged_metric":
        event["type"] = "metric"
        return event

    if event.get("type") != "metric":
        return event

    if event.get("__grouped__"):
        event.pop("__grouped__")
        return event

    for k in ("timestamp", "type", "id"):
        if k not in event:
            continue
        event.pop(k)

    # Delete a key startswith `_` for grouping.
    event = {k: v for k, v in event.items() if not k.startswith("_")}

    key = []
    fields = []

    for k, v in sorted(event.items()):
        (fields if isinstance(v, (numbers.Number, bool)) else key).append((k, v))

    key = (tuple(key), tuple(sorted(k for k, _ in fields)))
    METRICS_STATE_LOCK.acquire()
    try:
        state = METRICS_STATE.get(key, {"num": 0, "fields": {}})
        sfields = state["fields"]
        num = state["num"]

        for fk, fv in fields:
            favg = sfields.get(fk, 0.0)
            favg = (favg * num + fv) / (num + 1)  # moving average
            sfields[fk] = favg

        state["num"] += 1

        METRICS_STATE[key] = state
    finally:
        METRICS_STATE_LOCK.release()

    raise structlog.DropEvent


def define_log_processors():
    """
    log processors that structlog executes before final rendering
    """
    # these processors should accept logger, method_name and event_dict
    # and return a new dictionary which will be passed as event_dict to the next one.
    return [
        structlog.processors.TimeStamper(fmt="iso"),
        _structlog_default_keys_processor,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _configure_logger(
    fmt, quiet, level, fpath, processors, metric_grouping_interval, minimal
):
    """
    configures a logger when required write to stderr or a file
    """

    # NOTE not thread safe. Multiple BaseScripts cannot be instantiated concurrently.

    global _GLOBAL_LOG_CONFIGURED
    if _GLOBAL_LOG_CONFIGURED:
        return

    assert fmt in ["json", "pretty"]

    _processors = define_log_processors()
    _processors += processors or []
    if metric_grouping_interval:
        _processors.append(metrics_grouping_processor)

    if minimal:
        _processors.append(_structlog_minimal_processor)

    streams = []

    if fpath:
        streams.append(open(fpath, "a"))

    if fmt == "json" and not quiet:
        streams.append(sys.stderr)

    if fmt == "pretty" and not quiet:
        _processors.append(StderrConsoleRenderer())

    _processors.append(structlog.processors.JSONRenderer())

    # a global level struct log config unless otherwise specified.
    level = getattr(logging, level.upper())

    stream = streams[0] if len(streams) == 1 else Stream(*streams)
    atexit.register(stream.close)

    structlog.configure(
        processors=_processors,
        context_class=dict,
        logger_factory=LevelLoggerFactory(stream, level=level),
        wrapper_class=BoundLevelLogger,
        cache_logger_on_first_use=True,
    )

    # TODO take care of removing other handlers
    stdlib_root_log = logging.getLogger()
    stdlib_root_log.addHandler(StdlibStructlogHandler())
    stdlib_root_log.setLevel(level)

    _GLOBAL_LOG_CONFIGURED = True


def init_logger(
    fmt=None,
    quiet=False,
    level="INFO",
    fpath=None,
    processors=None,
    metric_grouping_interval=None,
    minimal=False,
):
    """
    fmt=pretty/json controls only stderr; file always gets json.
    """

    global LOG
    if LOG is not None:
        return LOG

    if quiet and fpath is None:
        # no need for a log - return a dummy
        return Dummy()

    if not fmt and not quiet:
        fmt = "pretty" if sys.stderr.isatty() else "json"

    _configure_logger(
        fmt, quiet, level, fpath, processors, metric_grouping_interval, minimal
    )

    log = structlog.get_logger()
    log._force_flush_q = queue.Queue(maxsize=FORCE_FLUSH_Q_SIZE)

    if metric_grouping_interval:
        keep_running = Thread(target=dump_metrics, args=(log, metric_grouping_interval))
        keep_running.daemon = True
        keep_running.start()

    # TODO functionality to change even the level of global stdlib logger.

    LOG = log
    return log


def pretty_print(colors=True):
    r = structlog.dev.ConsoleRenderer(colors=colors)
    for line in sys.stdin:
        print(r(None, None, json.loads(line)))


def get_logger():
    return LOG
