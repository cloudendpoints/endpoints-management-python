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

"""Google Service Control Client"""

from __future__ import absolute_import

from ..gen import servicecontrol_v1_messages as sc_messages
from ..gen import servicemanagement_v1_messages as sm_messages
from ..gen import servicecontrol_v1_client as api_client

# Alias the generated MetricKind and ValueType enums to simplify their usage
# elsewhere
MetricKind = sm_messages.MetricDescriptor.MetricKindValueValuesEnum
ValueType = sm_messages.MetricDescriptor.ValueTypeValueValuesEnum
