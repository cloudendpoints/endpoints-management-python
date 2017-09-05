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

"""metric_descriptor provides funcs for working with `MetricDescriptor` instances.

:class:`KnownMetrics` is an :class:`enum.Enum` that defines the list of known
`MetricDescriptor` instances.  It is a complex enumeration that includes various
attributes including

- the full metric name
- the kind of the metric
- the value type of the metric
- a func for updating :class:`Operation`s from a `ReportRequestInfo`

"""

from __future__ import absolute_import


from enum import Enum
from . import distribution, metric_value, sc_messages, MetricKind, ValueType


def _add_metric_value(name, value, an_op):
    an_op.metricValueSets.append(
        sc_messages.MetricValueSet(metricName=name, metricValues=[value]))


def _add_int64_metric_value(name, value, an_op):
    _add_metric_value(
        name, metric_value.create(int64Value=value), an_op)


def _set_int64_metric_to_constant_1(name, dummy_info, op):
    _add_int64_metric_value(name, 1, op)


def _set_int64_metric_to_constant_1_if_http_error(name, info, op):
    if info.response_code >= 400:
        _add_int64_metric_value(name, 1, op)


def _add_distribution_metric_value(name, value, an_op, distribution_args):
    d = distribution.create_exponential(*distribution_args)
    distribution.add_sample(value, d)
    _add_metric_value(
        name, metric_value.create(distributionValue=d), an_op)


_SIZE_DISTRIBUTION_ARGS = (8, 10.0, 1.0)


def _set_distribution_metric_to_request_size(name, info, an_op):
    if info.request_size >= 0:
        _add_distribution_metric_value(name, info.request_size, an_op,
                                       _SIZE_DISTRIBUTION_ARGS)


def _set_distribution_metric_to_response_size(name, info, an_op):
    if info.response_size >= 0:
        _add_distribution_metric_value(name, info.response_size, an_op,
                                       _SIZE_DISTRIBUTION_ARGS)


_TIME_DISTRIBUTION_ARGS = (8, 10.0, 1e-6)


def _set_distribution_metric_to_request_time(name, info, an_op):
    if info.request_time:
        _add_distribution_metric_value(name, info.request_time.total_seconds(),
                                       an_op, _TIME_DISTRIBUTION_ARGS)


def _set_distribution_metric_to_backend_time(name, info, an_op):
    if info.backend_time:
        _add_distribution_metric_value(name, info.backend_time.total_seconds(),
                                       an_op, _TIME_DISTRIBUTION_ARGS)


def _set_distribution_metric_to_overhead_time(name, info, an_op):
    if info.overhead_time:
        _add_distribution_metric_value(name, info.overhead_time.total_seconds(),
                                       an_op, _TIME_DISTRIBUTION_ARGS)


class Mark(Enum):
    """Enumerates the types of metric."""
    PRODUCER = 1
    CONSUMER = 2
    PRODUCER_BY_CONSUMER = 3


class KnownMetrics(Enum):
    """Enumerates the known metrics."""

    CONSUMER_REQUEST_COUNT = (
        u'serviceruntime.googleapis.com/api/consumer/request_count',
        MetricKind.DELTA,
        ValueType.INT64,
        _set_int64_metric_to_constant_1,
        Mark.CONSUMER,
    )
    PRODUCER_REQUEST_COUNT = (
        u'serviceruntime.googleapis.com/api/producer/request_count',
        MetricKind.DELTA,
        ValueType.INT64,
        _set_int64_metric_to_constant_1,
    )
    PRODUCER_BY_CONSUMER_REQUEST_COUNT = (
        u'serviceruntime.googleapis.com/api/producer/by_consumer/request_count',
        MetricKind.DELTA,
        ValueType.INT64,
        _set_int64_metric_to_constant_1,
        Mark.PRODUCER_BY_CONSUMER,
    )
    CONSUMER_REQUEST_SIZES = (
        u'serviceruntime.googleapis.com/api/consumer/request_sizes',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_request_size,
        Mark.CONSUMER,
    )
    PRODUCER_REQUEST_SIZES = (
        u'serviceruntime.googleapis.com/api/producer/request_sizes',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_request_size,
    )
    PRODUCER_BY_CONSUMER_REQUEST_SIZES = (
        'serviceruntime.googleapis.com/api/producer/by_consumer/request_sizes',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_request_size,
        Mark.PRODUCER_BY_CONSUMER,
    )
    CONSUMER_RESPONSE_SIZES = (
        u'serviceruntime.googleapis.com/api/consumer/response_sizes',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_response_size,
        Mark.CONSUMER,
    )
    PRODUCER_RESPONSE_SIZES = (
        u'serviceruntime.googleapis.com/api/producer/response_sizes',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_response_size,
    )
    PRODUCER_BY_CONSUMER_RESPONSE_SIZES = (
        'serviceruntime.googleapis.com/api/producer/by_consumer/response_sizes',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_response_size,
        Mark.PRODUCER_BY_CONSUMER,
    )
    CONSUMER_ERROR_COUNT = (
        u'serviceruntime.googleapis.com/api/consumer/error_count',
        MetricKind.DELTA,
        ValueType.INT64,
        _set_int64_metric_to_constant_1_if_http_error,
        Mark.CONSUMER,
    )
    PRODUCER_ERROR_COUNT = (
        u'serviceruntime.googleapis.com/api/producer/error_count',
        MetricKind.DELTA,
        ValueType.INT64,
        _set_int64_metric_to_constant_1_if_http_error,
    )
    PRODUCER_BY_CONSUMER_ERROR_COUNT = (
        'serviceruntime.googleapis.com/api/producer/by_consumer/error_count',
        MetricKind.DELTA,
        ValueType.INT64,
        _set_int64_metric_to_constant_1_if_http_error,
        Mark.PRODUCER_BY_CONSUMER,
    )
    CONSUMER_TOTAL_LATENCIES = (
        u'serviceruntime.googleapis.com/api/consumer/total_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_request_time,
        Mark.CONSUMER,
    )
    PRODUCER_TOTAL_LATENCIES = (
        u'serviceruntime.googleapis.com/api/producer/total_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_request_time,
    )
    PRODUCER_BY_CONSUMER_TOTAL_LATENCIES = (
        'serviceruntime.googleapis.com/api/producer/by_consumer/'
        'total_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_request_time,
        Mark.PRODUCER_BY_CONSUMER,
    )
    CONSUMER_BACKEND_LATENCIES = (
        u'serviceruntime.googleapis.com/api/consumer/backend_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_backend_time,
        Mark.CONSUMER,
    )
    PRODUCER_BACKEND_LATENCIES = (
        u'serviceruntime.googleapis.com/api/producer/backend_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_backend_time,
    )
    PRODUCER_BY_CONSUMER_BACKEND_LATENCIES = (
        'serviceruntime.googleapis.com/api/producer/by_consumer/'
        'backend_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_backend_time,
        Mark.PRODUCER_BY_CONSUMER,
    )
    CONSUMER_REQUEST_OVERHEAD_LATENCIES = (
        u'serviceruntime.googleapis.com/api/consumer/request_overhead_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_overhead_time,
        Mark.CONSUMER,
    )
    PRODUCER_REQUEST_OVERHEAD_LATENCIES = (
        u'serviceruntime.googleapis.com/api/producer/request_overhead_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_overhead_time,
    )
    PRODUCER_BY_CONSUMER_REQUEST_OVERHEAD_LATENCIES = (
        'serviceruntime.googleapis.com/api/producer/by_consumer/'
        'request_overhead_latencies',
        MetricKind.DELTA,
        ValueType.DISTRIBUTION,
        _set_distribution_metric_to_overhead_time,
        Mark.PRODUCER_BY_CONSUMER,
    )

    def __init__(self, metric_name, kind, value_type, update_op_func,
                 mark=Mark.PRODUCER):
        """Constructor.

        update_op_func is used to when updating an `Operation` from a
        `ReportRequestInfo`.

        Args:
           metric_name (str): the name of the metric descriptor
           kind (:class:`MetricKind`): the ``kind`` of the described metric
           value_type (:class:`ValueType`): the `value type` of the described metric
           update_op_func (function): the func to update an operation

        """
        self.kind = kind
        self.metric_name = metric_name
        if mark is Mark.CONSUMER:
            self.update_op_func = self._consumer_metric(update_op_func)
        elif mark is Mark.PRODUCER_BY_CONSUMER:
            self.update_op_func = self._by_consumer_metric(update_op_func)
        else:
            self.update_op_func = update_op_func
        self.value_type = value_type
        self.mark = mark

    def matches(self, desc):
        """Determines if a given metric descriptor matches this enum instance

        Args:
           desc (:class:`endpoints_management.gen.servicecontrol_v1_messages.MetricDescriptor`): the
              instance to test

        Return:
           `True` if desc is supported, otherwise `False`

        """
        return (self.metric_name == desc.name and
                self.kind == desc.metricKind and
                self.value_type == desc.valueType)

    def do_operation_update(self, info, an_op):
        """Updates an operation using the assigned update_op_func

        Args:
           info: (:class:`endpoints_management.control.report_request.Info`): the
              info instance to update
           an_op: (:class:`endpoints_management.control.report_request.Info`):
              the info instance to update

        Return:
           `True` if desc is supported, otherwise `False`

        """
        self.update_op_func(self.metric_name, info, an_op)

    def _consumer_metric(self, update_op_func):
        def resulting_updater(metric_name, info, an_op):
            if info.api_key_valid:
                update_op_func(metric_name, info, an_op)

        return resulting_updater

    def _by_consumer_metric(self, update_op_func):
        def resulting_updater(metric_name, info, an_op):
            if info.consumer_project_number > 0:
                update_op_func(metric_name, info, an_op)

        return resulting_updater

    @classmethod
    def is_supported(cls, desc):
        """Determines if the given metric descriptor is supported.

        Args:
           desc (:class:`endpoints_management.gen.servicecontrol_v1_messages.MetricDescriptor`): the
             metric descriptor to test

        Return:
           `True` if desc is supported, otherwise `False`

        """
        for m in cls:
            if m.matches(desc):
                return True
        return False
