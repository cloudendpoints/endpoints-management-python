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

import hashlib

import unittest2
from expects import equal, expect


from google.scc import signing


class TestAddDictToHash(unittest2.TestCase):
    NOTHING_ADDED = hashlib.md5().digest()

    def test_should_add_nothing_when_dict_is_none(self):
        md5 = hashlib.md5()
        signing.add_dict_to_hash(md5, None)
        expect(md5.digest()).to(equal(self.NOTHING_ADDED))

    def test_should_add_matching_hashes_for_matching_dicts(self):
        a_dict = {'test': 'dict'}
        same_dict = dict(a_dict)
        want_hash = hashlib.md5()
        signing.add_dict_to_hash(want_hash, a_dict)
        want = want_hash.digest()
        got_hash = hashlib.md5()
        signing.add_dict_to_hash(got_hash, same_dict)
        got = got_hash.digest()
        expect(got).to(equal(want))
