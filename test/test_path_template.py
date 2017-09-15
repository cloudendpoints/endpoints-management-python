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

# pylint: disable=missing-docstring,no-self-use,no-init,invalid-name
"""Unit tests for the path_template module."""

from __future__ import absolute_import
import unittest2

from endpoints_management.control.path_template import PathTemplate, ValidationException


class TestPathTemplate(unittest2.TestCase):
    """Unit tests for PathTemplate."""

    def test_len(self):
        self.assertEqual(len(PathTemplate(u'a/b/**/*/{a=hello/world}')), 6)

    def test_fail_invalid_token(self):
        self.assertRaises(ValidationException,
                          PathTemplate, u'hello/wor*ld')

    def test_fail_when_impossible_match(self):
        template = PathTemplate(u'hello/world')
        self.assertRaises(ValidationException,
                          template.match, u'hello')
        template = PathTemplate(u'hello/world')
        self.assertRaises(ValidationException,
                          template.match, u'hello/world/fail')

    def test_fail_mismatched_literal(self):
        template = PathTemplate(u'hello/world')
        self.assertRaises(ValidationException,
                          template.match, u'hello/world2')

    def test_fail_when_multiple_path_wildcards(self):
        self.assertRaises(ValidationException,
                          PathTemplate, u'buckets/*/**/**/objects/*')

    def test_fail_if_inner_binding(self):
        self.assertRaises(ValidationException,
                          PathTemplate, u'buckets/{hello={world}}')

    def test_fail_unexpected_eof(self):
        self.assertRaises(ValidationException,
                          PathTemplate, u'a/{hello=world')

    def test_match_atomic_resource_name(self):
        template = PathTemplate(u'buckets/*/*/objects/*')
        self.assertEqual({u'$0': u'f', u'$1': u'o', u'$2': u'bar'},
                         template.match(u'buckets/f/o/objects/bar'))
        template = PathTemplate(u'/buckets/{hello}')
        self.assertEqual({u'hello': u'world'},
                         template.match(u'buckets/world'))
        template = PathTemplate(u'/buckets/{hello=*}')
        self.assertEqual({u'hello': u'world'},
                         template.match(u'buckets/world'))

    def test_match_escaped_chars(self):
        template = PathTemplate(u'buckets/*/objects')
        self.assertEqual({u'$0': u'hello%2F%2Bworld'},
                         template.match(u'buckets/hello%2F%2Bworld/objects'))

    def test_match_template_with_unbounded_wildcard(self):
        template = PathTemplate(u'buckets/*/objects/**')
        self.assertEqual({u'$0': u'foo', u'$1': u'bar/baz'},
                         template.match(u'buckets/foo/objects/bar/baz'))

    def test_match_with_unbound_in_middle(self):
        template = PathTemplate(u'bar/**/foo/*')
        self.assertEqual({u'$0': u'foo/foo', u'$1': u'bar'},
                         template.match(u'bar/foo/foo/foo/bar'))

    def test_render_atomic_resource(self):
        template = PathTemplate(u'buckets/*/*/*/objects/*')
        url = template.render({
            u'$0': u'f', u'$1': u'o', u'$2': u'o', u'$3': u'google.com:a-b'})
        self.assertEqual(url, u'buckets/f/o/o/objects/google.com')

    def test_render_fail_when_too_few_variables(self):
        template = PathTemplate(u'buckets/*/*/*/objects/*')
        self.assertRaises(ValidationException,
                          template.render,
                          {u'$0': u'f', u'$1': u'l', u'$2': u'o'})

    def test_render_with_unbound_in_middle(self):
        template = PathTemplate(u'bar/**/foo/*')
        url = template.render({u'$0': u'1/2', u'$1': u'3'})
        self.assertEqual(url, u'bar/1/2/foo/3')

    def test_to_string(self):
        template = PathTemplate(u'bar/**/foo/*')
        self.assertEqual(str(template), u'bar/{$0=**}/foo/{$1=*}')
        template = PathTemplate(u'buckets/*/objects/*')
        self.assertEqual(str(template), u'buckets/{$0=*}/objects/{$1=*}')
        template = PathTemplate(u'/buckets/{hello}')
        self.assertEqual(str(template), u'buckets/{hello=*}')
        template = PathTemplate(u'/buckets/{hello=what}/{world}')
        self.assertEqual(str(template), u'buckets/{hello=what}/{world=*}')
        template = PathTemplate(u'/buckets/helloazAZ09-.~_what')
        self.assertEqual(str(template), u'buckets/helloazAZ09-.~_what')
