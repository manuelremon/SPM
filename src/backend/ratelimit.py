import time
from collections import deque, defaultdict
from functools import wraps
from flask import request, jsonify

_buckets = defaultdict(deque)  # key -> deque[timestamps]

def _now(): return time.monotonic()

def _check(key, limit, window):
    q = _buckets[key]
    t = _now()
    # purga
    cutoff = t - window
    while q and q[0] <= cutoff:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(t)
    return True

def limit(key='rl', limit=30, window=60):
    """Token bucket simple por IP: limit reqs cada window segundos."""
    def deco(f):
        @wraps(f)
        def w(*a, **kw):
            ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or 'na').split(',')[0].strip()
            k = f'{key}:{ip}'
            if not _check(k, limit, window):
                return jsonify({'error':'rate_limited'}), 429
            return f(*a, **kw)
        return w
    return deco
