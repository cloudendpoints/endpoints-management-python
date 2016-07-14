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

"""client provides a complete standalone service control client.

:class:`Client` is a package-level facade that encapsulates all service control
functionality.

The :class:`Loaders` simplify ``Client`` initialization.

``Client`` needs to stop and start a thread to implement its behaviour.  In most
environments, the default thread class is sufficient.  However, on Google App Engine,
it's necessary to use the appengine specific threading class instead.

:func:`use_gae_thread` and `use_default_thread` can be used to change the thread
class used by new instances of `Client`.

Example:

  >>> from google.scc import client
  >>>
  >>> # use on appengine with package-default settings
  >>> service_name = 'my-appengine-service-name'
  >>> client.use_gae_thread()
  >>> gae_client = client.Loaders.DEFAULT.load(service_name)
  >>> gae_client.start()

"""
from __future__ import absolute_import

from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import os
import sched
import threading
import time

from . import CheckAggregationOptions, ReportAggregationOptions, to_cache_timer
import google.apigen.servicecontrol_v1_client as http_client
from .aggregators import check_request, report_request


logger = logging.getLogger(__name__)


CONFIG_VAR = 'ENDPOINTS_SERVER_CONFIG_FILE'


def _load_from_well_known_env():
    if CONFIG_VAR not in os.environ:
        logger.info('did not load server config; no environ var %s', CONFIG_VAR)
        return None
    json_file = os.environ[CONFIG_VAR]
    if not os.path.exists(os.environ[CONFIG_VAR]):
        logger.warn('did not load service; missing config file %s', json_file)
        return None
    try:
        with open(json_file) as f:
            json_dict = json.load(f)
            check_json = json_dict['checkAggregatorConfig']
            report_json = json_dict['reportAggregatorConfig']
            check_options = CheckAggregationOptions(
                num_entries=check_json['cacheEntries'],
                expiration=check_json['responseExpirationMs'],
                flush_interval=timedelta(
                    milliseconds=check_json['flushIntervalMs']))
            report_options = ReportAggregationOptions(
                num_entries=report_json['cacheEntries'],
                flush_interval=timedelta(
                    milliseconds=report_json['flushIntervalMs']))
            return check_options, report_options
    except (KeyError, ValueError):
        logger.warn('did not load service; bad json config file %s', json_file)
        return None


def _load_default():
    return CheckAggregationOptions(), ReportAggregationOptions()


class Loaders(Enum):
    """Enumerates the functions used to load clients from server configs."""
    # pylint: disable=too-few-public-methods
    ENVIRONMENT = (_load_from_well_known_env,)
    DEFAULT = (_load_default,)

    def __init__(self, load_func):
        """Constructor.

        load_func is used to load a client config
        """
        self._load_func = load_func

    def load(self, service_name, **kw):
        check_opts, report_opts = self._load_func(**kw)
        return Client(service_name, check_opts, report_opts, **kw)


_THREAD_CLASS = threading.Thread


class Client(object):
    """Client is a package-level facade that encapsulates all service control
    functionality.

    Using one of the :class:`Loaders` makes it easy to initialize ``Client``
    instances.

    Example:

      >>> from google.scc import client
      >>> service_name = 'my-service-name'
      >>>
      >>> # create an scc client using the package default values
      >>> default_client = client.Loaders.DEFAULT.load(service_name)

      >>> # create an scc client by loading configuration from the
      >>> # a JSON file configured by an environment variable
      >>> json_conf_client = client.Loaders.ENVIRONMENT(service_name)

    Client is thread-compatible

    """
    # pylint: disable=too-many-instance-attributes

    def __init__(self,
                 service_name,
                 check_options,
                 report_options,
                 timer=datetime.now):
        """

        Args:
            service_name (str): the name of the service to be controlled
            check_options (:class:google.scc.CheckAggregationOptions): configures
               checking
            report_options (:class:google.scc.ReportAggregationOptions): configures
               reporting
            timer (:func[[datetime.datetime]]: used to obtain the current time.
        """
        self._check_aggregator = check_request.Aggregator(service_name,
                                                          check_options,
                                                          timer=timer)
        self._report_aggregator = report_request.Aggregator(service_name,
                                                            report_options,
                                                            timer=timer)
        self._running = False
        self._scheduler = None
        self._stopped = False
        self._timer = timer
        self._thread = None
        self._transport = http_client.ServicecontrolV1()
        self._lock = threading.RLock()

    def start(self):
        """Starts processing.

        Calling this method

        - starts the thread that regularly flushes all enabled caches.
        - enables the other methods on the instance to be called successfully

        I.e, even when the configuration disables aggregation, it is invalid to
        access the other methods of an instance until ``start`` is called -
        Calls to other public methods will fail with an AssertionError.

        """
        with self._lock:
            if self._running:
                logger.info('%s is already started', self)
            self._stopped = False
            self._running = True
            self._thread = _THREAD_CLASS(self._schedule_flushes)
            self._thread.start()

    def stop(self):
        """Halts processing

        This will lead to the caches being cleared and a stop to the current
        processing thread.

        """

        self._assert_is_running()
        with self._lock:
            self._stopped = True
            if self._scheduler and self._scheduler.empty():
                # if there are events scheduled, then _running will subsequently
                # be set False by the scheduler thread.  This handles the
                # case where there are no events, e.g because all aggreagation
                # was disabled
                self._running = False

    def check(self, check_req):
        """Process a check_request.

        The req is first passed to the check_aggregator.  If there is a valid
        cached response, that is returned, otherwise a response is obtained from
        the transport.

        Args:
          check_req (``ServicecontrolServicesCheckRequest``): to be sent to
            the service control service

        Returns:
           ``CheckResponse``: either the cached response if one is applicable
            or a response from making a transport request, or None if
            if the request to the transport fails

        """

        self._assert_is_running()
        res = self._check_aggregator.check(check_req)
        if res:
            return res

        # Application code should not fail because check request's don't
        # complete, They should fail open, so here simply log the error and
        # return None to indicate that no response was obtained
        try:
            return self._transport.services.check(check_req)
        except Exception:  # pylint: disable=broad-except
            logger.error('direct send of check request failed %s', check_request)
            return None

    def report(self, report_req):
        """Processes a report request.

        It will aggregate it with prior report_requests to be send later
        or it will send it immediately if that's appropriate.
        """
        self._assert_is_running()
        if not self._report_aggregator.report(report_req):
            logger.info('need to send for a report request directly')
            try:
                self._transport.services.report(report_req)
            except Exception:  # pylint: disable=broad-except
                logger.error('direct send for report request failed')

    def add_check_response(self, req, resp):
        """Adds the response from sending to `req` to this instance's cache.

        Args:
          req (`ServicecontrolServicesCheckRequest`): the request
          resp (CheckResponse): the response from sending the request
        """
        self._assert_is_running()
        self._check_aggregator.add_response(req, resp)

    def _assert_is_running(self):
        assert self._running, '%s needs to be running' % (self,)

    def _schedule_flushes(self):
        self._scheduler = sched.scheduler(to_cache_timer(self._timer), time.sleep)
        self._flush_schedule_check_aggregator()
        self._flush_schedule_report_aggregator()
        self._scheduler.run()  # this should blocks until self._stopped is set,
        logger.info('scheduler.run completed, %s will exit', threading.current_thread())

    def _check_if_stopped(self):
        with self._lock:
            if not self._stopped:
                return False

            self._check_aggregator.clear()
            self._report_aggregator.clear()
            self._running = False
            return True

    def _flush_schedule_check_aggregator(self):
        if self._check_if_stopped:
            return

        flush_period = self._check_aggregator.flush_interval.total_seconds()
        if flush_period < 0:  # caching is disabled
            return

        logger.debug('flushing the check aggregator')
        for req in self._check_aggregator.flush():
            try:
                resp = self._transport.services.check(req)
            except Exception:  # pylint: disable=broad-except
                logger.error('failed to flush check_req %s', req)
            self.add_check_response(req, resp)

        # schedule a repeat of this method
        self._scheduler.enter(
            flush_period,
            2,  # a higher priority than report flushes
            self._flush_schedule_check_aggregator,
            ()
        )

    def _flush_schedule_report_aggregator(self):
        if self._check_if_stopped:
            return

        flush_period = self._report_aggregator.flush_interval.total_seconds()
        if flush_period < 0:  # caching is disabled
            return

        logger.debug('flushing the report aggregator')
        for req in self._report_aggregator.flush():
            try:
                self._transport.services.report(req)
            except Exception:  # pylint: disable=broad-except
                logger.error('failed to flush report_req %s', req)

        # schedule a repeat of this method
        self._scheduler.enter(
            flush_period,
            1,  # a lower priority than check flushes
            self._flush_schedule_report_aggregator,
            ()
        )


def use_default_thread():
    """Makes ``Client``s started after this use the standard Thread class."""
    global _THREAD_CLASS  # pylint: disable=global-statement
    _THREAD_CLASS = threading.Thread


def use_gae_thread():
    """Makes ``Client``s started after this use the appengine thread class."""
    global _THREAD_CLASS  # pylint: disable=global-statement
    try:
        from google.appengine.api.background_thread import background_thread
        _THREAD_CLASS = background_thread.BackgroundThread
    except ImportError:
        logger.error(
            'Could not install appengine background threads!'
            ' Please install the python AppEngine SDK and use this from there'
        )
