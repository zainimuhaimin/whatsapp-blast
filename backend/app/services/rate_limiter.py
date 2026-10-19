"""Token bucket rate limit di Redis (atomic via Lua)."""
import time

import redis

# Kapasitas bucket = limit per jam; refill linear per detik.
_LUA_ACQUIRE = """
local bucket = KEYS[1]
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_per_sec = tonumber(ARGV[3])
local data = redis.call('HMGET', bucket, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then tokens = capacity end
if ts == nil then ts = now end
tokens = math.min(capacity, tokens + (now - ts) * refill_per_sec)
local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end
redis.call('HMSET', bucket, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', bucket, 7200)
return allowed
"""


def acquire(r: redis.Redis, bucket_key: str, limit_per_hour: int) -> bool:
    """
    Ambil 1 token dari bucket. True bila boleh kirim sekarang.
    limit_per_hour <= 0 berarti tidak dibatasi.
    """
    if limit_per_hour <= 0:
        return True
    allowed = r.eval(
        _LUA_ACQUIRE,
        1,
        bucket_key,
        time.time(),
        limit_per_hour,
        limit_per_hour / 3600.0,
    )
    return bool(allowed)
