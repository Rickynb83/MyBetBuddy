import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import requests
from typing import List, Dict
from dotenv import load_dotenv
import os
import io
from lib.fetch_fixtures import API_KEY, LEAGUES

# Set page config
st.set_page_config(
    page_title="Football Match Predictions",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"  # Changed from 'collapsed' to 'expanded'
)

# Load environment variables
load_dotenv('.env.local')

# Custom CSS for better styling
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
    .metric-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .prediction-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# App title with styling
st.title("⚽ Football Match Predictions")

# Initialize session state for fixtures
if 'fixtures' not in st.session_state:
    st.session_state.fixtures = []
if 'selected_matches' not in st.session_state:
    st.session_state.selected_matches = []

# Fetch fixtures when app starts
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_fixtures():
    from lib.fetch_fixtures import fetch_fixtures
    return fetch_fixtures()

# Load fixtures
fixtures = load_fixtures()

# Get unique leagues from fixtures
leagues = []
if fixtures:
    leagues = sorted(list({f['league'] for f in fixtures}))
    print(f"Found {len(leagues)} leagues: {leagues}")
    if not leagues:
        st.warning("No leagues found in fixtures. Please try again later.")
else:
    st.warning("No fixtures found. Please try again later.")

# Sidebar for selections
with st.sidebar:
    st.header("Settings")
    
    # AI Provider Selection
    ai_provider = st.selectbox(
        "Select AI Provider",
        ["OpenAI", "Anthropic", "HuggingFace"],
        help="Choose the AI model for predictions"
    )
    
    # League Selection
    if leagues:
        selected_leagues = st.multiselect(
            "Select Leagues",
            leagues,
            default=leagues,
            help="Choose leagues to show fixtures from"
        )
    else:
        st.error("No leagues available")

# Filter matches based on selections
def filter_matches():
    if not fixtures:
        return []
        
    filtered_matches = []
    for fixture in fixtures:
        try:
            if (not selected_leagues or fixture['league'] in selected_leagues):
                filtered_matches.append(fixture)
        except Exception as e:
            print(f"Error processing match date: {e}")
            continue
    
    return filtered_matches

# Get filtered matches
filtered_matches = filter_matches()

# Fetch standings
from lib.fetch_fixtures import fetch_standings
standings = fetch_standings()

# Now display standings with filtered matches available
if standings:
    st.header("League Standings")
    
    # Group standings by league
    league_standings = {}
    for team, rank in standings.items():
        league_name = next((match['league'] for match in filtered_matches if match['homeTeam'] == team or match['awayTeam'] == team), None)
        if league_name:
            if league_name not in league_standings:
                league_standings[league_name] = []
            league_standings[league_name].append({'team': team, 'rank': rank})
    
    # Create tabs for each league
    if league_standings:
        tabs = st.tabs(list(league_standings.keys()))
        for tab, league_name in zip(tabs, league_standings.keys()):
            with tab:
                # Get team stats from API
                response = requests.get(
                    'https://api-football-v1.p.rapidapi.com/v3/standings',
                    headers={
                        'X-RapidAPI-Key': API_KEY,
                        'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
                    },
                    params={
                        'season': 2024,
                        'league': next(league['id'] for league in LEAGUES if league['name'] == league_name)
                    }
                )
                
                data = response.json()
                if data.get('response'):
                    standings_data = data['response'][0]['league']['standings'][0]
                    
                    # Create DataFrame
                    table_data = []
                    for team in standings_data:
                        table_data.append({
                            "Position": team['rank'],
                            "Team": team['team']['name'],
                            "Played": team['all']['played'],
                            "Won": team['all']['win'],
                            "Drawn": team['all']['draw'],
                            "Lost": team['all']['lose'],
                            "GF": team['all']['goals']['for'],
                            "GA": team['all']['goals']['against'],
                            "GD": team['goalsDiff'],
                            "Points": team['points'],
                            "Form": team['form']
                        })
                    
                    df = pd.DataFrame(table_data)
                    
                    # Style the table
                    def style_table(row):
                        styles = []
                        pos = row['Position']
                        
                        if pos <= 4:  # Champions League
                            color = '#e6f3e6'  # Light green
                        elif pos == 5:  # Europa League
                            color = '#e6ffe6'  # Very light green
                        elif pos >= len(table_data) - 2:  # Relegation
                            color = '#ffe6e6'  # Light red
                        else:
                            color = 'white'
                            
                        return [f'background-color: {color}'] * len(row)
                    
                    # Apply styling and display
                    styled_df = df.style.apply(style_table, axis=1)
                    st.dataframe(
                        styled_df,
                        hide_index=True,
                        column_config={
                            "Position": st.column_config.NumberColumn(width=70),
                            "Team": st.column_config.Column(width=200),
                            "Played": st.column_config.NumberColumn(width=70),
                            "Won": st.column_config.NumberColumn(width=70),
                            "Drawn": st.column_config.NumberColumn(width=70),
                            "Lost": st.column_config.NumberColumn(width=70),
                            "GF": st.column_config.NumberColumn("Goals For", width=70),
                            "GA": st.column_config.NumberColumn("Goals Against", width=70),
                            "GD": st.column_config.NumberColumn("Goal Diff", width=70),
                            "Points": st.column_config.NumberColumn(width=70),
                            "Form": st.column_config.Column("Last 5", width=100)
                        },
                        use_container_width=True
                    )
                    
                    # Add legend
                    st.markdown("""
                    **Key:**
                    - <span style='background-color: #e6f3e6; padding: 2px 6px;'>Champions League</span>
                    - <span style='background-color: #e6ffe6; padding: 2px 6px;'>Europa League</span>
                    - <span style='background-color: #ffe6e6; padding: 2px 6px;'>Relegation</span>
                    """, unsafe_allow_html=True)

# Add this function after the filter_matches function
def analyze_matches(matches):
    from lib.fetch_fixtures import fetch_standings
    standings = fetch_standings()
    
    predictions = []
    for match in matches:
        # Split "Team A vs Team B" into separate teams
        home_team, away_team = match['homeTeam'], match['awayTeam']
        
        # Get positions
        home_pos = standings.get(home_team, "N/A")
        away_pos = standings.get(away_team, "N/A")
        
        # Calculate probabilities based on positions
        if home_pos != "N/A" and away_pos != "N/A":
            # Better position means higher win probability
            position_diff = away_pos - home_pos
            
            # Add home advantage
            home_advantage = 10
            
            # Calculate base probabilities
            home_prob = min(75, max(15, 35 + home_advantage + (position_diff * 2)))
            away_prob = min(75, max(15, 35 - home_advantage - (position_diff * 2)))
            draw_prob = 100 - home_prob - away_prob
            
            # Determine alternative bet based on team positions
            if abs(position_diff) > 10:
                alt_bet = "Over 2.5 Goals" if home_pos < away_pos else "Under 2.5 Goals"
            elif abs(position_diff) < 3:
                alt_bet = "Both Teams to Score"
            else:
                alt_bet = "+1.5 Goals" if min(home_pos, away_pos) < 6 else "Under 3.5 Goals"
        else:
            # Default probabilities if positions unknown
            home_prob = 35
            away_prob = 35
            draw_prob = 30
            alt_bet = "Over 2.5 Goals"
        
        predictions.append({
            "fixture": f"{home_team} vs {away_team}",
            "home_pos": f"{home_pos}th",
            "away_pos": f"{away_pos}th",
            "home": f"{home_prob:.0f}%",
            "draw": f"{draw_prob:.0f}%",
            "away": f"{away_prob:.0f}%",
            "altBet": alt_bet
        })
    
    return predictions

# Main content area
col1, col2 = st.columns([4, 1])  # Changed from [2, 1] to [4, 1]

with col1:
    st.subheader("Available Matches")
    
    # Create a table of all available matches with positions
    available_matches = []
    
    for match in filtered_matches:
        home_team = match['homeTeam']
        away_team = match['awayTeam']
        
        home_pos = standings.get(home_team)
        away_pos = standings.get(away_team)
        
        print(f"Team positions - {home_team}: {home_pos}, {away_team}: {away_pos}")  # Debug output
        
        available_matches.append({
            "Date": match['matchDate'],
            "Time": match['time'],
            "League": match['league'],
            "Home Position": f"{home_pos}th" if home_pos is not None else "N/A",
            "Home Team": home_team,
            "Away Team": away_team,
            "Away Position": f"{away_pos}th" if away_pos is not None else "N/A",
            "Select": False
        })
    
    # Display available matches table with auto-fitting columns
    if available_matches:
        matches_df = pd.DataFrame(available_matches)
        
        # Initialize select_all in session state if not present
        if 'select_all' not in st.session_state:
            st.session_state.select_all = False
        
        # Add Select All checkbox above the table
        st.session_state.select_all = st.checkbox(
            "Select All Matches", 
            value=st.session_state.select_all,
            key="select_all_checkbox"
        )
        
        # Reorder columns for better view
        column_order = [
            "Date",
            "Time",
            "League",
            "Home Position",
            "Home Team",
            "Away Team", 
            "Away Position",
            "Select"
        ]
        matches_df = matches_df[column_order]
        
        # Set all Select values based on select_all checkbox
        matches_df["Select"] = st.session_state.select_all
        
        edited_df = st.data_editor(
            matches_df,
            hide_index=True,
            column_config={
                "Date": st.column_config.Column(
                    width=65,
                ),
                "Time": st.column_config.Column(
                    width=55,
                ),
                "League": st.column_config.Column(
                    "League",
                    width=100,
                ),
                "Home Position": st.column_config.Column(
                    "Pos",
                    width=40,
                ),
                "Home Team": st.column_config.Column(
                    "Home",
                    width=130,
                ),
                "Away Team": st.column_config.Column(
                    "Away",
                    width=130,
                ),
                "Away Position": st.column_config.Column(
                    "Pos",
                    width=40,
                ),
                "Select": st.column_config.CheckboxColumn(
                    "✓",
                    width=40,
                    default=False
                )
            },
            use_container_width=True,
            num_rows="dynamic"
        )
        
        # Get selected matches from edited dataframe
        if 'Select' in edited_df.columns:
            selected_rows = edited_df[edited_df['Select']]
            selected_matches = [
                f"{row['Home Team']} vs {row['Away Team']}"
                for _, row in selected_rows.iterrows()
            ]
            
            if selected_matches:
                if st.button("Analyze Selected Matches", type="primary"):
                    match_objects = [
                        match for match in filtered_matches
                        if f"{match['homeTeam']} vs {match['awayTeam']}" in selected_matches
                    ]
                    st.session_state.predictions = analyze_matches(match_objects)

with col2:
    if st.session_state.selected_matches:
        st.subheader("Selected Matches")
        for match in st.session_state.selected_matches:
            st.info(match)

# Predictions Display
if st.session_state.get("predictions"):
    st.header("Match Predictions")
    
    # Create table data
    table_data = []
    for pred in st.session_state.predictions:
        home_team, away_team = pred["fixture"].split(" vs ")
        table_data.append({
            "Home Position": pred["home_pos"],
            "Home": home_team,
            "Away": away_team,
            "Away Position": pred["away_pos"],
            "Home Win": pred["home"],
            "Draw": pred["draw"],
            "Away Win": pred["away"],
            "Alternative Bet": pred["altBet"]
        })
    
    # Display as table
    df = pd.DataFrame(table_data)
    st.table(df)
    
    # Add Excel export option with enhanced formatting
    def convert_df_to_excel():
        # Create new DataFrame with additional columns
        export_df = df.copy()
        
        # Add highest probability columns
        export_df['Highest %'] = export_df.apply(lambda row: max(
            float(row['Home Win'].strip('%')),
            float(row['Draw'].strip('%')),
            float(row['Away Win'].strip('%'))
        ), axis=1).astype(str) + '%'
        
        export_df['Prediction'] = export_df.apply(lambda row: (
            'Home Win' if float(row['Home Win'].strip('%')) == float(row['Highest %'].strip('%'))
            else 'Draw' if float(row['Draw'].strip('%')) == float(row['Highest %'].strip('%'))
            else 'Away Win'
        ), axis=1)

        # Sort by highest probability (descending)
        export_df['Sort Value'] = export_df['Highest %'].str.rstrip('%').astype(float)
        export_df = export_df.sort_values('Sort Value', ascending=False)
        export_df = export_df.drop('Sort Value', axis=1)  # Remove the sorting column

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='Predictions', index=False)
            
            # Get the workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Predictions']
            
            # Add formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#0e1117',
                'font_color': 'white',
                'border': 1,
                'align': 'center'
            })
            
            percent_format = workbook.add_format({
                'num_format': '0%',
                'align': 'center'
            })
            
            center_format = workbook.add_format({
                'align': 'center'
            })
            
            # Format the header row
            for col_num, value in enumerate(export_df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Format percentage columns
            for row in range(1, len(export_df) + 1):
                worksheet.write_number(row, 4, float(export_df.iloc[row-1]['Home Win'].strip('%'))/100, percent_format)
                worksheet.write_number(row, 5, float(export_df.iloc[row-1]['Draw'].strip('%'))/100, percent_format)
                worksheet.write_number(row, 6, float(export_df.iloc[row-1]['Away Win'].strip('%'))/100, percent_format)
                worksheet.write_number(row, 8, float(export_df.iloc[row-1]['Highest %'].strip('%'))/100, percent_format)
            
            # Center align all other cells
            for col in [0, 1, 2, 3, 7, 9]:  # Non-percentage columns
                for row in range(1, len(export_df) + 1):
                    worksheet.write(row, col, export_df.iloc[row-1][export_df.columns[col]], center_format)
            
            # Auto-adjust columns width
            for column in export_df:
                column_length = max(export_df[column].astype(str).apply(len).max(), len(column))
                col_idx = export_df.columns.get_loc(column)
                worksheet.set_column(col_idx, col_idx, column_length + 2)
            
            # Freeze the header row
            worksheet.freeze_panes(1, 0)
            
            # Add alternating row colors without grouping
            for row in range(1, len(export_df) + 1):
                if row % 2 == 0:
                    for col in range(len(export_df.columns)):
                        cell_format = workbook.add_format({
                            'bg_color': '#f0f0f0',
                            'align': 'center'
                        })
                        if col in [4, 5, 6, 8]:  # Percentage columns
                            cell_format.set_num_format('0%')
                        worksheet.write(row, col, export_df.iloc[row-1][export_df.columns[col]], cell_format)
        
        return output.getvalue()
    
    # Add download button
    excel_file = convert_df_to_excel()
    current_date = datetime.now().strftime('%Y-%m-%d')
    st.download_button(
        label="📥 Download Predictions as Excel",
        data=excel_file,
        file_name=f'football_predictions_{current_date}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Data updated:** {}".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
with col2:
    st.markdown("**API Status:** 🟢 Online")
with col3:
    if st.button("New Analysis", type="secondary"):
        st.session_state.predictions = None
        st.rerun()