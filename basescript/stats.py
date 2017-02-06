from __future__ import absolute_import

import time
import datetime
from threading import Lock
from pytz import UTC

_now = datetime.datetime.utcnow

EPOCH = UTC.localize(datetime.datetime.utcfromtimestamp(0))

def _convert_timestamp(timestamp, precision='ms'):
    """
    converts a given datetime object into an influx timestamp.
    borrowed from
    https://github.com/influxdata/influxdb-python/blob/c9fcede02e1d29360356732632ae6f0fbadcfcb6/influxdb/line_protocol.py#L19

    precision values are
        - n  : nanoseconds
        - u  : microseconds
        - ms : milliseconds (default)
        - s  : seconds
        - m  : minutes
        - h  : hours
    """

    if not timestamp.tzinfo:
        timestamp = UTC.localize(timestamp)

    ns = (timestamp - EPOCH).total_seconds() * 1e9

    # take care of our default case first
    if precision == 'ms':
        return int(ns / 1e6)

    if precision == 'n':
        return int(ns)

    if precision == 'u':
        return int(ns / 1e3)

    if precision == 's':
        return int(ns / 1e9)

    if precision == 'm':
        return int((ns / 1e9) / 60)

    if precision == 'h':
        return int((ns / 1e9) / 3600)

    raise ValueError("unknown precision %s" % precision)

class Series(object):
    """
    metrics for a particular series.
    a series is a combination of retention policy, measurement and tags.
    a series has many fields (data / metrics) in the form of
    counters, gauges and timers.
    """

    def __init__(self, series_key):
        """
        Creates a series given a series_key which looks like
        measurement tagkey1=value1,tagkey2=value2,...tagkeyn=valuen
        use Series.make_series_key to generate such a series_key
        """
        self.__key = series_key
        self._last_accessed_time = _now()

        self._reset()

    def _reset(self):
        self._modified = False
        self._counters = {}
        self._gauges = {}
        self._timers = {}
        self._fields = {}

    @staticmethod
    def make_series_key(measurement, **tags):
        """
        creates the key to make a series
        a series is a combination of retention policy, measurement and tags
        NOTE: ignores tags who's values are None
        """
        # TODO include retention policy in the series key creation ?
        if len(tags) == 0:
            return measurement

        tags_srtd = sorted([ '%s=%s' % (k,v) for k,v in tags.iteritems() if v is not None ])
        tags_str = ','.join(tags_srtd)
        # TODO if relying on this format later, make sure k,v do not have spaces or commas

        series = '%s,%s' % (measurement, tags_str)
        return series.strip()

    def fields(self, **fields):
        """
        sets the values for fields that aren't counters,
        gauges or timers.
        does not do any extra processing for such fields.
        if multiple values are observed for the same field in a given interval,
        it uses the latest value.
        """
        self._modified = True
        self._last_accessed_time = _now()

        for field, value in fields.iteritems():
            self._fields[field] = value

        return self

    def count(self, **fields):
        """
        adds or subtracts the fields
        """
        self._modified = True
        self._last_accessed_time = _now()

        # TODO assert values are integers ?
        c = self._counters
        for field, value in fields.iteritems():
            c[field] = value + c.get(field, 0)

        return self

    def gauge(self, **fields):
        """
        sets the values for the given fields
        """
        self._modified = True
        self._last_accessed_time = _now()

        g = self._gauges
        # TODO assert values are integers ?
        for field, value in fields.iteritems():
            g[field] = value

        return self

    def time(self, **fields):
        """
        adds timing information for the given fields
        """
        self._modified = True
        self._last_accessed_time = _now()

        # TODO calculate every time for cpu cycles ?
        # I choose to only store, and calculate later

        # https://blog.pkhamre.com/understanding-statsd-and-graphite/

        t = self._timers
        for field, value in fields.iteritems():
            # TODO is setdefault too slow ?
            t.setdefault(field, []).append(value)

        return self

    def _to_line_protocol(self, ts=None, precision='ms'):
        """
        returns the influxdb line protocol representation of this series
        measurement,tagkey1=tagval1,...,tagkeyn=tagvaln fieldkey1=fieldval1,...,fieldkeyn=fieldvaln timestamp
        https://docs.influxdata.com/influxdb/v1.1/write_protocols/line_protocol_tutorial/

        if no timestamp is given, it will create the current timestamp.
        if a timestamp is provided, it assumes it is in the provided precision format.
        """

        fields = []
        fields.extend('%s=%s' % (k,v) for k,v in self._fields.iteritems())
        fields.extend('c_%s=%s' % (k,v) for k,v in self._counters.iteritems())
        fields.extend('g_%s=%s' % (k, v) for k,v in self._gauges.iteritems())

        for timer_name, timer_values in self._timers.iteritems():
            agg_values = self._aggregate_timer_values(timer_values)
            fields.extend('t_%s_%s=%s' % (timer_name, k, v) for k,v in agg_values.iteritems() )

        # TODO is there a cap on max number of fields on a line ?
        # we can always send two lines with same timestamp

        # TODO what if there aren't any fields to send ? Not possible

        # NOTE: sorting fields makes it easier to test it. is it overkill ?
        fields.sort()
        fields = ','.join(fields)
        ts = ts or _convert_timestamp(_now(), precision=precision)
        return '%s %s %s' % (self.__key, fields, ts)

    @staticmethod
    def _aggregate_timer_values(values):
        """
        aggregates the values from a timer to give
          - count
          - lower
          - mean
          - mean_90
          - std # TODO
          - sum
          - sum_90
          - upper
          - upper_90
        https://blog.pkhamre.com/understanding-statsd-and-graphite/
        """
        # TODO numpy would make this easier but since we don't have it..
        # TODO numpy would be faster. if numpy is installed, we should use it.
        if len(values) == 0:
            return {}

        values = sorted(values)
        count = len(values)
        min_val = values[0]
        max_val = values[-1]

        cum_val = [min_val]
        for v in values[1:]:
            cum_val.append(v + cum_val[-1])

        ssum = cum_val[count - 1]
        mean = float(ssum) / count

        metrics = {
            "sum": ssum,
            "mean": mean,
            "lower": min_val,
            "upper": max_val,
            "count": count,
        }

        if count == 1:
            return metrics

        # don't want to lose shape of the data while aggregating.
        # sum, count and mean aren't enough
        # TODO standard deviation, quartiles
        # TODO more than just 90 percentile
        threshold_index = int(round(((100.0 - 90.0) / 100.0) * count))
        num_in_threshold = count - threshold_index
        max_at_threshold = values[num_in_threshold - 1]
        ssum = cum_val[num_in_threshold - 1]
        mean = float(ssum) / num_in_threshold
        metrics["sum_90"] = ssum
        metrics["mean_90"] = mean
        metrics["upper_90"] = max_at_threshold

        return metrics

    def __hash__(self):
        return hash(self.__key)

    def __eq__(self, o):
        if not isinstance(o, Series):
            return False

        return self.__key == o.__key

    def __neq__(self, o):
        return not self == 0

    def __str__(self):
        return self.__key

    __unicode__ = __str__

    def __repr__(self):
        return "Series(%r)" % self.__key

class ThreadSafeSeries(Series):
    """
    simple thread safe version of Series which acquires and releases a lock
    before running each function
    """
    # TODO unit tests ? avoid deadlocks ?
    # TODO time this to see how performant it is

    def __init__(self, series_key, lock):
        super(ThreadSafeSeries, self).__init__(series_key)
        self.lock = lock

        def safe_access(fn):
            def decked(*args, **kwargs):
                self.lock.acquire()
                ret_val = fn(*args, **kwargs)
                self.lock.release()
                return ret_val

            return decked

        fns = ('fields', 'count', 'gauge', 'time')
        for fn_name in fns:
            fn = getattr(self, fn_name)
            decked_fn = safe_access(fn)
            setattr(self, fn_name, decked_fn)

    def __repr__(self):
        return "ThreadSafeSeries(%r)" % self.__key

class Stats(object):
    """
    aggregate and write periodic influxdb stats
    """
    # TODO what is the level of these stats ?
    # if it is our own logger we can have our own format for it , just like info etc.
    # so it is always written.

    # if a particular series is dormant for the given duration, it is dropped to save
    # memory
    DORMANT_DURATION = datetime.timedelta(minutes=1)

    # stats are dumped given the dump interval
    DUMP_INTERVAL = datetime.timedelta(seconds=1)

    def __init__(self, log, thread_safe=False, **tags):
        self.log = log

        self.lock = Lock()
        self.series_map = {}
        self.thread_safe = thread_safe

        # tags that must always be appended to a measurement
        # example hostname
        self.tags = { k:v for k,v in tags.iteritems()
            if isinstance(v, basestring) and len(v) > 0
        }

    def measure(self, measurement, **tags):
        # NOTE incase of conflict, the global tags take preference.
        # hostname cannot be overridden by a measure.
        # TODO log errors in case of conflict
        tags.update(self.tags)

        series_key = Series.make_series_key(measurement, **tags)

        self.lock.acquire()

        series = self.series_map.get(series_key, None)
        if series is None:
            # TODO profiling of number of objects, speed sacrificed for thread safety, etc
            if self.thread_safe:
                series = ThreadSafeSeries(series_key, self.lock)
            else:
                series = Series(series_key)

            self.series_map[series_key] = series

        self.lock.release()

        return series

    def dump_stats(self):
        """
        dumps the stats from the series maps
        """
        # TODO maintain global state
        # TODO session stats

        # TODO choose good buffering for stats
        lines = []
        keys_to_del = []
        dormant_duration = self.DORMANT_DURATION

        self.lock.acquire()

        now = _now()
        ts = _convert_timestamp(timestamp=now, precision='ms')

        for series_key, series in self.series_map.iteritems():

            if series._modified:
                # TODO should all of them get the same time ?
                # pass the now timestamp to them ?
                # NOTE will this be a problem when looking at metrics for order of events within a second ?
                # TODO is there any point of millisecond precision ? We are running this every second.
                lines.append(series._to_line_protocol(ts=ts, precision='ms'))
                series._reset()
                continue

            # series wasn't modified. need to check if we need to delete it or not
            if (now - series._last_accessed_time) >= dormant_duration :
                keys_to_del.append(series_key)

        # TODO unittest periodic deletion of keys
        for k in keys_to_del:
            del self.series_map[k]

        self.lock.release()

        return lines

    def dump_stats_periodically(self, interval=None):
        """
        periodically dump the stats into the log.
        interval must be a datetime timedelta object.
        caller must invoke as a thread.
        """
        interval = interval or self.DUMP_INTERVAL
        assert isinstance(interval, datetime.timedelta)

        self.log.debug("dumping stats periodically", interval=interval)

        interval_s = interval.total_seconds()
        while True:
            # TODO is try except needed ?
            influxdb_protocol_lines = self.dump_stats()
            for line in influxdb_protocol_lines:
                self.log._dump_stats(line)

            time.sleep(interval_s)

