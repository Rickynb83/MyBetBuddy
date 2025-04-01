"""
Simple cache implementation for MyBetBuddy predictions.
"""

import os
import json
from datetime import datetime, timedelta
import hashlib
from typing import Optional, Dict, Any

class DataCache:
    def __init__(self, cache_dir='cache'):
        self.cache_dir = cache_dir
        self._memory_cache = {}
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
    
    def _get_cache_key(self, data_type: str, params: Dict) -> str:
        """Generate a unique cache key for the data type and parameters."""
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params)
        return f"{data_type}:{hashlib.md5(param_str.encode()).hexdigest()}"
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get the full path for a cache file."""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def _is_cache_valid(self, cache_data: Dict, max_age_hours: int, data_type: str) -> bool:
        """Check if cache is valid based on age and match times."""
        try:
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time > timedelta(hours=max_age_hours):
                print(f"DEBUG: Cache expired - created at {cache_time}")
                return False
            
            # For standings and fixtures, check if any matches have been played since cache was created
            if data_type in ['standings', 'fixtures']:
                if 'last_match_time' in cache_data:
                    last_match_time = datetime.fromisoformat(cache_data['last_match_time'])
                    if last_match_time > cache_time:
                        print(f"DEBUG: New matches played since cache was created")
                        return False
            
            return True
        except Exception as e:
            print(f"ERROR: Cache validation error: {str(e)}")
            return False
    
    def get(self, data_type: str, params: Dict, max_age_hours: Optional[int] = None) -> Optional[Dict]:
        """
        Get cached data if it exists and is not too old.
        
        Args:
            data_type: Type of data (e.g., 'team_stats', 'h2h', 'standings', 'fixtures')
            params: Dictionary of parameters used to fetch the data
            max_age_hours: Maximum age of cached data in hours. If None, uses default based on data_type
            
        Returns:
            Cached data if valid, None otherwise
        """
        # Set default cache durations based on data type
        if max_age_hours is None:
            if data_type in ['standings', 'fixtures']:
                max_age_hours = 24 * 7  # 7 days for standings and fixtures
            elif data_type == 'predictions':
                max_age_hours = 24 * 7  # 7 days for predictions
            else:
                max_age_hours = 24  # 1 day for other data
        
        cache_key = self._get_cache_key(data_type, params)
        
        try:
            # Try in-memory cache first
            if cache_key in self._memory_cache:
                cache_data = self._memory_cache[cache_key]
                if self._is_cache_valid(cache_data, max_age_hours, data_type):
                    return cache_data['data']
                else:
                    del self._memory_cache[cache_key]
            
            # Try file-based cache
            cache_path = self._get_cache_path(cache_key)
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        cache_data = json.load(f)
                        if self._is_cache_valid(cache_data, max_age_hours, data_type):
                            # Update in-memory cache
                            self._memory_cache[cache_key] = cache_data
                            return cache_data['data']
                        else:
                            # Remove expired file cache
                            os.remove(cache_path)
                except Exception as e:
                    print(f"ERROR: File cache read error: {str(e)}")
            
            return None
            
        except Exception as e:
            print(f"ERROR: Cache read error: {str(e)}")
            return None
    
    def set(self, data_type: str, params: Dict, data: Any, last_match_time: Optional[datetime] = None):
        """
        Cache data with timestamp.
        
        Args:
            data_type: Type of data (e.g., 'team_stats', 'h2h', 'standings', 'fixtures')
            params: Dictionary of parameters used to fetch the data
            data: The data to cache
            last_match_time: Optional timestamp of the most recent match
        """
        cache_key = self._get_cache_key(data_type, params)
        
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        if last_match_time:
            cache_data['last_match_time'] = last_match_time.isoformat()
        
        try:
            # Update in-memory cache
            self._memory_cache[cache_key] = cache_data
            
            # Update file cache
            cache_path = self._get_cache_path(cache_key)
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
                
            print(f"DEBUG: Successfully cached {data_type}")
            
        except Exception as e:
            print(f"ERROR: Cache write error: {str(e)}")
    
    def clear(self, data_type: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            data_type: Optional type of data to clear. If None, clears all cache.
        """
        try:
            # Clear in-memory cache
            if data_type:
                keys_to_remove = [k for k in self._memory_cache.keys() if k.startswith(f"{data_type}:")]
                for k in keys_to_remove:
                    del self._memory_cache[k]
            else:
                self._memory_cache.clear()
            
            # Clear file cache
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    if data_type is None or filename.startswith(f"{data_type}:"):
                        try:
                            os.remove(os.path.join(self.cache_dir, filename))
                        except Exception as e:
                            print(f"ERROR: Failed to remove cache file {filename}: {str(e)}")
                    
            print(f"DEBUG: Cleared cache for {data_type if data_type else 'all types'}")
            
        except Exception as e:
            print(f"ERROR: Cache clear error: {str(e)}")

# Create a global cache instance
cache = DataCache() 