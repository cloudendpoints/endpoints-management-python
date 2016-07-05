# Copyright 2016, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Google Service Control Client"""

from __future__ import absolute_import

import collections
import datetime
import google.apigen.servicecontrol_v1_messages as messages

__version__ = '0.1.0'

# Alias the generated MetricKind and ValueType enums to simplify their usage
# elsewhere
MetricKind = messages.MetricDescriptor.MetricKindValueValuesEnum
ValueType = messages.MetricDescriptor.ValueTypeValueValuesEnum


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
    DEFAULT_FLUSH_INTERVAL = datetime.timedelta(seconds=1)

    def __new__(cls,
                num_entries=DEFAULT_NUM_ENTRIES,
                flush_interval=DEFAULT_FLUSH_INTERVAL):
        """Invokes the base constructor with default values."""
        assert isinstance(num_entries, int), 'should be an int'
        assert isinstance(flush_interval,
                          datetime.timedelta), 'should be a timedelta'

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
    DEFAULT_FLUSH_INTERVAL = datetime.timedelta(milliseconds=500)
    DEFAULT_EXPIRATION = datetime.timedelta(seconds=1)

    def __new__(cls,
                num_entries=DEFAULT_NUM_ENTRIES,
                flush_interval=DEFAULT_FLUSH_INTERVAL,
                expiration=DEFAULT_EXPIRATION):
        """Invokes the base constructor with default values."""
        assert isinstance(num_entries, int), 'should be an int'
        assert isinstance(flush_interval,
                          datetime.timedelta), 'should be a timedelta'
        assert isinstance(expiration,
                          datetime.timedelta), 'should be a timedelta'
        if expiration <= flush_interval:
            expiration = flush_interval + datetime.timedelta(milliseconds=1)
        return super(cls, CheckAggregationOptions).__new__(
            cls,
            num_entries,
            flush_interval,
            expiration)
