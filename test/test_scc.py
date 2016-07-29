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
import sys
import unittest2
from expects import expect, equal

from google.scc import CheckAggregationOptions
from google.scc import ReportAggregationOptions


class TestCheckAggregationOptions(unittest2.TestCase):
    AN_INTERVAL = datetime.timedelta(milliseconds=2)
    A_LOWER_INTERVAL = datetime.timedelta(milliseconds=1)

    def test_should_create_with_defaults(self):
        options = CheckAggregationOptions()
        expect(options.num_entries).to(equal(
            CheckAggregationOptions.DEFAULT_NUM_ENTRIES))
        expect(options.flush_interval).to(equal(
            CheckAggregationOptions.DEFAULT_FLUSH_INTERVAL))
        expect(options.expiration).to(equal(
            CheckAggregationOptions.DEFAULT_EXPIRATION))

    def test_should_ignores_lower_expiration(self):
        wanted_expiration = (
            self.AN_INTERVAL + datetime.timedelta(milliseconds=1))
        options = CheckAggregationOptions(flush_interval=self.AN_INTERVAL,
                                          expiration=self.A_LOWER_INTERVAL)
        expect(options.flush_interval).to(equal(self.AN_INTERVAL))
        expect(options.expiration).to(equal(wanted_expiration))
        expect(options.expiration).not_to(equal(self.A_LOWER_INTERVAL))


class TestReportAggregationOptions(unittest2.TestCase):

    def test_should_create_with_defaults(self):
        options = ReportAggregationOptions()
        expect(options.num_entries).to(equal(
            ReportAggregationOptions.DEFAULT_NUM_ENTRIES))
        expect(options.flush_interval).to(equal(
            ReportAggregationOptions.DEFAULT_FLUSH_INTERVAL))
