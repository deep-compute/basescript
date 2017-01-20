# consider using http://docs.pytest.org/en/latest/fixture.html#fixture

import unittest
import datetime

import basescript.stats

class TestTimestampConversion(unittest.TestCase):
    def test_millisecond_conversion(self):
        """
        from http://currentmillis.com/?1484899750312
        """
        t = datetime.datetime(2017, 01, 20, 8, 9, 10, 312125)
        timestamp = basescript.stats._convert_timestamp(t, precision='ms')
        self.assertEqual(timestamp, 1484899750312)

    def test_microsecond_conversion(self):
        """
        from http://currentmillis.com/?1484899750312
        """
        t = datetime.datetime(2017, 01, 20, 8, 9, 10, 312125)
        timestamp = basescript.stats._convert_timestamp(t, precision='u')
        self.assertEqual(timestamp, 1484899750312125)

    # TODO more conversions

class TestSeries(unittest.TestCase):

    def test_aggregate_zero_timer_values(self):
        values = []
        aggregates = basescript.stats.Series._aggregate_timer_values([])
        self.assertEqual(aggregates, {})

    def test_aggregate_one_timer_value(self):
        values = [450]
        aggregates = basescript.stats.Series._aggregate_timer_values(values)
        expected = {
            "lower": 450, "upper": 450, "sum": 450, "count": 1, "mean": 450,
        }
        # NOTE using assertDictContainsSubset for better reporting of keys
        self.assertDictContainsSubset(aggregates, expected)
        self.assertDictContainsSubset(expected, aggregates)

    def test_aggregate_multiple_timer_values(self):
        """
        tests the computed aggregated values
        """

        values = [
            450,
            120,
            553,
            994,
            334,
            844,
            675,
            496,
        ]

        aggregates = basescript.stats.Series._aggregate_timer_values(values)
        expected = {
            "lower": 120, "count": 8,
            "upper": 994, "mean": 558.25, "sum": 4466,
            "mean_90": 496.0, "upper_90": 844, "sum_90": 3472,
        }

        self.assertDictContainsSubset(aggregates, expected)

    def test_gen_series_key_zero_tags(self):
        series_key = basescript.stats.Series.make_series_key("my_measurement")
        expected = "my_measurement"
        self.assertEqual(series_key, expected)

    def test_gen_series_key_one_tag(self):
        series_key = basescript.stats.Series.make_series_key("my_measurement", mytag="myval")
        expected = "my_measurement,mytag=myval"
        self.assertEqual(series_key, expected)

        # all tags should be strings
        series_key = basescript.stats.Series.make_series_key("my_measurement", mytag=12)
        expected = "my_measurement,mytag=12"
        self.assertEqual(series_key, expected, "failed on integer tag")

    def test_gen_series_key_multiple_tags(self):
        series_key = basescript.stats.Series.make_series_key("my_measurement",
            mytag1="abcd", mytag2="defg", alpha_tag="xyz", num_tag=123, beta="aaa",
        )
        expected = "my_measurement,alpha_tag=xyz,beta=aaa,mytag1=abcd,mytag2=defg,num_tag=123"
        self.assertEqual(series_key, expected)

    def _test_last_accessed_times_in_non_decreasing_order(self, lats):
        # all the last_accessed_times must be in increasing order starting with None
        for i in xrange(0, len(lats) - 1):
            a, b = lats[i], lats[i+1]
            self.assertIsNot(a, b)

            self.assertTrue(b >= a)

    def test_series_counter(self):
        series_key = "my_measurement,mytag1=myval1"

        last_accessed_times = []
        series = basescript.stats.Series(series_key)
        last_accessed_times.append(series._last_accessed_time)

        ret_val = series.count(tests=5, exams=2)
        self.assertIs(series, ret_val)
        self.assertEqual(series._counters, { "tests": 5, "exams": 2 })
        last_accessed_times.append(series._last_accessed_time)

        series.count(tests=2)
        self.assertEqual(series._counters, { "tests": 7, "exams": 2 })
        last_accessed_times.append(series._last_accessed_time)

        series.count(tests=-5)
        self.assertEqual(series._counters, { "tests": 2, "exams": 2})
        last_accessed_times.append(series._last_accessed_time)

        self._test_last_accessed_times_in_non_decreasing_order(last_accessed_times)

        # TODO test non numeric ? floats ? for handling failures ?

    def test_series_gauge(self):
        series_key = "my_measurement,mytag1=myval1"

        last_accessed_times = []
        series = basescript.stats.Series(series_key)
        last_accessed_times.append(series._last_accessed_time)

        ret_val = series.gauge(files=10, directories=3)
        self.assertIs(series, ret_val)
        self.assertEqual(series._gauges, { "files": 10, "directories": 3 })
        last_accessed_times.append(series._last_accessed_time)

        series.gauge(files=4)
        self.assertEqual(series._gauges, { "files": 4, "directories": 3 })
        last_accessed_times.append(series._last_accessed_time)

        series.gauge(directories=2)
        self.assertEqual(series._gauges, { "files": 4, "directories": 2 })
        last_accessed_times.append(series._last_accessed_time)

        self._test_last_accessed_times_in_non_decreasing_order(last_accessed_times)
        # TODO test non numeric ? floats ? for handling failures ?

    def test_series_time(self):
        series_key = "my_measurement,mytag1=myval1"

        last_accessed_times = []
        series = basescript.stats.Series(series_key)
        last_accessed_times.append(series._last_accessed_time)

        ret_val = series.time(user_time=100)
        self.assertIs(series, ret_val)
        self.assertEqual(series._timers, { "user_time": [ 100 ] })
        last_accessed_times.append(series._last_accessed_time)

        series.time(user_time=300)
        self.assertEqual(series._timers, { "user_time": [ 100, 300 ] })
        last_accessed_times.append(series._last_accessed_time)

        self._test_last_accessed_times_in_non_decreasing_order(last_accessed_times)

        # TODO tests for multiple timers together ? is it necessary ?

    # TODO test 'fields'

    def test_gen_line_protocol(self):
        # TODO better stats for this
        # NOTE - how to specify that this will work only if test_aggregate_multiple_timer_values works
        series_key = 'my_measurement,mytag1=myval1'

        series = basescript.stats.Series(series_key)
        series._counters = { 'tests': 5, 'classes': 2 }
        series._gauges = { 'files': 1, 'modules': 1 }
        series._timers = {
            'runtime': [ 450, 120, 553, 994, 334, 844, 675, 496 ]
        }
        series._fields = { 'random': 123 }

        # TODO test with other precisions ?
        ts = basescript.stats._convert_timestamp(basescript.stats._now(), precision='ms')
        result = series._to_line_protocol(ts, precision='ms')

        expected_fields = [
            'random=123', # fields
            'c_tests=5', 'c_classes=2', # counters
            'g_files=1', 'g_modules=1', # gauges
            # timers
            't_runtime_lower=120', 't_runtime_count=8', 't_runtime_upper=994',
            't_runtime_mean=558.25', 't_runtime_sum=4466',
            't_runtime_mean_90=496.0', 't_runtime_upper_90=844', 't_runtime_sum_90=3472',
        ]
        expected_fields.sort()

        expected = 'my_measurement,mytag1=myval1 %s %s' % (
            ','.join(expected_fields), ts,
        )
        self.assertEqual(result, expected)

    def test_series_hash_ability(self):
        series_key = 'my_measurement,mytag1=myval1'

        s1 = basescript.stats.Series(series_key)
        s2 = basescript.stats.Series(series_key)

        self.assertIsNot(s1, s2)
        self.assertEqual(hash(s1), hash(s2))
        self.assertEqual(s1, s2)

        sample_dict = {}
        sample_dict[s1] = 'a'
        sample_dict[s2] = 'b'

        self.assertEqual(sample_dict, { s2 : 'b' })

        sample_set = set()
        sample_set.add(s1)
        sample_set.add(s2)

        self.assertEqual(len(sample_set), 1)
        self.assertEqual(sample_set, set([s1]))
        self.assertEqual(sample_set, set([s2]))
        self.assertEqual(sample_set, set([s1, s2]))

if __name__ == '__main__':
    unittest.main()
