from __future__ import absolute_import

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
