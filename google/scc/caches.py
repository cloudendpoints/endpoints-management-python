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

"""caches provide functions and classes used to support caching.

caching is provide by extensions of the cache classes provided by the
cachetools open-source library.

:func:`create` creates a cache instance specifed by either
:class:`google.scc.CheckAggregationOptions` or a
:class:`google.scc.ReportAggregationOptions`

"""

from __future__ import absolute_import

# pylint: disable=too-many-ancestors
#
# It affects the DequeOutTTLCache and DequeOutLRUCache which extend
# cachetools.TTLCache and cachetools.LRUCache respectively.  Within cachetools,
# those classes each extend Cache, which itself extends DefaultMapping. It does
# makes sense to have this chain of ancestors, so it's right the disable the
# warning here.

import collections
import logging
import threading
from datetime import timedelta

import cachetools

from google.scc import CheckAggregationOptions, ReportAggregationOptions, to_cache_timer

logger = logging.getLogger(__name__)


ZERO_INTERVAL = timedelta()


def create(options, timer=None):
    """Create a cache specified by ``options``

    ``options`` is an instance of either
    :class:`google.scc.CheckAggregationOptions` or
    :class:`google.scc.ReportAggregationOptions`

    The returned cache is wrapped in a :class:`LockedObject`, requiring it to
    be accessed in a with statement that gives synchronized access

    Example:
      >>> options = CheckAggregationOptions()
      >>> synced_cache = make_cache(options)
      >>> with synced_cache as cache:  #  acquire the lock
      ...    cache['a_key'] = 'a_value'

    Args:
      options (object): an instance of either of the options classes

    Returns:
      :class:`cachetools.Cache`: the cache implementation specified by options
        or None: if options is ``None`` or if options.num_entries < 0

    Raises:
       ValueError: if options is not a support type

    """
    if not (isinstance(options, CheckAggregationOptions) or
            isinstance(options, ReportAggregationOptions)):
        logger.error('make_cache(): bad options %s', options)
        raise ValueError('Invalid options')

    if (options.num_entries <= 0):
        return None

    if (options.flush_interval > ZERO_INTERVAL):
        # options always has a flush_interval, but may have an expiration
        # field. If the expiration is present, use that instead of the
        # flush_interval for the ttl
        ttl = getattr(options, 'expiration', options.flush_interval)
        return LockedObject(
            DequeOutTTLCache(
                options.num_entries,
                ttl=ttl.total_seconds(),
                timer=to_cache_timer(timer)
            ))

    return LockedObject(DequeOutLRUCache(options.num_entries))


class DequeOutTTLCache(cachetools.TTLCache):
    """Extends ``TTLCache`` so that expired items are placed in a ``deque``."""

    def __init__(self, maxsize, ttl, out_deque=None, **kw):
        """Constructor.

        Args:
          maxsize (int): the maximum number of entries in the queue
          ttl (int): the ttl for entries added to the cache
          out_deque :class:`collections.deque`: a `deque` in which to add items
            that expire from the cache
          **kw: the other keyword args supported by the constructor to
            :class:`cachetools.TTLCache`

        Raises:
          ValueError: if out_deque is not a collections.deque

        """
        super(DequeOutTTLCache, self).__init__(maxsize, ttl, **kw)
        if out_deque is None:
            out_deque = collections.deque()
        elif not isinstance(out_deque, collections.deque):
            raise ValueError('out_deque should be a collections.deque')
        self._out_deque = out_deque
        self._tracking = {}

    def __setitem__(self, key, value, **kw):
        super(DequeOutTTLCache, self).__setitem__(key, value, **kw)
        self._tracking[key] = value

    @property
    def out_deque(self):
        """The :class:`collections.deque` to which expired items are added."""
        self.expire()
        expired = dict((k, v) for (k, v) in self._tracking.items()
                       if self.get(k) is None)
        for k, v in expired.items():
            del self._tracking[k]
            self._out_deque.append(v)
        return self._out_deque


class DequeOutLRUCache(cachetools.LRUCache):
    """Extends ``LRUCache`` so that expired items are placed in a ``deque``."""

    def __init__(self, maxsize, out_deque=None, **kw):
        """Constructor.

        Args:
          maxsize (int): the maximum number of entries in the queue
          out_deque :class:`collections.deque`: a `deque` in which to add items
            that expire from the cache
          **kw: the other keyword args supported by constructor to
            :class:`cachetools.LRUCache`

        Raises:
          ValueError: if out_deque is not a collections.deque

        """
        super(DequeOutLRUCache, self).__init__(maxsize, **kw)
        if out_deque is None:
            out_deque = collections.deque()
        elif not isinstance(out_deque, collections.deque):
            raise ValueError('out_deque should be collections.deque')
        self._out_deque = out_deque
        self._tracking = {}

    def __setitem__(self, key, value, **kw):
        super(DequeOutLRUCache, self).__setitem__(key, value, **kw)
        self._tracking[key] = value

    @property
    def out_deque(self):
        """The :class:`collections.deque` to which expired items are added."""
        expired = dict((k, v) for (k, v) in iter(self._tracking.items())
                       if self.get(k) is None)
        for k, v in iter(expired.items()):
            del self._tracking[k]
            self._out_deque.append(v)
        return self._out_deque


class LockedObject(object):
    """LockedObject protects an object with a re-entrant lock.

    The lock is required by the context manager protocol.
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, obj):
        self._lock = threading.RLock()
        self._obj = obj

    def __enter__(self):
        self._lock.acquire()
        return self._obj

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self._lock.release()
