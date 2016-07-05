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

"""service provides funcs for working with `Service` instances.

:func:`extract_report_spec` obtains objects used to determine what metrics,
labels and logs are included in a report request.

"""

from __future__ import absolute_import

import logging

from . import label_descriptor, metric_descriptor


logger = logging.getLogger(__name__)


def extract_report_spec(
        service,
        label_is_supported=label_descriptor.KnownLabels.is_supported,
        metric_is_supported=metric_descriptor.KnownMetrics.is_supported):
    """Obtains the used logs, metrics and labels from a service.

    label_is_supported and metric_is_supported are filter functions used to
    determine if label_descriptors or metric_descriptors found in the service
    are supported.

    Args:
       service (:class:`google.apigen.servicecontrol_v1_messages.Service`):
          a service instance
       label_is_supported (:func): determines if a given label is supported
       metric_is_supported (:func): determines if a given metric is supported

    Return:
       tuple: (
         logs (set[string}), # the logs to report to
         metrics (list[string]), # the metrics to use
         labels (list[string]) # the labels to add
       )
    """
    resource_descs = service.monitoredResources
    labels_dict = {}
    logs = set()
    if service.logging:
        logs = _add_logging_destinations(
            service.logging.producerDestinations,
            resource_descs,
            service.logs,
            labels_dict,
            label_is_supported
        )
    metrics_dict = {}
    monitoring = service.monitoring
    if monitoring:
        for destinations in (monitoring.consumerDestinations,
                             monitoring.producerDestinations):
            _add_monitoring_destinations(destinations,
                                         resource_descs,
                                         service.metrics,
                                         metrics_dict,
                                         metric_is_supported,
                                         labels_dict,
                                         label_is_supported)
    return logs, metrics_dict.keys(), labels_dict.keys()


def _add_logging_destinations(destinations,
                              resource_descs,
                              log_descs,
                              labels_dict,
                              is_supported):
    all_logs = set()
    for d in destinations:
        if not _add_labels_for_a_monitored_resource(resource_descs,
                                                    d.monitoredResource,
                                                    labels_dict,
                                                    is_supported):
            continue  # skip bad monitored resources
        for log in d.logs:
            if _add_labels_for_a_log(log_descs, log, labels_dict, is_supported):
                all_logs.add(log)  # only add correctly configured logs
    return all_logs


def _add_monitoring_destinations(destinations,
                                 resource_descs,
                                 metric_descs,
                                 metrics_dict,
                                 metric_is_supported,
                                 labels_dict,
                                 label_is_supported):
    # pylint: disable=too-many-arguments
    for d in destinations:
        if not _add_labels_for_a_monitored_resource(resource_descs,
                                                    d.monitoredResource,
                                                    labels_dict,
                                                    label_is_supported):
            continue  # skip bad monitored resources
        for metric_name in d.metrics:
            metric_desc = _find_metric_descriptor(metric_descs, metric_name,
                                                  metric_is_supported)
            if not metric_desc:
                continue  # skip unrecognized or unsupported metric
            if not _add_labels_from_descriptors(metric_desc.labels, labels_dict,
                                                label_is_supported):
                continue  # skip metrics with bad labels
            metrics_dict[metric_name] = metric_desc


def _add_labels_from_descriptors(descs, labels_dict, is_supported):
    # only add labels if there are no conflicts
    for desc in descs:
        existing = labels_dict.get(desc.key)
        if existing and existing.valueType != desc.valueType:
            logger.warn('halted label scan: conflicting label in %s', desc.key)
            return False
    # Update labels_dict
    for desc in descs:
        if is_supported(desc):
            labels_dict[desc.key] = desc
    return True


def _add_labels_for_a_log(logging_descs, log_name, labels_dict, is_supported):
    for d in logging_descs:
        if d.name == log_name:
            _add_labels_from_descriptors(d.labels, labels_dict, is_supported)
            return True
    logger.warn('bad log label scan: log not found %s', log_name)
    return False


def _add_labels_for_a_monitored_resource(resource_descs,
                                         resource_name,
                                         labels_dict,
                                         is_supported):
    for d in resource_descs:
        if d.type == resource_name:
            _add_labels_from_descriptors(d.labels, labels_dict, is_supported)
            return True
    logger.warn('bad monitored resource label scan: resource not found %s',
                resource_name)
    return False


def _find_metric_descriptor(metric_descs, name, metric_is_supported):
    for d in metric_descs:
        if name != d.name:
            continue
        if metric_is_supported(d):
            return d
        else:
            return None
    return None
