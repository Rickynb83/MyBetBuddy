import os
import json
import requests
from datetime import datetime, timedelta

# API-Football setup
API_KEY = os.getenv('API_FOOTBALL_KEY', 'your_api_key_here')
print(f"API Key loaded: {API_KEY[:5]}...{API_KEY[-5:] if len(API_KEY) > 10 else ''}")

# League IDs
LEAGUES = {
    'Premier League': 39,
    'La Liga': 140,
    'Ligue 1': 61,
    'Bundesliga': 78,
    'Serie A': 135,
    'Süper Lig': 203
}

def api_football_request(endpoint, params):
    """Make a request to the API-Football API with proper headers."""
    try:
        print(f"Making API request to {endpoint} with params: {params}")
        response = requests.get(
            f'https://v3.football.api-sports.io/{endpoint}',
            headers={
                'x-rapidapi-host': 'v3.football.api-sports.io',
                'x-rapidapi-key': API_KEY
            },
            params=params
        )
        
        print(f"API response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"API Error: Status {response.status_code} for {endpoint}")
            return None
            
        data = response.json()
        
        if data.get('errors'):
            print(f"API Error: {data['errors']}")
            return None
            
        return data
    except Exception as e:
        print(f"API Request Error ({endpoint}): {e}")
        import traceback
        print(traceback.format_exc())
        return None

def fetch_fixtures(league):
    """Fetch fixtures for a league in the next 7 days."""
    try:
        today = datetime.now()
        end_date = today + timedelta(days=7)
        
        print(f"\n=== Fetching fixtures for league {league} ===")
        print(f"Date range: {today.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        data = api_football_request('fixtures', {
            'from': today.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
            'league': league,
            'season': '2024',
            'timezone': 'Europe/London'
        })
        
        if not data:
            print(f"❌ No data returned from API for {league}")
            return []
            
        if not data.get('response'):
            print(f"ℹ️ No fixtures found for {league} in the next 7 days.")
            return []
        
        print(f"✅ Found {len(data['response'])} fixtures for {league}")
        
        fixtures = []
        for match in data['response']:
            fixture_data = {
                'fixture_id': match['fixture']['id'],
                'homeTeam': match['teams']['home']['name'],
                'home_team_id': match['teams']['home']['id'],
                'awayTeam': match['teams']['away']['name'],
                'away_team_id': match['teams']['away']['id'],
                'date': match['fixture']['date'],
                'league': match['league']['name'],
                'country': match['league']['country']
            }
            fixtures.append(fixture_data)
            print(f"✅ Added fixture: {fixture_data['homeTeam']} vs {fixture_data['awayTeam']} on {fixture_data['date']}")
        
        return fixtures
    except Exception as e:
        print(f"❌ Error fetching fixtures for {league}: {e}")
        import traceback
        print(traceback.format_exc())
        return []

def main():
    """Run diagnostics for fixtures data."""
    print("=== MyBetBuddy Fixtures Diagnostics ===")
    print(f"Running on: {'Heroku' if os.environ.get('DYNO') else 'Local'}")
    print(f"Current time: {datetime.now()}")
    
    # Check environment variables
    print("\n=== Environment Variables ===")
    env_vars = {
        'API_FOOTBALL_KEY': os.getenv('API_FOOTBALL_KEY', '')[:5] + '...' if os.getenv('API_FOOTBALL_KEY') else 'Not set',
        'DYNO': os.getenv('DYNO', 'Not set'),
        'PORT': os.getenv('PORT', 'Not set')
    }
    
    for key, value in env_vars.items():
        print(f"{key}: {value}")
    
    # Test API status
    print("\n=== API Status Check ===")
    status = api_football_request('status', {})
    if status and status.get('response'):
        print(f"API Status: Active")
        print(f"Account Type: {status['response'].get('account', {}).get('name', 'Unknown')}")
        print(f"Requests Today: {status['response'].get('requests', {}).get('current', 'Unknown')}")
        print(f"Requests Limit: {status['response'].get('requests', {}).get('limit_day', 'Unknown')}")
    else:
        print("API Status: Failed to get status")
    
    # Fetch fixtures for top leagues
    for league_name, league_id in LEAGUES.items():
        fixtures = fetch_fixtures(league_id)
        print(f"\nResults for {league_name}: {len(fixtures)} fixtures found")
        
        if fixtures:
            # Print first 2 fixtures as a sample
            print("\nSample fixtures:")
            for i, fixture in enumerate(fixtures[:2]):
                print(f"{i+1}. {fixture['homeTeam']} vs {fixture['awayTeam']} on {fixture['date']}")
    
    print("\n=== Diagnostics Complete ===")

if __name__ == "__main__":
    main() 