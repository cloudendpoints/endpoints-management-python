# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Google Service Control Client"""

from __future__ import absolute_import

import collections
from datetime import datetime, timedelta
import google.apigen.servicecontrol_v1_messages as messages

# 0.1.0 was the integration test start point
# 0.1.1 fixed a dependency issue
# 0.1.2 was an attempt to fix thread instantion
# 0.1.3 fixed app_info.url handling and various typos
__version__ = '0.1.3'

# Alias the generated MetricKind and ValueType enums to simplify their usage
# elsewhere
MetricKind = messages.MetricDescriptor.MetricKindValueValuesEnum
ValueType = messages.MetricDescriptor.ValueTypeValueValuesEnum

USER_AGENT = 'ESP'
SERVICE_AGENT = USER_AGENT + '/' + __version__


class ReportAggregationOptions(
        collections.namedtuple(
            'ReportAggregegationOptions',
            ['num_entries',
             'flush_interval'])):
    """Holds values used to control report aggregation behavior.

    Attributes:

        num_entries: the maximum number of cache entries that can be kept in
          the aggregation cache

        flush_interval (:class:`datetime.timedelta`): the maximum delta before
          aggregated report requests are flushed to the server.  The cache
          entry is deleted after the flush
    """
    # pylint: disable=too-few-public-methods
    DEFAULT_NUM_ENTRIES = 200
    DEFAULT_FLUSH_INTERVAL = timedelta(seconds=1)

    def __new__(cls,
                num_entries=DEFAULT_NUM_ENTRIES,
                flush_interval=DEFAULT_FLUSH_INTERVAL):
        """Invokes the base constructor with default values."""
        assert isinstance(num_entries, int), 'should be an int'
        assert isinstance(flush_interval, timedelta), 'should be a timedelta'

        return super(cls, ReportAggregationOptions).__new__(
            cls,
            num_entries,
            flush_interval)


class CheckAggregationOptions(
        collections.namedtuple(
            'CheckAggregationOptions',
            ['num_entries',
             'flush_interval',
             'expiration'])):
    """Holds values used to control report check behavior.

    Attributes:

        num_entries: the maximum number of cache entries that can be kept in
          the aggregation cache
        flush_interval (:class:`datetime.timedelta`): the maximum delta before
          aggregated report requests are flushed to the server.  The cache
          entry is deleted after the flush.
        expiration (:class:`datetime.timedelta`): elapsed time before a cached
          check response should be deleted.  This value should be larger than
          ``flush_interval``, otherwise it will be ignored, and instead a value
          equivalent to flush_interval + 1ms will be used.
    """
    # pylint: disable=too-few-public-methods
    DEFAULT_NUM_ENTRIES = 200
    DEFAULT_FLUSH_INTERVAL = timedelta(milliseconds=500)
    DEFAULT_EXPIRATION = timedelta(seconds=1)

    def __new__(cls,
                num_entries=DEFAULT_NUM_ENTRIES,
                flush_interval=DEFAULT_FLUSH_INTERVAL,
                expiration=DEFAULT_EXPIRATION):
        """Invokes the base constructor with default values."""
        assert isinstance(num_entries, int), 'should be an int'
        assert isinstance(flush_interval, timedelta), 'should be a timedelta'
        assert isinstance(expiration, timedelta), 'should be a timedelta'
        if expiration <= flush_interval:
            expiration = flush_interval + timedelta(milliseconds=1)
        return super(cls, CheckAggregationOptions).__new__(
            cls,
            num_entries,
            flush_interval,
            expiration)


def to_cache_timer(datetime_func):
    """Converts a datetime_func to a timestamp_func.

    Args:
       datetime_func (callable[[datatime]]): a func that returns the current
         time

    Returns:
       time_func (callable[[timestamp]): a func that returns the timestamp
         from the epoch
    """
    if datetime_func is None:
        datetime_func = datetime.utcnow

    def _timer():
        """Return the timestamp since the epoch."""
        return (datetime_func() - datetime(1970, 1, 1)).total_seconds()

    return _timer
