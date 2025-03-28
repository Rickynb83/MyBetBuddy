"""
Simple cache implementation for MyBetBuddy predictions.
"""

import os
import json
from datetime import datetime, timedelta
import hashlib

class DataCache:
    def __init__(self, cache_dir='cache'):
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
        print(f"DEBUG: Cache initialized with directory {self.cache_dir}")
        
    def _ensure_cache_dir(self):
        """Ensure the cache directory exists."""
        if not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
                print(f"DEBUG: Created cache directory {self.cache_dir}")
            except Exception as e:
                print(f"ERROR: Failed to create cache directory: {str(e)}")
    
    def _get_cache_key(self, data_type, params):
        """Generate a unique cache key for the data type and parameters."""
        # Sort parameters to ensure consistent keys
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params)
        return hashlib.md5(f"{data_type}:{param_str}".encode()).hexdigest()
    
    def _get_cache_path(self, cache_key):
        """Get the full path for a cache file."""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get(self, data_type, params, max_age_hours=24):
        """
        Get cached data if it exists and is not too old.
        
        Args:
            data_type: Type of data (e.g., 'team_stats', 'h2h')
            params: Dictionary of parameters used to fetch the data
            max_age_hours: Maximum age of cached data in hours
            
        Returns:
            Cached data if valid, None otherwise
        """
        cache_key = self._get_cache_key(data_type, params)
        cache_path = self._get_cache_path(cache_key)
        
        print(f"DEBUG: Checking cache for {data_type} with key {cache_key}")
        
        # Check for Heroku environment - skip file cache on Heroku
        if os.environ.get('DYNO'):
            print(f"DEBUG: Running on Heroku, skipping file cache lookup")
            return None
        
        if not os.path.exists(cache_path):
            print(f"DEBUG: Cache miss - no file at {cache_path}")
            return None
            
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
                
            # Check if cache is too old
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time > timedelta(hours=max_age_hours):
                print(f"DEBUG: Cache expired - created at {cache_time}")
                return None
            
            print(f"DEBUG: Cache hit for {data_type}")    
            return cache_data['data']
            
        except Exception as e:
            print(f"ERROR: Cache read error: {str(e)}")
            return None
    
    def set(self, data_type, params, data):
        """
        Cache data with timestamp.
        
        Args:
            data_type: Type of data (e.g., 'team_stats', 'h2h')
            params: Dictionary of parameters used to fetch the data
            data: The data to cache
        """
        cache_key = self._get_cache_key(data_type, params)
        cache_path = self._get_cache_path(cache_key)
        
        # Check for Heroku environment - skip file cache on Heroku
        if os.environ.get('DYNO'):
            print(f"DEBUG: Running on Heroku, skipping file cache write")
            return
        
        print(f"DEBUG: Caching {data_type} with key {cache_key}")
        
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
                print(f"DEBUG: Successfully cached {data_type}")
        except Exception as e:
            print(f"ERROR: Cache write error: {str(e)}")
    
    def clear(self, data_type=None):
        """
        Clear cache files.
        
        Args:
            data_type: Optional type of data to clear. If None, clears all cache.
        """
        # Check for Heroku environment - skip file cache on Heroku
        if os.environ.get('DYNO'):
            print(f"DEBUG: Running on Heroku, skipping cache clear")
            return
            
        print(f"DEBUG: Clearing cache for {data_type if data_type else 'all types'}")
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    if data_type is None or filename.startswith(data_type):
                        try:
                            os.remove(os.path.join(self.cache_dir, filename))
                            print(f"DEBUG: Removed cache file {filename}")
                        except Exception as e:
                            print(f"ERROR: Failed to remove cache file {filename}: {str(e)}")
        except Exception as e:
            print(f"ERROR: Failed to list cache directory: {str(e)}")

# Simple in-memory cache for Heroku
_memory_cache = {}

def cache_get(key):
    """Get a value from the in-memory cache"""
    if key in _memory_cache:
        value, expiry = _memory_cache[key]
        if datetime.now() < expiry:
            return value
        # Remove expired entry
        del _memory_cache[key]
    return None

def cache_set(key, value, ttl=3600):
    """Set a value in the in-memory cache with TTL in seconds"""
    expiry = datetime.now() + timedelta(seconds=ttl)
    _memory_cache[key] = (value, expiry)

def cache_delete(key):
    """Delete a value from the in-memory cache"""
    if key in _memory_cache:
        del _memory_cache[key]

def cache_clear():
    """Clear the entire in-memory cache"""
    _memory_cache.clear()

# Create a global cache instance
cache = DataCache() 