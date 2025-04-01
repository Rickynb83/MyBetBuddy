from lib.cache import cache
import time
from datetime import datetime, timedelta

def test_cache():
    print("Testing cache system...")
    
    # Test 1: Basic set and get
    print("\nTest 1: Basic set and get")
    cache.set('test', {'id': 1}, {'value': 'test data'})
    result = cache.get('test', {'id': 1})
    print("Cache get result:", result)
    assert result == {'value': 'test data'}, "Basic set/get failed"
    
    # Test 2: Cache invalidation
    print("\nTest 2: Cache invalidation")
    time.sleep(1)  # Wait a second
    cache.set('test', {'id': 1}, {'value': 'updated data'})
    result = cache.get('test', {'id': 1})
    print("Updated cache result:", result)
    assert result == {'value': 'updated data'}, "Cache update failed"
    
    # Test 3: Cache with match time
    print("\nTest 3: Cache with match time")
    now = datetime.now()
    future_match = now + timedelta(hours=1)
    cache.set('standings', {'league_id': 1}, 
              {'value': 'standings data'}, 
              last_match_time=future_match)
    result = cache.get('standings', {'league_id': 1})
    print("Standings cache result:", result)
    assert result is None, "Cache should be invalid due to future match"
    
    # Test 4: Cache clearing
    print("\nTest 4: Cache clearing")
    cache.set('test', {'id': 1}, {'value': 'to be cleared'})
    cache.clear('test')
    result = cache.get('test', {'id': 1})
    print("After clear result:", result)
    assert result is None, "Cache clear failed"
    
    # Test 5: Cache expiration
    print("\nTest 5: Cache expiration")
    cache.set('expire_test', {'id': 1}, {'value': 'expire data'})
    result = cache.get('expire_test', {'id': 1}, max_age_hours=0)  # Should expire immediately
    print("Expired cache result:", result)
    assert result is None, "Cache expiration failed"
    
    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    test_cache() 