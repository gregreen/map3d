#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  rate_limit.py
#  Decorator to rate limit a given view.
#
#  Adapted by Gregory Green from http://flask.pocoo.org/snippets/70/
#  Originally by Armin Ronacher
#

from map3d import app, redis

import time

from flask import request, g
import functools


class RateLimit(object):
    expiration_window = 10

    def __init__(self, key_prefix, limit, per, send_x_headers):
        # Calculate the next multiple of <per> above current time
        self.reset = (int(time.time()) // per) * per + per

        # Set key to combination of the prefix and the reset time
        self.key = key_prefix + str(self.reset)

        # <limit> requests are allowed per <per> seconds
        self.limit = limit
        self.per = per

        # If true, send header information back to IP after each request
        # detailing usage and rate-limit info
        self.send_x_headers = send_x_headers

        # Set the key (in the Redis store) with an expiration time
        p = redis.pipeline()
        p.incr(self.key)
        p.expireat(self.key, self.reset + self.expiration_window)

        self.current = min(p.execute()[0], limit)

    remaining = property(lambda x: x.limit - x.current)
    over_limit = property(lambda x: x.current >= x.limit)


def get_view_rate_limit():
    return getattr(g, '_view_rate_limit', None)

def on_over_limit(rlimit):
    return 'You have hit the rate limit for this resource.', 429

def ratelimit(limit, per=300, send_x_headers=False,
              over_limit=on_over_limit,
              scope_func=lambda: request.remote_addr,
              key_func=lambda: request.endpoint):

    def decorator(f):
        @functools.wraps(f)
        def rate_limited(*args, **kwargs):
            # The key prefix is, by default, a combination of the IP and view addresses
            key_prefix = 'rate-limit/%s/%s/' % (key_func(), scope_func())

            # Construct the rate limiter, and save it to flask.g
            rlimit = RateLimit(key_prefix, limit, per, send_x_headers)
            g._view_rate_limit = rlimit

            # Return a standard response if the IP has reached their limit
            if (over_limit is not None) and rlimit.over_limit:
                return over_limit(rlimit)

            return f(*args, **kwargs)

        return rate_limited
        #return update_wrapper(rate_limited, f)

    return decorator

@app.after_request
def inject_x_rate_headers(response):
    limit = get_view_rate_limit()

    if limit and limit.send_x_headers:
        h = response.headers
        h.add('X-RateLimit-Remaining', str(limit.remaining))
        h.add('X-RateLimit-Limit', str(limit.limit))
        h.add('X-RateLimit-Reset', str(limit.reset))

    return response
