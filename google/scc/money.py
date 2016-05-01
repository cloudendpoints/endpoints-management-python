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

"""money provides funcs for working with `Money` instances.

:func:`check_valid` determines if a `Money` instance is valid
:func:`add` adds two `Money` instances together

"""

from __future__ import absolute_import

import google.apigen.servicecontrol_v1_messages as messages

import logging
import sys

logger = logging.getLogger(__name__)

_INT64_MAX = sys.maxint
_INT64_MIN = -sys.maxint - 1
_BILLION = 1000000000
MAX_NANOS = _BILLION - 1
_MSG_3_LETTERS_LONG = 'The currency code is not 3 letters long'
_MSG_UNITS_NANOS_MISMATCH = 'The signs of the units and nanos do not match'
_MSG_NANOS_OOB = 'The nanos field must be between -999999999 and 999999999'


def check_valid(money):
    """Determine if an instance of `Money` is valid.

    Args:
      money (:class:`google.apigen.servicecontrol_v1_messages.Money`): the
        instance to test

    Raises:
      ValueError: if the money instance is invalid
    """
    if not isinstance(money, messages.Money):
        raise ValueError('Inputs should be of type %s' % (messages.Money,))
    currency = money.currencyCode
    if not currency or len(currency) != 3:
        raise ValueError(_MSG_3_LETTERS_LONG)
    units = money.units
    nanos = money.nanos
    if ((units > 0) and (nanos < 0)) or ((units < 0) and (nanos > 0)):
        raise ValueError(_MSG_UNITS_NANOS_MISMATCH)
    if abs(nanos) > MAX_NANOS:
        raise ValueError(_MSG_NANOS_OOB)


def add(a, b, allow_overflow=False):
    """Adds two instances of `Money`.

    Args:
      a (:class:`google.apigen.servicecontrol_v1_messages.Money`): one money
        value
      b (:class:`google.apigen.servicecontrol_v1_messages.Money`): another
        money value
      allow_overflow: determines if the addition is allowed to overflow

    Return:
      `Money`: an instance of Money

    Raises:
      ValueError: if the inputs do not have the same currency code
      OverflowError: if the sum overflows and allow_overflow is not `True`
    """
    for m in (a, b):
        if not isinstance(m, messages.Money):
            raise ValueError('Inputs should be of type %s' % (messages.Money,))
    if a.currencyCode != b.currencyCode:
        raise ValueError('Money values need the same currency to be summed')
    nano_carry, nanos_sum = _sum_nanos(a, b)
    units_sum_no_carry = a.units + b.units
    units_sum = units_sum_no_carry + nano_carry

    # Adjust when units_sum and nanos_sum have different signs
    if units_sum > 0 and nanos_sum < 0:
        units_sum -= 1
        nanos_sum += _BILLION
    elif units_sum < 0 and nanos_sum > 0:
        units_sum += 1
        nanos_sum -= _BILLION

    # Return the result, detecting overflow if it occurs
    sign_a = _sign_of(a)
    sign_b = _sign_of(b)
    if sign_a > 0 and sign_b > 0 and units_sum >= _INT64_MAX:
        if not allow_overflow:
            raise OverflowError('Money addition positive overflow')
        else:
            return messages.Money(units=_INT64_MAX,
                                  nanos=MAX_NANOS,
                                  currencyCode=a.currencyCode)
    elif (sign_a < 0 and sign_b < 0 and
          (units_sum_no_carry <= -_INT64_MAX or units_sum <= -_INT64_MAX)):
        if not allow_overflow:
            raise OverflowError('Money addition negative overflow')
        else:
            return messages.Money(units=_INT64_MIN,
                                  nanos=-MAX_NANOS,
                                  currencyCode=a.currencyCode)
    else:
        return messages.Money(units=units_sum,
                              nanos=nanos_sum,
                              currencyCode=a.currencyCode)


def _sum_nanos(a, b):
    the_sum = a.nanos + b.nanos
    carry = 0
    if the_sum > _BILLION:
        carry = 1
        the_sum -= _BILLION
    elif the_sum <= -_BILLION:
        carry = -1
        the_sum += _BILLION
    return carry, the_sum


def _sign_of(money):
    """Determines the amount sign of a money instance

    Args:
      money (:class:`google.apigen.servicecontrol_v1_messages.Money`): the
        instance to test

    Return:
      int: 1, 0 or -1

    """
    units = money.units
    nanos = money.nanos
    if units:
        if units > 0:
            return 1
        elif units < 0:
            return -1
    if nanos:
        if nanos > 0:
            return 1
        elif nanos < 0:
            return -1
    return 0
