# Copyright 2017 Google Inc. All Rights Reserved.
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

"""quota_request supports aggregation of AllocateQuotaRequests.

:func:`sign` generated a signature from AllocateQuotaRequests
:class:`~endpoints_management.gen.servicecontrol_v1_message.QuotaOperation` represents
information regarding an operation, and is a key constituent of
:class:`~endpoints_management.gen.servicecontrol_v1_message.AllocateQuotaRequest`.

The :class:`.Aggregator` implements the strategy for aggregating AllocateQuotaRequests
and caching their responses.

"""

from __future__ import absolute_import

import collections
import copy
import hashlib
import httplib
import logging
from datetime import datetime

from apitools.base.py import encoding

from . import (caches, label_descriptor, metric_value, operation, sc_messages,
               signing)
from .. import USER_AGENT, SERVICE_AGENT

logger = logging.getLogger(__name__)

# alias for brevity
_QuotaErrors = sc_messages.QuotaError.CodeValueValuesEnum
_IS_OK = (httplib.OK, u'')
_IS_UNKNOWN = (
    httplib.INTERNAL_SERVER_ERROR,
    u'Request blocked due to unsupported block reason {detail}')
_QUOTA_ERROR_CONVERSION = {
    _QuotaErrors.RESOURCE_EXHAUSTED: (
        429,
        'Quota allocation failed',
    ),
    _QuotaErrors.BILLING_NOT_ACTIVE: (
        httplib.FORBIDDEN,
        u'Project {project_id} has billing disabled. Please enable it',
    ),
    _QuotaErrors.PROJECT_DELETED: (
        httplib.FORBIDDEN,
        u'Project {project_id} has been deleted',
    ),
    _QuotaErrors.API_KEY_INVALID: (
        httplib.BAD_REQUEST,
        u'API not valid. Please pass a valid API key',
    ),
    _QuotaErrors.API_KEY_EXPIRED: (
        httplib.BAD_REQUEST,
        u'API key expired. Please renew the API key',
    ),


    # Fail open for internal server errors
    _QuotaErrors.UNSPECIFIED: _IS_OK,
    _QuotaErrors.PROJECT_STATUS_UNAVAILABLE: _IS_OK,
    _QuotaErrors.SERVICE_STATUS_UNAVAILABLE: _IS_OK,
    _QuotaErrors.BILLING_STATUS_UNAVAILABLE: _IS_OK,
    _QuotaErrors.QUOTA_SYSTEM_UNAVAILABLE: _IS_OK,
}


def convert_response(allocate_quota_response, project_id):
    """Computes a http status code and message `AllocateQuotaResponse`

    The return value a tuple (code, message) where

    code: is the http status code
    message: is the message to return

    Args:
       allocate_quota_response (:class:`endpoints_management.gen.servicecontrol_v1_messages.AllocateQuotaResponse`):
         the response from calling an api

    Returns:
       tuple(code, message)
    """
    if not allocate_quota_response or not allocate_quota_response.allocateErrors:
        return _IS_OK

    # only allocate_quota the first error for now, as per ESP
    theError = allocate_quota_response.allocateErrors[0]
    error_tuple = _QUOTA_ERROR_CONVERSION.get(theError.code, _IS_UNKNOWN)
    if error_tuple[1].find(u'{') == -1:  # no replacements needed:
        return error_tuple

    updated_msg = error_tuple[1].format(project_id=project_id, detail=theError.description or u'')
    return error_tuple[0], updated_msg


def sign(allocate_quota_request):
    """Obtains a signature for an operation in a `AllocateQuotaRequest`

    Args:
       op (:class:`endpoints_management.gen.servicecontrol_v1_messages.Operation`): an
         operation used in a `AllocateQuotaRequest`

    Returns:
       string: a secure hash generated from the operation
    """
    if not isinstance(allocate_quota_request, sc_messages.AllocateQuotaRequest):
        raise ValueError(u'Invalid request')
    op = allocate_quota_request.allocateOperation
    if op is None or op.methodName is None or op.consumerId is None:
        logging.error(u'Bad %s: not initialized => not signed', allocate_quota_request)
        raise ValueError(u'allocate_quota request must be initialized with an operation')
    md5 = hashlib.md5()
    md5.update(op.methodName.encode('utf-8'))
    md5.update(b'\x00')
    md5.update(op.consumerId.encode('utf-8'))
    if op.labels:
        signing.add_dict_to_hash(md5, encoding.MessageToPyValue(op.labels))
    for value_set in op.quotaMetrics:
        md5.update(b'\x00')
        md5.update(value_set.metricName.encode('utf-8'))
        for mv in value_set.metricValues:
            metric_value.update_hash(md5, mv)

    md5.update(b'\x00')
    return md5.digest()


_KNOWN_LABELS = label_descriptor.KnownLabels


_INFO_FIELDS = (u'client_ip', u'quota_info', u'config_id') + operation.Info._fields


class Info(collections.namedtuple(u'Info', _INFO_FIELDS), operation.Info):
    """Holds the information necessary to fill in QuotaRequest.

    In addition the attributes in :class:`operation.Info`, this has:

    Attributes:
       client_ip: the client IP address
       quota_info: the quota info from the method

    """
    def __new__(cls, client_ip=u'', quota_info=None, config_id=None, **kw):
        """Invokes the base constructor with default values."""
        op_info = operation.Info(**kw)
        return super(Info, cls).__new__(cls, client_ip, quota_info, config_id, **op_info._asdict())

    def as_allocate_quota_request(self, timer=datetime.utcnow):
        """Makes a `ServicecontrolServicesAllocateQuotaRequest` from this instance

        Returns:
          a ``ServicecontrolServicesAllocateQuotaRequest``

        Raises:
          ValueError: if the fields in this instance are insufficient to
            to create a valid ``ServicecontrolServicesAllocateQuotaRequest``

        """
        if not self.service_name:
            raise ValueError(u'the service name must be set')
        if not self.operation_id:
            raise ValueError(u'the operation id must be set')
        if not self.operation_name:
            raise ValueError(u'the operation name must be set')
        op = super(Info, self).as_operation(timer=timer)
        labels = {}
        if self.client_ip:
            labels[_KNOWN_LABELS.SCC_CALLER_IP.label_name] = self.client_ip

        if self.referer:
            labels[_KNOWN_LABELS.SCC_REFERER.label_name] = self.referer

        qop = sc_messages.QuotaOperation(
            operationId=op.operationId,
            methodName=op.operationName,
            consumerId=op.consumerId,
            quotaMode=sc_messages.QuotaOperation.QuotaModeValueValuesEnum.BEST_EFFORT,
        )
        qop.labels = encoding.PyValueToMessage(
            sc_messages.QuotaOperation.LabelsValue, labels)

        quota_info = self.quota_info if self.quota_info else {}
        qop.quotaMetrics = [
            sc_messages.MetricValueSet(
                metricName=name, metricValues=[sc_messages.MetricValue(int64Value=cost)])
            for name, cost in quota_info.items()
        ]

        allocate_quota_request = sc_messages.AllocateQuotaRequest(allocateOperation=qop)
        if self.config_id:
            allocate_quota_request.serviceConfigId = self.config_id
        return sc_messages.ServicecontrolServicesAllocateQuotaRequest(
            serviceName=self.service_name,
            allocateQuotaRequest=allocate_quota_request)


class Aggregator(object):
    """Caches and aggregates ``AllocateQuotaRequests``.

    Concurrency: Thread safe.

    """

    def __init__(self, service_name, options, kinds=None,
                 timer=datetime.utcnow):
        """Constructor.

        Args:
          service_name (string): names the service that all requests aggregated
            by this instance will be sent
          options (:class:`~endpoints_management.caches.QuotaOptions`): configures the
            caching and flushing behavior of this instance
          kinds (dict[string,[endpoints_management.control.MetricKind]]): specifies the
            kind of metric for each each metric name.
          timer (function([[datetime]]): a function that returns the current
            as a time as a datetime instance
        """
        self._service_name = service_name
        self._options = options
        self._cache = caches.create(options, timer=timer, use_deque=False)
        # When using the result of `with self._out as out`, you must disable no-member
        # in pyflakes. Known issue with no fix ETA:
        # https://github.com/PyCQA/astroid/issues/347
        # https://github.com/PyCQA/pylint/issues/1437
        self._out = caches.LockedObject(collections.deque())
        self._kinds = {} if kinds is None else dict(kinds)
        self._timer = timer
        self._in_flush_all = False

    @property
    def service_name(self):
        """The service to which all aggregated requests should belong."""
        return self._service_name

    @property
    def flush_interval(self):
        """The interval between calls to flush.

        Returns:
           timedelta: the period between calls to flush if, or ``None`` if no
           cache is set

        """
        return None if self._cache is None else self._options.flush_interval

    def flush(self):
        """Flushes this instance's cache.

        The driver of this instance should call this method every
        `flush_interval`.

        Returns:
          list['ServicecontrolServicesAllocateQuotaRequest']: corresponding
          to AllocateQuotaRequests that were pending

        """
        if self._cache is None:
            return []
        with self._cache as c, self._out as out:
            c.expire()
            now = self._timer()
            for item in c.values():
                if (not self._in_flush_all) and (not self._should_expire(item)):
                    if (not item.is_in_flight) and item._op_aggregator is not None:
                        item.is_in_flight = True
                        item.last_refresh_timestamp = now
                        out.append(item.extract_request())  # pylint: disable=no-member
            flushed_items = list(out)
            out.clear()  # pylint: disable=no-member
            for req in flushed_items:
                assert isinstance(req, sc_messages.ServicecontrolServicesAllocateQuotaRequest)
            return flushed_items

    def clear(self):
        """Clears this instance's cache."""
        if self._cache is not None:
            with self._cache as c, self._out as out:
                self.in_flush_all = True
                c.clear()
                out.clear()  # pylint: disable=no-member
                self.in_flush_all = False

    def add_response(self, req, resp):
        """Adds the response from sending to `req` to this instance's cache.

        Args:
          req (`ServicecontrolServicesAllocateQuotaRequest`): the request
          resp (AllocateQuotaResponse): the response from sending the request
        """
        if self._cache is None:
            return
        signature = sign(req.allocateQuotaRequest)
        with self._cache as c:
            now = self._timer()
            item = c.get(signature)
            if item is None:
                c[signature] = CachedItem(
                    req, resp, self.service_name, now)
            else:
                # Update the cached item to reflect that it is updated
                item.last_check_time = now
                item.response = resp
                item.is_in_flight = False
                c[signature] = item

    def allocate_quota(self, req):
        if self._cache is None:
            return None  # no cache, send request now
        if not isinstance(req, sc_messages.ServicecontrolServicesAllocateQuotaRequest):
            raise ValueError(u'Invalid request')
        if req.serviceName != self.service_name:
            logger.error(u'bad allocate_quota(): service_name %s does not match ours %s',
                         req.serviceName, self.service_name)
            raise ValueError(u'Service name mismatch')
        allocate_quota_request = req.allocateQuotaRequest
        if allocate_quota_request is None:
            logger.error(u'bad allocate_quota(): no allocate_quota_request in %s', req)
            raise ValueError(u'Expected operation not set')
        op = allocate_quota_request.allocateOperation
        if op is None:
            logger.error(u'bad allocate_quota(): no operation in %s', req)
            raise ValueError(u'Expected operation not set')

        signature = sign(allocate_quota_request)
        with self._cache as cache, self._out as out:
            now = self._timer()
            logger.debug(u'checking the cache for %r\n%s', signature, cache)
            item = cache.get(signature)
            if item is None:
                # to avoid sending concurrent allocate_quota from
                # concurrent requests, insert a temporary positive
                # response in the cache. Quota requests from other API
                # requests will be aggregated to this temporary
                # element until the response for the actual request
                # arrives.
                temp_response = sc_messages.AllocateQuotaResponse(operationId=op.operationId)
                item = CachedItem(allocate_quota_request, temp_response, self.service_name, now)
                item.signature = signature
                item.is_in_flight = True
                cache[signature] = item
                out.append(req)  # pylint: disable=no-member
                return temp_response  # positive response
            if not item.is_in_flight and self._should_refresh(item):
                item.is_in_flight = True
                item.last_refreshed_timestamp = now

                refresh_request = item.extract_request()
                if not item.is_positive_response():
                    # if the cached response is negative, then use NORMAL QuotaMode instead of BEST_EFFORT
                    normal = sc_messages.QuotaOperation.QuotaModeValueValuesEnum.NORMAL
                    refresh_request.allocateQuotaRequest.allocateOperation.quotaMode = normal
                out.append(refresh_request)  # pylint: disable=no-member
            if item.is_positive_response():
                item.aggregate(allocate_quota_request)
            return item.response

    def _should_refresh(self, item):
        age = self._timer() - item.last_check_time
        return age >= self._options.flush_interval

    def _should_expire(self, item):
        age = self._timer() - item.last_check_time
        return age >= self._options.expiration


class CachedItem(object):
    """CachedItem holds items cached along with a ``AllocateQuotaRequest``.

    Thread compatible.

    Attributes:
       response (:class:`sc_messages.CachedResponse`): the cached response
       is_flushing (bool): indicates if it's been detected that item
         is stale, and needs to be flushed
       quota_scale (int): WIP, used to determine quota
       last_check_time (datetime.datetime): the last time this instance
         was checked

    """

    def __init__(self, req, resp, service_name, last_check_time):
        assert isinstance(req, sc_messages.AllocateQuotaRequest)
        self.request = req
        self.response = resp
        self.last_check_time = last_check_time
        self.is_in_flight = False
        self._service_name = service_name
        self._op_aggregator = None

    def aggregate(self, req):
        assert isinstance(req, sc_messages.AllocateQuotaRequest)
        if self._op_aggregator is None:
            # This is correct behavior; we have no need to aggregate the req
            # from the constructor since it has already been sent.
            self._op_aggregator = QuotaOperationAggregator(req.allocateOperation)
        else:
            self._op_aggregator.merge_operation(req.allocateOperation)

    def extract_request(self):
        if self._op_aggregator is None:
            allocate_quota_request = self.request
        else:
            op = self._op_aggregator.as_quota_operation()
            self._op_aggregator = None
            allocate_quota_request = sc_messages.AllocateQuotaRequest(allocateOperation=op)
        return sc_messages.ServicecontrolServicesAllocateQuotaRequest(
            serviceName=self._service_name,
            allocateQuotaRequest=allocate_quota_request)

    def is_positive_response(self):
        return len(self.response.allocateErrors) == 0


class QuotaOperationAggregator(object):
    def __init__(self, op):
        # The protorpc version used here lacks MergeFrom
        self.op = copy.deepcopy(op)
        self.op.quotaMetrics = []
        self.metric_value_sets = {}
        self.merge_operation(op)

    def merge_operation(self, op):
        assert isinstance(op, sc_messages.QuotaOperation)
        for mv_set in op.quotaMetrics:
            metric_name = mv_set.metricName
            if metric_name not in self.metric_value_sets:
                self.metric_value_sets[metric_name] = mv_set.metricValues[0]
            else:
                self.metric_value_sets[metric_name] = metric_value.merge(
                    metric_value.MetricKind.DELTA,
                    self.metric_value_sets[metric_name],
                    mv_set.metricValues[0]
                )

    def as_quota_operation(self):
        op = copy.deepcopy(self.op)
        for m_name, m_value in self.metric_value_sets.items():
            op.quotaMetrics.append(sc_messages.MetricValueSet(
                metricName=m_name, metricValues=[m_value]))
        return op
