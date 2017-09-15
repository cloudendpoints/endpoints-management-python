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

import base64
import datetime
import unittest2
from expects import be_none, be_true, expect, equal, raise_error

from endpoints_management.control import (label_descriptor, sm_messages,
                                          report_request)

_KNOWN = label_descriptor.KnownLabels
ValueType = label_descriptor.ValueType

class KnownLabelsBase(object):
    SUBJECT = None
    GIVEN_INFO = report_request.Info(
        api_method = u'dummy_method',
        api_version = u'dummy_version',
        location = u'dummy_location',
        referer = u'dummy_referer',
        consumer_project_number=1234)
    WANTED_LABEL_DICT = {}

    def _matching_descriptor(self, hide_default=False):
        res = sm_messages.LabelDescriptor(
            key=self.SUBJECT.label_name,
            valueType=self.SUBJECT.value_type)
        if res.valueType == ValueType.STRING and hide_default:
            res.valueType = None
        return res

    def _not_matched(self):
        d = self._matching_descriptor()
        d.valueType = ValueType.INT64  # no known labels have this type
        return d

    def test_should_be_supported(self):
        expect(_KNOWN.is_supported(self._matching_descriptor())).to(be_true)
        expect(_KNOWN.is_supported(
            self._matching_descriptor(hide_default=True))).to(be_true)
        expect(_KNOWN.is_supported(self._not_matched())).not_to(be_true)

    def test_should_be_matched_correctly(self):
        expect(self.SUBJECT.matches(self._matching_descriptor())).to(be_true)
        expect(self.SUBJECT.matches(
            self._matching_descriptor(hide_default=True))).to(be_true)
        expect(self.SUBJECT.matches(self._not_matched())).not_to(be_true)

    def test_should_update_request_info(self):
        given_dict = {}
        self.SUBJECT.do_labels_update(self.GIVEN_INFO, given_dict)
        expect(given_dict).to(equal(self.WANTED_LABEL_DICT))


class TestCredentialIdWithNoCreds(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.CREDENTIAL_ID


class TestCredentialIdWithApiKey(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.CREDENTIAL_ID
    GIVEN_INFO = report_request.Info(
        api_key = u'dummy_api_key',
    )
    WANTED_LABEL_DICT = {SUBJECT.label_name: b'apiKey:dummy_api_key'}


class TestCredentialIdWithAuthIssuer(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.CREDENTIAL_ID
    GIVEN_INFO = report_request.Info(
        auth_issuer = u'dummy_issuer',
        auth_audience = u'dummy_audience')
    WANTED_VALUE = b'jwtAuth:issuer=' + base64.urlsafe_b64encode(b'dummy_issuer')
    WANTED_VALUE += b'&audience=' + base64.urlsafe_b64encode(b'dummy_audience')
    WANTED_LABEL_DICT = {SUBJECT.label_name: WANTED_VALUE}


class EndUser(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.END_USER


class EndUserCountry(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.END_USER_COUNTRY


class ErrorType(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.ERROR_TYPE
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'2xx'}


class Protocol(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.PROTOCOL
    WANTED_LABEL_DICT = {
        SUBJECT.label_name: report_request.ReportedProtocols.UNKNOWN.name
    }


class Referer(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.REFERER
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'dummy_referer'}


class ResponseCode(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.RESPONSE_CODE
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'200'}


class ResponseCodeClass(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.RESPONSE_CODE_CLASS
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'2xx'}


class StatusCodeWithOkStatus(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.STATUS_CODE
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'0'}


class StatusCodeWithKnown4XXStatus(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.STATUS_CODE
    GIVEN_INFO = report_request.Info(
        response_code = 401,
    )
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'16'}


class StatusCodeWithUnknown4XXStatus(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.STATUS_CODE
    GIVEN_INFO = report_request.Info(
        response_code = 477,
    )
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'9'}


class StatusCodeWithKnown5XXStatus(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.STATUS_CODE
    GIVEN_INFO = report_request.Info(
        response_code = 501,
    )
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'12'}


class StatusCodeWithUnknown5XXStatus(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.STATUS_CODE
    GIVEN_INFO = report_request.Info(
        response_code = 577,
    )
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'13'}


class StatusCodeWithUnknownStatus(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.STATUS_CODE
    GIVEN_INFO = report_request.Info(
        response_code = 777,
    )
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'2'}


class GaeCloneId(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GAE_CLONE_ID


class GaeModuleId(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GAE_MODULE_ID


class GaeReplicaIndex(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GAE_REPLICA_INDEX


class GaeVersionId(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GAE_VERSION_ID


class GcpLocation(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_LOCATION
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'dummy_location'}


class GcpProject(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_PROJECT


class GcpRegion(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_REGION


class GcpResourceId(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_RESOURCE_ID


class GcpResourceType(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_RESOURCE_TYPE


class GcpService(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_SERVICE


class GcpZone(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_ZONE


class GcpUid(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_UID


class GcpApiMethod(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_API_METHOD
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'dummy_method'}


class GcpApiVersion(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.GCP_API_VERSION
    WANTED_LABEL_DICT = {SUBJECT.label_name: u'dummy_version'}


class SccAndroidCertFingerprint(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_ANDROID_CERT_FINGERPRINT


class SccAndroidPackageName(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_ANDROID_PACKAGE_NAME


class SccCallerIp(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_CALLER_IP


class SccIosBundleId(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_IOS_BUNDLE_ID


class SccPlatform(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_PLATFORM
    WANTED_LABEL_DICT = {
        SUBJECT.label_name: report_request.ReportedPlatforms.UNKNOWN.name
    }


class SccReferer(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_REFERER


class SccServiceAgent(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_SERVICE_AGENT
    WANTED_LABEL_DICT = {SUBJECT.label_name: label_descriptor.SERVICE_AGENT}


class SccUserAgent(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_USER_AGENT
    WANTED_LABEL_DICT = {SUBJECT.label_name: label_descriptor.USER_AGENT}


class SccConsumerProject(KnownLabelsBase, unittest2.TestCase):
    SUBJECT = _KNOWN.SCC_CONSUMER_PROJECT
    WANTED_LABEL_DICT = {SUBJECT.label_name: "1234"}
