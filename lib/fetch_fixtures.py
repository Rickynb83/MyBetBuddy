import requests
from datetime import datetime, timedelta
import os
import time
import streamlit as st
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# League IDs
LEAGUES = {
    # England
    'Premier League': 39,
    'Championship': 40,
    'League One': 41,
    'League Two': 42,
    
    # Spain
    'La Liga': 140,
    
    # France
    'Ligue 1': 61,
    
    # Germany
    'Bundesliga': 78,
    
    # Netherlands
    'Eredivisie': 88,
    
    # Portugal
    'Primeira Liga': 94,
    
    # Denmark
    'Superliga': 119,
    
    # Greece
    'Super League 1': 197,
    
    # Italy
    'Serie A': 135,
    
    # Scotland
    'Premiership': 179,
    
    # Turkey
    'Süper Lig': 203
}

API_KEY = os.getenv('API_FOOTBALL_KEY', 'your_api_key_here')

print("API Key Loaded:", API_KEY[:5] + "..." + API_KEY[-5:])  # Print the first and last 5 characters of the API key for verification

# Base API function to reduce repetition
def api_football_request(endpoint, params):
    """Make a request to the API-Football API with proper headers."""
    try:
        response = requests.get(
            f'https://v3.football.api-sports.io/{endpoint}',
            headers={
                'x-rapidapi-host': 'v3.football.api-sports.io',
                'x-rapidapi-key': API_KEY
            },
            params=params
        )
        
        # Only log errors, not successful requests
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

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_fixtures(league):
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
            print(f"ℹ️ No fixtures found for {league} in the next 7 days. This could be due to:")
            print(f"   - League break (e.g., international break, cup competitions)")
            print(f"   - Season break")
            print(f"   - No scheduled matches in this period")
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
                'country': match['league']['country'],
                'venue': match['fixture']['venue']['name'] if match['fixture'].get('venue') else 'Unknown'
            }
            fixtures.append(fixture_data)
            print(f"✅ Added fixture: {fixture_data['homeTeam']} vs {fixture_data['awayTeam']} on {fixture_data['date']}")
        
        return fixtures
    except Exception as e:
        print(f"❌ Error fetching fixtures for {league}: {e}")
        import traceback
        print(traceback.format_exc())
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_standings():
    try:
        standings = {league: [] for league in LEAGUES.keys()}  # Create a dictionary for each league
        
        # Special handling for leagues with known issues
        problem_leagues = {
            'Superliga': {'season': 2023, 'expected_teams': 12, 'multiple_groups': True},
            'Super League 1': {'season': 2023, 'expected_teams': 14, 'multiple_groups': True},
            'Primeira Liga': {'season': 2023, 'expected_teams': 18}
        }
        
        for league_name, league_id in LEAGUES.items():
            print(f"Fetching standings for {league_name}")
            
            # First try current season (2024)
            use_season = 2024
            if league_name in problem_leagues:
                # For problem leagues, try recommended season first
                use_season = problem_leagues[league_name]['season']
            
            data = api_football_request('standings', {
                'season': use_season,
                'league': league_id
            })
            
            if data and data.get('response'):
                for league_data in data['response']:
                    if league_data['league'].get('standings'):
                        # Check if we have multiple standings groups (championship/relegation format)
                        standings_groups = league_data['league']['standings']
                        
                        # Handle leagues with multiple groups (championship and relegation groups)
                        if isinstance(standings_groups, list) and len(standings_groups) > 1 and league_name in problem_leagues and problem_leagues[league_name].get('multiple_groups'):
                            print(f"Found multiple standings groups for {league_name}: {len(standings_groups)} groups")
                            
                            # Combine all groups but keep track of seen teams to avoid duplicates
                            league_standings = []
                            seen_team_ids = set()
                            
                            for group in standings_groups:
                                for team in group:
                                    if team['team']['id'] not in seen_team_ids:
                                        league_standings.append(team)
                                        seen_team_ids.add(team['team']['id'])
                                    else:
                                        print(f"Skipping duplicate team: {team['team']['name']} (ID: {team['team']['id']})")
                        else:
                            # Use the first group (normal leagues)
                            league_standings = standings_groups[0] if standings_groups else []
                        
                        # Check if we got meaningful data
                        if (not league_standings or 
                            (league_name in problem_leagues and 
                             len(league_standings) < problem_leagues[league_name]['expected_teams'])):
                            
                            print(f"Warning: Received incomplete standings data for {league_name}. Only {len(league_standings) if league_standings else 0} teams.")
                            
                            # Try alternative season for problem leagues
                            alt_season = 2023 if use_season == 2024 else 2024
                            print(f"Trying season {alt_season} for {league_name}")
                            
                            alt_data = api_football_request('standings', {
                                'season': alt_season,
                                'league': league_id
                            })
                            
                            if alt_data and alt_data.get('response'):
                                for alt_league_data in alt_data['response']:
                                    if alt_league_data['league'].get('standings'):
                                        # Multiple groups for alternative season
                                        alt_standings_groups = alt_league_data['league']['standings']
                                        
                                        if isinstance(alt_standings_groups, list) and len(alt_standings_groups) > 1 and league_name in problem_leagues and problem_leagues[league_name].get('multiple_groups'):
                                            print(f"Found multiple standings groups for {league_name} in season {alt_season}: {len(alt_standings_groups)} groups")
                                            
                                            # Combine all groups but avoid duplicates
                                            alt_standings = []
                                            seen_team_ids = set()
                                            
                                            for group in alt_standings_groups:
                                                for team in group:
                                                    if team['team']['id'] not in seen_team_ids:
                                                        alt_standings.append(team)
                                                        seen_team_ids.add(team['team']['id'])
                                                    else:
                                                        print(f"Skipping duplicate team: {team['team']['name']} (ID: {team['team']['id']})")
                                        else:
                                            # Use the first group (normal leagues)
                                            alt_standings = alt_standings_groups[0] if alt_standings_groups else []
                                        
                                        if alt_standings and len(alt_standings) > len(league_standings):
                                            print(f"Using {alt_season} season data for {league_name} which has {len(alt_standings)} teams")
                                            league_standings = alt_standings
                        
                        # Final processed standings with no duplicates
                        standings_list = []
                        seen_team_ids = set()
                        
                        for team in league_standings:
                            if team['team']['id'] not in seen_team_ids:
                                standings_list.append({
                                    'team': team['team']['name'],
                                    'team_id': team['team']['id'],  # Add team ID
                                    'rank': int(team['rank']),  # Original rank (will be recalculated)
                                    'points': team['points'],
                                    'goalsDiff': team['goalsDiff'],
                                    'played': team['all']['played'],
                                    'won': team['all']['win'],
                                    'drawn': team['all']['draw'],
                                    'lost': team['all']['lose'],
                                    'for': team['all']['goals']['for'],
                                    'against': team['all']['goals']['against'],
                                    'form': team['form']
                                })
                                seen_team_ids.add(team['team']['id'])
                        
                        # Sort by points (descending), then goal difference (descending), then goals for (descending)
                        standings_list.sort(key=lambda x: (-x['points'] if x['points'] is not None else -999, 
                                                          -x['goalsDiff'] if x['goalsDiff'] is not None else -999, 
                                                          -x['for'] if x['for'] is not None else -999))
                        
                        # Recalculate ranks
                        for i, team in enumerate(standings_list):
                            team['rank'] = i + 1
                            
                        standings[league_name] = standings_list
                        print(f"✅ Added {league_name} standings with {len(standings[league_name])} teams")
            else:
                print(f"No data returned for {league_name}.")
                standings[league_name] = []
            
            time.sleep(0.1)
            
        return standings
        
    except Exception as e:
        print(f"Error fetching standings: {e}")
        return {}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_predictions(fixture_id):
    """Fetch predictions for a specific fixture from API-Football."""
    try:
        print(f"\n=== Fetching prediction for fixture ID: {fixture_id} ===")
        
        # Use the correct API endpoint and headers format
        data = api_football_request('predictions', {
            'fixture': fixture_id
        })
        
        # Print the raw API response for debugging
        print(f"Raw API Response: {data}")
        
        if data and data.get('response') and len(data['response']) > 0:
            prediction_data = data['response'][0]
            print(f"\nPrediction Data Structure:")
            print(f"Keys in prediction_data: {prediction_data.keys()}")
            
            if 'predictions' in prediction_data:
                predictions = prediction_data['predictions']
                print(f"Keys in predictions: {predictions.keys()}")
                
                # Get the winner prediction
                winner = predictions.get('winner', {}).get('name', '')
                print(f"\nPredicted Winner: {winner}")
                
                # Get the betting advice
                advice = predictions.get('advice', '')
                print(f"Betting Advice: {advice}")
                
                # Get the win or draw probability (it's a boolean)
                win_or_draw = predictions.get('win_or_draw', False)
                print(f"Win or Draw: {win_or_draw}")
                
                # Get the under/over prediction
                under_over = predictions.get('under_over', '')
                print(f"Under/Over: {under_over}")
                
                # Get the goals prediction
                goals = predictions.get('goals', '')
                print(f"Goals: {goals}")
                
                # Get the percentages
                if 'percent' in predictions:
                    prediction = predictions['percent']
                    print(f"\nRaw prediction percentages: {prediction}")
                    
                    # Extract the prediction percentages directly from API
                    home_win = float(prediction.get('home', '0').replace('%', ''))
                    draw = float(prediction.get('draw', '0').replace('%', ''))
                    away_win = float(prediction.get('away', '0').replace('%', ''))
                    
                    # Print raw API data for debugging
                    print(f"\nProcessed prediction percentages:")
                    print(f"Home Win: {home_win}%")
                    print(f"Draw: {draw}%")
                    print(f"Away Win: {away_win}%")
                    print(f"Total: {home_win + draw + away_win}%")
                    
                    # Check if the predictions make sense
                    if home_win + draw + away_win != 100:
                        print("WARNING: Prediction percentages do not sum to 100%")
                        return None
                    
                    # Return the predictions with additional context
                    return {
                        'home_win': round(home_win, 2),
                        'draw': round(draw, 2),
                        'away_win': round(away_win, 2),
                        'winner': winner,
                        'advice': advice,
                        'win_or_draw': win_or_draw,
                        'under_over': under_over,
                        'goals': goals
                    }
                else:
                    print("No 'percent' key in predictions")
            else:
                print("No 'predictions' key in prediction_data")
            
            return None
        else:
            print(f"No prediction available for fixture ID {fixture_id}")
            return None
    except Exception as e:
        print(f"Error fetching prediction: {e}")
        import traceback
        print(traceback.format_exc())
        return None

# NEW FUNCTIONS FOR ADDITIONAL DATA

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_head_to_head(team1_id, team2_id, last=10):
    """Fetch head-to-head stats between two teams."""
    try:
        data = api_football_request('fixtures/headtohead', {
            'h2h': f"{team1_id}-{team2_id}",
            'last': last
        })
        
        if not data or not data.get('response'):
            return []
            
        h2h_matches = []
        for match in data['response']:
            # Create a readable format for each match
            match_data = {
                'date': match['fixture']['date'],
                'league': match['league']['name'],
                'home_team': match['teams']['home']['name'],
                'away_team': match['teams']['away']['name'],
                'home_goals': match['goals']['home'],
                'away_goals': match['goals']['away'],
                'winner': 'Draw' if match['teams']['home']['winner'] is None else 
                         (match['teams']['home']['name'] if match['teams']['home']['winner'] else 
                          match['teams']['away']['name'])
            }
            h2h_matches.append(match_data)
            
        return h2h_matches
    except Exception as e:
        print(f"Error fetching head-to-head: {e}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_team_statistics(team_id, league_id, season='2024'):
    """Fetch detailed statistics for a team in a specific league."""
    try:
        data = api_football_request('teams/statistics', {
            'team': team_id,
            'league': league_id,
            'season': season
        })
        
        if not data or not data.get('response'):
            return {}
            
        stats = data['response']
        
        # Create a structured format with the most relevant stats
        team_stats = {
            'team': stats['team']['name'],
            'form': stats.get('form', ''),
            'fixtures': {
                'played': {
                    'home': stats['fixtures']['played']['home'],
                    'away': stats['fixtures']['played']['away'],
                    'total': stats['fixtures']['played']['total']
                },
                'wins': {
                    'home': stats['fixtures']['wins']['home'],
                    'away': stats['fixtures']['wins']['away'],
                    'total': stats['fixtures']['wins']['total']
                },
                'draws': {
                    'home': stats['fixtures']['draws']['home'],
                    'away': stats['fixtures']['draws']['away'],
                    'total': stats['fixtures']['draws']['total']
                },
                'losses': {
                    'home': stats['fixtures']['loses']['home'],
                    'away': stats['fixtures']['loses']['away'],
                    'total': stats['fixtures']['loses']['total']
                }
            },
            'goals': {
                'for': {
                    'total': stats['goals']['for']['total']['total'],
                    'average': stats['goals']['for']['average']['total'],
                    'minute': stats['goals']['for']['minute']
                },
                'against': {
                    'total': stats['goals']['against']['total']['total'],
                    'average': stats['goals']['against']['average']['total'],
                    'minute': stats['goals']['against']['minute']
                }
            },
            'clean_sheets': stats.get('clean_sheet', {}),
            'failed_to_score': stats.get('failed_to_score', {}),
            'lineups': stats.get('lineups', []),
            'cards': stats.get('cards', {})
        }
        
        return team_stats
    except Exception as e:
        print(f"Error fetching team statistics: {e}")
        return {}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_players(team_id, season='2024'):
    """Fetch players for a specific team."""
    try:
        data = api_football_request('players', {
            'team': team_id,
            'season': season
        })
        
        if not data or not data.get('response'):
            return []
            
        players = []
        for player in data['response']:
            player_data = {
                'id': player['player']['id'],
                'name': player['player']['name'],
                'age': player['player']['age'],
                'nationality': player['player']['nationality'],
                'position': player['statistics'][0]['games']['position'],
                'matches': player['statistics'][0]['games']['appearences'],
                'goals': player['statistics'][0]['goals']['total'],
                'assists': player['statistics'][0]['goals']['assists'],
                'yellow_cards': player['statistics'][0]['cards']['yellow'],
                'red_cards': player['statistics'][0]['cards']['red'],
                'minutes_played': player['statistics'][0]['games']['minutes']
            }
            players.append(player_data)
            
        return players
    except Exception as e:
        print(f"Error fetching players: {e}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_lineups(fixture_id):
    """Fetch lineups for a specific fixture."""
    try:
        data = api_football_request('fixtures/lineups', {
            'fixture': fixture_id
        })
        
        if not data or not data.get('response'):
            return {}
            
        lineups = {}
        for team_lineup in data['response']:
            team_name = team_lineup['team']['name']
            lineups[team_name] = {
                'formation': team_lineup.get('formation', 'Unknown'),
                'starting_xi': [player['player']['name'] for player in team_lineup.get('startXI', [])],
                'substitutes': [player['player']['name'] for player in team_lineup.get('substitutes', [])]
            }
            
        return lineups
    except Exception as e:
        print(f"Error fetching lineups: {e}")
        return {}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_venue_info(venue_name):
    """Fetch information about a specific venue."""
    try:
        data = api_football_request('venues', {
            'name': venue_name
        })
        
        if not data or not data.get('response'):
            return {}
            
        if len(data['response']) > 0:
            venue = data['response'][0]
            venue_info = {
                'id': venue['id'],
                'name': venue['name'],
                'city': venue['city'],
                'country': venue['country'],
                'capacity': venue['capacity'],
                'surface': venue['surface'],
                'address': venue['address']
            }
            return venue_info
        else:
            return {}
    except Exception as e:
        print(f"Error fetching venue info: {e}")
        return {}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_injuries(team_id, league_id, season='2024'):
    """Fetch injuries for a specific team."""
    try:
        data = api_football_request('injuries', {
            'team': team_id,
            'league': league_id,
            'season': season
        })
        
        if not data or not data.get('response'):
            return []
            
        injuries = []
        for injury in data['response']:
            injury_data = {
                'player': injury['player']['name'],
                'type': injury['player']['type'],
                'reason': injury['player']['reason'],
                'start_date': injury.get('fixture', {}).get('date', ''),
                'end': injury.get('fixture', {}).get('end', 'Unknown')
            }
            injuries.append(injury_data)
            
        return injuries
    except Exception as e:
        print(f"Error fetching injuries: {e}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_team_form(team_id, last=5):
    """Fetch recent form for a specific team."""
    try:
        data = api_football_request('fixtures', {
            'team': team_id,
            'last': last,
            'status': 'FT'
        })
        
        if not data or not data.get('response'):
            return []
            
        matches = []
        for match in data['response']:
            is_home = match['teams']['home']['id'] == team_id
            opponent = match['teams']['away']['name'] if is_home else match['teams']['home']['name']
            team_goals = match['goals']['home'] if is_home else match['goals']['away']
            opponent_goals = match['goals']['away'] if is_home else match['goals']['home']
            result = 'W' if (is_home and match['teams']['home']['winner']) or (not is_home and match['teams']['away']['winner']) else \
                     'L' if (is_home and not match['teams']['home']['winner'] and match['teams']['away']['winner']) or \
                           (not is_home and not match['teams']['away']['winner'] and match['teams']['home']['winner']) else 'D'
                           
            match_data = {
                'date': match['fixture']['date'],
                'competition': match['league']['name'],
                'venue': 'Home' if is_home else 'Away',
                'opponent': opponent,
                'score': f"{team_goals}-{opponent_goals}",
                'result': result
            }
            matches.append(match_data)
            
        return matches
    except Exception as e:
        print(f"Error fetching team form: {e}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_weather_for_fixture(fixture_id):
    """Fetch weather information for a fixture (if available)."""
    try:
        data = api_football_request('fixtures', {
            'id': fixture_id
        })
        
        if not data or not data.get('response') or len(data['response']) == 0:
            return {}
            
        fixture = data['response'][0]
        if 'fixture' in fixture and 'venue' in fixture['fixture']:
            venue_city = fixture['fixture'].get('venue', {}).get('city', '')
            
            if venue_city:
                # Note: In a real app, you might need to call a separate weather API
                # For now, we'll return placeholder data
                return {
                    'city': venue_city,
                    'temperature': 'N/A (would require weather API)',
                    'condition': 'N/A (would require weather API)',
                    'humidity': 'N/A (would require weather API)',
                    'wind': 'N/A (would require weather API)'
                }
        return {}
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return {}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_referee_info(fixture_id):
    """Fetch referee information for a fixture."""
    try:
        data = api_football_request('fixtures', {
            'id': fixture_id
        })
        
        if not data or not data.get('response') or len(data['response']) == 0:
            return {}
            
        fixture = data['response'][0]
        if 'fixture' in fixture and 'referee' in fixture['fixture']:
            referee_name = fixture['fixture']['referee']
            if referee_name:
                # Return basic referee info
                return {
                    'name': referee_name,
                    # In a more complete implementation, you might fetch referee stats
                    'fixtures': 'N/A (would require additional API calls)',
                    'yellow_cards': 'N/A (would require additional API calls)',
                    'red_cards': 'N/A (would require additional API calls)'
                }
        return {}
    except Exception as e:
        print(f"Error fetching referee info: {e}")
        return {}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_available_leagues():
    """Fetch all available leagues from API-Football."""
    try:
        data = api_football_request('leagues', {
            'season': 2024
        })
        
        if not data or not data.get('response'):
            print("No leagues data available")
            return []
            
        leagues = []
        for league in data['response']:
            league_info = {
                'id': league['league']['id'],
                'name': league['league']['name'],
                'country': league['country']['name'],
                'type': league['league']['type']
            }
            leagues.append(league_info)
            
        # Sort leagues by country and name
        leagues.sort(key=lambda x: (x['country'], x['name']))
        
        # Print available leagues
        print("\nAvailable Leagues:")
        print("=================")
        current_country = None
        for league in leagues:
            if league['country'] != current_country:
                current_country = league['country']
                print(f"\n{current_country}:")
            print(f"  {league['name']} (ID: {league['id']})")
            
        return leagues
    except Exception as e:
        print(f"Error fetching available leagues: {e}")
        return []

# Add this line at the end of the file to test the function
if __name__ == "__main__":
    fetch_available_leagues()