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

from __future__ import absolute_import

import datetime
import unittest2
from expects import expect, equal, raise_error

import google.apigen.servicecontrol_v1_messages as messages
from google.scc import timestamp, MetricKind
from google.scc.aggregators import metric_value, operation

_A_FLOAT_VALUE = 1.1
_REALLY_EARLY = timestamp.to_rfc3339(datetime.datetime(1970, 1, 1, 10, 0, 0))
_EARLY = timestamp.to_rfc3339(datetime.datetime(1980, 1, 1, 10, 0, 0))
_LATER = timestamp.to_rfc3339(datetime.datetime(1980, 2, 2, 10, 0, 0))
_LATER_STILL = timestamp.to_rfc3339(datetime.datetime(1981, 2, 2, 10, 0, 0))

_TEST_LABELS = {
    'key1': 'value1',
    'key2': 'value2',
}

# in tests, the description field is not currently used, but should be filled
_TESTS = [
    {
        'description': 'update the start time to that of the earliest',
        'kinds': None,
        'initial': messages.Operation(
            startTime=_EARLY,
            endTime=_LATER
        ),
        'ops': [
            messages.Operation(
                startTime=_REALLY_EARLY,
                endTime=_LATER
            ),
            messages.Operation(
                startTime=_LATER,
                endTime=_LATER
            ),
        ],
        'want': messages.Operation(startTime=_REALLY_EARLY, endTime=_LATER)
    },
    {
        'description': 'update the end time to that of the latest',
        'kinds': None,
        'initial': messages.Operation(
            startTime=_EARLY,
            endTime=_LATER
        ),
        'ops': [
            messages.Operation(
                startTime=_EARLY,
                endTime=_LATER
            ),
            messages.Operation(
                startTime=_EARLY,
                endTime=_LATER_STILL
            ),
        ],
        'want': messages.Operation(startTime=_EARLY, endTime=_LATER_STILL)
    },
    {
        'description': 'combine the log entries',
        'kinds': None,
        'initial': messages.Operation(
            startTime=_EARLY,
            endTime=_LATER,
            logEntries=[messages.LogEntry(textPayload='initial')]
        ),
        'ops': [
            messages.Operation(
                startTime=_EARLY,
                endTime=_LATER,
                logEntries=[messages.LogEntry(textPayload='agg1')]
            ),
            messages.Operation(
                startTime=_EARLY,
                endTime=_LATER,
                logEntries=[messages.LogEntry(textPayload='agg2')]
            ),
        ],
        'want': messages.Operation(
            startTime=_EARLY,
            endTime=_LATER,
            logEntries=[
                messages.LogEntry(textPayload='initial'),
                messages.LogEntry(textPayload='agg1'),
                messages.LogEntry(textPayload='agg2')
            ]
        )
    },
    {
        'description': 'combines the metric value using the default kind',
        'kinds': None,
        'initial': messages.Operation(
            startTime=_EARLY,
            endTime=_LATER,
            metricValueSets = [
                messages.MetricValueSet(
                    metricName='some_floats',
                    metricValues=[
                        metric_value.create(
                            labels=_TEST_LABELS,
                            doubleValue=_A_FLOAT_VALUE,
                            endTime=_EARLY
                        ),
                    ]
                ),
                messages.MetricValueSet(
                    metricName='other_floats',
                    metricValues=[
                        metric_value.create(
                            labels=_TEST_LABELS,
                            doubleValue=_A_FLOAT_VALUE,
                            endTime=_EARLY
                        ),
                    ]
                )
            ]
        ),
        'ops': [
            messages.Operation(
                startTime=_EARLY,
                endTime=_LATER,
                metricValueSets = [
                    messages.MetricValueSet(
                        metricName='some_floats',
                        metricValues=[
                            metric_value.create(
                                labels=_TEST_LABELS,
                                doubleValue=_A_FLOAT_VALUE,
                                endTime=_LATER
                            ),
                        ]
                    ),
                ]
            ),
            messages.Operation(
                startTime=_EARLY,
                endTime=_LATER,
                metricValueSets = [
                    messages.MetricValueSet(
                        metricName='other_floats',
                        metricValues=[
                            metric_value.create(
                                labels=_TEST_LABELS,
                                doubleValue=_A_FLOAT_VALUE,
                                endTime=_LATER_STILL
                            ),
                        ]
                    )
                ]

            ),
        ],
        'want': messages.Operation(
            startTime=_EARLY,
            endTime=_LATER,
            metricValueSets = [
                messages.MetricValueSet(
                    metricName='other_floats',
                    metricValues=[
                        metric_value.create(
                            labels=_TEST_LABELS,
                            doubleValue=_A_FLOAT_VALUE * 2,
                            endTime=_LATER_STILL
                        ),
                    ]
                ),
                messages.MetricValueSet(
                    metricName='some_floats',
                    metricValues=[
                        metric_value.create(
                            labels=_TEST_LABELS,
                            doubleValue=_A_FLOAT_VALUE * 2,
                            endTime=_LATER
                        ),
                    ]
                )
            ]
        )
    },
    {
        'description': 'combines a metric value using a kind that is not DELTA',
        'kinds': { 'some_floats': MetricKind.GAUGE },
        'initial': messages.Operation(
            startTime=_EARLY,
            endTime=_LATER,
            metricValueSets = [
                messages.MetricValueSet(
                    metricName='some_floats',
                    metricValues=[
                        metric_value.create(
                            labels=_TEST_LABELS,
                            doubleValue=_A_FLOAT_VALUE,
                            endTime=_EARLY
                        ),
                    ]
                ),
                messages.MetricValueSet(
                    metricName='other_floats',
                    metricValues=[
                        metric_value.create(
                            labels=_TEST_LABELS,
                            doubleValue=_A_FLOAT_VALUE,
                            endTime=_EARLY
                        ),
                    ]
                )
            ]
        ),
        'ops': [
            messages.Operation(
                startTime=_EARLY,
                endTime=_LATER,
                metricValueSets = [
                    messages.MetricValueSet(
                        metricName='some_floats',
                        metricValues=[
                            metric_value.create(
                                labels=_TEST_LABELS,
                                doubleValue=_A_FLOAT_VALUE,
                                endTime=_LATER
                            ),
                        ]
                    ),
                ]
            ),
            messages.Operation(
                startTime=_EARLY,
                endTime=_LATER,
                metricValueSets = [
                    messages.MetricValueSet(
                        metricName='other_floats',
                        metricValues=[
                            metric_value.create(
                                labels=_TEST_LABELS,
                                doubleValue=_A_FLOAT_VALUE,
                                endTime=_LATER_STILL
                            ),
                        ]
                    )
                ]

            ),
        ],
        'want': messages.Operation(
            startTime=_EARLY,
            endTime=_LATER,
            metricValueSets = [
                messages.MetricValueSet(
                    metricName='other_floats',
                    metricValues=[
                        metric_value.create(
                            labels=_TEST_LABELS,
                            doubleValue=_A_FLOAT_VALUE * 2,
                            endTime=_LATER_STILL
                        ),
                    ]
                ),
                messages.MetricValueSet(
                    metricName='some_floats',
                    metricValues=[
                        metric_value.create(
                            labels=_TEST_LABELS,
                            doubleValue=_A_FLOAT_VALUE,
                            endTime=_LATER
                        ),
                    ]
                )
            ]
        )
    }
]

class TestOperationAggregation(unittest2.TestCase):

    def test_should_aggregate_as_expected(self):
        for t in _TESTS:
            desc = t['description']
            initial = t['initial']
            want = t['want']
            agg = operation.Aggregator(initial, kinds=t['kinds'])
            for o in t['ops']:
                agg.add(o)
                got = agg.as_operation()
            try:
                expect(got).to(equal(want))
            except AssertionError as e:
                raise AssertionError('Failed to {0}\n{1}'.format(desc, e))
