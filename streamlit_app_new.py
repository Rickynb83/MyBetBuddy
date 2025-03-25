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
import json
from streamlit_javascript import st_javascript
import secrets
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from supabase import create_client, Client
import bcrypt
from io import BytesIO

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

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Authentication functions
def authenticate_user(username, password):
    """Authenticate user with username and password"""
    try:
        # Get user from database
        user = supabase.table('users').select('*').eq('username', username).execute()
        
        if user.data and len(user.data) > 0:
            user_data = user.data[0]
            # Verify password
            if verify_password(user_data['password'], password):
                return user_data
        return None
    except Exception as e:
        print(f"Authentication error: {e}")
        return None

def generate_reset_token():
    """Generate a secure random token for password reset"""
    return secrets.token_urlsafe(32)

def send_reset_email(email, reset_token):
    """Send password reset email using Zoho Mail"""
    try:
        # Get Zoho credentials from environment variables
        zoho_password = os.getenv('ZOHO_EMAIL_PASSWORD')
        if not zoho_password:
            print("Error: Zoho password not found in environment variables")
            st.error("Email configuration error: Zoho password not found")
            return False
            
        # Email configuration
        sender_email = "welcome@mybetbuddy.app"  # Your Zoho email
        sender_password = zoho_password
        receiver_email = email
        
        print(f"Attempting to send email from {sender_email} to {receiver_email}")
        
        # Create a complete reset link
        reset_link = f"https://mybetbuddy-df3f219c1b11.herokuapp.com/reset-password?token={reset_token}"
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "Password Reset Request"
        msg['Date'] = formatdate(localtime=True)
        
        # Email body
        body = f"""
        Hello,
        
        You have requested to reset your password for MyBetBuddy. Click the link below to reset your password:
        
        {reset_link}
        
        This link will expire in 24 hours.
        
        If you did not request this password reset, please ignore this email.
        
        Best regards,
        MyBetBuddy Team
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        print("Connecting to Zoho Mail SMTP server...")
        # Create SMTP session with Zoho Mail settings
        with smtplib.SMTP_SSL('smtppro.zoho.eu', 465) as server:  # Use SSL port 465
            print("Attempting to login...")
            server.login(sender_email, sender_password)
            print("Login successful, sending message...")
            server.send_message(msg)
            print("Message sent successfully")
        
        return True
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        if hasattr(e, 'smtp_error'):
            print(f"SMTP Error: {e.smtp_error}")
        if hasattr(e, 'smtp_code'):
            print(f"SMTP Code: {e.smtp_code}")
        st.error(f"Failed to send reset email: {str(e)}")
        return False

def request_password_reset(email):
    """Handle password reset request."""
    try:
        # Debug: Print the email being searched for
        print(f"Searching for email: {email}")
        
        # Check if email exists
        response = supabase.table('users').select('id').eq('email', email).execute()
        
        # Debug: Print the response
        print(f"Database response: {response}")
        
        if not response.data:
            st.error("Email not found. Please check your email address.")
            return False
            
        # Generate reset token
        reset_token = generate_reset_token()
        expires_at = datetime.now() + timedelta(hours=24)
        
        # Debug: Print the update data
        print(f"Updating user with token: {reset_token}")
        
        # Update user with reset token
        update_response = supabase.table('users').update({
            'reset_token': reset_token,
            'reset_token_expires': expires_at.isoformat()
        }).eq('email', email).execute()
        
        # Debug: Print the update response
        print(f"Update response: {update_response}")
        
        # Send reset email
        if send_reset_email(email, reset_token):
            st.success("Password reset link has been sent to your email.")
            return True
        else:
            st.error("Failed to send reset email. Please try again later.")
            return False
            
    except Exception as e:
        print(f"Error in request_password_reset: {str(e)}")
        st.error(f"Error processing reset request: {str(e)}")
        return False

def reset_password(token, new_password):
    """Reset user's password using reset token."""
    try:
        # Verify token and get user
        response = supabase.table('users').select('id').eq('reset_token', token).execute()
        
        if not response.data:
            st.error("Invalid or expired reset token.")
            return False
            
        user = response.data[0]
        
        # Update password and clear reset token
        supabase.table('users').update({
            'password': new_password,
            'reset_token': None,
            'reset_token_expires': None
        }).eq('id', user['id']).execute()
        
        return True
    except Exception as e:
        st.error(f"Error resetting password: {str(e)}")
        return False

def register_user(username, email, password):
    """Register a new user in Supabase"""
    try:
        # Check if username already exists
        existing_username = supabase.table('users').select('id').eq('username', username).execute()
        if existing_username.data:
            st.error("Username already exists")
            return False
            
        # Check if email already exists
        existing_email = supabase.table('users').select('id').eq('email', email).execute()
        if existing_email.data:
            st.error("Email already registered. Please use a different email or try logging in.")
            return False
            
        # Check if email is whitelisted
        whitelist = load_whitelist()
        if email not in whitelist:
            st.error(f"Email not in whitelist. Please contact the administrator.")
            return False
            
        # Hash the password using bcrypt
        hashed_password = hash_password(password)
        
        # Insert new user into Supabase
        response = supabase.table('users').insert({
            'username': username,
            'email': email,
            'password': hashed_password
        }).execute()
        
        if response.data:
            st.success("Registration successful! Please login.")
            return True
        else:
            st.error("Registration failed. Please try again.")
            return False
            
    except Exception as e:
        st.error(f"Registration error: {str(e)}")
        return False

def verify_password(stored_password, provided_password):
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def hash_password(password):
    """Create a hashed password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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
        
        # Add tabs for login, register, and password reset
        tab1, tab2, tab3 = st.tabs(["Login", "Register", "Reset Password"])
        
        with tab1:
            st.subheader("Login")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login"):
                user = authenticate_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid username or password")
                    print(f"Login failed for username: {username}")  # Debug print
        
        with tab2:
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
                else:
                    # Register user in Supabase
                    if register_user(reg_username, reg_email, reg_password):
                        st.success("Registration successful! Please login.")
                        st.rerun()  # Rerun to show login form
        
        with tab3:
            st.subheader("Reset Password")
            st.write("Enter your email address to receive a password reset link")
            reset_email = st.text_input("Email", key="reset_email")
            if st.button("Send Reset Link"):
                if request_password_reset(reset_email):
                    st.success("Password reset link has been sent to your email")
                else:
                    st.error("Email not found or error sending reset link")
        
        # Stop execution here if not authenticated
        if not st.session_state.authenticated:
            st.stop()
    
    # Show logout button if authenticated
    if st.session_state.authenticated:
        st.sidebar.success(f"Welcome {st.session_state.username}")
        
        # Add mobile view toggle
        st.sidebar.markdown("### Display Settings")
        mobile_view = st.sidebar.checkbox("Mobile-friendly view", value=st.session_state.get('mobile_view', False))
        if mobile_view != st.session_state.get('mobile_view', False):
            st.session_state.mobile_view = mobile_view
            st.rerun()
        
        # Add compact tables toggle
        compact_tables = st.sidebar.checkbox("Compact tables (better for small screens)", value=st.session_state.get('compact_tables', False))
        if compact_tables != st.session_state.get('compact_tables', False):
            st.session_state.compact_tables = compact_tables
            st.rerun()
        
        # Add admin section for password reset (only for admin users)
        if st.session_state.username == "admin" or st.session_state.username == "rickynb83":
            st.sidebar.markdown("### Admin Tools")
            st.sidebar.markdown("#### Reset User Password")
            
            # Get list of usernames
            user_list = list(users.keys())
            selected_user = st.sidebar.selectbox("Select User", user_list)
            
            new_password = st.sidebar.text_input("New Password", type="password", key="new_password")
            confirm_password = st.sidebar.text_input("Confirm Password", type="password", key="confirm_password")
            
            if st.sidebar.button("Reset Password"):
                if new_password != confirm_password:
                    st.sidebar.error("Passwords do not match")
                elif not new_password:
                    st.sidebar.error("Password cannot be empty")
                else:
                    # Update the user's password
                    users[selected_user]['password'] = hash_password(new_password)
                    save_users(users)
                    st.sidebar.success(f"Password reset for {selected_user}")
        
        if st.sidebar.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()

# Apply custom CSS for consistent font sizes and adjust padding to fix header overlap
st.markdown("""
<style>
    /* Force all tables to fit within the container width */
    .stDataFrame, .stTable, [data-testid="stDataFrameResizable"] {
        width: auto !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
    }
    
    /* Force table to use fixed layout and fit within container */
    .stDataFrame table, .stTable table {
        width: auto !important;
        table-layout: fixed !important;
        font-size: 14px;
    }
    
    /* Force all table cells to wrap content and limit width */
    .stDataFrame table td, .stTable table td,
    .stDataFrame table th, .stTable table th {
        white-space: normal !important;
        word-break: break-word !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        padding: 0.15rem 0.2rem !important;
        font-size: inherit !important;
    }
    
    /* Remove top padding to prevent header overlap */
    .block-container {
        padding-top: 3rem;
    }
    
    /* Style for analysis sections */
    .analysis-section {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    
    /* Adjust font sizes for mobile */
    @media screen and (max-width: 640px) {
        .stDataFrame table, .stTable table {
            font-size: 10px !important;
        }
        
        .stDataFrame table td, .stTable table td,
        .stDataFrame table th, .stTable table th {
            padding: 0.1rem 0.15rem !important;
        }
        
        h1 {
            font-size: 1.5rem !important;
        }
        
        h2 {
            font-size: 1.3rem !important;
        }
        
        h3 {
            font-size: 1.1rem !important;
        }
        
        .stButton button {
            font-size: 0.8rem;
            padding: 0.3rem 0.5rem;
        }
        
        /* Reduce padding on mobile */
        .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
    }
    
    /* Tablet adjustments */
    @media screen and (min-width: 641px) and (max-width: 1024px) {
        .stDataFrame table, .stTable table {
            font-size: 12px !important;
        }
    }
    
    /* Ensure buttons and interactive elements are touch-friendly */
    button, select, .stSelectbox, .stMultiselect {
        min-height: 36px;
    }
    
    /* Hide horizontal scrollbar */
    .stDataFrame::-webkit-scrollbar-horizontal,
    .stTable::-webkit-scrollbar-horizontal,
    [data-testid="stDataFrameResizable"]::-webkit-scrollbar-horizontal {
        display: none !important;
    }
    
    /* Additional fixes for Streamlit's internal containers */
    [data-testid="stDataFrameResizable"] {
        overflow-x: hidden !important;
        width: auto !important;
    }
    
    /* Target the specific container that might be causing scrolling */
    [data-testid="stHorizontalBlock"] {
        overflow-x: hidden !important;
        max-width: 100% !important;
    }
    
    /* Target the table wrapper */
    .stDataFrame > div, .stTable > div {
        overflow-x: hidden !important;
    }
    
    /* Disable all horizontal scrolling in the app */
    div[data-testid="stAppViewContainer"] {
        overflow-x: hidden !important;
    }
    
    /* Disable column resizing */
    .resize-handle {
        display: none !important;
    }
    
    /* Fix for tab navigation bar */
    .stTabs [data-baseweb="tab-list"] {
        flex-wrap: wrap !important;
        overflow-x: hidden !important;
    }
    
    /* API-Football widget style for standings table */
    .api-football-standings {
        width: 100%;
        border-collapse: collapse;
        font-family: Arial, sans-serif;
        font-size: 14px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        border-radius: 4px;
        overflow: hidden;
    }
    
    .api-football-standings th {
        background-color: #38003c !important;
        color: white !important;
        font-weight: bold !important;
        text-align: center !important;
        padding: 10px 5px !important;
        font-size: 12px !important;
        position: sticky !important;
        top: 0 !important;
        z-index: 10 !important;
    }
    
    .api-football-standings td {
        padding: 8px 5px;
        text-align: center;
        border-bottom: 1px solid #f0f0f0;
    }
    
    .api-football-standings tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    
    .api-football-standings tr:hover {
        background-color: #f0f0f0;
    }
    
    .team-cell {
        display: flex;
        align-items: center;
        text-align: left;
        padding-left: 5px;
    }
    
    .form-badge {
        display: inline-block;
        width: 16px;
        height: 16px;
        line-height: 16px;
        text-align: center;
        border-radius: 50%;
        color: white;
        font-size: 10px;
        margin-right: 2px;
    }
    
    .form-w {
        background-color: #4CAF50;
    }
    
    .form-d {
        background-color: #FFC107;
    }
    
    .form-l {
        background-color: #F44336;
    }
    
    /* Ensure tables are aligned properly */
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 0 !important;
    }
    
    .stTabs [data-baseweb="tab-panel"] h3 {
        margin-top: 1rem !important;
        margin-bottom: 0.5rem !important;
        height: 40px !important;
        line-height: 40px !important;
    }
    
    /* Ensure both tables have the same top alignment */
    .stTabs [data-baseweb="tab-panel"] .stSubheader {
        margin-top: 0 !important;
        margin-bottom: 0.5rem !important;
        height: 40px !important;
        line-height: 40px !important;
    }
    
    /* Ensure columns have equal spacing */
    .stTabs [data-baseweb="tab-panel"] .row-widget {
        margin-top: 0 !important;
    }
    
    /* Scrollable container styling with fixed header */
    .standings-scroll-container {
        max-height: 500px;
        overflow-y: auto;
        border-radius: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    /* Custom scrollbar styling */
    .standings-scroll-container::-webkit-scrollbar {
        width: 8px;
    }
    
    .standings-scroll-container::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    .standings-scroll-container::-webkit-scrollbar-thumb {
        background: #38003c;
        border-radius: 4px;
    }
    
    .standings-scroll-container::-webkit-scrollbar-thumb:hover {
        background: #5a1e5a;
    }
    
    /* Style for data editor headers */
    .stDataFrame [data-testid="stDataFrameResizable"] th {
        background-color: #38003c !important;
        color: white !important;
        font-weight: bold !important;
        text-align: center !important;
        padding: 10px 5px !important;
        font-size: 12px !important;
    }
    
    /* Style for data editor header cells */
    .stDataFrame [data-testid="stDataFrameResizable"] thead th:hover {
        background-color: #38003c !important;
        color: white !important;
    }
    
    /* Style for data editor header cells when selected */
    .stDataFrame [data-testid="stDataFrameResizable"] thead th:focus {
        background-color: #38003c !important;
        color: white !important;
    }
    
    /* Style for data editor header cells when active */
    .stDataFrame [data-testid="stDataFrameResizable"] thead th:active {
        background-color: #38003c !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if 'show_instructions' not in st.session_state:
    st.session_state.show_instructions = False

# App title
st.title("⚽ MyBetBuddy - Football Match Predictions")

# Add instructions button below the title
if st.button("📖 Instructions", key="instructions_button"):
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

# Fetch standings
standings = fetch_standings()
print("Standings Data:", standings)  # Debug line to check the fetched standings data

# Add debug print to check the structure of the standings data
for league_name, league_data in standings.items():
    print(f"League: {league_name}, Number of teams: {len(league_data)}")
    if league_data and len(league_data) > 0:
        print(f"First team: {league_data[0]}")

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
    'Premiership': 179,  # Scottish Premiership
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

# Callback function to handle fixture selection updates
def handle_fixture_selection(key, selected):
    """
    Handles fixture selection updates from the UI.
    
    This function is called when a user clicks a checkbox in the fixtures table.
    It parses the fixture key to extract team names and date, then updates the
    session state accordingly.
    
    Parameters:
    -----------
    key : str
        The fixture key in format "Home Team vs Away Team (Date)"
    selected : bool
        Whether the fixture is selected (True) or deselected (False)
    """
    print(f"Handling fixture selection: {key}, Selected: {selected}")
    
    # Parse the key to get fixture details
    parts = key.split(" vs ")
    if len(parts) == 2 and "(" in parts[1]:
        home_team = parts[0]
        away_team_date = parts[1].split(" (")
        away_team = away_team_date[0]
        date = away_team_date[1].rstrip(")")
        
        # Find the fixture in the session state
        fixture_found = False
        for i, fixture in enumerate(st.session_state.selected_fixtures):
            if (fixture.get('Home Team') == home_team and 
                fixture.get('Away Team') == away_team and 
                fixture.get('Date') == date):
                
                # If deselected, remove from selected fixtures
                if not selected:
                    st.session_state.selected_fixtures.pop(i)
                    print(f"Removed fixture: {key}")
                fixture_found = True
                break
        
        # If selected and not found, we need to add it directly
        if selected and not fixture_found:
            print(f"Adding fixture directly: {key}")
            # Find the fixture in the current league's fixtures DataFrame
            for league_name, league_id in LEAGUES.items():
                try:
                    fixtures = fetch_fixtures(league_id)
                    if fixtures:
                        fixtures_df = pd.DataFrame(fixtures)
                        if not fixtures_df.empty:
                            # Convert to proper format
                            fixtures_df['Date'] = pd.to_datetime(fixtures_df['date']).dt.strftime('%d/%m %I:%M %p')
                            fixtures_df['Date'] = fixtures_df['Date'].str.replace(' AM', 'am').str.replace(' PM', 'pm')
                            fixtures_df = fixtures_df.rename(columns={'homeTeam': 'Home Team', 'awayTeam': 'Away Team'})
                            
                            # Find the matching fixture
                            for _, row in fixtures_df.iterrows():
                                if (row['Home Team'] == home_team and 
                                    row['Away Team'] == away_team):
                                    
                                    # Get standings for this league to add positions
                                    standings_data = fetch_standings().get(league_name, [])
                                    standings_df = pd.DataFrame(standings_data)
                                    
                                    # Get positions if available
                                    home_position = 'N/A'
                                    away_position = 'N/A'
                                    
                                    if not standings_df.empty and 'team' in standings_df.columns and 'rank' in standings_df.columns:
                                        home_team_data = standings_df[standings_df['team'] == home_team]
                                        away_team_data = standings_df[standings_df['team'] == away_team]
                                        
                                        if not home_team_data.empty:
                                            home_position = str(home_team_data.iloc[0]['rank'])
                                        
                                        if not away_team_data.empty:
                                            away_position = str(away_team_data.iloc[0]['rank'])
                                    
                                    # Create fixture dict with all necessary data
                                    fixture_dict = {
                                        'Date': row['Date'],
                                        'Home Position': home_position,
                                        'Home Team': row['Home Team'],
                                        'Away Team': row['Away Team'],
                                        'Away Position': away_position,
                                        'fixture_id': row['fixture_id'],
                                        'home_team_id': row['home_team_id'],
                                        'away_team_id': row['away_team_id'],
                                        'venue': row['venue'],
                                        'league': league_name
                                    }
                                    
                                    # Add to session state
                                    st.session_state.selected_fixtures.append(fixture_dict)
                                    print(f"Added fixture to selected_fixtures: {fixture_dict}")
                                    print(f"Current selected fixtures count: {len(st.session_state.selected_fixtures)}")
                                    break
                except Exception as e:
                    print(f"Error finding fixture in {league_name}: {e}")
    
    # Print the current state of selected fixtures for debugging
    print(f"Current selected fixtures after handling: {len(st.session_state.selected_fixtures)}")
    for i, fixture in enumerate(st.session_state.selected_fixtures[:3]):  # Show first 3 for debugging
        print(f"Fixture {i+1}: {fixture.get('Home Team')} vs {fixture.get('Away Team')} ({fixture.get('Date')})")
    
    # Only rerun if there were actual changes
    if 'last_selection' not in st.session_state:
        st.session_state.last_selection = None
    
    if st.session_state.last_selection != key:
        st.session_state.last_selection = key
        st.rerun()

# Display standings if available
if standings:
    # Create tabs for each league
    league_tabs = st.tabs(LEAGUES.keys())

    # Pass selected fixtures to JavaScript
    selected_keys = []
    if st.session_state.selected_fixtures:
        for fixture in st.session_state.selected_fixtures:
            if isinstance(fixture, dict) and 'Home Team' in fixture and 'Away Team' in fixture and 'Date' in fixture:
                selected_keys.append(f"{fixture['Home Team']} vs {fixture['Away Team']} ({fixture['Date']})")
    
    # Create JavaScript to store selected fixtures
    js_code = f"""
    window.selectedFixtures = {json.dumps(selected_keys)};
    console.log("Initialized selected fixtures:", window.selectedFixtures);
    """
    st.markdown(f"<script>{js_code}</script>", unsafe_allow_html=True)

    for league, tab in zip(LEAGUES.keys(), league_tabs):
        with tab:
            # Create two columns inside the tab with adjusted ratios
            tab_col1, tab_col2 = st.columns([1.4, 1.6])  # Reduced standings width by 30% and increased fixtures width

            with tab_col1:
                # Add subheader for standings
                st.subheader(f"{league} Standings")
                
                # Create a DataFrame for the current league standings
                standings_df = pd.DataFrame(standings[league])

                # Debug: Print the raw standings data
                print(f"\nDEBUG - Raw standings data for {league}:")
                print(standings[league][:3])  # Print first 3 teams
                
                # Remove the extra columns and keep only the necessary columns
                standings_df = standings_df[['rank', 'team', 'played', 'won', 'drawn', 'lost', 'for', 'against', 'points', 'goalsDiff', 'form']]

                # Rename the columns to match the desired table headings
                standings_df.columns = ['Position', 'Team', 'Played', 'Won', 'Drawn', 'Lost', 'For', 'Against', 'Points', 'Goal Difference', 'Form']

                # Sort the DataFrame by Position
                standings_df = standings_df.sort_values(by='Position')
                
                # Debug: Print the sorted standings DataFrame
                print(f"\nDEBUG - Sorted standings DataFrame for {league}:")
                print(standings_df.head(3))

                # Function to parse form string
                def parse_form(form_str):
                    if not form_str:
                        return []
                    
                    # Handle different formats
                    if isinstance(form_str, str):
                        # Remove any whitespace or newlines
                        form_str = form_str.strip()
                        
                        # If it's a string like "WDLWW"
                        if all(c in "WDL" for c in form_str):
                            return list(form_str)
                        
                        # If it's a string like "W,D,L,W,W"
                        if "," in form_str:
                            return [c.strip() for c in form_str.split(",")]
                    
                    # If it's already a list
                    if isinstance(form_str, list):
                        return form_str
                    
                    # Default: try to convert to string and get first 5 characters
                    try:
                        return list(str(form_str)[:5])
                    except:
                        return []

                # Debug print to check the number of teams in the standings DataFrame
                print(f"Number of teams in {league} standings: {len(standings_df)}")
                
                # Create a simple HTML table with minimal formatting and no extra whitespace
                html_parts = []
                html_parts.append('<div class="standings-scroll-container">')
                html_parts.append('<table class="api-football-standings">')
                html_parts.append('<thead>')
                html_parts.append('<tr><th>#</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th><th>Form</th></tr>')
                html_parts.append('</thead>')
                html_parts.append('<tbody>')
                
                # Iterate through each row in the standings DataFrame (all teams)
                for _, row in standings_df.iterrows():
                    # Format the form badges
                    form_html = ""
                    if 'Form' in row and row['Form']:
                        form_results = parse_form(row['Form'])
                        for result in form_results:
                            if result == 'W':
                                form_html += "<span class='form-badge form-w'>W</span>"
                            elif result == 'D':
                                form_html += "<span class='form-badge form-d'>D</span>"
                            elif result == 'L':
                                form_html += "<span class='form-badge form-l'>L</span>"
                    
                    # Create the row HTML with no extra whitespace
                    html_parts.append(f'<tr><td>{row["Position"]}</td><td class="team-cell">{row["Team"]}</td><td>{row["Played"]}</td><td>{row["Won"]}</td><td>{row["Drawn"]}</td><td>{row["Lost"]}</td><td>{row["For"]}</td><td>{row["Against"]}</td><td>{row["Goal Difference"]}</td><td><strong>{row["Points"]}</strong></td><td>{form_html}</td></tr>')
                
                html_parts.append('</tbody>')
                html_parts.append('</table>')
                html_parts.append('</div>')
                
                # Join all parts with no extra whitespace
                standings_html = ''.join(html_parts)
                
                # Debug print to check the HTML structure
                print(f"Generated HTML for {league} standings with {len(standings_df)} rows")
                
                # Display the HTML table
                st.markdown(standings_html, unsafe_allow_html=True)

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
                
                if not fixtures_df.empty:
                    # Convert standings to DataFrame for mapping
                    current_standings_df = pd.DataFrame(standings[league])

                    # Add position columns for home and away teams
                    fixtures_df['Home Position'] = fixtures_df['homeTeam'].map(current_standings_df.set_index('team')['rank'])
                    fixtures_df['Away Position'] = fixtures_df['awayTeam'].map(current_standings_df.set_index('team')['rank'])

                    # Format the date with error handling
                    try:
                        # First try to parse the date column
                        fixtures_df['date'] = pd.to_datetime(fixtures_df['date'])
                        # Then format it
                        fixtures_df['Date'] = fixtures_df['date'].dt.strftime('%d/%m %I:%M %p')
                    except Exception as e:
                        print(f"Error formatting date: {e}")
                        # Fallback to a simpler date format
                        fixtures_df['Date'] = fixtures_df['date'].astype(str)

                    # Convert AM/PM to lowercase am/pm
                    fixtures_df['Date'] = fixtures_df['Date'].str.replace(' AM', 'am').str.replace(' PM', 'pm')

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

                    # Create a container for the fixtures table
                    fixtures_container = st.container()

                    # Display the fixtures in a table with selectable rows
                    with fixtures_container:
                        # Create a unique key for the data editor
                        editor_key = f"fixtures_editor_{league}"
                        
                        # Display the fixtures table with selectable rows
                        edited_df = st.data_editor(
                            fixtures_df[['Select', 'Home Team', 'Home Position', 'Away Team', 'Away Position', 'Date']],
                            hide_index=True,
                            use_container_width=True,
                            key=editor_key,
                            column_config={
                                "Select": st.column_config.CheckboxColumn(
                                    "Select",
                                    help="Select a fixture to analyze",
                                    default=False
                                ),
                                "Home Team": st.column_config.TextColumn("Home", width=150),
                                "Home Position": st.column_config.TextColumn("Pos", width=50),
                                "Away Team": st.column_config.TextColumn("Away", width=150),
                                "Away Position": st.column_config.TextColumn("Pos", width=50),
                                "Date": st.column_config.TextColumn("Date", width=100)
                            }
                        )

                        # Handle selection changes using Streamlit's native selection handling
                        if edited_df is not None:
                            for idx, row in edited_df.iterrows():
                                fixture_key = fixtures_df.iloc[idx]['key']
                                is_selected = row['Select']
                                
                                # Check if the selection state has changed
                                if fixture_key in selected_keys and not is_selected:
                                    # Fixture was deselected
                                    handle_fixture_selection(fixture_key, False)
                                elif fixture_key not in selected_keys and is_selected:
                                    # Fixture was selected
                                    handle_fixture_selection(fixture_key, True)
                        
                            # Only rerun if there were actual changes
                            if 'last_editor_state' not in st.session_state:
                                st.session_state.last_editor_state = {}
                            
                            current_state = str(edited_df['Select'].tolist())
                            if st.session_state.last_editor_state.get(editor_key) != current_state:
                                st.session_state.last_editor_state[editor_key] = current_state
                                st.rerun()

                    # Add select/deselect all buttons below the table
                    if st.button("Select/Deselect All", key=f"toggle_all_{league}"):
                        # Check if all fixtures are currently selected
                        all_selected = all(fixture_key in selected_keys for _, row in fixtures_df.iterrows() for fixture_key in [row['key']])
                        
                        if all_selected:
                            # Deselect all fixtures
                            for _, row in fixtures_df.iterrows():
                                fixture_key = row['key']
                                if fixture_key in selected_keys:
                                    # Remove fixture from session state
                                    st.session_state.selected_fixtures = [
                                        f for f in st.session_state.selected_fixtures 
                                        if not (f['Home Team'] == row['Home Team'] and 
                                               f['Away Team'] == row['Away Team'] and 
                                               f['Date'] == row['Date'])
                                    ]
                        else:
                            # Select all fixtures
                            for _, row in fixtures_df.iterrows():
                                fixture_key = row['key']
                                if fixture_key not in selected_keys:
                                    # Add fixture directly to session state
                                    fixture_dict = {
                                        'Date': row['Date'],
                                        'Home Position': row['Home Position'],
                                        'Home Team': row['Home Team'],
                                        'Away Team': row['Away Team'],
                                        'Away Position': row['Away Position'],
                                        'fixture_id': row['fixture_id'],
                                        'home_team_id': row['home_team_id'],
                                        'away_team_id': row['away_team_id'],
                                        'venue': row['venue'],
                                        'league': league
                                    }
                                    st.session_state.selected_fixtures.append(fixture_dict)
                                    print(f"Added fixture to selected_fixtures: {fixture_dict}")
                        st.rerun()

    # Display selected fixtures and analysis
    if st.session_state.selected_fixtures:
        st.markdown("---")
        st.subheader("Selected Fixtures")
        
        # Debug print for selected fixtures
        print(f"Displaying {len(st.session_state.selected_fixtures)} selected fixtures")
        for i, fixture in enumerate(st.session_state.selected_fixtures[:3]):  # Show first 3 for debugging
            print(f"Fixture {i+1}: {fixture.get('Home Team')} vs {fixture.get('Away Team')} ({fixture.get('Date')})")
        
        # Convert the session state to a DataFrame
        selected_df = pd.DataFrame(st.session_state.selected_fixtures)
        
        # Ensure the DataFrame has the correct columns
        if not selected_df.empty:
            display_columns = ['Home Team', 'Away Team', 'Date']
            for col in display_columns:
                if col not in selected_df.columns:
                    selected_df[col] = ""
            selected_df = selected_df[display_columns]
        
        # Display the DataFrame in a table format
        st.dataframe(
            selected_df,
            hide_index=True,
            use_container_width=False,
            column_config={
                "Home Team": st.column_config.TextColumn("Home", width=150),
                "Away Team": st.column_config.TextColumn("Away", width=150),
                "Date": st.column_config.TextColumn("Date", width=100)
            }
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
                        league_id = None
                        if isinstance(row['league'], str) and row['league'] in LEAGUE_IDS:
                            league_id = LEAGUE_IDS[row['league']]
                        else:
                            # Try to get league ID directly if it's already a number
                            try:
                                if str(row['league']).isdigit():
                                    league_id = int(row['league'])
                                # If league is not recognized, use a fallback ID (Premier League)
                                else:
                                    print(f"Invalid league: {row['league']} for {fixture_key}")
                                    print(f"Using fallback league ID for {fixture_key}")
                                    league_id = 39  # Use Premier League as fallback
                            except:
                                st.warning(f"League '{row['league']}' not recognized for {fixture_key}. Using fallback predictions.")
                                league_id = 39  # Use Premier League as fallback
                        
                        if not league_id:
                            st.error(f"Invalid league: {row['league']} for {fixture_key}")
                            print(f"Using fallback league ID for {fixture_key}")
                            league_id = 39  # Use Premier League as fallback
                        
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
                analysis_df['Highest Probability %'] = analysis_df[['Home Win %', 'Draw %', 'Away Win %']].apply(
                    lambda x: max(
                        float(x['Home Win %'].strip('%')), 
                        float(x['Draw %'].strip('%')), 
                        float(x['Away Win %'].strip('%'))
                    ), 
                    axis=1
                )
                
                # Format Highest Probability % as string with % symbol
                analysis_df['Highest Probability %'] = analysis_df['Highest Probability %'].apply(lambda x: f"{x:.0f}%")

                # Correct the logic for determining the predicted result
                analysis_df['Predicted Result'] = analysis_df.apply(
                    lambda row: 'Home Win' if float(row['Home Win %'].strip('%')) == float(row['Highest Probability %'].strip('%')) 
                    else ('Draw' if float(row['Draw %'].strip('%')) == float(row['Highest Probability %'].strip('%')) 
                    else 'Away Win'), 
                    axis=1
                )
            
            # Add a column for detailed analysis
            analysis_df['View Details'] = analysis_df.apply(
                lambda row: st.session_state.analysis_selections.get(
                    f"{row['Home Team']} vs {row['Away Team']} ({row['Date']})",
                    "Select Analysis"
                ),
                axis=1
            )
            
            # Sort the DataFrame by Highest Probability % in descending order
            analysis_df = analysis_df.sort_values('Highest Probability %', ascending=False)
            
            # Rename Highest Probability % to Prediction
            analysis_df = analysis_df.rename(columns={'Highest Probability %': 'Prediction'})
            
            # Display analysis results with all available data
            display_columns = [
                'Date', 'Home Team', 'Away Team',
                'Home Win %', 'Draw %', 'Away Win %',
                'Prediction', 'Predicted Result',
                'Prediction Details',  # This contains winner, advice, win_or_draw, under_over, and goals
                'View Details'  # Keep this as is for now
            ]

            # For mobile view or compact tables, show fewer columns
            if st.session_state.get('mobile_view', False) or st.session_state.get('compact_tables', False):
                display_columns = [
                    'Home Team', 'Away Team',
                    'Prediction', 'Predicted Result',
                    'View Details'
                ]

            # Ensure all columns exist and remove any duplicates
            analysis_df = analysis_df.loc[:, ~analysis_df.columns.duplicated()]

            # Create a unique key for the data editor
            editor_key = f"analysis_editor_{len(st.session_state.selected_fixtures)}"
            
            # Add export button before the table
            if st.button("📥 Export Analysis"):
                # Create Excel writer
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    analysis_df.to_excel(writer, sheet_name='Match Analysis', index=False)
                    
                    # Get the workbook and the worksheet
                    workbook = writer.book
                    worksheet = writer.sheets['Match Analysis']
                    
                    # Add formats
                    header_format = workbook.add_format({
                        'bold': True,
                        'text_wrap': True,
                        'valign': 'top',
                        'align': 'center',
                        'bg_color': '#38003c',
                        'font_color': 'white',
                        'border': 1
                    })
                    
                    # Format the header row
                    for col_num, value in enumerate(analysis_df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    
                    # Auto-adjust column widths
                    for idx, col in enumerate(analysis_df):
                        max_length = max(
                            analysis_df[col].astype(str).apply(len).max(),
                            len(str(col))
                        )
                        worksheet.set_column(idx, idx, max_length + 2)
                
                # Get the value of the BytesIO buffer and write it to the response
                excel_data = output.getvalue()
                
                # Create a download button
                st.download_button(
                    label="Download Excel File",
                    data=excel_data,
                    file_name="match_analysis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            # Display the analysis table with a dropdown for each row
            edited_df = st.data_editor(
                analysis_df[display_columns],
                hide_index=True,
                use_container_width=False,
                key=editor_key,
                column_config={
                    "Date": st.column_config.TextColumn("Date", width=100),
                    "Home Team": st.column_config.TextColumn("Home", width=150),
                    "Away Team": st.column_config.TextColumn("Away", width=150),
                    "Home Win %": st.column_config.TextColumn("H%", width=60),
                    "Draw %": st.column_config.TextColumn("D%", width=60),
                    "Away Win %": st.column_config.TextColumn("A%", width=60),
                    "Prediction": st.column_config.TextColumn("Pred", width=70),
                    "Predicted Result": st.column_config.TextColumn("Result", width=80),
                    "View Details": st.column_config.SelectboxColumn(
                        "Additional Analysis",
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
                        width=120
                    ),
                    "Prediction Details": st.column_config.TextColumn(
                        "Details", 
                        width=120
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