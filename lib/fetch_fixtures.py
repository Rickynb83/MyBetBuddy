import requests
from datetime import datetime, timedelta
import os
import time
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# League IDs
LEAGUES = {
    'Premier League': 39,
    'La Liga': 140,
    'Serie A': 135,
    'Bundesliga': 78,
    'Ligue 1': 61,
    'Primeira Liga': 94
}

API_KEY = os.getenv('RAPIDAPI_KEY', '9de1ba57aemsha83e8eaec65d2a2p1b2275jsn1fdde0303250')

@st.cache_data(ttl=43200)
def fetch_fixtures():
    try:
        today = datetime.now()
        end_date = today + timedelta(days=7)
        
        response = requests.get(
            'https://api-football-v1.p.rapidapi.com/v3/fixtures',
            headers={
                'X-RapidAPI-Key': API_KEY,
                'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
            },
            params={
                'from': today.strftime('%Y-%m-%d'),
                'to': end_date.strftime('%Y-%m-%d'),
                'league': ','.join(str(id) for id in LEAGUES.values()),
                'timezone': 'Europe/London'
            }
        )
        
        data = response.json()
        if not data.get('response'):
            return []
            
        fixtures = []
        for match in data['response']:
            fixtures.append({
                'homeTeam': match['teams']['home']['name'],
                'awayTeam': match['teams']['away']['name'],
                'date': match['fixture']['date'],
                'league': match['league']['name'],
                'country': match['league']['country']
            })
            
        return fixtures
    except Exception as e:
        print(f"Error fetching fixtures: {e}")
        return []

@st.cache_data(ttl=43200)
def fetch_standings():
    try:
        standings = {}
        
        for league in LEAGUES:
            print(f"Fetching standings for {league}")
            response = requests.get(
                'https://api-football-v1.p.rapidapi.com/v3/standings',
                headers={
                    'X-RapidAPI-Key': API_KEY,
                    'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
                },
                params={
                    'season': 2024,
                    'league': LEAGUES[league]
                }
            )
            
            data = response.json()
            
            if data.get('response'):
                for league_data in data['response']:
                    if league_data['league'].get('standings'):
                        league_standings = league_data['league']['standings'][0]
                        for team in league_standings:
                            standings[team['team']['name']] = team['rank']
                        print(f"✅ Added {league} standings")
            
            time.sleep(0.1)
            
        return standings
        
    except Exception as e:
        print(f"Error fetching standings: {e}")
        return {}