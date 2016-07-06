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

"""report_request supports aggregation of ReportRequests.

It proves :class:`.Aggregator` that aggregates and batches together
ReportRequests.

"""


from __future__ import absolute_import

import collections
import functools
import hashlib
import logging
from datetime import datetime, timedelta

import google.apigen.servicecontrol_v1_messages as messages
from apitools.base.py import encoding
from enum import Enum
from .. import caches, signing
from . import operation

logger = logging.getLogger(__name__)


_UNSET_SIZE = -1


def _validate_int_arg(name, value):
    if value == _UNSET_SIZE or (isinstance(value, int) and value > 0):
        return
    raise ValueError('%s should be a positive int/long' % (name,))


def _validate_timedelta_arg(name, value):
    if value is None or isinstance(value, timedelta):
        return
    raise ValueError('%s should be a timedelta' % (name,))


class ReportedProtocols(Enum):
    """Enumerates the protocols that might be reported in a call to report."""
    # pylint: disable=too-few-public-methods
    UNKNOWN = 0
    HTTP = 1
    HTTP2 = 2
    GRPC = 3


class ReportedPlatforms(Enum):
    """Enumerates the platforms that might be reported in a call to report."""
    # pylint: disable=too-few-public-methods
    UNKNOWN = 0
    GAE = 1
    GCE = 2
    GKE = 3


class Info(
        collections.namedtuple(
            'Info', (
                'api_name',
                'api_method',
                'api_version',
                'auth_issuer',
                'auth_audience',
                'backend_time',
                'location',
                'log_message',
                'method',
                'overhead_time',
                'platform',
                'protocol',
                'request_size',
                'request_time',
                'response_code',
                'response_size',
                'url',
            ) + operation.Info._fields),
        operation.Info):
    """Holds the information necessary to fill in a ReportRequest.

    In the attribute descriptions below, N/A means 'not available'

    Attributes:
       api_name (string): the api name and version
       api_method (string): the full api method name
       api_version (string): the api version
       auth_issuer (string): the auth issuer
       auth_audience (string): the auth audience
       backend_time(datetime.timedelta): the backend request time, None for N/A
       location (string): the location of the service
       log_message (string): a message to log as an info log
       method (string): the HTTP method used to make the request
       overhead_time(datetime.timedelta): the overhead time, None for N/A
       request_size(int): the request size in bytes, -1 means N/A
       request_time(datetime.timedelta): the request time
       response_size(int): the request size in bytes, -1 means N/A
       response_code(int): the code of the http response
       url (string): the request url

    """
    # pylint: disable=too-many-arguments,too-many-locals

    def __new__(cls,
                api_name='',
                api_method='',
                api_version='',
                auth_issuer='',
                auth_audience='',
                backend_time=None,
                location='',
                log_message='',
                method='',
                platform=ReportedPlatforms.UNKNOWN,
                protocol=ReportedProtocols.UNKNOWN,
                overhead_time=None,
                request_size=_UNSET_SIZE,
                request_time=None,
                response_size=_UNSET_SIZE,
                response_code=200,
                url='',
                **kw):
        """Invokes the base constructor with default values."""
        op_info = operation.Info(**kw)
        _validate_timedelta_arg('backend_time', backend_time)
        _validate_timedelta_arg('overhead_time', overhead_time)
        _validate_timedelta_arg('request_time', request_time)
        _validate_int_arg('request_size', request_size)
        _validate_int_arg('response_size', response_size)
        if not isinstance(protocol, ReportedProtocols):
            raise ValueError('protocol should be a %s' % (ReportedProtocols,))
        if not isinstance(platform, ReportedPlatforms):
            raise ValueError('platform should be a %s' % (ReportedPlatforms,))
        return super(cls, Info).__new__(
            cls,
            api_name,
            api_method,
            api_version,
            auth_issuer,
            auth_audience,
            backend_time,
            location,
            log_message,
            method,
            overhead_time,
            platform,
            protocol,
            request_size,
            request_time,
            response_code,
            response_size,
            url,
            **op_info._asdict())


class Aggregator(object):
    """Aggregates Service Control Report requests.

    :func:`report` determines if a `ReportRequest` should be sent to the
    service immediately

    """

    CACHED_OK = object()
    """A sential returned by :func:`report` when a request is cached OK."""

    MAX_OPERATION_COUNT = 1000
    """The maximum number of operations to send in a report request."""

    def __init__(self, service_name, options, kinds=None, timer=datetime.now):
        """
        Constructor

        Args:
          service_name (string): name of the service being aggregagated
          options (:class:`.ReportAggregationOptions`): configures the behavior
            of this aggregator
          kinds (dict[string, [:class:`.MetricKind`]]): describes the
            type of metrics used during aggregation
          timer (function([[datetime]]): a function that returns the current
            as a time as a datetime instance

        """
        self._cache = caches.create(options, timer=timer)
        self._options = options
        self._kinds = kinds
        self._service_name = service_name

    @property
    def flush_interval(self):
        """The interval between calls to flush.

        Returns:
           timedelta: the period between calls to flush if, or ``None`` if no
           cache is set

        """
        return None if self._cache is None else self._options.flush_interval

    @property
    def service_name(self):
        """The service to which all requests being aggregated should belong."""
        return self._service_name

    def flush(self):
        """Flushes this instance's cache.

        The driver of this instance should call this method every
        `flush_interval`.

        Returns:
          list[``ServicecontrolServicesReportRequest``]: corresponding to the
            pending cached operations

        """
        if self._cache is None:
            return []
        with self._cache as c:
            flushed_ops = [x.as_operation() for x in list(c.out_deque)]
            c.out_deque.clear()
            reqs = []
            max_ops = self.MAX_OPERATION_COUNT
            for x in range(0, len(flushed_ops), max_ops):
                report_request = messages.ReportRequest(
                    operations=flushed_ops[x:x + max_ops])
                reqs.append(
                    messages.ServicecontrolServicesReportRequest(
                        serviceName=self.service_name,
                        reportRequest=report_request))

            return reqs

    def clear(self):
        """Clears the cache."""
        if self._cache is not None:
            with self._cache as k:
                k.clear()
                k.out_deque.clear()

    def report(self, req):
        """Adds a report request to the cache.

        Returns ``None`` if it could not be aggregated, and callers need to
        send the request to the server, otherwise it returns ``CACHED_OK``.

        Args:
           req (:class:`messages.ReportRequest`): the request
             to be aggregated

        Result:
           ``None`` if the request as not cached, otherwise ``CACHED_OK``

        """
        if self._cache is None:
            return None  # no cache, send request now
        if not isinstance(req, messages.ServicecontrolServicesReportRequest):
            raise ValueError('Invalid request')
        if req.serviceName != self.service_name:
            logger.error('bad report(): service_name %s does not match ours %s',
                         req.serviceName, self.service_name)
            raise ValueError('Service name mismatch')
        report_req = req.reportRequest
        if report_req is None:
            logger.error('bad report(): no report_request in %s', req)
            raise ValueError('Expected report_request not set')
        if _has_high_important_operation(report_req) or self._cache is None:
            return None
        ops_by_signature = _key_by_signature(report_req.operations,
                                             _sign_operation)

        # Concurrency:
        #
        # This holds a lock on the cache while updating it.  No i/o operations
        # are performed, so any waiting threads see minimal delays
        with self._cache as cache:
            for key, op in iter(ops_by_signature.items()):
                agg = cache.get(key)
                if agg is None:
                    cache[key] = operation.Aggregator(op, self._kinds)
                else:
                    agg.add(op)

        return self.CACHED_OK


def _has_high_important_operation(req):
    def is_important(op):
        return (op.importance !=
                messages.Operation.ImportanceValueValuesEnum.LOW)

    return functools.reduce(lambda x, y: x and is_important(y),
                            req.operations, True)


def _key_by_signature(operations, signature_func):
    """Creates a dictionary of operations keyed by signature

    Args:
      operations (iterable[Operations]): the input operations

    Returns:
       dict[string, [Operations]]: the operations keyed by signature
    """
    return dict((signature_func(op), op) for op in operations)


def _sign_operation(op):
    """Obtains a signature for an operation in a ReportRequest.

    Args:
       op (:class:`google.apigen.servicecontrol_v1_messages.Operation`): an
         operation used in a `ReportRequest`

    Returns:
       string: a unique signature for that operation
    """
    md5 = hashlib.md5()
    md5.update(op.consumerId)
    md5.update('\x00')
    md5.update(op.operationName)
    if op.labels:
        signing.add_dict_to_hash(md5, encoding.MessageToPyValue(op.labels))
    return md5.digest()
