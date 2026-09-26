-- Atomic fixed-window rate limit check with optional per-client limit.
--
-- KEYS[1] = counter prefix, example: rl:{user_123}
-- KEYS[2] = per-client limit key, example: rl:limit:{user_123}
--
-- ARGV[1] = default limit
-- ARGV[2] = window size in seconds
--
-- Returns:
-- {
--   allowed,          -- 1 = allowed, 0 = denied
--   remaining,        -- remaining requests in current window
--   reset_at,         -- unix time when current window ends
--   current,          -- current counter value
--   effective_limit   -- limit actually used for this client
-- }

redis.replicate_commands()

local default_limit = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])

local effective_limit = default_limit

local custom_limit = redis.call('GET', KEYS[2])

if custom_limit then
    local parsed_limit = tonumber(custom_limit)

    if parsed_limit and parsed_limit >= 0 then
        effective_limit = math.floor(parsed_limit)
    end
end

local redis_time = redis.call('TIME')
local now_seconds = tonumber(redis_time[1])

local window_number = math.floor(now_seconds / window_seconds)
local reset_at = (window_number + 1) * window_seconds

local ttl_seconds = reset_at - now_seconds + 1

if ttl_seconds <= 0 then
    ttl_seconds = 1
end

local counter_key = KEYS[1] .. ':' .. window_number

local current = redis.call('INCR', counter_key)

if current == 1 then
    redis.call('EXPIRE', counter_key, ttl_seconds)
end

if current > effective_limit then
    return {0, 0, reset_at, current, effective_limit}
end

return {1, effective_limit - current, reset_at, current, effective_limit}