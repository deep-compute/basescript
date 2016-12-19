import sys
import logging
from structlog import BoundLoggerBase, PrintLogger, get_logger

class StdlibStructlogHandler(logging.Handler):
    def __init__(self):
        super(StdlibStructlogHandler, self).__init__()
        self._log = get_logger()

    def emit(self, record):
        kw = {
            '_': {
                'fn': record.funcName,
                'ln': record.lineno,
                'name': record.name,
                'file': record.pathname,
            },
            # to tell the structlog that there is no need to get the frames again
            '_frame_info': True,
        }

        levelname = record.levelname.lower()

        if record.exc_info is not None:
            kw['exc_info'] = record.exc_info
            levelname = 'exception'

        fn = getattr(self._log, levelname)
        event = record.msg
        args = record.args or []

        fn(event, *args, **kw)

# Logger with an interface similar to python's standard library logger
# to be used with structlog.PrintLoggerFactory
class LevelLogger(PrintLogger):
    def __init__(self, stream=None, level=None):
        """
        Creates a leveled logger with defaults
        stream=sys.stderr
        level=logging.WARNING
        """
        if stream is None:
            stream = sys.stderr

        super(LevelLogger, self).__init__(file=stream)

        self.level = level or logging.WARNING
        assert isinstance(self.level, int), "expected int but got %r" % level

    def setLevel(self, level):
        assert isinstance(level, int), "expected int but got %r" % level
        self.level = level

    def isEnabledFor(self, level):
        return level >= self.level

class LevelLoggerFactory(object):
    def __init__(self, stream=None, level=None):
        self.stream = stream
        self.level = level

    def __call__(self, *args):
        return LevelLogger(stream=self.stream, level=self.level)

class BoundLevelLogger(BoundLoggerBase):
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

        _frame_info_present = event_dict.pop('_frame_info', False)
        # if it is the standard library logger. then event dict is already populated
        if _frame_info_present:
            return event_dict

        func = caller_frame.f_code.co_name
        module = caller_frame.f_globals.get('__name__', '??')
        filename = caller_frame.f_code.co_filename
        lineno = caller_frame.f_lineno

        event_dict.update({
            "_": {
                "fn": func,
                "ln": lineno,
                "name": module,
                "file": filename,
            },
        })
        return event_dict

    def debug(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.debug` with the result.
        """
        if not self._logger.isEnabledFor(logging.DEBUG):
            return

        kw = self._add_base_info(kw)
        kw['level'] = "debug"
        return self._proxy_to_logger('debug', event, *args, **kw)

    def info(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.info` with the result.
        """
        if not self._logger.isEnabledFor(logging.INFO):
            return

        kw = self._add_base_info(kw)
        kw['level'] = "info"
        return self._proxy_to_logger('info', event, *args, **kw)

    def warning(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.warning` with the result.
        """
        if not self._logger.isEnabledFor(logging.WARNING):
            return

        kw = self._add_base_info(kw)
        kw['level'] = "warning"
        return self._proxy_to_logger('warning', event, *args, **kw)

    warn = warning

    def error(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.error` with the result.
        """
        if not self._logger.isEnabledFor(logging.ERROR):
            return

        kw = self._add_base_info(kw)
        kw['level'] = "error"
        return self._proxy_to_logger('error', event, *args, **kw)

    def critical(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.critical` with the result.
        """
        if not self._logger.isEnabledFor(logging.CRITICAL):
            return

        kw = self._add_base_info(kw)
        kw['level'] = "critical"
        return self._proxy_to_logger('critical', event, *args, **kw)

    def exception(self, event=None, *args, **kw):
        """
        Process event and call :meth:`logging.Logger.error` with the result,
        after setting ``exc_info`` to `True`.
        """
        if not self._logger.isEnabledFor(logging.exception):
            return

        kw = self._add_base_info(kw)
        kw['level'] = "exception"
        kw.setdefault('exc_info', True)
        kw['_frame_info'] = True
        return self.error(event, *args, **kw)

    fatal = critical

    def _proxy_to_logger(self, method_name, event, *event_args,
                         **event_kw):
        """
        Propagate a method call to the wrapped logger.

        This is the same as the superclass implementation, except that
        it also preserves positional arguments in the `event_dict` so
        that the stdblib's support for format strings can be used.
        """
        if event_args:
            event_kw['positional_args'] = event_args
        return super(BoundLevelLogger, self)._proxy_to_logger(method_name,
                                                         event=event,
                                                         **event_kw)

    #
    # Pass-through methods to mimick the stdlib's logger interface.
    #

    def setLevel(self, level):
        """
        Calls :meth:`logging.Logger.setLevel` with unmodified arguments.
        """
        self._logger.setLevel(level)

