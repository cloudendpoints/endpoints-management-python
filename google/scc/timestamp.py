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

"""timestamp provides functions that support working with timestamps.

:func:`to_rfc3339` and :func:`from_rfc3339` convert between standard python
datetime types and the rfc3339 representation used in json messsages.

:func:`compare` allows comparison of any timestamp representation, either the
standard python datetime types, or an rfc3339 string representation

"""

from __future__ import absolute_import

import datetime
import logging

import strict_rfc3339

logger = logging.getLogger(__name__)


_EPOCH_START = datetime.datetime(1970, 1, 1)


def compare(a, b):
    """Compares two timestamps.

    ``a`` and ``b`` must be the same type, in addition to normal
    representations of timestamps that order naturally, they can be rfc3339
    formatted strings.

    Args:
      a (string|object): a timestamp
      b (string|object): another timestamp

    Returns:
      int: -1 if a < b, 0 if a == b or 1 if a > b

    Raises:
      ValueError: if a or b are not the same type
      ValueError: if a or b strings but not in valid rfc3339 format

    """
    a_is_text = isinstance(a, basestring)
    b_is_text = isinstance(b, basestring)
    if type(a) != type(b) and not (a_is_text and b_is_text):
        logger.error('Cannot compare %s to %s, types differ %s!=%s',
                     a, b, type(a), type(b))
        raise ValueError('cannot compare inputs of differing types')

    if a_is_text:
        a = from_rfc3339(a, with_nanos=True)
        b = from_rfc3339(b, with_nanos=True)

    if a < b:
        return -1
    elif a > b:
        return 1
    else:
        return 0


def to_rfc3339(timestamp):
    """Converts ``timestamp`` to an RFC 3339 date string format.

    ``timestamp`` can be either a ``datetime.datetime`` or a
    ``datetime.timedelta``.  Instances of the later are assumed to be a delta
    with the beginining of the unix epoch, 1st of January, 1970

    The returned string is always Z-normalized.  Examples of the return format:
    '1972-01-01T10:00:20.021Z'

    Args:
      timestamp (datetime|timedelta): represents the timestamp to convert

    Returns:
      string: timestamp converted to a rfc3339 compliant string as above

    Raises:
      ValueError: if timestamp is not a datetime.datetime or datetime.timedelta

    """
    if isinstance(timestamp, datetime.datetime):
        timestamp = timestamp - _EPOCH_START
    if not isinstance(timestamp, datetime.timedelta):
        logger.error('Could not convert %s to a rfc3339 time,', timestamp)
        raise ValueError('Invalid timestamp type')
    return strict_rfc3339.timestamp_to_rfc3339_utcoffset(
        timestamp.total_seconds())


def from_rfc3339(rfc3339_text, with_nanos=False):
    """Parse a RFC 3339 date string format to datetime.date.

    Example of accepted format: '1972-01-01T10:00:20.021-05:00'

    - By default, the result is a datetime.datetime
    - If with_nanos is true, the result is a 2-tuple, (datetime.datetime,
    nanos), where the second field represents the possible nanosecond
    resolution component of the second field.

    Args:
      rfc3339_text (string): An rfc3339 formatted date string
      with_nanos (bool): Determines if nanoseconds should be parsed from the
        string

    Raises:
      ValueError: if ``rfc3339_text`` is invalid

    Returns:
      :class:`datetime.datetime`: when with_nanos is False
      tuple(:class:`datetime.datetime`, int): when with_nanos is True

    """
    timestamp = strict_rfc3339.rfc3339_to_timestamp(rfc3339_text)
    result = datetime.datetime.utcfromtimestamp(timestamp)
    if with_nanos:
        return (result, int((timestamp - int(timestamp)) * 1e9))
    else:
        return result
