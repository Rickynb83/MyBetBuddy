"""
Simple cache implementation for MyBetBuddy predictions.
"""

# Simple in-memory cache
cache = {}

def cache_get(key):
    """Get a value from the cache."""
    if key in cache:
        return cache[key]
    return None

def cache_set(key, value, ttl=None):
    """Set a value in the cache."""
    cache[key] = value
    return value

def cache_delete(key):
    """Delete a value from the cache."""
    if key in cache:
        del cache[key]
    return None

def cache_clear():
    """Clear the entire cache."""
    cache.clear() 