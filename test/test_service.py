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
import json
import unittest2

from apitools.base.py import encoding
from expects import be_none, expect, equal, raise_error

import google.apigen.servicecontrol_v1_messages as messages
from google.scc import service


_LOGGING_DESTINATIONS_INPUT = """
{
  "logs": [{
    "name": "endpoints-log",
    "labels": [{
      "key": "supported/endpoints-log-label"
    }, {
      "key": "unsupported/endpoints-log-label"
    }]
  }, {
    "name": "unreferenced-log",
    "labels": [{
      "key": "supported/unreferenced-log-label"
    }]
  }],

  "monitoredResources": [{
    "type": "endpoints.googleapis.com/endpoints",
    "labels": [{
      "key": "unsupported/endpoints"
    }, {
      "key": "supported/endpoints"
    }]
  }],

  "logging": {
    "producerDestinations": [{
      "monitoredResource": "bad-monitored-resource",
      "logs": [
        "bad-monitored-resource-log"
      ]
    }, {
      "monitoredResource": "endpoints.googleapis.com/endpoints",
      "logs": [
        "bad-endpoints-log",
        "endpoints-log"
      ]
    }]
  }
}

"""


class _JsonMetricBase(object):

    def setUp(self):
        self._subject = encoding.JsonToMessage(messages.Service, self._INPUT)

    def _extract(self):
        return service.extract_report_spec(
            self._subject,
            label_is_supported=fake_is_label_supported,
            metric_is_supported=fake_is_metric_supported
        )


class TestLoggingDestinations(_JsonMetricBase, unittest2.TestCase):
    _INPUT = _LOGGING_DESTINATIONS_INPUT
    _WANTED_LABELS = [
        'supported/endpoints-log-label',
        'supported/endpoints'
    ]

    def test_should_access_the_valid_referenced_log(self):
        logs, _metrics, _labels =  self._extract()
        expect(logs).to(equal(set(['endpoints-log'])))

    def test_should_not_specify_any_metrics(self):
        _logs, metrics, _labels =  self._extract()
        expect(metrics).to(equal([]))

    def test_should_specify_the_labels_associated_with_the_valid_log(self):
        _logs, _metrics, labels =  self._extract()
        expect(set(labels)).to(equal(set(self._WANTED_LABELS)))

    def test_should_drop_conflicting_log_labels(self):
        conflicting_label = messages.LabelDescriptor(
            key='supported/endpoints-log-label',
            valueType=messages.LabelDescriptor.ValueTypeValueValuesEnum.BOOL
        )
        bad_log_desc = messages.LogDescriptor(
            name='bad-endpoints-log',
            labels=[conflicting_label]
        )
        self._subject.logs.append(bad_log_desc)
        _logs, _metrics, labels =  self._extract()
        expect(set(labels)).to(equal(set(self._WANTED_LABELS)))



_METRIC_DESTINATIONS_INPUTS = """
{
  "metrics": [{
    "name": "supported/endpoints-metric",
    "labels": [{
      "key": "supported/endpoints-metric-label"
    }, {
      "key": "unsupported/endpoints-metric-label"
    }]
  }, {
    "name": "unsupported/unsupported-endpoints-metric",
    "labels": [{
      "key": "supported/unreferenced-metric-label"
    }]
  }, {
    "name": "supported/non-existent-resource-metric",
    "labels": [{
      "key": "supported/non-existent-resource-metric-label"
    }]
  }],

  "monitoredResources": {
    "type": "endpoints.googleapis.com/endpoints",
    "labels": [{
      "key": "unsupported/endpoints"
    }, {
      "key": "supported/endpoints"
    }]
  },

  "monitoring": {
    "consumerDestinations": [{
      "monitoredResource": "endpoints.googleapis.com/endpoints",
      "metrics": [
        "supported/endpoints-metric",
        "unsupported/unsupported-endpoints-metric",
        "supported/unknown-metric"
      ]
    }, {
      "monitoredResource": "endpoints.googleapis.com/non-existent",
      "metrics": [
         "supported/endpoints-metric",
         "unsupported/unsupported-endpoints-metric",
         "supported/unknown-metric",
         "supported/non-existent-resource-metric"
      ]
    }]
  }
}

"""

class TestMetricDestinations(_JsonMetricBase, unittest2.TestCase):
    _INPUT = _METRIC_DESTINATIONS_INPUTS
    _WANTED_METRICS = [
        'supported/endpoints-metric'
    ]
    _WANTED_LABELS = [
        'supported/endpoints-metric-label',
        'supported/endpoints'
    ]

    def test_should_not_load_any_logs(self):
        logs, _metrics, _labels =  self._extract()
        expect(logs).to(equal(set()))

    def test_should_specify_some_metrics(self):
        _logs, metrics, _labels =  self._extract()
        expect(metrics).to(equal(self._WANTED_METRICS))

    def test_should_specify_the_labels_associated_with_the_metrics(self):
        _logs, _metrics, labels =  self._extract()
        expect(set(labels)).to(equal(set(self._WANTED_LABELS)))


_NOT_SUPPORTED_PREFIX = 'unsupported/'


_COMBINED_INPUTS = """
{
  "logs": {
    "name": "endpoints-log",
    "labels": [{
      "key": "supported/endpoints-log-label"
    }, {
      "key": "unsupported/endpoints-log-label"
    }]
  },

  "metrics": [{
    "name": "supported/endpoints-metric",
    "labels": [{
      "key": "supported/endpoints-metric-label"
    }, {
      "key": "unsupported/endpoints-metric-label"
    }]
  }, {
    "name": "supported/endpoints-consumer-metric",
    "labels": [{
      "key": "supported/endpoints-metric-label"
    }, {
      "key": "supported/endpoints-consumer-metric-label"
    }]
  }, {
    "name": "supported/endpoints-producer-metric",
    "labels": [{
      "key": "supported/endpoints-metric-label"
    }, {
      "key": "supported/endpoints-producer-metric-label"
    }]
  }],

  "monitoredResources": {
    "type": "endpoints.googleapis.com/endpoints",
    "labels": [{
      "key": "unsupported/endpoints"
    }, {
      "key": "supported/endpoints"
    }]
  },

  "logging": {
    "producerDestinations": [{
      "monitoredResource": "endpoints.googleapis.com/endpoints",
      "logs": ["endpoints-log"]
    }]
  },

  "monitoring": {
    "consumerDestinations": [{
      "monitoredResource": "endpoints.googleapis.com/endpoints",
      "metrics": [
         "supported/endpoints-consumer-metric",
         "supported/endpoints-metric"
      ]
    }],

    "producerDestinations": [{
      "monitoredResource": "endpoints.googleapis.com/endpoints",
      "metrics": [
         "supported/endpoints-producer-metric",
         "supported/endpoints-metric"
      ]
    }]
  }
}

"""

class TestCombinedExtraction(_JsonMetricBase, unittest2.TestCase):
    _INPUT = _COMBINED_INPUTS
    _WANTED_METRICS = [
        "supported/endpoints-metric",
        "supported/endpoints-consumer-metric",
        "supported/endpoints-producer-metric"
    ]
    _WANTED_LABELS = [
        "supported/endpoints",  # from monitored resource
        "supported/endpoints-log-label",  # from log
        "supported/endpoints-metric-label",  # from both metrics
        "supported/endpoints-consumer-metric-label",  # from consumer metric
        "supported/endpoints-producer-metric-label"  # from producer metric
    ]

    def test_should_load_the_specified_logs(self):
        logs, _metrics, _labels =  self._extract()
        expect(logs).to(equal(set(['endpoints-log'])))

    def test_should_load_the_specified_metrics(self):
        _logs, metrics, _labels =  self._extract()
        expect(set(metrics)).to(equal(set(self._WANTED_METRICS)))

    def test_should_load_the_specified_metrics(self):
        _logs, _metrics, labels =  self._extract()
        expect(set(labels)).to(equal(set(self._WANTED_LABELS)))


def fake_is_label_supported(label_desc):
    return not label_desc.key.startswith(_NOT_SUPPORTED_PREFIX)


def fake_is_metric_supported(metric_desc):
    return not metric_desc.name.startswith(_NOT_SUPPORTED_PREFIX)
