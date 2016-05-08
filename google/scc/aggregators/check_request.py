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

"""check_request supports aggregation of CheckRequests.

:func:`sign` generated a signature from CheckRequests
:class:`~google.apigen.servicecontrol_v1_message.Operation` represents
information regarding an operation, and is a key constituent of
:class:`~google.apigen.servicecontrol_v1_message.CheckRequest` and
:class:`~google.apigen.servicecontrol_v1_message.ReportRequests.

The :class:`.Aggregator` support this.

"""

from __future__ import absolute_import

import hashlib
import logging
from datetime import datetime

from apitools.base.py import encoding

import google.apigen.servicecontrol_v1_messages as messages
from .. import caches, signing
from . import metric_value, operation

logger = logging.getLogger(__name__)


def sign(check_request):
    """Obtains a signature for an operation in a `CheckRequest`

    Args:
       op (:class:`google.apigen.servicecontrol_v1_messages.Operation`): an
         operation used in a `CheckRequest`

    Returns:
       string: a secure hash generated from the operation
    """
    if not isinstance(check_request, messages.CheckRequest):
        raise ValueError('Invalid request')
    op = check_request.operation
    if op is None or op.operationName is None or op.consumerId is None:
        logging.error('Bad %s: not initialized => not signed', check_request)
        raise ValueError('check request must be initialized with an operation')
    md5 = hashlib.md5()
    md5.update(op.operationName)
    md5.update('\x00')
    md5.update(op.consumerId)
    if op.labels:
        signing.add_dict_to_hash(md5, encoding.MessageToPyValue(op.labels))
    for value_set in op.metricValueSets:
        md5.update('\x00')
        md5.update(value_set.metricName)
        for mv in value_set.metricValues:
            metric_value.update_hash(md5, mv)
    md5.update('\x00')
    if op.quotaProperties:
        # N.B: this differs form cxx implementation, which serializes the
        # protobuf. This should be OK as the exact hash used does not need to
        # match across implementations.
        md5.update(repr(op.quotaProperties))
    md5.update('\x00')

    return md5.digest()


class Aggregator(object):
    """Caches and aggregates ``CheckRequests``.

    Concurrency: Thread safe.

    Usage:

    Creating a new cache entry and use cached response

    Example:
      >>> options = CheckAggregationOptions()
      >>> agg = Aggregator('my_service', options)
      >>> req = ServicecontrolServicesCheckRequest(...)
      >>> # check returns None as the request is not cached
      >>> if agg.check(req) is not None:
      ...    resp = service.check(req)
      ...    agg = service.add_response(req, resp)
      >>> agg.check(req)  # response now cached according as-per options
      <CheckResponse ....>

    Refreshing a cached entry after a flush interval

    The flush interval is constrained to be shorter than the actual cache
    expiration.  This allows the response to potentially remain cached and be
    aggregated with subsequent check requests for the same operation.

    Example:
      >>> # continuing from the previous example,
      >>> # ... after the flush interval
      >>> # - the response is still in the cache, i.e, not expired
      >>> # - the first call after the flush interval returns None, subsequent
      >>> #  calls continue to return the cached response
      >>> agg.check(req)  # signals the caller to call service.check(req)
      None
      >>> agg.check(req)  # next call returns the cached response
      <CheckResponse ....>

    Flushing the cache

    Once a response is expired, if there is an outstanding, cached CheckRequest
    for it, this should be sent and their responses added back to the
    aggregator instance, as they will contain quota updates that have not been
    sent.

    Example:

      >>> # continuing the previous example
      >>> for req in agg.flush():  # an iterable of cached CheckRequests
      ...     resp = caller.send_req(req)  # caller sends them
      >>>     agg.add_response(req, resp)  # and caches their responses

    """

    def __init__(self, service_name, options, kinds=None, timer=datetime.now):
        """Constructor.

        Args:
          service_name (string): names the service that all requests aggregated
            by this instance will be sent
          options (:class:`~google.scc.CheckAggregationOptions`): configures the
            caching and flushing behavior of this instance
          kinds (dict[string,[google.scc.MetricKind]]): specifies the kind
            kind of metric for each each metric name.
          timer (function([[datetime]]): a function that returns the current
            as a time as a datetime instance
        """
        self._service_name = service_name
        self._options = options
        self._cache = caches.create(options, timer=timer)
        self._kinds = {} if kinds is None else dict(kinds)
        self._timer = timer

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
        return None if self._cache is None else self._options.expiration

    def flush(self):
        """Flushes this instance's cache.

        The driver of this instance should call this method every
        `flush_interval`.

        Returns:
          list['CheckRequest']: corresponding to CheckRequests that were
          pending

        """
        if self._cache is None:
            return []
        with self._cache as c:
            flushed_items = list(c.out_deque)
            c.out_deque.clear()
            cached_reqs = [item.extract_request() for item in flushed_items]
            cached_reqs = [req for req in cached_reqs if req is not None]
            return cached_reqs

    def clear(self):
        """Clears this instance's cache."""
        if self._cache is not None:
            with self._cache as c:
                c.clear()
                c.out_deque.clear()

    def add_response(self, req, resp):
        """Adds the response from sending to `req` to this instance's cache.

        Args:
          req (`ServicecontrolServicesCheckRequest`): the request
          resp (CheckResponse): the response from sending the request
        """
        if self._cache is None:
            return
        signature = sign(req.check_request)
        with self._cache as c:
            now = self._timer()
            quota_scale = 0  # WIP
            item = c.get(signature)
            if item is None:
                c[signature] = CachedItem(
                    resp, self.service_name, now, quota_scale)
            else:
                # Update the cached item to reflect that it is updated
                item.last_check_time = now
                item.response = resp
                item.quota_scale = quota_scale
                item.is_flushing = False
                c[signature] = item

    def check(self, req):
        """Determine if ``req`` is in this instances cache.

        Determine if there are cache hits for the request in this aggregator
        instance.

        Not in the cache

        If req is not in the cache, it returns ``None`` to indicate that the
        caller should send the request.

        Cache Hit; response has errors

        When a cached CheckResponse has errors, it's assumed that ``req`` would
        fail as well, so the cached CheckResponse is returned.  However, the
        first CheckRequest after the flush interval has elapsed should be sent
        to the server to refresh the CheckResponse, though until it's received,
        subsequent CheckRequests should fail with the cached CheckResponse.

        Cache behaviour - response passed

        If the cached CheckResponse has no errors, it's assumed that ``req``
        will succeed as well, so the CheckResponse is returned, with the quota
        info updated to the same as requested.  The requested tokens are
        aggregated until flushed.

        Args:
          req (``ServicecontrolServicesCheckRequest``): to be sent to
            the service control service

        Raises:
           ValueError: if the ``req`` service_name is not the same as
             this instances

        Returns:
           ``CheckResponse``: if an applicable response is cached by this
             instance is available for use or None, if there is no applicable
             response

        """
        if self._cache is None:
            return None  # no cache, send request now
        if not isinstance(req, messages.ServicecontrolServicesCheckRequest):
            raise ValueError('Invalid request')
        if req.serviceName != self.service_name:
            logger.error('bad check(): service_name %s does not match ours %s',
                         req.serviceName, self.service_name)
            raise ValueError('Service name mismatch')
        check_request = req.check_request
        if check_request is None:
            logger.error('bad check(): no check_request in %s', req)
            raise ValueError('Expected operation not set')
        op = check_request.operation
        if op is None:
            logger.error('bad check(): no operation in %s', req)
            raise ValueError('Expected operation not set')
        if op.importance != messages.Operation.ImportanceValueValuesEnum.LOW:
            return None  # op is important, send request now

        signature = sign(check_request)
        with self._cache as cache:
            logger.debug('checking the cache for %s\n%s', signature, cache)
            item = cache.get(signature)
            if item is None:
                return None  # signal to caller to send req
            else:
                return self._handle_cached_response(req, item)

    def _handle_cached_response(self, req, item):
        with self._cache:  # defensive, this re-entrant lock should be held
            if len(item.response.checkErrors) > 0:
                if self._is_current(item):
                    return item.response

                # There are errors, but now it's ok to send a new request
                item.last_check_time = self._timer()
                return None  # signal caller to send req
            else:
                item.update_request(req, self._kinds)
                if self._is_current(item):
                    return item.response

                if (item.is_flushing):
                    logger.warn('last refresh request did not complete')
                item.is_flushing = True
                item.last_check_time = self._timer()
                return None  # signal caller to send req

    def _is_current(self, item):
        age = self._timer() - item.last_check_time
        return age < self._options.flush_interval


class CachedItem(object):
    """CachedItem holds items cached along with a ``CheckRequest``.

    Thread compatible.

    Attributes:
       response (:class:`messages.CachedResponse`): the cached response
       is_flushing (bool): indicates if it's been detected that item
         is stale, and needs to be flushed
       quota_scale (int): WIP, used to determine quota
       last_check_time (datetime.datetime): the last time this instance
         was checked

    """

    def __init__(self, resp, service_name, last_check_time, quota_scale):
        self.last_check_time = last_check_time
        self.quota_scale = quota_scale
        self.is_flushing = False
        self.response = resp
        self._service_name = service_name
        self._op_aggregator = None

    def update_request(self, req, kinds):
        agg = self._op_aggregator
        if agg is None:
            self._op_aggregator = operation.Aggregator(
                req.check_request.operation, kinds)
        else:
            agg.add(req.check_request.operation)

    def extract_request(self):
        if self._op_aggregator is None:
            return None

        op = self._op_aggregator.as_operation()
        self._op_aggregator = None
        check_request = messages.CheckRequest(operation=op)
        return messages.ServicecontrolServicesCheckRequest(
            serviceName=self._service_name,
            check_request=check_request)
