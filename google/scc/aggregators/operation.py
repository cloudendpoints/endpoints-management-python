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

"""operation provides support for working with `Operation` instances.

:class:`~google.apigen.servicecontrol_v1_message.Operation` represents
information regarding an operation, and is a key constituent of
:class:`~google.apigen.servicecontrol_v1_message.CheckRequest` and
:class:`~google.apigen.servicecontrol_v1_message.ReportRequests.

The :class:`.Aggregator` support this.

"""

from __future__ import absolute_import

import collections
import logging
from datetime import datetime

from apitools.base.py import encoding

import google.apigen.servicecontrol_v1_messages as messages
from .. import timestamp, MetricKind
from . import metric_value

logger = logging.getLogger(__name__)


class Info(
        collections.namedtuple(
            'Info', [
                'api_key',
                'api_key_valid',
                'consumer_project_id',
                'operation_id',
                'operation_name',
                'referer',
                'service_name',
            ])):
    """Holds basic information about an api call.

    This class is one of several used to mediate between the raw service
    control api surface and python frameworks. Client code can construct
    operations using this surface

    Attributes:
        api_key (string): the api key
        api_key_valid (bool): it the request has a valid api key. By default
          it is true, it will only be set to false if the api key cannot
          be validated by the service controller
        consumer_project_id (string): the project id of the api consumer
        operation_id (string): identity of the operation, which must be unique
          within the scope of the service. Calls to report and check on the
          same operation should carry the same operation id
        operation_name (string): the fully-qualified name of the operation
        referer (string): the referer header, or if not present the origin
        service_name(string): the name of service

    """

    def __new__(cls,
                api_key='',
                api_key_valid=False,
                consumer_project_id='',
                operation_id='',
                operation_name='',
                referer='',
                service_name=''):
        """Invokes the base constructor with default values."""
        return super(cls, Info).__new__(
            cls,
            api_key,
            api_key_valid,
            consumer_project_id,
            operation_id,
            operation_name,
            referer,
            service_name)

    def as_operation(self, timer=datetime.now):
        """Makes an ``Operation`` from this instance.

        Returns:
          an ``Operation``

        """
        now = timestamp.to_rfc3339(timer())
        op = messages.Operation(endTime=now, startTime=now)
        if self.operation_id:
            op.operationId = self.operation_id
        if self.operation_name:
            op.operationName = self.operation_name
        if self.api_key and self.api_key_valid:
            op.consumerId = 'api_key:' + self.api_key
        elif self.consumer_project_id:
            op.consumerId= 'project:' + self.consumer_project_id
        return op


class Aggregator(object):
    """Container that implements operation aggregation.

    Thread compatible.
    """
    DEFAULT_KIND = MetricKind.DELTA
    """Used when kinds are not specified, or are missing a metric name"""

    def __init__(self, initial_op, kinds=None):
        """Constructor.

        If kinds is not specifed, all operations will be merged assuming
        they are of Kind ``DEFAULT_KIND``

        Args:
           initial_op (
             :class:`google.apigen.servicecontrol_v1_messages.Operation`): the
               initial version of the operation
           kinds (dict[string,[string]]): specifies the metric kind for
              each metric name

        """
        assert isinstance(initial_op, messages.Operation)
        if kinds is None:
            kinds = {}
        self._kinds = kinds
        self._metric_values_by_name_then_sign = collections.defaultdict(dict)
        our_op = encoding.CopyProtoMessage(initial_op)
        self._merge_metric_values(our_op)
        our_op.metricValueSets = []
        self._op = our_op

    def as_operation(self):
        """Obtains a single `Operation` representing this instances contents.

        Returns:
           :class:`google.apigen.servicecontrol_v1_messages.Operation`
        """
        result = encoding.CopyProtoMessage(self._op)
        names = sorted(self._metric_values_by_name_then_sign.keys())
        for name in names:
            mvs = self._metric_values_by_name_then_sign[name]
            result.metricValueSets.append(
                messages.MetricValueSet(
                    metricName=name, metricValues=mvs.values()))
        return result

    def add(self, other_op):
        """Combines `other_op` with the operation held by this aggregator.

        N.B. It merges the operations log entries and metric values, but makes
        the assumption the operation is consistent.  It's the callers
        responsibility to ensure consistency

        Args:
           other_op (
             class:`google.apigen.servicecontrol_v1_messages.Operation`):
             an operation merge into this one

        """
        self._op.logEntries.extend(other_op.logEntries)
        self._merge_timestamps(other_op)
        self._merge_metric_values(other_op)

    def _merge_metric_values(self, other_op):
        for value_set in other_op.metricValueSets:
            name = value_set.metricName
            kind = self._kinds.get(name, self.DEFAULT_KIND)
            by_signature = self._metric_values_by_name_then_sign[name]
            for mv in value_set.metricValues:
                signature = metric_value.sign(mv)
                prior = by_signature.get(signature)
                if prior is not None:
                    metric_value.merge(kind, prior, mv)
                by_signature[signature] = mv

    def _merge_timestamps(self, other_op):
        # Update the start time and end time in self._op  as needed
        if (other_op.startTime and
            (self._op.startTime is None or
             timestamp.compare(other_op.startTime, self._op.startTime) == -1)):
            self._op.startTime = other_op.startTime

        if (other_op.endTime and
            (self._op.endTime is None or timestamp.compare(
                self._op.endTime, other_op.endTime) == -1)):
            self._op.endTime = other_op.endTime
