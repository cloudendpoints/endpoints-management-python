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
from expects import be_none, equal, expect, raise_error

from apitools.base.py import encoding

import google.apigen.servicecontrol_v1_messages as messages
from google.scc import ReportAggregationOptions
from google.scc.aggregators import report_request, metric_value


_TEST_CONSUMER_ID = 'testConsumerID'
_TEST_OP1_NAME = 'testOp1'
_TEST_OP2_NAME = 'testOp2'


class TestInfo(unittest2.TestCase):

    def test_should_construct_with_no_args(self):
        expect(report_request.Info()).not_to(be_none)

    def test_should_raise_if_constructed_with_a_bad_protocol(self):
        testf = lambda: report_request.Info(protocol=object())
        # not a report_request.ReportedProtocols
        expect(testf).to(raise_error(ValueError))

    def test_should_raise_if_constructed_with_a_bad_platform(self):
        testf = lambda: report_request.Info(platform=object())
        expect(testf).to(raise_error(ValueError))

    def test_should_raise_if_constructed_with_a_bad_request_size(self):
        testf = lambda: report_request.Info(request_size=object())
        expect(testf).to(raise_error(ValueError))
        testf = lambda: report_request.Info(request_size=-2)
        expect(testf).to(raise_error(ValueError))

    def test_should_raise_if_constructed_with_a_bad_response_size(self):
        testf = lambda: report_request.Info(response_size=object())
        expect(testf).to(raise_error(ValueError))
        testf = lambda: report_request.Info(response_size=-2)
        expect(testf).to(raise_error(ValueError))

    def test_should_raise_if_constructed_with_a_bad_backend_time(self):
        testf = lambda: report_request.Info(backend_time=object())
        expect(testf).to(raise_error(ValueError))

    def test_should_raise_if_constructed_with_a_bad_overhead_time(self):
        testf = lambda: report_request.Info(overhead_time=object())
        expect(testf).to(raise_error(ValueError))

    def test_should_raise_if_constructed_with_a_bad_request_time(self):
        testf = lambda: report_request.Info(request_time=object())
        expect(testf).to(raise_error(ValueError))



class TestAggregatorReport(unittest2.TestCase):
    SERVICE_NAME = 'service.report'

    def setUp(self):
        self.timer = _DateTimeTimer()
        self.agg = report_request.Aggregator(
            self.SERVICE_NAME, ReportAggregationOptions())

    def test_should_fail_if_req_is_bad(self):
        testf = lambda: self.agg.report(object())
        expect(testf).to(raise_error(ValueError))
        testf = lambda: self.agg.report(None)
        expect(testf).to(raise_error(ValueError))

    def test_should_fail_if_service_name_does_not_match(self):
        req = _make_test_request(self.SERVICE_NAME + '-will-not-match')
        testf = lambda: self.agg.report(req)
        expect(testf).to(raise_error(ValueError))

    def test_should_fail_if_check_request_is_missing(self):
        req = messages.ServicecontrolServicesReportRequest(
            serviceName=self.SERVICE_NAME)
        testf = lambda: self.agg.report(req)
        expect(testf).to(raise_error(ValueError))


class TestAggregatorTheCannotCache(unittest2.TestCase):
    SERVICE_NAME = 'service.no_cache'

    def setUp(self):
        # -ve num_entries means no cache is present
        self.agg = report_request.Aggregator(
            self.SERVICE_NAME,
            ReportAggregationOptions(num_entries=-1))

    def test_should_not_cache_responses(self):
        req = _make_test_request(self.SERVICE_NAME)
        expect(self.agg.report(req)).to(be_none)

    def test_should_have_empty_flush_response(self):
        expect(len(self.agg.flush())).to(equal(0))

    def test_should_have_none_as_flush_interval(self):
        expect(self.agg.flush_interval).to(be_none)


class TestCachingAggregator(unittest2.TestCase):
    SERVICE_NAME = 'service.with_cache'

    def setUp(self):
        self.timer = _DateTimeTimer()
        self.flush_interval = datetime.timedelta(seconds=1)
        options = ReportAggregationOptions(flush_interval=self.flush_interval)
        self.agg = report_request.Aggregator(
            self.SERVICE_NAME, options, timer=self.timer)

    def test_should_have_option_flush_interval_as_the_flush_interval(self):
        expect(self.agg.flush_interval).to(equal(self.flush_interval))

    def test_should_not_cache_requests_with_important_operations(self):
        req = _make_test_request(
            self.SERVICE_NAME,
            importance=messages.Operation.ImportanceValueValuesEnum.HIGH)
        agg = self.agg
        expect(agg.report(req)).to(be_none)

    def test_should_cache_requests_and_return_cached_ok(self):
        req = _make_test_request(self.SERVICE_NAME, n=2, start=0)
        agg = self.agg
        expect(agg.report(req)).to(equal(report_request.Aggregator.CACHED_OK))

    def test_should_cache_requests_and_batch_them_on_flush(self):
        req1 = _make_test_request(self.SERVICE_NAME, n=2, start=0)
        req2 = _make_test_request(self.SERVICE_NAME, n=2, start=2)

        agg = self.agg
        expect(agg.report(req1)).to(equal(report_request.Aggregator.CACHED_OK))
        expect(agg.report(req2)).to(equal(report_request.Aggregator.CACHED_OK))
        # no immediate requests for flush
        flushed_reqs = agg.flush()
        expect(len(flushed_reqs)).to(equal(0))

        self.timer.tick() # time passes ...
        self.timer.tick() # ... and is now past the flush_interval
        flushed_reqs = agg.flush()
        expect(len(flushed_reqs)).to(equal(1))
        flushed_ops = flushed_reqs[0].report_request.operations
        expect(len(flushed_ops)).to(equal(4)) # number of ops in the req{1,2}

    def test_should_aggregate_operations_in_requests(self):
        n = 261 # arbitrary
        agg = self.agg
        for _ in range(n):
            # many requests, but only two ops
            req = _make_test_request(self.SERVICE_NAME, n=2, start=0)
            expect(agg.report(req)).to(
                equal(report_request.Aggregator.CACHED_OK))

        # time passes ...
        self.timer.tick()
        self.timer.tick() # ... and is now past the flush_interval
        flushed_reqs = agg.flush()
        expect(len(flushed_reqs)).to(equal(1))
        flushed_ops = flushed_reqs[0].report_request.operations
        expect(len(flushed_ops)).to(equal(2)) # many requests, but only two ops

    def test_may_clear_aggregated_operations(self):
        n = 261 # arbitrary
        agg = self.agg
        for i in range(n):
            # many requests, but only two ops
            req = _make_test_request(self.SERVICE_NAME, n=2, start=0)
            expect(agg.report(req)).to(
                equal(report_request.Aggregator.CACHED_OK))

        # time passes ...
        agg.clear()  # the aggregator is cleared
        self.timer.tick()
        self.timer.tick() # ... and is now past the flush_interval
        flushed_reqs = agg.flush()
        expect(len(flushed_reqs)).to(equal(0))  # but there is nothing


class _DateTimeTimer(object):
    def __init__(self, auto=False):
        self.auto = auto
        self.time = datetime.datetime(1970, 1, 1)

    def __call__(self):
        if self.auto:
            self.tick()
        return self.time

    def tick(self):
        self.time += datetime.timedelta(seconds=1)


def _make_op_names(n, start=0):
    return ('testOp%d' % (x,) for x in range(start, start + n))


def _make_test_request(service_name, importance=None, n=3, start=0):
    if importance is None:
        importance = messages.Operation.ImportanceValueValuesEnum.LOW
    op_names = _make_op_names(n, start=start)
    ops = [messages.Operation(consumerId=_TEST_CONSUMER_ID,
                              operationName=op_name,
                              importance=importance) for op_name in op_names]
    if ops:
        ops[0].labels = encoding.PyValueToMessage(
            messages.Operation.LabelsValue, {
                'key1': 'always add a label to the first op'
            })
    report_request = messages.ReportRequest(operations=ops)
    return messages.ServicecontrolServicesReportRequest(
        serviceName=service_name,
        report_request=report_request)
