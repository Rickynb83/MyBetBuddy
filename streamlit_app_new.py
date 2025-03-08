import os
import sys
from pathlib import Path
import time
import re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import csv
import hashlib
import base64

# Add the current directory to the Python path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from lib.fetch_fixtures import (
    fetch_fixtures, fetch_standings, LEAGUES,
    fetch_head_to_head, fetch_team_statistics, fetch_players,
    fetch_lineups, fetch_venue_info, fetch_injuries,
    fetch_team_form, fetch_weather_for_fixture, fetch_referee_info
)
import random
from lib.predictions import predict_match, create_fallback_prediction

# Load environment variables
load_dotenv()

# Set page config (must be the first Streamlit command)
st.set_page_config(
    page_title="MyBetBuddy - Football Match Predictions", 
    page_icon="⚽", 
    layout="wide",
    initial_sidebar_state="collapsed"  # Start with sidebar collapsed
)

# Toggle for development mode (set to True to disable authentication during development)
DEVELOPMENT_MODE = False  # Authentication enabled for testing

# Simple authentication functions
def load_whitelist():
    """Load the whitelist of authorized email addresses from CSV"""
    try:
        whitelist_df = pd.read_csv('Whitelist.csv')
        return whitelist_df['email'].tolist()
    except Exception as e:
        st.error(f"Error loading whitelist: {e}")
        return []

def hash_password(password):
    """Create a hashed password"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    """Load users from credentials file"""
    if os.path.exists("users.yaml"):
        with open("users.yaml", 'r') as file:
            return yaml.load(file, Loader=SafeLoader) or {}
    return {}

def save_users(users):
    """Save users to credentials file"""
    with open("users.yaml", 'w') as file:
        yaml.dump(users, file)

# Custom authentication
if not DEVELOPMENT_MODE:
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    
    # Load users and whitelist
    users = load_users()
    whitelist = load_whitelist()
    
    # If not authenticated, show login/register form
    if not st.session_state.authenticated:
        st.title("MyBetBuddy - Football Match Predictions")
        st.subheader("Login")
        
        # Toggle between login and register
        login_tab, register_tab = st.tabs(["Login", "Register"])
        
        with login_tab:
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login"):
                if username in users and users[username]['password'] == hash_password(password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        with register_tab:
            st.subheader("Register New Account")
            st.info("You must use a whitelisted email to register.")
            
            reg_username = st.text_input("Username", key="reg_username")
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            reg_password2 = st.text_input("Confirm Password", type="password", key="reg_password2")
            
            if st.button("Register"):
                # Validate inputs
                if not reg_username or not reg_email or not reg_password:
                    st.error("All fields are required")
                elif reg_password != reg_password2:
                    st.error("Passwords do not match")
                elif reg_username in users:
                    st.error("Username already exists")
                elif reg_email not in whitelist:
                    st.error(f"Email not in whitelist. Authorized emails: {whitelist}")
                else:
                    # Create new user
                    users[reg_username] = {
                        'email': reg_email,
                        'password': hash_password(reg_password)
                    }
                    save_users(users)
                    st.success("Registration successful! Please login.")
        
        # Stop execution here if not authenticated
        if not st.session_state.authenticated:
            st.stop()
    
    # Show logout button if authenticated
    if st.session_state.authenticated:
        st.sidebar.success(f"Welcome {st.session_state.username}")
        if st.sidebar.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()

# Apply custom CSS for consistent font sizes and adjust padding to fix header overlap
st.markdown("""
<style>
    /* Adjust font size for all tables */
    .stDataFrame table, .stTable table {
        font-size: 16px;
    }
    /* Remove top padding to prevent header overlap */
    .block-container {
        padding-top: 3rem;
    }
    /* Adjust table widths */
    .stDataFrame, .stTable {
        width: 100%;
    }
    /* Style for analysis sections */
    .analysis-section {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# App title
st.title("⚽ MyBetBuddy - Football Match Predictions")

# Create a layout with two columns for the title area
title_col1, title_col2 = st.columns([3, 1])

# Add instructions button in the right column
with title_col2:
    # Initialize session state for instructions visibility if it doesn't exist
    if 'show_instructions' not in st.session_state:
        st.session_state.show_instructions = False
    
    # Create the Instructions button
    if st.button("Instructions", key="instructions_button"):
        st.session_state.show_instructions = not st.session_state.show_instructions

# Display instructions if the button has been clicked
if st.session_state.show_instructions:
    st.info("""
    ### Instructions
    1. Toggle between leagues to view upcoming fixtures
    2. Select fixtures from the fixtures list to be analysed
    3. Once you have selected all your fixtures, select Analyze Selected Fixtures to view the predictions
    4. On the Match Analysis table, on the Additional Analysis, there is a drop down menu with additional analysis
    """)

# Add refresh button
if st.button("🔄 Refresh Data"):
    # Clear all caches
    st.cache_data.clear()
    # Clear all session state except authentication
    for key in list(st.session_state.keys()):
        if key not in ['authentication_status', 'username', 'name']:
            del st.session_state[key]
    st.rerun()

# Fetch standings
standings = fetch_standings()
print("Standings Data:", standings)  # Debug line to check the fetched standings data

# Initialize session state for selected fixtures and analysis data
if 'selected_fixtures' not in st.session_state:
    st.session_state.selected_fixtures = []
if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = {}
if 'analysis_selections' not in st.session_state:
    st.session_state.analysis_selections = {}
if 'show_analysis' not in st.session_state:
    st.session_state.show_analysis = False

# Initialize league mappings - Must match IDs used in API-Football
LEAGUE_IDS = {
    'Premier League': 39,
    'La Liga': 140,
    'Bundesliga': 78,  # Updated to correct ID
    'Serie A': 135,
    'Ligue 1': 61,
    'Eredivisie': 88,
    'Primeira Liga': 94,
    'Super Lig': 203,
    'Championship': 40,
    'League One': 41,
    'League Two': 42,
    'Super League': 183,
    'Super League 1': 197,  # Add correct ID if needed
    'Süper Lig': 145  # Add correct ID if needed
}

# Add caching decorator for predictions with unique key for each match
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_prediction(home_team_id, away_team_id, league_id):
    try:
        # Ensure proper types for all IDs
        home_id = int(home_team_id)
        away_id = int(away_team_id)
        league = int(league_id)
        
        if not all([home_id, away_id, league]):
            print(f"Invalid team or league ID: {home_id}, {away_id}, {league}")
            return create_fallback_prediction()
            
        # Call prediction function with proper types
        result = predict_match(home_id, away_id, league)
        
        # Validate result
        if not result or not isinstance(result, dict):
            print(f"Invalid prediction result type: {type(result)}")
            return create_fallback_prediction()
            
        # Check for template/default results
        if result.get('metadata', {}).get('error') == 'Fallback prediction used':
            print(f"Fallback prediction was used for {home_id} vs {away_id}")
            
        return result
    except Exception as e:
        print(f"Prediction error in cache function: {str(e)}")
        return create_fallback_prediction()

# Display standings if available
if standings:
    # Create tabs for each league
    league_tabs = st.tabs(LEAGUES.keys())

    for league, tab in zip(LEAGUES.keys(), league_tabs):
        with tab:
            # Create two columns inside the tab with adjusted ratios
            tab_col1, tab_col2 = st.columns([1.4, 1.6])  # Reduced standings width by 30% and increased fixtures width

            with tab_col1:
                # Change from st.markdown to st.subheader to match fixtures table
                st.subheader(f"{league} Standings")
                
                # Create a DataFrame for the current league standings
                standings_df = pd.DataFrame(standings[league])

                # Remove the extra columns and keep only the necessary columns
                standings_df = standings_df[['rank', 'team', 'played', 'won', 'drawn', 'lost', 'for', 'against', 'points', 'goalsDiff', 'form']]

                # Rename the columns to match the desired table headings
                standings_df.columns = ['Position', 'Team', 'Played', 'Won', 'Drawn', 'Lost', 'For', 'Against', 'Points', 'Goal Difference', 'Form']

                # Sort the DataFrame by Position
                standings_df = standings_df.sort_values(by='Position')

                # Create display columns in exact order with Position first
                display_columns = ['Position', 'Team', 'Played', 'Won', 'Drawn', 'Lost', 'For', 'Against', 'Points', 'Goal Difference', 'Form']
                
                # Display the standings table with consistent styling
                st.dataframe(
                    standings_df[display_columns],
                    hide_index=True,
                    height=320,
                    use_container_width=True,
                    column_config={
                        col: st.column_config.TextColumn(
                            col,
                            disabled=True,
                            required=True,
                            width="small"  # Consistent column widths
                        ) for col in display_columns
                    }
                )

            with tab_col2:
                # Display fixtures for each league
                st.subheader(f"{league} Fixtures")
                
                # Fetch fixtures for this league
                fixtures = fetch_fixtures(LEAGUES[league])
                
                if not fixtures:
                    st.info(f"ℹ️ No upcoming fixtures found for {league} in the next 7 days. This is likely due to:")
                    st.markdown("""
                    - League break (e.g., international break, cup competitions)
                    - Season break
                    - No scheduled matches in this period
                    """)
                    continue
                
                fixtures_df = pd.DataFrame(fixtures)
                
                if fixtures_df.empty:
                    st.warning(f"No fixtures data found for {league}. Check the API response.")

                if not fixtures_df.empty:
                    # Convert standings to DataFrame for mapping
                    current_standings_df = pd.DataFrame(standings[league])

                    # Add position columns for home and away teams
                    fixtures_df['Home Position'] = fixtures_df['homeTeam'].map(current_standings_df.set_index('team')['rank'])
                    fixtures_df['Away Position'] = fixtures_df['awayTeam'].map(current_standings_df.set_index('team')['rank'])

                    # Format the date
                    fixtures_df['Date'] = pd.to_datetime(fixtures_df['date']).dt.strftime('%d/%m/%Y %I:%M %p')

                    # Rearrange and rename columns
                    fixtures_df = fixtures_df.rename(columns={
                        'homeTeam': 'Home Team',
                        'awayTeam': 'Away Team'
                    })

                    # Add a key column for identifying fixtures across leagues
                    fixtures_df['key'] = fixtures_df.apply(
                        lambda row: f"{row['Home Team']} vs {row['Away Team']} ({row['Date']})", 
                        axis=1
                    )

                    # Check if any fixtures are already selected
                    selected_keys = []
                    if st.session_state.selected_fixtures:
                        for fixture in st.session_state.selected_fixtures:
                            if isinstance(fixture, dict) and 'Home Team' in fixture and 'Away Team' in fixture and 'Date' in fixture:
                                selected_keys.append(f"{fixture['Home Team']} vs {fixture['Away Team']} ({fixture['Date']})")
                    
                    # Mark fixtures as selected if they're in the session state
                    fixtures_df['Select'] = fixtures_df['key'].apply(lambda x: x in selected_keys)

                    # Update column order to include Select
                    fixtures_df = fixtures_df[['Select', 'Date', 'Home Position', 'Home Team', 'Away Team', 'Away Position', 'fixture_id', 'home_team_id', 'away_team_id', 'venue', 'league', 'key']]

                    # Handle missing position data
                    fixtures_df['Home Position'] = fixtures_df['Home Position'].fillna('N/A')
                    fixtures_df['Away Position'] = fixtures_df['Away Position'].fillna('N/A')

                    # Convert position columns to strings to avoid type issues
                    fixtures_df['Home Position'] = fixtures_df['Home Position'].astype(str)
                    fixtures_df['Away Position'] = fixtures_df['Away Position'].astype(str)

                    # Ensure all columns are of expected types
                    fixtures_df['Select'] = fixtures_df['Select'].astype(bool)
                    fixtures_df['Date'] = fixtures_df['Date'].astype(str)
                    fixtures_df['Home Team'] = fixtures_df['Home Team'].astype(str)
                    fixtures_df['Away Team'] = fixtures_df['Away Team'].astype(str)

                    # Hide key column and IDs from display
                    display_df = fixtures_df.drop(columns=['key', 'fixture_id', 'home_team_id', 'away_team_id', 'venue', 'league'])

                    try:
                        # Display fixtures table with selection column
                        edited_df = st.data_editor(
                            display_df,
                            hide_index=True,
                            use_container_width=True,
                            key=f"fixture_editor_{league}",  # Add unique key for each league
                            column_config={
                                "Select": st.column_config.CheckboxColumn(
                                    "Select",
                                    default=False,
                                    width="small",
                                    help="Select fixtures to analyze"
                                ),
                                "Date": st.column_config.TextColumn("Date", width="medium"),
                                "Home Position": st.column_config.TextColumn("Home Pos", width="small"),
                                "Home Team": st.column_config.TextColumn("Home Team", width="medium"),
                                "Away Team": st.column_config.TextColumn("Away Team", width="medium"),
                                "Away Position": st.column_config.TextColumn("Away Pos", width="small")
                            }
                        )

                        # Get current selections from this league
                        current_selections = edited_df[edited_df['Select']]
                        
                        # For selections in this league, add or update in session state
                        all_selections = []
                        if len(st.session_state.selected_fixtures) > 0:
                            # Start with current selections from other leagues
                            for fixture in st.session_state.selected_fixtures:
                                if isinstance(fixture, dict) and 'Home Team' in fixture and 'Away Team' in fixture and 'Date' in fixture:
                                    fixture_key = f"{fixture['Home Team']} vs {fixture['Away Team']} ({fixture['Date']})"
                                    # Only keep selections that aren't from the current league (they'll be added back if still selected)
                                    if not any(fixture_key == key for key in fixtures_df['key'].tolist()):
                                        all_selections.append(fixture)
                        
                        # Add current selections from this league, including fixture_id
                        if not current_selections.empty:
                            for _, selected_row in current_selections.iterrows():
                                # Get the original row with all IDs
                                original_row = fixtures_df[
                                    (fixtures_df['Home Team'] == selected_row['Home Team']) & 
                                    (fixtures_df['Away Team'] == selected_row['Away Team']) &
                                    (fixtures_df['Date'] == selected_row['Date'])
                                ]
                                
                                if not original_row.empty:
                                    # Create fixture dict with all necessary data
                                    fixture_dict = {
                                        'Date': selected_row['Date'],
                                        'Home Position': selected_row['Home Position'],
                                        'Home Team': selected_row['Home Team'],
                                        'Away Team': selected_row['Away Team'],
                                        'Away Position': selected_row['Away Position'],
                                        'fixture_id': original_row.iloc[0]['fixture_id'],
                                        'home_team_id': original_row.iloc[0]['home_team_id'],
                                        'away_team_id': original_row.iloc[0]['away_team_id'],
                                        'venue': original_row.iloc[0]['venue'],
                                        'league': original_row.iloc[0]['league']
                                    }
                                    all_selections.append(fixture_dict)
                        
                        # Update session state with all selections
                        st.session_state.selected_fixtures = all_selections

                    except Exception as e:
                        st.error(f"Error displaying fixtures: {e}")
                        print(f"Error details: {str(e)}")  # Add debug print
                else:
                    st.write("No upcoming fixtures available for this league.")

    # Display selected fixtures and analysis
    if st.session_state.selected_fixtures:
        st.markdown("---")
        st.subheader("Selected Fixtures")
        
        # Convert the session state to a DataFrame
        selected_df = pd.DataFrame(st.session_state.selected_fixtures)
        
        # Ensure the DataFrame has the correct columns
        if not selected_df.empty:
            display_columns = ['Date', 'Home Position', 'Home Team', 'Away Team', 'Away Position']
            for col in display_columns:
                if col not in selected_df.columns:
                    selected_df[col] = ""
            selected_df = selected_df[display_columns]
        
        # Display the DataFrame in a table format
        st.dataframe(
            selected_df,
            hide_index=True,
            use_container_width=True
        )

        # Add analyze button
        if st.button("Analyze Selected Fixtures"):
            st.session_state.show_analysis = True
            st.rerun()

        # Display analysis if enabled
        if st.session_state.show_analysis:
            with st.spinner("Fetching predictions and analysis data..."):
                st.subheader("Match Analysis")
                
                # Create analysis DataFrame
                analysis_df = pd.DataFrame(st.session_state.selected_fixtures)
                
                # Ensure we have all necessary IDs
                for _, row in analysis_df.iterrows():
                    fixture_key = f"{row['Home Team']} vs {row['Away Team']} ({row['Date']})"
                    
                    # Get the original fixture data to access IDs
                    original_fixture = next(
                        (f for f in st.session_state.selected_fixtures 
                         if f['Home Team'] == row['Home Team'] and 
                         f['Away Team'] == row['Away Team'] and 
                         f['Date'] == row['Date']),
                        None
                    )
                    
                    if original_fixture:
                        # Update the row with all necessary IDs
                        row.update({
                            'home_team_id': original_fixture.get('home_team_id'),
                            'away_team_id': original_fixture.get('away_team_id'),
                            'fixture_id': original_fixture.get('fixture_id'),
                            'venue': original_fixture.get('venue'),
                            'league': original_fixture.get('league')
                        })
                
                # Process predictions in batches
                batch_size = 3  # Reduce batch size
                total_fixtures = len(analysis_df)
                progress_bar = st.progress(0)

                # Initialize prediction lists
                home_win_pcts = []
                draw_pcts = []
                away_win_pcts = []
                predictions_source = []
                prediction_details = []

                for batch_start in range(0, total_fixtures, batch_size):
                    batch_end = min(batch_start + batch_size, total_fixtures)
                    
                    for i in range(batch_start, batch_end):
                        if i >= len(analysis_df):
                            continue
                        
                        row = analysis_df.iloc[i]
                        fixture_key = f"{row['Home Team']} vs {row['Away Team']} ({row['Date']})"
                        
                        # Get correct league ID from the mapping
                        if isinstance(row['league'], str) and row['league'] in LEAGUE_IDS:
                            league_id = LEAGUE_IDS[row['league']]
                        else:
                            # Try to get league ID directly if it's already a number
                            league_id = int(row['league']) if str(row['league']).isdigit() else None
                        
                        if not league_id:
                            st.error(f"Invalid league: {row['league']} for {fixture_key}")
                            raise ValueError("Invalid league ID")
                        
                        # Get cached prediction with unique key for each match
                        prediction = get_cached_prediction(
                            row['home_team_id'],
                            row['away_team_id'],
                            league_id
                        )
                        
                        if prediction and isinstance(prediction, dict):
                            home_win_pcts.append(prediction['probabilities']['home_win'] * 100)
                            draw_pcts.append(prediction['probabilities']['draw'] * 100)
                            away_win_pcts.append(prediction['probabilities']['away_win'] * 100)
                            predictions_source.append("Our Model")
                            
                            details = []
                            if 'expected_goals' in prediction:
                                details.append(f"Expected Goals: {prediction['expected_goals']['home']:.2f} - {prediction['expected_goals']['away']:.2f}")
                            if 'cards' in prediction:
                                details.append(f"Expected Cards: {prediction['cards']['total']:.1f}")
                            if 'metadata' in prediction and 'confidence' in prediction['metadata']:
                                details.append(f"Confidence: {prediction['metadata']['confidence']}")
                            prediction_details.append("\n".join(details))
                        else:
                            raise ValueError("Invalid prediction result")
                    
                    # Add a small delay between predictions
                    time.sleep(0.2)
                
                # Update the progress bar
                progress = (batch_end / total_fixtures)
                progress_bar.progress(progress)

                # After all predictions are done, update DataFrame
                analysis_df['Home Win %'] = home_win_pcts
                analysis_df['Draw %'] = draw_pcts
                analysis_df['Away Win %'] = away_win_pcts
                analysis_df['Source'] = predictions_source
                analysis_df['Prediction Details'] = prediction_details
            
                # Format results as percentages and display prediction result
                analysis_df['Home Win %'] = analysis_df['Home Win %'].apply(lambda x: f"{x:.0f}%")
                analysis_df['Draw %'] = analysis_df['Draw %'].apply(lambda x: f"{x:.0f}%")
                analysis_df['Away Win %'] = analysis_df['Away Win %'].apply(lambda x: f"{x:.0f}%")

                # Ensure numeric comparison for highest probability
                analysis_df['Highest Probability %'] = analysis_df[['Home Win %', 'Draw %', 'Away Win %']].apply(lambda x: max(float(x['Home Win %'].strip('%')), float(x['Draw %'].strip('%')), float(x['Away Win %'].strip('%'))), axis=1)

                # Correct the logic for determining the predicted result
                analysis_df['Predicted Result'] = analysis_df.apply(lambda row: 'Home Win' if float(row['Home Win %'].strip('%')) == row['Highest Probability %'] else ('Draw' if float(row['Draw %'].strip('%')) == row['Highest Probability %'] else 'Away Win'), axis=1)
            
            # Add a column for detailed analysis
            analysis_df['View Details'] = analysis_df.apply(
                lambda row: st.session_state.analysis_selections.get(
                    f"{row['Home Team']} vs {row['Away Team']} ({row['Date']})",
                    "Select Analysis"
                ),
                axis=1
            )
            
            # Display analysis results with all available data
            display_columns = [
                'Date', 'Home Team', 'Away Team',
                'Home Win %', 'Draw %', 'Away Win %',
                'Highest Probability %', 'Predicted Result',
                'Prediction Details',  # This contains winner, advice, win_or_draw, under_over, and goals
                'Source',
                'View Details'
            ]

            # Ensure all columns exist and remove any duplicates
            analysis_df = analysis_df.loc[:, ~analysis_df.columns.duplicated()]

            # Create a unique key for the data editor
            editor_key = f"analysis_editor_{len(st.session_state.selected_fixtures)}"
            
            # Display the analysis table with a dropdown for each row
            edited_df = st.data_editor(
                analysis_df[display_columns],
                hide_index=True,
                use_container_width=True,
                key=editor_key,
                column_config={
                    "View Details": st.column_config.SelectboxColumn(
                        "Additional Analysis",  # Change only the display name
                        options=[
                            "Select Analysis",
                            "Head-to-Head",
                            "Team Statistics",
                            "Player Information",
                            "Lineups",
                            "Venue Information",
                            "Injuries",
                            "Team Form",
                            "Weather",
                            "Referee Information",
                            "All Data"
                        ],
                        width="medium"
                    ),
                    "Prediction Details": st.column_config.TextColumn(
                        "Alternative Bet",
                        width="large"
                    )
                }
            )
            
            # Update session state with current selections and trigger rerun if needed
            for idx, row in edited_df.iterrows():
                fixture_key = f"{row['Home Team']} vs {row['Away Team']} ({row['Date']})"
                current_selection = st.session_state.analysis_selections.get(fixture_key, "Select Analysis")
                if row['View Details'] != current_selection:
                    st.session_state.analysis_selections[fixture_key] = row['View Details']
                    st.rerun()
            
            # Create a container for detailed analysis
            st.markdown("---")
            st.subheader("Detailed Analysis")
            
            # Display analysis for each fixture based on session state
            for fixture_key, analysis_type in st.session_state.analysis_selections.items():
                if analysis_type != "Select Analysis":
                    # Find the corresponding row in the analysis DataFrame
                    row = analysis_df[
                        (analysis_df['Home Team'] + " vs " + analysis_df['Away Team'] + " (" + analysis_df['Date'] + ")") == fixture_key
                    ].iloc[0]
                    
                    # Create a container for the detailed analysis
                    with st.expander(f"Analysis for: {row['Home Team']} vs {row['Away Team']}", expanded=True):
                        # Fetch and display the selected analysis type
                        if analysis_type in ["Head-to-Head", "All Data"]:
                            st.subheader("Head-to-Head Statistics")
                            if 'home_team_id' in row and 'away_team_id' in row and row['home_team_id'] and row['away_team_id']:
                                h2h_data = fetch_head_to_head(row['home_team_id'], row['away_team_id'])
                                if h2h_data:
                                    h2h_df = pd.DataFrame(h2h_data)
                                    st.dataframe(h2h_df, hide_index=True)
                                else:
                                    st.info("No head-to-head data available.")
                            else:
                                st.warning("Team IDs not available for head-to-head analysis.")
                        
                        if analysis_type in ["Team Statistics", "All Data"]:
                            st.subheader("Team Statistics")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**{row['Home Team']} Statistics**")
                                if 'home_team_id' in row and 'league' in row and row['home_team_id'] and row['league']:
                                    home_stats = fetch_team_statistics(row['home_team_id'], row['league'])
                                    if home_stats:
                                        # Convert nested dictionary to DataFrame
                                        stats_data = []
                                        for category, values in home_stats.items():
                                            if isinstance(values, dict):
                                                for subcategory, subvalues in values.items():
                                                    if isinstance(subvalues, dict):
                                                        for key, value in subvalues.items():
                                                            stats_data.append({
                                                                'Category': f"{category} - {subcategory}",
                                                                'Metric': key,
                                                                'Value': value
                                                            })
                                        st.dataframe(pd.DataFrame(stats_data), hide_index=True)
                                    else:
                                        st.info("No statistics available for home team.")
                                else:
                                    st.warning("Team or league ID not available for home team statistics.")
                            with col2:
                                st.write(f"**{row['Away Team']} Statistics**")
                                if 'away_team_id' in row and 'league' in row and row['away_team_id'] and row['league']:
                                    away_stats = fetch_team_statistics(row['away_team_id'], row['league'])
                                    if away_stats:
                                        # Convert nested dictionary to DataFrame
                                        stats_data = []
                                        for category, values in away_stats.items():
                                            if isinstance(values, dict):
                                                for subcategory, subvalues in values.items():
                                                    if isinstance(subvalues, dict):
                                                        for key, value in subvalues.items():
                                                            stats_data.append({
                                                                'Category': f"{category} - {subcategory}",
                                                                'Metric': key,
                                                                'Value': value
                                                            })
                                        st.dataframe(pd.DataFrame(stats_data), hide_index=True)
                                    else:
                                        st.info("No statistics available for away team.")
                                else:
                                    st.warning("Team or league ID not available for away team statistics.")
                        
                        if analysis_type in ["Player Information", "All Data"]:
                            st.subheader("Player Information")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**{row['Home Team']} Players**")
                                home_players = fetch_players(row['home_team_id'])
                                if home_players:
                                    st.dataframe(pd.DataFrame(home_players), hide_index=True)
                                else:
                                    st.info("No player information available for home team.")
                            with col2:
                                st.write(f"**{row['Away Team']} Players**")
                                away_players = fetch_players(row['away_team_id'])
                                if away_players:
                                    st.dataframe(pd.DataFrame(away_players), hide_index=True)
                                else:
                                    st.info("No player information available for away team.")
                        
                        if analysis_type in ["Lineups", "All Data"]:
                            st.subheader("Lineups")
                            lineups = fetch_lineups(row['fixture_id'])
                            if lineups:
                                # Convert lineups to DataFrame format
                                lineup_data = []
                                for team, data in lineups.items():
                                    lineup_data.append({
                                        'Team': team,
                                        'Formation': data['formation'],
                                        'Starting XI': ', '.join(data['starting_xi']),
                                        'Substitutes': ', '.join(data['substitutes'])
                                    })
                                st.dataframe(pd.DataFrame(lineup_data), hide_index=True)
                            else:
                                st.info("No lineup information available.")
                        
                        if analysis_type in ["Venue Information", "All Data"]:
                            st.subheader("Venue Information")
                            venue_info = fetch_venue_info(row['venue'])
                            if venue_info:
                                # Convert venue info to DataFrame
                                venue_data = [{
                                    'Name': venue_info['name'],
                                    'City': venue_info['city'],
                                    'Country': venue_info['country'],
                                    'Capacity': venue_info['capacity'],
                                    'Surface': venue_info['surface'],
                                    'Address': venue_info['address']
                                }]
                                st.dataframe(pd.DataFrame(venue_data), hide_index=True)
                            else:
                                st.info("No venue information available.")
                        
                        if analysis_type in ["Injuries", "All Data"]:
                            st.subheader("Injuries")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**{row['Home Team']} Injuries**")
                                home_injuries = fetch_injuries(row['home_team_id'], row['league'])
                                if home_injuries:
                                    st.dataframe(pd.DataFrame(home_injuries), hide_index=True)
                                else:
                                    st.info("No injury information available for home team.")
                            with col2:
                                st.write(f"**{row['Away Team']} Injuries**")
                                away_injuries = fetch_injuries(row['away_team_id'], row['league'])
                                if away_injuries:
                                    st.dataframe(pd.DataFrame(away_injuries), hide_index=True)
                                else:
                                    st.info("No injury information available for away team.")
                        
                        if analysis_type in ["Team Form", "All Data"]:
                            st.subheader("Team Form")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**{row['Home Team']} Recent Form**")
                                home_form = fetch_team_form(row['home_team_id'])
                                if home_form:
                                    st.dataframe(pd.DataFrame(home_form), hide_index=True)
                                else:
                                    st.info("No form data available for home team.")
                            with col2:
                                st.write(f"**{row['Away Team']} Recent Form**")
                                away_form = fetch_team_form(row['away_team_id'])
                                if away_form:
                                    st.dataframe(pd.DataFrame(away_form), hide_index=True)
                                else:
                                    st.info("No form data available for away team.")
                        
                        if analysis_type in ["Weather", "All Data"]:
                            st.subheader("Weather Information")
                            weather = fetch_weather_for_fixture(row['fixture_id'])
                            if weather:
                                # Convert weather info to DataFrame
                                weather_data = [{
                                    'City': weather['city'],
                                    'Temperature': weather['temperature'],
                                    'Condition': weather['condition'],
                                    'Humidity': weather['humidity'],
                                    'Wind': weather['wind']
                                }]
                                st.dataframe(pd.DataFrame(weather_data), hide_index=True)
                            else:
                                st.info("No weather information available.")
                        
                        if analysis_type in ["Referee Information", "All Data"]:
                            st.subheader("Referee Information")
                            referee = fetch_referee_info(row['fixture_id'])
                            if referee:
                                # Convert referee info to DataFrame
                                referee_data = [{
                                    'Name': referee['name'],
                                    'Fixtures': referee['fixtures'],
                                    'Yellow Cards': referee['yellow_cards'],
                                    'Red Cards': referee['red_cards']
                                }]
                                st.dataframe(pd.DataFrame(referee_data), hide_index=True)
                            else:
                                st.info("No referee information available.")
            
            # Check if any predictions were simulated
            if "Simulated" in analysis_df['Source'].values:
                st.warning("Some predictions are simulated because fixture IDs were not available for all selected matches.")

            # Debug: Log data for Inter vs Monza after columns are created
            for i in range(len(analysis_df)):
                row = analysis_df.iloc[i]
                if row['Home Team'] == 'Inter' and row['Away Team'] == 'Monza':
                    print(f"Debug: Inter vs Monza - Home Win %: {row['Home Win %']}, Draw %: {row['Draw %']}, Away Win %: {row['Away Win %']}, Highest Probability %: {row['Highest Probability %']}, Predicted Result: {row['Predicted Result']}")

            # Ensure 'Highest Probability %' is formatted as a percentage
            analysis_df['Highest Probability %'] = analysis_df['Highest Probability %'].apply(lambda x: f"{float(x):.0f}%")

            # Correct string parsing for expected goals and cards
            analysis_df['Prediction Details'] = analysis_df.apply(
                lambda row: f"Highest Probability: {row['Predicted Result']}\nExpected Goals: {row['Prediction Details'].split('Expected Goals: ')[1].split(' ')[0].strip()}\nExpected Cards: {row['Prediction Details'].split('Expected Cards: ')[1].split(' ')[0].strip()}",
                axis=1
            )

            # Ensure the 'View Details' column in the Match Analysis table is renamed to 'Additional Analysis'
            if 'View Details' in analysis_df.columns:
                analysis_df.rename(columns={'View Details': 'Additional Analysis'}, inplace=True)

else:
    st.warning("No standings data available. Please check back later.") 