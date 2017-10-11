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

from __future__ import absolute_import

import datetime
import httplib
import unittest2
import mock
from operator import attrgetter
from expects import be, be_none, be_true, be_false, equal, expect, raise_error

from apitools.base.py import encoding

from endpoints_management.control import caches, label_descriptor, timestamp
from endpoints_management.control import (quota_request, metric_value,
                                          sc_messages)


class TestSign(unittest2.TestCase):

    def setUp(self):
        op = sc_messages.QuotaOperation(
            consumerId=_TEST_CONSUMER_ID,
            methodName=_TEST_OP_NAME
        )
        self.test_quota_request = sc_messages.AllocateQuotaRequest(allocateOperation=op)
        self.test_op = op

    def test_should_fail_if_operation_is_not_set(self):
        testf = lambda: quota_request.sign(sc_messages.AllocateQuotaRequest())
        expect(testf).to(raise_error(ValueError))

    def test_should_fail_on_invalid_input(self):
        testf = lambda: quota_request.sign(None)
        expect(testf).to(raise_error(ValueError))
        testf = lambda: quota_request.sign(object())
        expect(testf).to(raise_error(ValueError))

    def test_should_fail_if_operation_has_no_method_name(self):
        op = sc_messages.QuotaOperation(consumerId=_TEST_CONSUMER_ID)
        testf = lambda: quota_request.sign(
            sc_messages.AllocateQuotaRequest(allocateOperation=op))
        expect(testf).to(raise_error(ValueError))

    def test_should_fail_if_operation_has_no_consumer_id(self):
        op = sc_messages.QuotaOperation(methodName=_TEST_OP_NAME)
        testf = lambda: quota_request.sign(
            sc_messages.AllocateQuotaRequest(allocateOperation=op))
        expect(testf).to(raise_error(ValueError))

    def test_should_sign_a_valid_quota_request(self):
        quota_request.sign(self.test_quota_request)

    def test_should_change_signature_when_labels_are_added(self):
        without_labels = quota_request.sign(self.test_quota_request)
        self.test_op.labels = encoding.PyValueToMessage(
            sc_messages.QuotaOperation.LabelsValue, {
                u'key1': u'value1',
                u'key2': u'value2'})
        with_labels = quota_request.sign(self.test_quota_request)
        expect(with_labels).not_to(equal(without_labels))

    def test_should_change_signature_when_metric_values_are_added(self):
        without_mvs = quota_request.sign(self.test_quota_request)
        self.test_op.quotaMetrics = [
            sc_messages.MetricValueSet(
                metricName=u'a_float',
                metricValues=[
                    metric_value.create(
                        labels={
                            u'key1': u'value1',
                            u'key2': u'value2'},
                        doubleValue=1.1,
                    ),
                ]
            )
        ]
        with_mvs = quota_request.sign(self.test_quota_request)
        expect(with_mvs).not_to(equal(without_mvs))


class TestAggregatorQuota(unittest2.TestCase):
    SERVICE_NAME = u'service.quota'
    FAKE_OPERATION_ID = u'service.general.quota'

    def setUp(self):
        self.timer = _DateTimeTimer()
        self.agg = quota_request.Aggregator(
            self.SERVICE_NAME, caches.QuotaOptions())

    def test_should_fail_if_req_is_bad(self):
        testf = lambda: self.agg.allocate_quota(object())
        expect(testf).to(raise_error(ValueError))
        testf = lambda: self.agg.allocate_quota(None)
        expect(testf).to(raise_error(ValueError))

    def test_should_fail_if_service_name_does_not_match(self):
        req = _make_test_request(self.SERVICE_NAME + u'-will-not-match')
        testf = lambda: self.agg.allocate_quota(req)
        expect(testf).to(raise_error(ValueError))

    def test_should_fail_if_quota_request_is_missing(self):
        req = sc_messages.ServicecontrolServicesAllocateQuotaRequest(
            serviceName=self.SERVICE_NAME)
        testf = lambda: self.agg.allocate_quota(req)
        expect(testf).to(raise_error(ValueError))

    def test_should_fail_if_operation_is_missing(self):
        req = sc_messages.ServicecontrolServicesAllocateQuotaRequest(
            serviceName=self.SERVICE_NAME,
            allocateQuotaRequest=sc_messages.AllocateQuotaRequest())
        testf = lambda: self.agg.allocate_quota(req)
        expect(testf).to(raise_error(ValueError))

    def test_should_return_none_initially_as_req_is_not_cached(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        fake_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        agg = self.agg
        actual = agg.allocate_quota(req)
        expect(actual).to(equal(fake_response))


class TestAggregatorThatCannotCache(unittest2.TestCase):
    SERVICE_NAME = u'service.no_cache'
    FAKE_OPERATION_ID = u'service.no_cache.op_id'

    def setUp(self):
        # -ve num_entries means no cache is present
        self.agg = quota_request.Aggregator(
            self.SERVICE_NAME,
            caches.QuotaOptions(num_entries=-1))

    def test_should_not_cache_responses(self):
        req = _make_test_request(self.SERVICE_NAME)
        fake_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        agg = self.agg
        expect(agg.allocate_quota(req)).to(be_none)
        agg.add_response(req, fake_response)
        expect(agg.allocate_quota(req)).to(be_none)
        agg.clear()
        expect(agg.allocate_quota(req)).to(be_none)

    def test_should_have_empty_flush_response(self):
        expect(len(self.agg.flush())).to(equal(0))

    def test_should_have_none_as_flush_interval(self):
        expect(self.agg.flush_interval).to(be_none)



class TestCachingAggregator(unittest2.TestCase):
    SERVICE_NAME = u'service.with_cache'
    FAKE_OPERATION_ID = u'service.with_cache.op_id'

    def setUp(self):
        self.timer = _DateTimeTimer()
        self.expiration = datetime.timedelta(seconds=2)
        self.flush_interval = datetime.timedelta(seconds=1)
        options = caches.QuotaOptions(
            flush_interval=self.flush_interval,
            expiration=self.expiration)
        self.agg = quota_request.Aggregator(
            self.SERVICE_NAME, options, timer=self.timer)

    def test_should_have_flush_interval_as_flush_interval(self):
        expect(self.agg.flush_interval).to(equal(self.flush_interval))

    def test_should_cache_responses(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        temp_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        real_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID,
            quotaMetrics=[sc_messages.MetricValueSet(
                metricName=u'a_float',
                metricValues=[
                    metric_value.create(
                        labels={
                            u'key1': u'value1',
                            u'key2': u'value2'},
                        doubleValue=1.1,
                    ),
                ]
            )]
        )
        agg = self.agg
        expect(agg.allocate_quota(req)).to(equal(temp_response))
        agg.add_response(req, real_response)
        expect(agg.allocate_quota(req)).to(equal(real_response))

    def test_should_update_temp_response_with_actual(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        temp_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        real_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID,
            quotaMetrics=[sc_messages.MetricValueSet(
                metricName=u'a_float',
                metricValues=[
                    metric_value.create(
                        labels={
                            u'key1': u'value1',
                            u'key2': u'value2'},
                        doubleValue=1.1,
                    ),
                ]
            )]
        )
        agg = self.agg
        agg.allocate_quota(req)
        signature = quota_request.sign(req.allocateQuotaRequest)
        with agg._cache as cache:
            item = cache[signature]
            expect(item.response).to(equal(temp_response))
            expect(item.is_in_flight).to(be_true)
            agg.add_response(req, real_response)
            item = cache[signature]
            expect(item.response).to(equal(real_response))
            expect(item.is_in_flight).to(be_false)

    def test_request_aggregation(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        signature = quota_request.sign(req.allocateQuotaRequest)
        agg = self.agg
        agg.allocate_quota(req)
        with agg._cache as cache:
            item = cache[signature]
            expect(item._op_aggregator).to(be_none)
        agg.allocate_quota(req)
        agg.allocate_quota(req)
        with agg._out as out:
            expect(len(out)).to(equal(1))
        with agg._cache as cache:
            item = cache[signature]
            expect(item._op_aggregator).not_to(be_none)

    def test_aggregated_requests_should_be_sent_on_flush(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        signature = quota_request.sign(req.allocateQuotaRequest)
        agg = self.agg
        agg.allocate_quota(req)
        expect(len(agg.flush())).to(equal(1))  # initial request
        simple_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        agg.add_response(req, simple_response)
        agg.allocate_quota(req)
        agg.allocate_quota(req)
        expect(len(agg.flush())).to(equal(1))  # aggregated next two requests

    def test_expiration(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        temp_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        real_response = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID,
            quotaMetrics=[sc_messages.MetricValueSet(
                metricName=u'a_float',
                metricValues=[
                    metric_value.create(
                        labels={
                            u'key1': u'value1',
                            u'key2': u'value2'},
                        doubleValue=1.1,
                    ),
                ]
            )]
        )
        agg = self.agg
        agg.allocate_quota(req)
        assert len(agg.flush()) == 1
        agg.add_response(req, real_response)
        signature = quota_request.sign(req.allocateQuotaRequest)
        with agg._cache as cache, agg._out as out:
            assert len(out) == 0
            assert signature in cache
            self.timer.tick()
            self.timer.tick()
            assert len(agg.flush()) == 0
            assert len(out) == 0
            assert signature in cache
            self.timer.tick()  # expired at 3rd second
            assert len(agg.flush()) == 0
            assert len(out) == 0
            assert signature not in cache


class TestCacheItem(unittest2.TestCase):
    SERVICE_NAME = u'service.quota'
    FAKE_OPERATION_ID = u'service.general.quota'

    def test_request_aggregation(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        req = req.allocateQuotaRequest
        resp = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        item = quota_request.CachedItem(req, resp, self.SERVICE_NAME, None)
        expect(item._op_aggregator).to(be_none)
        with mock.patch.object(quota_request, 'QuotaOperationAggregator') as QOA:
            agg = QOA.return_value
            item.aggregate(req)
            expect(item._op_aggregator).to(be(agg))
            QOA.assert_called_once_with(req.allocateOperation)
            item.aggregate(req)
            agg.merge_operation.assert_called_once_with(req.allocateOperation)

    def test_request_extraction_no_aggregation(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        a_req = req.allocateQuotaRequest
        resp = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        item = quota_request.CachedItem(a_req, resp, self.SERVICE_NAME, None)
        expect(item._op_aggregator).to(be_none)
        expect(item.extract_request()).to(equal(req))

    def test_request_extraction_with_aggregation(self):
        req = _make_test_request(self.SERVICE_NAME, self.FAKE_OPERATION_ID)
        req = req.allocateQuotaRequest
        req.allocateOperation.quotaMetrics = [
            sc_messages.MetricValueSet(
                metricName=u'a_float',
                metricValues=[
                    metric_value.create(
                        labels={
                            u'key1': u'value1',
                            u'key2': u'value2'},
                        int64Value=12,
                    ),
                ]
            )
        ]

        resp = sc_messages.AllocateQuotaResponse(
            operationId=self.FAKE_OPERATION_ID)
        item = quota_request.CachedItem(req, resp, self.SERVICE_NAME, None)
        expect(item._op_aggregator).to(be_none)
        item.aggregate(req)
        item.aggregate(req)

        extracted = item.extract_request()
        op = extracted.allocateQuotaRequest.allocateOperation
        expect(op.quotaMetrics[0].metricValues[0].int64Value).to(equal(24))


_TEST_CONSUMER_ID = u'testConsumerID'
_TEST_OP_NAME = u'testOperationName'


def _make_test_request(service_name, operation_id=None, importance=None):
    if importance is None:
        importance = sc_messages.Operation.ImportanceValueValuesEnum.LOW
    op = sc_messages.QuotaOperation(
        consumerId=_TEST_CONSUMER_ID,
        methodName=_TEST_OP_NAME,
        operationId=operation_id,
    )
    quota_request = sc_messages.AllocateQuotaRequest(allocateOperation=op)
    return sc_messages.ServicecontrolServicesAllocateQuotaRequest(
        serviceName=service_name,
        allocateQuotaRequest=quota_request)


_WANTED_USER_AGENT = label_descriptor.USER_AGENT
_WANTED_SERVICE_AGENT = label_descriptor.SERVICE_AGENT
_START_OF_EPOCH = timestamp.to_rfc3339(datetime.datetime(1970, 1, 1, 0, 0, 0))
_TEST_SERVICE_NAME = u'a_service_name'
_INFO_TESTS = [
    (quota_request.Info(
        operation_id=u'an_op_id',
        operation_name=u'an_op_name',
        referer=u'a_referer',
        service_name=_TEST_SERVICE_NAME),
     sc_messages.QuotaOperation(
         labels = encoding.PyValueToMessage(
             sc_messages.QuotaOperation.LabelsValue, {
                 u'servicecontrol.googleapis.com/referer': u'a_referer',
             }),
         operationId=u'an_op_id',
         methodName=u'an_op_name',
         quotaMode=sc_messages.QuotaOperation.QuotaModeValueValuesEnum.BEST_EFFORT)),
    (quota_request.Info(
        android_cert_fingerprint=u'an_android_cert_fingerprint',
        android_package_name=u'an_android_package_name',
        api_key=u'an_api_key',
        api_key_valid=True,
        ios_bundle_id=u'an_ios_bundle_id',
        operation_id=u'an_op_id',
        operation_name=u'an_op_name',
        referer=u'a_referer',
        service_name=_TEST_SERVICE_NAME),
     sc_messages.QuotaOperation(
         consumerId=u'api_key:an_api_key',
         labels = encoding.PyValueToMessage(
             sc_messages.QuotaOperation.LabelsValue, {
                 u'servicecontrol.googleapis.com/referer': u'a_referer',
             }),
         operationId=u'an_op_id',
         methodName=u'an_op_name',
         quotaMode=sc_messages.QuotaOperation.QuotaModeValueValuesEnum.BEST_EFFORT)),
    (quota_request.Info(
        api_key=u'an_api_key',
        api_key_valid=False,
        client_ip=u'127.0.0.1',
        consumer_project_id=u'project_id',
        operation_id=u'an_op_id',
        operation_name=u'an_op_name',
        referer=u'a_referer',
        service_name=_TEST_SERVICE_NAME),
     sc_messages.QuotaOperation(
         consumerId=u'project:project_id',
         labels = encoding.PyValueToMessage(
             sc_messages.QuotaOperation.LabelsValue, {
                 u'servicecontrol.googleapis.com/caller_ip': u'127.0.0.1',
                 u'servicecontrol.googleapis.com/referer': u'a_referer',
             }),
         operationId=u'an_op_id',
         methodName=u'an_op_name',
         quotaMode=sc_messages.QuotaOperation.QuotaModeValueValuesEnum.BEST_EFFORT)),
]
_INCOMPLETE_INFO_TESTS = [
    quota_request.Info(
        operation_name=u'an_op_name',
        service_name=_TEST_SERVICE_NAME),
    quota_request.Info(
        operation_id=u'an_op_id',
        service_name=_TEST_SERVICE_NAME),
    quota_request.Info(
        operation_id=u'an_op_id',
        operation_name=u'an_op_name')
]

KEYGETTER = attrgetter(u'key')


class TestInfo(unittest2.TestCase):
    def test_should_construct_with_no_args(self):
        expect(quota_request.Info()).not_to(be_none)

    def test_should_convert_using_as_quota_request(self):
        timer = _DateTimeTimer()
        for info, want in _INFO_TESTS:
            got = info.as_allocate_quota_request(timer=timer)
            # These additional properties have no well-defined order, so sort them.
            got.allocateQuotaRequest.allocateOperation.labels.additionalProperties.sort(key=KEYGETTER)
            want.labels.additionalProperties.sort(key=KEYGETTER)
            expect(got.allocateQuotaRequest.allocateOperation).to(equal(want))
            expect(got.serviceName).to(equal(_TEST_SERVICE_NAME))

    def test_should_fail_as_quota_request_on_incomplete_info(self):
        timer = _DateTimeTimer()
        for info in _INCOMPLETE_INFO_TESTS:
            testf = lambda: info.as_allocate_quota_request(timer=timer)
            expect(testf).to(raise_error(ValueError))


class TestConvertResponse(unittest2.TestCase):
    PROJECT_ID = u'test_convert_response'

    def test_should_be_ok_with_no_errors(self):
        code, message = quota_request.convert_response(
            sc_messages.AllocateQuotaResponse(), self.PROJECT_ID)
        expect(code).to(equal(httplib.OK))
        expect(message).to(equal(u''))

    def test_should_include_project_id_in_error_text_when_needed(self):
        resp = sc_messages.AllocateQuotaResponse(
            allocateErrors = [
                sc_messages.QuotaError(
                    code=sc_messages.QuotaError.CodeValueValuesEnum.PROJECT_DELETED)
            ]
        )
        code, got = quota_request.convert_response(resp, self.PROJECT_ID)
        want = u'Project %s has been deleted' % (self.PROJECT_ID,)
        expect(code).to(equal(httplib.FORBIDDEN))
        expect(got).to(equal(want))

    def test_should_include_detail_in_error_text_when_needed(self):
        detail = u'details, details, details'
        resp = sc_messages.AllocateQuotaResponse(
            allocateErrors = [
                sc_messages.QuotaError(
                    code=sc_messages.QuotaError.CodeValueValuesEnum.OUT_OF_RANGE,
                    description=detail)
            ]
        )
        code, got = quota_request.convert_response(resp, self.PROJECT_ID)
        expect(code).to(equal(httplib.INTERNAL_SERVER_ERROR))
        assert got.endswith(detail)


class _DateTimeTimer(object):
    def __init__(self, auto=False):
        self.auto = auto
        self.time = datetime.datetime.utcfromtimestamp(0)

    def __call__(self):
        if self.auto:
            self.tick()
        return self.time

    def tick(self):
        self.time += datetime.timedelta(seconds=1)
