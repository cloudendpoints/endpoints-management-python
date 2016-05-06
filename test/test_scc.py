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
