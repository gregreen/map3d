#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  redis_logger.py
#  
#  Copyright 2015 greg <greg@greg-UX301LAA>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

from map3d import redis

import time, datetime
from functools import wraps

#from redis import Redis
#redis = Redis()


def timestamp(func):
    def append_timestamp(*args, **kwargs):
        time_prefix = datetime.datetime.now().strftime('%Y-%b-%d: %H:%M:%S')
        return '[{0}] {1}'.format(time_prefix, func(*args, **kwargs))
    
    return append_timestamp


class Logger(object):
    '''
    A thread-safe logging object. Multiple processes can instantiate a
    Logger() object that writes to the same file. A Redis-based lock
    mediates access to the log file.
    '''
    
    def __init__(self, log_name, log_fname, flush_every=3):
        self.log_name = log_name
        self.log_fname = log_fname
        self.p = redis.pipeline()
        
        self.flush_every = flush_every
        self.counter = 0
    
    def __del__(self):
        self.flush()
    
    @timestamp
    def compose(self, message):
        return message
    
    def write(self, message):
        self.p.rpush(self.log_name, self.compose(message)).execute()
        
        self.counter += 1
        if self.counter >= self.flush_every:
            self.flush()
            self.counter = 0
    
    def flush(self):
        with Lock(self.log_name + '_lock', timeout=0.1):
            # Pop all elements from the list
            n = self.p.llen(self.log_name).execute()[0]
            
            for k in xrange(n):
                self.p.lpop(self.log_name)
            
            msg = self.p.execute()
            
            lines = '\n'.join(msg) + '\n'
            
            f = open(self.log_fname, 'a')
            f.write(lines)
            f.close()


class Lock(object):
    def __init__(self, key, expires=60, timeout=10):
        """
        Distributed locking using Redis SETNX and GETSET.

        Usage::

            with Lock('my_lock'):
                print "Critical section"

        :param  expires     We consider any existing lock older than
                            ``expires`` seconds to be invalid in order to
                            detect crashed clients. This value must be higher
                            than it takes the critical section to execute.
        :param  timeout     If another client has already obtained the lock,
                            sleep for a maximum of ``timeout`` seconds before
                            giving up. A value of 0 means we never wait.
        """

        self.key = key
        self.timeout = timeout
        self.expires = expires

    def __enter__(self):
        timeout = self.timeout
        while timeout >= 0:
            expires = time.time() + self.expires + 1

            if redis.setnx(self.key, expires):
                # We gained the lock; enter critical section
                return

            current_value = redis.get(self.key)

            # We found an expired lock and nobody raced us to replacing it
            if current_value and float(current_value) < time.time() and \
                redis.getset(self.key, expires) == current_value:
                    return

            timeout -= 1
            time.sleep(1)

        raise LockTimeout("Timeout whilst waiting for lock")

    def __exit__(self, exc_type, exc_value, traceback):
        redis.delete(self.key)

class LockTimeout(BaseException):
    pass


def main():
    logger = Logger('test_log', 'test_log.txt')
    
    for k in xrange(100):
        logger.write('hello')
        logger.write('world')
    
    #logger.flush()
    
    return 0

if __name__ == '__main__':
    main()

