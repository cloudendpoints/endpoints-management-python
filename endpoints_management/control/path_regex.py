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

"""Implements a utility for parsing path templates."""

# This is ported over from endpoints.api_config_manager.

from __future__ import absolute_import

import base64
import re

# Internal constants
_PATH_VARIABLE_PATTERN = r'[a-zA-Z_][a-zA-Z_.\d]*'
_PATH_VALUE_PATTERN = r'[^/?#\[\]{}]*'

RegexError = re.error  # convenient alias


def _to_safe_path_param_name(matched_parameter):
    """Creates a safe string to be used as a regex group name.

    Only alphanumeric characters and underscore are allowed in variable name
    tokens, and numeric are not allowed as the first character.

    We cast the matched_parameter to base32 (since the alphabet is safe),
    strip the padding (= not safe) and prepend with _, since we know a token
    can begin with underscore.

    Args:
      matched_parameter: A string containing the parameter matched from the URL
        template.

    Returns:
      A string that's safe to be used as a regex group name.
    """
    return '_' + base64.b32encode(matched_parameter).rstrip('=')

def compile_path_pattern(pattern):
    r"""Generates a compiled regex pattern for a path pattern.

    e.g. '/MyApi/v1/notes/{id}'
    returns re.compile(r'/MyApi/v1/notes/(?P<id>[^/?#\[\]{}]*)')

    Args:
      pattern: A string, the parameterized path pattern to be checked.

    Returns:
      A compiled regex object to match this path pattern.
    """

    def replace_variable(match):
      """Replaces a {variable} with a regex to match it by name.

      Changes the string corresponding to the variable name to the base32
      representation of the string, prepended by an underscore. This is
      necessary because we can have message variable names in URL patterns
      (e.g. via {x.y}) but the character '.' can't be in a regex group name.

      Args:
        match: A regex match object, the matching regex group as sent by
          re.sub().

      Returns:
        A string regex to match the variable by name, if the full pattern was
        matched.
      """
      if match.lastindex > 1:
        var_name = _to_safe_path_param_name(match.group(2))
        return '%s(?P<%s>%s)' % (match.group(1), var_name,
                                 _PATH_VALUE_PATTERN)
      return match.group(0)

    pattern = re.sub('(/|^){(%s)}(?=/|$|:)' % _PATH_VARIABLE_PATTERN,
                     replace_variable, pattern)
    return re.compile(pattern + '/?$')
