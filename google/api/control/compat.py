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

from __future__ import absolute_import

# This file exists only to make imports from the appropriate locations
# in PY2 vs PY3; it does not need to be linted.

# flake8: noqa
# pylint: skip-file

from future.utils import PY3

if PY3:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
    from urllib.parse import urlparse, parse_qs
    import http.client as httplib
else:
    from urllib2 import Request, urlopen, URLError
    from urlparse import urlparse, parse_qs
    import httplib
