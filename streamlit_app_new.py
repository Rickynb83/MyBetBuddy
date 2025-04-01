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
import streamlit.components.v1 as components

# Add the current directory to the Python path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from lib.fetch_fixtures import (
    fetch_fixtures, fetch_standings, LEAGUES,
    fetch_head_to_head, fetch_team_statistics, fetch_players,
    fetch_lineups, fetch_venue_info, fetch_injuries,
    fetch_team_form, fetch_weather_for_fixture, fetch_referee_info,
    api_football_request
)
import random
from lib.predictions import predict_match, create_fallback_prediction

# Add prediction caching to minimize API calls
def get_cached_prediction(home_team_id, away_team_id, league_id):
    """Get prediction for a match, using cached results if available"""
    # Create a unique key for this prediction
    cache_key = f"prediction_{home_team_id}_{away_team_id}_{league_id}"
    
    # Check if we already have this prediction cached in session state
    if 'prediction_cache' not in st.session_state:
        st.session_state.prediction_cache = {}
        
    if cache_key in st.session_state.prediction_cache:
        return st.session_state.prediction_cache[cache_key]
    
    # If not cached, calculate the prediction
    try:
        prediction = predict_match(home_team_id, away_team_id, league_id)
        st.session_state.prediction_cache[cache_key] = prediction
        return prediction
    except Exception as e:
        print(f"Error calculating prediction: {e}")
        # Return fallback prediction if real prediction fails
        fallback = create_fallback_prediction()
        st.session_state.prediction_cache[cache_key] = fallback
        return fallback

# Add a helper function for predicted result
def get_predicted_result(home_team_id, away_team_id, league_id):
    """Get the predicted result for a match"""
    prediction = get_cached_prediction(home_team_id, away_team_id, league_id)
    
    home_win_pct = prediction['probabilities']['home_win'] * 100
    draw_pct = prediction['probabilities']['draw'] * 100
    away_win_pct = prediction['probabilities']['away_win'] * 100
    
    # Determine most likely result
    max_pct = max(home_win_pct, draw_pct, away_win_pct)
    if max_pct == home_win_pct:
        return "Home Win"
    elif max_pct == draw_pct:
        return "Draw"
    else:
        return "Away Win"

# Fix the display_selected_fixtures function to use components.html
def display_selected_fixtures():
    """Display the selected fixtures in a formatted table"""
    if "selected_fixtures" not in st.session_state:
        st.session_state.selected_fixtures = []
    
    selected_fixtures = st.session_state.selected_fixtures
    
    if not selected_fixtures:
        st.write("No fixtures selected. Please select fixtures from the table above.")
        return

    # Add CSS for the selected fixtures table (inline in the HTML)
    css_styles = """
    <style>
    /* Basic styling for the selected fixtures table */
    .selected-fixtures-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 1rem;
        border: 1px solid #333;
        background-color: #000;
        color: #fff;
    }
    
    .selected-fixtures-table th {
        background-color: #000;
        color: #ccc;
        padding: 8px;
        text-align: center;
        border: 1px solid #333;
    }
    
    .selected-fixtures-table td {
        padding: 8px;
        vertical-align: middle;
        border: 1px solid #333;
        color: #fff;
    }
    
    .selected-fixtures-table tr:hover {
        background-color: #111;
    }
    </style>
    """

    # Display the selected fixtures header
    st.subheader("Selected Fixtures")
    
    # Build the HTML table for selected fixtures
    table_html = css_styles + """
    <table class="selected-fixtures-table">
    <thead>
        <tr>
            <th>Home Team</th>
            <th>vs</th>
            <th>Away Team</th>
            <th>Date</th>
            <th>Probability</th>
            <th>Prediction</th>
        </tr>
    </thead>
    <tbody>
    """
    
    # Build the rows HTML
    rows_html = ""
    for fixture in selected_fixtures:
        # Extract fixture details
        home_team = fixture['Home Team']
        away_team = fixture['Away Team']
        date = fixture['Date']
        home_team_id = fixture.get('home_team_id', '0')
        away_team_id = fixture.get('away_team_id', '0')
        league_id = fixture.get('league', 39)
        home_position = fixture.get('Home Position', 'N/A')
        away_position = fixture.get('Away Position', 'N/A')
        
        # Calculate predictions
        prediction = get_cached_prediction(
            home_team_id,
            away_team_id,
            league_id
        )
        
        home_win_pct = int(prediction['probabilities']['home_win'] * 100)
        draw_pct = int(prediction['probabilities']['draw'] * 100)
        away_win_pct = int(prediction['probabilities']['away_win'] * 100)
        
        # Determine most likely result
        max_pct = max(home_win_pct, draw_pct, away_win_pct)
        if max_pct == home_win_pct:
            result = "Home Win"
        elif max_pct == draw_pct:
            result = "Draw"
        else:
            result = "Away Win"
        
        # Add row to the table HTML using string formatting
        rows_html += """
        <tr>
            <td>
                <div style="display: flex; align-items: center;">
                    <img src="https://media.api-sports.io/football/teams/{0}.png" 
                        alt="{1}" style="width: 24px; height: 24px; margin-right: 8px;">
                    <div>
                      <span style="font-weight: 500; color: #fff;">{1}</span>
                      <br>
                      <small style="color: #888;">({2})</small>
                    </div>
                </div>
            </td>
            <td style="text-align: center; color: #888;">vs</td>
            <td>
                <div style="display: flex; align-items: center;">
                    <img src="https://media.api-sports.io/football/teams/{3}.png" 
                        alt="{4}" style="width: 24px; height: 24px; margin-right: 8px;">
                    <div>
                      <span style="font-weight: 500; color: #fff;">{4}</span>
                      <br>
                      <small style="color: #888;">({5})</small>
                    </div>
                </div>
            </td>
            <td style="text-align: center; color: #888;">{6}</td>
            <td>
                <div style="color: #888;">
                  H: <span style="font-weight: 500; color: #fff;">{7}%</span><br>
                  D: <span style="font-weight: 500; color: #fff;">{8}%</span><br>
                  A: <span style="font-weight: 500; color: #fff;">{9}%</span>
                </div>
            </td>
            <td style="text-align: center; font-weight: 500; color: #fff;">{10}</td>
        </tr>
        """.format(
            home_team_id, home_team, home_position,
            away_team_id, away_team, away_position,
            date, home_win_pct, draw_pct, away_win_pct, result
        )
    
    # Close the table HTML
    table_html += rows_html + """
    </tbody>
    </table>
    """
    
    # Display the table using components.html instead of markdown
    components.html(table_html, height=len(selected_fixtures) * 100 + 100, scrolling=True)  # Dynamic height based on number of fixtures

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
    try:
        # Get Zoho email password from environment variables
        zoho_password = os.getenv('ZOHO_EMAIL_PASSWORD')
        if not zoho_password:
            print("Error: ZOHO_EMAIL_PASSWORD environment variable not found")
            return False

        # Create message
        msg = MIMEMultipart()
        msg['From'] = 'welcome@mybetbuddy.app'
        msg['To'] = email
        msg['Subject'] = 'Password Reset Request'

        # Create the reset link
        reset_link = f"https://mybetbuddy-df3f219c1b11.herokuapp.com/?reset_token={reset_token}"
        
        # Create the email body
        body = f"""
        Hello,

        You have requested to reset your password for MyBetBuddy. Click the link below to reset your password:

        {reset_link}

        If you did not request this password reset, please ignore this email.

        Best regards,
        MyBetBuddy Team
        """
        
        msg.attach(MIMEText(body, 'plain'))

        # Connect to Zoho Mail SMTP server using SSL
        print("Attempting to connect to Zoho SMTP server...")
        server = smtplib.SMTP_SSL('smtppro.zoho.eu', 465)
        
        print("Attempting to login with credentials...")
        try:
            server.login('welcome@mybetbuddy.app', zoho_password)
            print("Login successful!")
        except smtplib.SMTPAuthenticationError as e:
            print(f"SMTP Authentication Error: {e}")
            print(f"Error code: {e.smtp_code}")
            print(f"Error message: {e.smtp_error}")
            print("Please verify:")
            print("1. The email address is correct")
            print("2. The App Password was generated for this specific email")
            print("3. The App Password was copied correctly")
            return False
        except smtplib.SMTPException as e:
            print(f"SMTP Error: {e}")
            print(f"Error code: {e.smtp_code}")
            print(f"Error message: {e.smtp_error}")
            return False

        # Send email
        print("Sending email...")
        server.send_message(msg)
        print("Email sent successfully!")
        server.quit()
        return True

    except Exception as e:
        print(f"Unexpected error in send_reset_email: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def request_password_reset(email):
    """Handle password reset request."""
    try:
        # Debug: Print the email being searched for
        print(f"Searching for email: {email}")
        
        # Check if email exists
        response = supabase.table('users').select('id, username').eq('email', email).execute()
        
        # Debug: Print the response
        print(f"Database response: {response}")
        
        if not response.data:
            st.error("Email not found. Please check your email address.")
            return False
            
        # Get user details before deletion
        user_id = response.data[0]['id']
        username = response.data[0]['username']
            
        # Generate reset token
        reset_token = generate_reset_token()
        expires_at = datetime.now() + timedelta(hours=24)
        
        # Debug: Print the update data
        print(f"Updating user with token: {reset_token}")
        
        # Delete the user's account
        delete_response = supabase.table('users').delete().eq('id', user_id).execute()
        
        # Debug: Print the delete response
        print(f"Delete response: {delete_response}")
        
        # Send reset email
        if send_reset_email(email, reset_token):
            st.success(f"Password reset link has been sent to your email. Your account has been deleted. You can now register again with the same username '{username}' and email address.")
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
            
        # Check if email is whitelisted (case-insensitive)
        whitelist = load_whitelist()
        email_lower = email.lower()  # Convert input email to lowercase
        whitelist_lower = [we.lower() for we in whitelist]  # Convert all whitelist emails to lowercase
        
        if email_lower not in whitelist_lower:
            st.error(f"Email not in whitelist. Please contact the administrator.")
            print(f"Email {email} not in whitelist. Available emails: {whitelist}")  # Debug print
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
            # Auto-login the user after successful registration
            st.session_state.authenticated = True
            st.session_state.username = username
            st.success("Registration successful! You are now logged in.")
            # Force page refresh to show the app
            st.rerun()
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

# Add custom CSS to reduce top padding
st.markdown("""
    <style>
    /* Reduce top padding */
    .main > div:first-child {
        padding-top: 1rem !important;
    }
    
    /* Remove extra padding from header block */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
    }
    
    /* Adjust header margins */
    header {
        margin-bottom: 0rem !important;
    }
    
    /* Hide Streamlit's default header decoration */
    .decoration {
        display: none !important;
    }
    
    /* Reduce padding for the main content area */
    .stApp > header + div {
        padding-top: 1rem !important;
    }
    
    /* Reduce gap between elements */
    .element-container {
        margin-bottom: 0.5rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state for statistics
if 'stats_type' not in st.session_state:
    st.session_state.stats_type = None
if 'current_fixture' not in st.session_state:
    st.session_state.current_fixture = None
if 'component_value' not in st.session_state:
    st.session_state.component_value = None

# Process component value immediately when received (as per docs)
if 'component_value' in st.session_state and st.session_state.component_value is not None:
    try:
        value = st.session_state.component_value
        print(f"Debug: Received component value: {value}")  # Debug print
        
        if isinstance(value, dict):
            print(f"Debug: Processing component value with keys: {list(value.keys())}")
            
            if 'stat_type' in value:
                stat_type = value['stat_type']
                print(f"Debug: Processing stat type: {stat_type}")  # Debug print
                
                # Store all information in session state
                st.session_state.stats_type = stat_type
                st.session_state.current_fixture = {
                    'home_id': value['home_id'],
                    'away_id': value['away_id'],
                    'home_team': value['home_team'],
                    'away_team': value['away_team']
                }
                
                # Open the sidebar to show the content
                st.session_state.sidebar_state = 'expanded'
                
                print(f"Debug: Updated session state - stats_type: {st.session_state.stats_type}, current_fixture: {st.session_state.current_fixture}")  # Debug print
                
                # Clear component value after processing
                st.session_state.component_value = None
                st.rerun()  # Rerun to process the new state and show sidebar
            else:
                print(f"Debug: No stat_type in component value")
        else:
            print(f"Debug: Component value is not a dict: {type(value)}")
    except Exception as e:
        print(f"Error processing component value: {e}")
        import traceback
        traceback.print_exc()
        st.session_state.component_value = None
else:
    print("Debug: No component_value in session state or value is None")  # Debug print

# Fetch standings but don't display errors if there's an issue
try:
    standings = fetch_standings()
except:
    standings = {}  # Use empty dict if fetch fails

# Toggle for development mode (set to True to disable authentication during development)
DEVELOPMENT_MODE = False  # Authentication enabled for production
# DEVELOPMENT_MODE = False  # Authentication enabled for production

# Simple authentication functions
def load_whitelist():
    """Load the whitelist of authorized email addresses from CSV"""
    try:
        # Print current working directory for debugging
        import os
        print(f"Current working directory: {os.getcwd()}")
        print(f"Attempting to load whitelist from: Whitelist.csv")
        
        if not os.path.exists('Whitelist.csv'):
            print(f"❌ Whitelist.csv file not found!")
            # List files in current directory
            print(f"Files in current directory: {os.listdir('.')}")
            return []
            
        whitelist_df = pd.read_csv('Whitelist.csv')
        emails = whitelist_df['email'].tolist()
        print(f"✅ Successfully loaded {len(emails)} emails from whitelist: {emails}")
        return emails
    except Exception as e:
        st.error(f"Error loading whitelist: {e}")
        print(f"❌ Error loading whitelist: {e}")
        import traceback
        print(traceback.format_exc())
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
    # Set up session state if not already
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        
    # TEMPORARY: Bypass authentication for testing
    # Remove this line for production
    # st.session_state.authenticated = True
        
    if 'username' not in st.session_state:
        st.session_state.username = None
    
    # Add selected fixtures tracker to session state
    if 'selected_fixtures' not in st.session_state:
        st.session_state.selected_fixtures = []
    
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
                    register_user(reg_username, reg_email, reg_password)
                    # Note: No need for additional success message here as register_user handles login
        
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
        
        # Remove mobile view toggle section
        # st.sidebar.markdown("### Display Settings")

        # Add responsive layout for mobile detection
        st.markdown("""
        <script>
        function updateMobileView() {
            const isMobile = window.innerWidth < 768;
            
            // Send the mobile detection to Streamlit
            const data = {
                mobile: isMobile
            };
            
            // Use Streamlit's setComponentValue API
            window.parent.postMessage({
                type: "streamlit:setComponentValue",
                value: data
            }, "*");
        }

        // Check on load and on resize
        window.addEventListener('load', updateMobileView);
        window.addEventListener('resize', updateMobileView);
        </script>
        """, unsafe_allow_html=True)

        # Remove mobile view and compact tables toggles
        # mobile_view = st.checkbox("Mobile-friendly view", value=st.session_state.get('mobile_view', False), help="Optimize the layout for mobile devices")
        # if mobile_view != st.session_state.get('mobile_view', False):
        #    st.session_state.mobile_view = mobile_view
        #    st.rerun()

        # Remove compact tables toggle
        # compact_tables = st.checkbox("Compact tables (better for small screens)", value=st.session_state.get('compact_tables', False))
        # if compact_tables != st.session_state.get('compact_tables', False):
        #    st.session_state.compact_tables = compact_tables
        #    st.rerun()
        
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
            
            # Add option to clear cache
            st.sidebar.markdown("#### Cache Management")
            if st.sidebar.button("Clear App Cache"):
                # This will clear all cached data
                st.cache_data.clear()
                st.sidebar.success("Cache cleared successfully!")
                st.rerun()  # Rerun to reload with fresh data
        
        if st.sidebar.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()
            
        # Add delete account button
        if st.sidebar.button("Delete Account", type="secondary", help="Permanently delete your account"):
            if st.session_state.username:
                # Show confirmation
                delete_confirm = st.sidebar.warning("Are you sure you want to delete your account? This action cannot be undone.")
                col1, col2 = st.sidebar.columns(2)
                with col1:
                    if st.button("Yes, delete my account"):
                        try:
                            current_username = st.session_state.username
                            # Delete user from Supabase
                            user_response = supabase.table("users").select("id").eq("username", current_username).execute()
                            if len(user_response.data) > 0:
                                user_id = user_response.data[0]['id']
                                supabase.table("users").delete().eq("id", user_id).execute()
                                
                                # Also remove from users.yaml if needed
                                users = load_users()
                                if current_username in users.get('usernames', {}):
                                    del users['usernames'][current_username]
                                    save_users(users)
                                
                                st.session_state.authenticated = False
                                st.session_state.username = None
                                st.success("Your account has been deleted successfully")
                                st.rerun()
                            else:
                                st.sidebar.error("Account not found")
                        except Exception as e:
                            st.sidebar.error(f"Error deleting account: {e}")
                with col2:
                    if st.button("No, keep my account"):
                        st.rerun()

# Add custom CSS for fixed header
st.markdown("""
    <style>
    /* Global styles - increase all text by 1 font size */
    .stApp {
        background-color: #000 !important;
        color: #fff !important;
        font-size: 16px !important; /* Base font size +1 */
    }
    
    /* Header responsive styling */
    @media (max-width: 768px) {
        .header {
            flex-direction: column !important;
            align-items: center !important;
            text-align: center !important;
        }
        
        .header h1 {
            margin-bottom: 10px !important;
            font-size: 24px !important;
        }
        
        [data-testid="column"]:last-child {
            margin-top: 10px !important;
        }
    }
    
    /* Main content area */
    .main .block-container {
        background-color: #000 !important;
        color: #fff !important;
        padding: 1rem !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6, .st-emotion-cache-10trblm {
        color: #fff !important;
        font-size: 130% !important; /* Make headers 30% larger */
    }
    
    /* League tabs styling - same color as team names, +2 font sizes */
    .st-emotion-cache-1oe5cao, .st-emotion-cache-13ejsyy, [data-testid="stHorizontalBlock"] .st-emotion-cache-ocqkz7 {
        color: #fff !important; /* Pure white */
        font-size: 18px !important; /* +1 font size (reduced from 19px) */
        font-weight: 700 !important; /* Extra bold */
    }
    
    /* Target all tabs - use multiple selectors for better coverage */
    [data-testid="stHorizontalBlock"] button, 
    [data-testid="stHorizontalBlock"] button p, 
    [data-baseweb="tab"] div, 
    div[role="tab"] p,
    div[role="tablist"] p {
        color: #fff !important; /* Pure white */
        font-size: 18px !important; /* +1 font size (reduced from 19px) */
        font-weight: 700 !important; /* Extra bold */
    }
    
    .st-emotion-cache-1oe5cao:hover, .st-emotion-cache-13ejsyy:hover {
        color: #fff !important;
        text-decoration: underline !important;
    }
    
    /* Active tab styling */
    .st-emotion-cache-pkbazv {
        color: #fff !important; /* Same color as team names */
        font-size: 18px !important; /* +1 font size (reduced from 19px) */
        font-weight: 700 !important; /* Extra bold */
    }
    
    /* Subheader styling for league name + Fixtures */
    .main .block-container h2 {
        font-size: 120% !important; /* Reduced from 130% */
    }
    
    /* DataEditor and tables */
    .st-emotion-cache-13b9s7d, .st-emotion-cache-1n76uvr {
        color: #fff !important;
        background-color: #111 !important;
        font-size: 16px !important; /* +1 font size */
    }
    
    .st-emotion-cache-13b9s7d th {
        background-color: #000 !important;
        color: #fff !important;
        font-weight: 700 !important;
    }
    
    .st-emotion-cache-13b9s7d td {
        color: #fff !important;
        border-color: #333 !important;
    }
    
    /* Buttons */
    .stButton button {
        background-color: #111 !important;
        color: #fff !important;
        border: 1px solid #333 !important;
        font-size: 16px !important; /* +1 font size */
    }
    
    .stButton button:hover {
        background-color: #222 !important;
        border-color: #444 !important;
    }
    
    /* Create a scrollable container for fixtures */
    .fixtures-container {
        max-height: calc(100vh - 400px) !important;
        overflow-y: auto !important;
        position: relative !important;
        border: 1px solid #333 !important;
        border-radius: 4px !important;
        margin-bottom: 20px !important;
        background-color: #000 !important;
        scrollbar-width: thin !important;
        scrollbar-color: #444 #222 !important;
    }

    /* Table styling */
    .fixtures-table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 0 !important;
        background-color: #000 !important;
        color: #fff !important;
        font-size: 16px !important; /* +1 font size */
    }

    /* Fixed header styling */
    .fixtures-table thead {
        position: sticky !important;
        top: 0 !important;
        z-index: 100 !important;
        background-color: #000 !important;
    }

    .fixtures-table th {
        position: sticky !important;
        top: 0 !important;
        z-index: 100 !important;
        background-color: #000 !important;
        color: #fff !important; /* Same color as team names */
        padding: 8px !important;
        text-align: left !important;
        border-bottom: 1px solid #333 !important;
        font-weight: 700 !important;
        font-size: 16px !important; /* +1 font size */
    }

    .fixtures-table td {
        padding: 12px !important;
        border-bottom: 1px solid #333 !important;
        color: #fff !important;
        font-size: 16px !important; /* +1 font size */
        word-wrap: break-word;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* Make scrollbars visible */
    .fixtures-container::-webkit-scrollbar, 
    div::-webkit-scrollbar {
        width: 8px !important;
        height: 8px !important;
    }
    .fixtures-container::-webkit-scrollbar-track, 
    div::-webkit-scrollbar-track {
        background: #222 !important;
    }
    .fixtures-container::-webkit-scrollbar-thumb, 
    div::-webkit-scrollbar-thumb {
        background: #444 !important;
        border-radius: 4px !important;
    }
    .fixtures-container::-webkit-scrollbar-thumb:hover, 
    div::-webkit-scrollbar-thumb:hover {
        background: #555 !important;
    }
    
    /* Simple horizontal scrolling for tabs */
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto !important;
        white-space: nowrap !important;
        padding: 0 10px !important;
        margin: 0 -10px !important;
        scrollbar-width: thin !important;
        scrollbar-color: #444 #222 !important;
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar {
        height: 8px !important;
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-track {
        background: #222 !important;
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
        background: #444 !important;
        border-radius: 4px !important;
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb:hover {
        background: #555 !important;
    }

    /* Data select dropdown styling */
    .data-select {
        background-color: #222;
        color: white;
        padding: 6px 12px;
        font-size: 14px;
        border: 1px solid #444;
        border-radius: 4px;
        cursor: pointer;
        width: 100%;
        font-weight: bold;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    
    .data-select:hover {
        background-color: #333;
    }
    
    .data-select:focus {
        outline: none;
        border-color: #444;
        box-shadow: 0 0 0 2px rgba(68, 68, 68, 0.5);
    }
    
    .data-select option {
        background-color: #333;
        color: white;
        padding: 10px;
    }

    /* Mobile responsive styles */
    @media (max-width: 768px) {
        .fixtures-container {
            max-height: 400px !important;
        }
        
        .fixtures-table th, .fixtures-table td {
            padding: 6px !important;
            font-size: 14px !important; /* Slightly smaller on mobile */
        }
        
        .fixtures-table img {
            width: 20px !important;
            height: 20px !important;
            margin-right: 4px !important;
        }
        
        /* Stack columns on mobile */
        .stHorizontalBlock {
            flex-wrap: wrap !important;
        }
        
        .stHorizontalBlock > div {
            flex: 1 1 100% !important;
            margin-bottom: 10px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# Add custom CSS for fixed header
st.markdown("""
    <style>
    /* Horizontal scroll for tabs */
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto !important;
        white-space: nowrap !important;
        padding: 0 10px !important;
        margin: 0 -10px !important;
        scrollbar-width: thin !important;
        scrollbar-color: #444 #222 !important;
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar {
        height: 8px !important;
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-track {
        background: #222 !important;
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
        background: #444 !important;
        border-radius: 4px !important;
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb:hover {
        background: #555 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Main content starts here
# Use columns to place title and instructions button in the same row
col1, col2 = st.columns([6, 1])
with col1:
    st.markdown("""
        <div class="header">
            <h1>⚽ MyBetBuddy - Football Match Predictions</h1>
        </div>
        """, unsafe_allow_html=True)
with col2:
    if st.button("📖", key="instructions_button", help="View Instructions"):
        st.session_state.show_instructions = not st.session_state.show_instructions

# Initialize session state variables
if 'show_instructions' not in st.session_state:
    st.session_state.show_instructions = False

# Display instructions if the button has been clicked
if st.session_state.show_instructions:
    st.info("""
    ### Instructions
    1. Toggle between leagues to view upcoming fixtures
    """)

# Close the main-header div (removing this could cause HTML issues)
st.markdown("</div>", unsafe_allow_html=True)

# Process form data request if present in URL parameters
form_data_request = st.query_params.get("form_data")
if form_data_request and form_data_request[0] == 'true':
    home_id = st.query_params.get("home_id", [""])[0]
    away_id = st.query_params.get("away_id", [""])[0]
    home_team = st.query_params.get("home", ["Home Team"])[0]
    away_team = st.query_params.get("away", ["Away Team"])[0]
    
    print(f"Processing form data request for {home_team} vs {away_team}")
    
    # Create a pop-up dialog using a Streamlit sidebar
    with st.sidebar:
        st.markdown("### Team Form Analysis")
        st.markdown(f"#### {home_team} vs {away_team}")
        
        # Clear other parameters to prevent state conflicts
        for param in ['h2h_data', 'more_stats']:
            if param in st.query_params:
                del st.query_params[param]
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{home_team} Form**")
            home_form = fetch_team_form(home_id)
            if home_form:
                st.dataframe(pd.DataFrame(home_form), hide_index=True)
            else:
                st.info("No form data available.")
        
        with col2:
            st.markdown(f"**{away_team} Form**")
            away_form = fetch_team_form(away_id)
            if away_form:
                st.dataframe(pd.DataFrame(away_form), hide_index=True)
            else:
                st.info("No form data available.")
        
        # Add a close button
        if st.button("Close"):
            # Clear parameters and reload without rerunning
            st.query_params.clear()
            st.experimental_set_query_params()

# Process h2h data request if present in URL parameters
h2h_data_request = st.query_params.get("h2h_data")
if h2h_data_request and h2h_data_request[0] == 'true':
    home_id = st.query_params.get("home_id", [""])[0]
    away_id = st.query_params.get("away_id", [""])[0]
    home_team = st.query_params.get("home", ["Home Team"])[0]
    away_team = st.query_params.get("away", ["Away Team"])[0]
    
    print(f"Processing H2H data request for {home_team} vs {away_team}")
    
    # Create a pop-up dialog using a Streamlit sidebar
    with st.sidebar:
        st.markdown("### Head-to-Head Analysis")
        st.markdown(f"#### {home_team} vs {away_team}")
        
        # Clear other parameters to prevent state conflicts
        for param in ['form_data', 'more_stats']:
            if param in st.query_params:
                del st.query_params[param]
        
        h2h_data = fetch_head_to_head(home_id, away_id)
        if h2h_data:
            h2h_df = pd.DataFrame(h2h_data)
            st.dataframe(h2h_df, hide_index=True)
        else:
            st.info("No head-to-head data available.")
        
        # Add a close button
        if st.button("Close"):
            # Clear parameters and reload without rerunning
            st.query_params.clear()
            st.experimental_set_query_params()

# Process more stats request if present in URL parameters
more_stats_request = st.query_params.get("more_stats")
if more_stats_request and more_stats_request[0] == 'true':
    home_id = st.query_params.get("home_id", [""])[0]
    away_id = st.query_params.get("away_id", [""])[0]
    home_team = st.query_params.get("home", ["Home Team"])[0]
    away_team = st.query_params.get("away", ["Away Team"])[0]
    
    print(f"Processing more stats request for {home_team} vs {away_team}")
    
    # Create a pop-up dialog using a Streamlit sidebar
    with st.sidebar:
        st.markdown("### Additional Statistics")
        st.markdown(f"#### {home_team} vs {away_team}")
        
        # Clear other parameters to prevent state conflicts
        for param in ['form_data', 'h2h_data']:
            if param in st.query_params:
                del st.query_params[param]
        
        # Create a selectbox for different statistics options
        stat_option = st.selectbox(
            "Select Statistics",
            [
                "Team Statistics",
                "Player Information",
                "Lineups",
                "Venue Information",
                "Injuries",
                "Weather",
                "Referee Information"
            ]
        )
        
        # Display the selected statistics
        if stat_option == "Team Statistics":
            st.markdown("##### Team Statistics")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{home_team}**")
                home_stats = fetch_team_statistics(home_id, league_id)
                if home_stats:
                    st.dataframe(pd.DataFrame([home_stats]), hide_index=True)
                else:
                    st.info("No statistics available.")
            
            with col2:
                st.markdown(f"**{away_team}**")
                away_stats = fetch_team_statistics(away_id, league_id)
                if away_stats:
                    st.dataframe(pd.DataFrame([away_stats]), hide_index=True)
                else:
                    st.info("No statistics available.")
        
        # Add other stat options here...
        
        # Add a close button
        if st.button("Close"):
            # Clear parameters and reload without rerunning
            st.query_params.clear()
            st.experimental_set_query_params()

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
    'Bundesliga': 78,
    'Serie A': 135,
    'Ligue 1': 61,
    'Eredivisie': 88,
    'Primeira Liga': 94,
    'Super Lig': 203,
    'Championship': 40,
    'League One': 41,
    'League Two': 42,
    'Super Liga': 271,  # Updated to correct ID for Danish Super Liga
    'Scottish Premiership': 179,  # Renamed from Premiership
    'Super League': 183,  # Swiss Super League
    'Süper Lig': 203  # Turkish Süper Lig
}

# Add this function to handle fixture selection
def handle_fixture_selection(fixture_key, selected):
    """Add or remove fixture from selected fixtures"""
    if not fixture_key:
        return
        
    # Get information about this fixture
    parts = fixture_key.split('|')
    if len(parts) < 3:
        return
        
    home_team, away_team, date = parts[0], parts[1], parts[2]
    
    if selected:
        # Add to selected fixtures if not already there
        if not any(f['Home Team'] == home_team and f['Away Team'] == away_team and f['Date'] == date for f in st.session_state.selected_fixtures):
            # Find the full fixture details from the current fixtures
            for league in st.session_state.fixtures:
                if league in st.session_state.fixtures:
                    for fixture in st.session_state.fixtures[league]:
                        if fixture['homeTeam'] == home_team and fixture['awayTeam'] == away_team:
                            # Create fixture dict with all necessary data
                            fixture_dict = {
                                'Date': date,
                                'Home Team': home_team,
                                'Away Team': away_team,
                                'fixture_id': fixture.get('fixture_id'),
                                'home_team_id': fixture.get('home_team_id'),
                                'away_team_id': fixture.get('away_team_id'),
                                'venue': fixture.get('venue'),
                                'league': league,
                                'Home Position': fixture.get('Home Position', 'N/A'),
                                'Away Position': fixture.get('Away Position', 'N/A')
                            }
                            st.session_state.selected_fixtures.append(fixture_dict)
                            print(f"Added fixture: {fixture_key}")
                            break
    else:
        # Remove from selected fixtures
        st.session_state.selected_fixtures = [
            f for f in st.session_state.selected_fixtures 
            if not (f['Home Team'] == home_team and f['Away Team'] == away_team and f['Date'] == date)
        ]
        print(f"Removed fixture: {fixture_key}")

# Display standings if available
if standings:
    # Create tabs for each league
    league_tabs = st.tabs(LEAGUES.keys())
    
    # Loop through leagues and tabs
    for league, tab in zip(LEAGUES.keys(), league_tabs):
        with tab:
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

            # Store fixtures in session state for reference when selecting
            if 'fixtures' not in st.session_state:
                st.session_state.fixtures = {}
            st.session_state.fixtures[league] = fixtures

            fixtures_df = pd.DataFrame(fixtures)
            
            if not fixtures_df.empty:
                # Convert standings to DataFrame for mapping
                current_standings_df = pd.DataFrame(standings[league])

                # Convert 'rank' column to integer to avoid decimal points
                if 'rank' in current_standings_df.columns:
                    current_standings_df['rank'] = current_standings_df['rank'].astype(int)

                # Add position columns for home and away teams
                fixtures_df['Home Position'] = fixtures_df['homeTeam'].map(current_standings_df.set_index('team')['rank'])
                fixtures_df['Away Position'] = fixtures_df['awayTeam'].map(current_standings_df.set_index('team')['rank'])
                
                # Ensure positions are integers
                fixtures_df['Home Position'] = fixtures_df['Home Position'].apply(
                    lambda x: int(x) if pd.notnull(x) and not isinstance(x, str) else x
                )
                fixtures_df['Away Position'] = fixtures_df['Away Position'].apply(
                    lambda x: int(x) if pd.notnull(x) and not isinstance(x, str) else x
                )

                # Format the date with error handling
                try:
                    # First try to parse the date column
                    fixtures_df['date'] = pd.to_datetime(fixtures_df['date'])
                    # Then format it - use try/except for each row to handle mixed timezones
                    def format_date(date_val):
                        try:
                            return date_val.strftime('%d/%m %I:%M %p')
                        except:
                            return str(date_val)
                    
                    fixtures_df['Date'] = fixtures_df['date'].apply(format_date)
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
                    # Generate fixtures table HTML header
                    table_html = """
                    <div class="fixtures-container">
                    <style>
                        .fixtures-container {
                            max-height: 600px;
                            overflow-y: auto;
                            position: relative;
                            border: 1px solid #333;
                            border-radius: 4px;
                            margin-bottom: 20px;
                            background-color: #000;
                            scrollbar-width: thin;
                            scrollbar-color: #444 #222;
                        }
                        
                        .fixtures-container::-webkit-scrollbar {
                            width: 8px;
                            height: 8px;
                        }
                        
                        .fixtures-container::-webkit-scrollbar-track {
                            background: #222;
                        }
                        
                        .fixtures-container::-webkit-scrollbar-thumb {
                            background: #444;
                            border-radius: 4px;
                        }
                        
                        .fixtures-container::-webkit-scrollbar-thumb:hover {
                            background: #555;
                        }
                        
                        .fixtures-table {
                            width: 100%;
                            border-collapse: collapse;
                            background-color: #000;
                            color: #fff;
                            table-layout: fixed;
                        }
                        .fixtures-table thead {
                            position: sticky;
                            top: 0;
                            z-index: 10;
                            background-color: #000;
                        }
                        .fixtures-table th {
                            background-color: #000;
                            color: #ccc;
                            padding: 8px 12px;
                            text-align: left;
                            border-bottom: 1px solid #333;
                            position: sticky;
                            top: 0;
                            z-index: 10;
                            font-weight: 500;
                            font-size: 13px;
                            white-space: nowrap;
                            overflow: hidden;
                            text-overflow: ellipsis;
                        }
                        .fixtures-table td {
                            padding: 12px !important;
                            border-bottom: 1px solid #333 !important;
                            color: #fff !important;
                            font-size: 16px !important; /* +1 font size */
                            word-wrap: break-word;
                            overflow: hidden;
                            text-overflow: ellipsis;
                        }
                        
                        /* Data select dropdown styling */
                        .data-select {
                            background-color: #222;
                            color: white;
                            padding: 6px 12px;
                            font-size: 14px;
                            border: 1px solid #444;
                            border-radius: 4px;
                            cursor: pointer;
                            width: 100%;
                            font-weight: bold;
                            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                        }
                        
                        .data-select:hover {
                            background-color: #333;
                        }
                        
                        .data-select:focus {
                            outline: none;
                            border-color: #444;
                            box-shadow: 0 0 0 2px rgba(68, 68, 68, 0.5);
                        }
                        
                        .data-select option {
                            background-color: #333;
                            color: white;
                            padding: 10px;
                        }
                        
                        /* Dropdown styles for Data button */
                        .dropbtn {
                            background-color: #1e88e5;
                            color: white;
                            padding: 6px 12px;
                            font-size: 14px;
                            border: none;
                            border-radius: 4px;
                            cursor: pointer;
                            width: 100%;
                            transition: background-color 0.3s;
                            font-weight: bold;
                            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                        }
                        
                        .dropbtn:hover {
                            background-color: #0d47a1;
                        }
                        
                        .data-menu {
                            position: relative;
                            display: inline-block;
                            width: 100%;
                        }
                        
                        .data-menu-content {
                            display: none;
                            position: absolute;
                            right: 0;
                            top: 100%;
                            background-color: #333;
                            min-width: 160px;
                            box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.5);
                            z-index: 9999;
                            border-radius: 4px;
                            border: 1px solid #444;
                            max-height: 300px;
                            overflow-y: auto;
                        }
                        
                        .data-menu-content.active {
                            display: block;
                        }
                        
                        .data-menu-content a {
                            color: white;
                            padding: 10px 16px;
                            text-decoration: none;
                            display: block;
                            text-align: left;
                            font-size: 14px;
                            transition: background-color 0.2s;
                            border-bottom: 1px solid #444;
                        }
                        
                        .data-menu-content a:hover {
                            background-color: #444;
                        }
                        
                        /* Mobile-specific styles */
                        @media (max-width: 768px) {
                            .fixtures-container {
                                max-height: 500px;
                                overflow-x: visible;
                                width: 100%;
                            }
                            
                            .fixtures-table {
                                width: 100%;
                                min-width: unset; /* Remove min-width to prevent horizontal scrolling */
                                table-layout: fixed; /* Force table to respect container width */
                            }
                            
                            .fixtures-table th, .fixtures-table td {
                                padding: 6px 4px !important;
                                font-size: 12px !important;
                                white-space: normal !important; /* Allow text to wrap */
                                overflow: hidden !important;
                                text-overflow: ellipsis !important;
                            }
                            
                            .fixtures-table th:nth-child(1), .fixtures-table td:nth-child(1) { width: 25%; }
                            .fixtures-table th:nth-child(2), .fixtures-table td:nth-child(2) { width: 10%; }
                            .fixtures-table th:nth-child(3), .fixtures-table td:nth-child(3) { width: 25%; }
                            .fixtures-table th:nth-child(4), .fixtures-table td:nth-child(4) { width: 10%; }
                            .fixtures-table th:nth-child(5), .fixtures-table td:nth-child(5) { width: 15%; }
                            .fixtures-table th:nth-child(6), .fixtures-table td:nth-child(6) { width: 15%; }
                            
                            /* Make team names and logos more compact */
                            .fixtures-table td div {
                                display: flex !important;
                                flex-direction: column !important;
                                align-items: flex-start !important;
                            }
                            
                            .fixtures-table img {
                                width: 16px !important;
                                height: 16px !important;
                                margin-right: 4px !important;
                            }
                            
                            /* Adjust select size for mobile */
                            .data-select {
                                padding: 4px 8px;
                                font-size: 12px;
                            }
                        }
                    </style>
                    <table class="fixtures-table">
                    <thead>
                        <tr>
                            <th>Home Team</th>
                            <th style="text-align: center;">vs</th>
                            <th>Away Team</th>
                            <th style="text-align: center;">Date</th>
                            <th>Probability</th>
                            <th style="text-align: center;">Prediction</th>
                        </tr>
                    </thead>
                    <tbody>
                    """
                    
                    # Add debug logging
                    print("Generating fixtures table for league:", league)
                    
                    # Generate the fixture rows HTML
                    fixture_rows_html = ""
                    for _, row in fixtures_df.iterrows():
                        # Debug logging for each fixture
                        print(f"Processing fixture: {row['Home Team']} vs {row['Away Team']}")
                        
                        # Calculate predictions for this fixture
                        if 'home_team_id' in row and 'away_team_id' in row:
                            league_id = LEAGUES[league]
                            prediction = get_cached_prediction(
                                row['home_team_id'],
                                row['away_team_id'],
                                league_id
                            )
                            
                            home_win_pct = int(prediction['probabilities']['home_win'] * 100)
                            draw_pct = int(prediction['probabilities']['draw'] * 100)
                            away_win_pct = int(prediction['probabilities']['away_win'] * 100)
                            
                            # Debug logging for predictions
                            print(f"Predictions for {row['Home Team']} vs {row['Away Team']}: H:{home_win_pct}% D:{draw_pct}% A:{away_win_pct}%")
                            
                            # Determine most likely result
                            max_pct = max(home_win_pct, draw_pct, away_win_pct)
                            if max_pct == home_win_pct:
                                result = "Home Win"
                            elif max_pct == draw_pct:
                                result = "Draw"
                            else:
                                result = "Away Win"
                        else:
                            print(f"Warning: Missing team IDs for {row['Home Team']} vs {row['Away Team']}")
                            home_win_pct = 33
                            draw_pct = 34
                            away_win_pct = 33
                            result = "Draw"
                        
                        # Add the row to the fixture rows HTML (without the statistics column)
                        fixture_rows_html += """
                        <tr>
                            <td>
                                <div style="display: flex; align-items: center;">
                                    <img src="https://media.api-sports.io/football/teams/{0}.png" 
                                         alt="{1}" style="width: 24px; height: 24px; margin-right: 8px;">
                                    <div>
                                      <span style="font-weight: 500; color: #fff;">{1}</span>
                                      <br>
                                      <small style="color: #888;">({2})</small>
                                    </div>
                                </div>
                            </td>
                            <td style="text-align: center; color: #888;">vs</td>
                            <td>
                                <div style="display: flex; align-items: center;">
                                    <img src="https://media.api-sports.io/football/teams/{3}.png" 
                                         alt="{4}" style="width: 24px; height: 24px; margin-right: 8px;">
                                    <div>
                                      <span style="font-weight: 500; color: #fff;">{4}</span>
                                      <br>
                                      <small style="color: #888;">({5})</small>
                                    </div>
                                </div>
                            </td>
                            <td style="text-align: center; color: #888;">{6}</td>
                            <td>
                                <div style="color: #888;">
                                  H: <span style="font-weight: 500; color: #fff;">{7}%</span><br>
                                  D: <span style="font-weight: 500; color: #fff;">{8}%</span><br>
                                  A: <span style="font-weight: 500; color: #fff;">{9}%</span>
                                </div>
                            </td>
                            <td style="text-align: center;">
                                <div style="font-weight: 500; color: #fff; margin-bottom: 8px;">{10}</div>
                                <!-- Stats dropdown temporarily disabled until fixed
                                <select class="data-select" onchange="if(this.value) handleStatClick(this.value, {0}, {3}, '{1}', '{4}')">
                                    <option value="">Data</option>
                                    <option value="cards">Cards</option>
                                    <option value="goals">Goals</option>
                                    <option value="form">Form</option>
                                    <option value="h2h">H2H</option>
                                    <option value="players">Players</option>
                                    <option value="stats">Statistics</option>
                                    <option value="lineups">Lineups</option>
                                    <option value="venue">Venue</option>
                                    <option value="injuries">Injuries</option>
                                </select>
                                -->
                            </td>
                        </tr>
                        """.format(
                            row['home_team_id'], row['Home Team'], row['Home Position'],
                            row['away_team_id'], row['Away Team'], row['Away Position'],
                            row['Date'], home_win_pct, draw_pct, away_win_pct, result
                        )
                    
                    # Add JavaScript functions for handling clicks with debug
                    table_html += """
                    <script>
                        // Function to show dropdown when data button is clicked
                        function toggleDataMenu(event, buttonId) {
                            event.preventDefault();
                            event.stopPropagation();
                            console.log('Debug: toggleDataMenu called for', buttonId);
                            
                            const content = document.getElementById(buttonId + '-content');
                            if (!content) {
                                console.error('Could not find content element:', buttonId + '-content');
                                return;
                            }
                            
                            console.log('Debug: Found content element', content);
                            
                            // Toggle active class and display
                            if (content.classList.contains('active')) {
                                content.classList.remove('active');
                                content.style.display = 'none';
                                console.log('Debug: Hiding dropdown menu');
                            } else {
                                // Close all other dropdowns first
                                document.querySelectorAll('.data-menu-content').forEach(menu => {
                                    menu.classList.remove('active');
                                    menu.style.display = 'none';
                                });
                                
                                // Show this dropdown
                                content.classList.add('active');
                                content.style.display = 'block';
                                console.log('Debug: Showing dropdown menu');
                            }
                        }
                        
                        // Add click event listener to document to close menus when clicking elsewhere
                        document.addEventListener('click', function(event) {
                            const isMenuClick = event.target.closest('.data-menu');
                            if (!isMenuClick) {
                                document.querySelectorAll('.data-menu-content').forEach(menu => {
                                    menu.classList.remove('active');
                                    menu.style.display = 'none';
                                });
                            }
                        });
                        
                        // Make sure the document is loaded before attaching listeners
                        document.addEventListener('DOMContentLoaded', function() {
                            console.log('Debug: DOMContentLoaded event fired, setting up event handlers');
                            
                            // Add click handlers to all data-menu buttons
                            document.querySelectorAll('.dropbtn').forEach(button => {
                                const menuId = button.getAttribute('data-menu-id');
                                if (menuId) {
                                    button.addEventListener('click', function(event) {
                                        toggleDataMenu(event, menuId);
                                    });
                                }
                            });
                        });
                        
                        function handleStatClick(statType, homeId, awayId, homeTeam, awayTeam) {
                            console.log('Debug: handleStatClick called with:', {
                                statType: statType,
                                homeId: homeId,
                                awayId: awayId,
                                homeTeam: homeTeam,
                                awayTeam: awayTeam
                            });
                            
                            try {
                                // Create a notification element
                                const notification = document.createElement('div');
                                notification.style.position = 'fixed';
                                notification.style.top = '20px';
                                notification.style.left = '50%';
                                notification.style.transform = 'translateX(-50%)';
                                notification.style.backgroundColor = '#4CAF50';
                                notification.style.color = 'white';
                                notification.style.padding = '10px 20px';
                                notification.style.borderRadius = '5px';
                                notification.style.zIndex = '9999';
                                notification.style.fontWeight = 'bold';
                                notification.textContent = 'Loading ' + statType + ' data...';
                                document.body.appendChild(notification);
                                
                                // Reset select element to default option
                                setTimeout(() => {
                                    const selects = document.querySelectorAll('.data-select');
                                    selects.forEach(select => {
                                        select.selectedIndex = 0;
                                    });
                                }, 100);
                                
                                // Send data to Streamlit using documented message format
                                const message = {
                                    type: 'streamlit:setComponentValue',
                                    value: {
                                        stat_type: statType,
                                        home_id: homeId,
                                        away_id: awayId,
                                        home_team: homeTeam,
                                        away_team: awayTeam
                                    }
                                };
                                
                                console.log('Debug: Sending message to Streamlit:', message);
                                window.parent.postMessage(message, '*');
                                
                                // Set timeout to remove notification
                                setTimeout(() => {
                                    document.body.removeChild(notification);
                                }, 3000);
                                
                                console.log('Debug: Message sent to Streamlit successfully');
                                return false; 
                            } catch (error) {
                                console.error('Error in handleStatClick:', error);
                                alert('Error processing click: ' + error.message);
                                return false;
                            }
                        }
                    </script>
                    """
                    
                    # Use components.html instead of markdown to render the HTML
                    components.html(table_html + fixture_rows_html + """
                    </tbody></table></div>
                    <script>
                        // Adjust component height based on screen size
                        function adjustComponentHeight() {
                            const isMobile = window.innerWidth < 768;
                            const componentElement = window.frameElement;
                            if (componentElement) {
                                componentElement.style.height = isMobile ? '400px' : '600px';
                                
                                // Make sure the table fits within the width
                                const tableElement = document.querySelector('.fixtures-table');
                                if (tableElement) {
                                    tableElement.style.width = '100%';
                                    
                                    // Set columns to equal width on mobile
                                    if (isMobile) {
                                        const thElements = document.querySelectorAll('.fixtures-table th');
                                        const tdElements = document.querySelectorAll('.fixtures-table td');
                                        
                                        // Configure column widths on mobile
                                        const widths = ['25%', '10%', '25%', '10%', '15%', '15%'];
                                        
                                        // Apply to header cells
                                        thElements.forEach((th, i) => {
                                            if (i < widths.length) {
                                                th.style.width = widths[i];
                                            }
                                        });
                                        
                                        // Apply to data cells
                                        for (let i = 0; i < tdElements.length; i++) {
                                            const colIndex = i % widths.length;
                                            tdElements[i].style.width = widths[colIndex];
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Run on load and on resize
                        window.addEventListener('load', adjustComponentHeight);
                        window.addEventListener('resize', adjustComponentHeight);
                    </script>
                    """, height=600, scrolling=True)

# Display statistics in sidebar based on selection
if st.session_state.stats_type and st.session_state.current_fixture:
    # Automatically expand the sidebar
    st.sidebar.markdown('<script>setTimeout(function() { document.querySelector("[data-testid=\'stSidebar\']").click(); }, 500);</script>', unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### Close")
        if st.button("✕", key="close_sidebar"):
            st.session_state.stats_type = None
            st.session_state.current_fixture = None
            st.rerun()
            
        fixture = st.session_state.current_fixture
        print(f"Debug: Current fixture: {fixture}")
        
        if st.session_state.stats_type == "cards":
            st.markdown("### Cards Analysis")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            st.info("Loading cards data for this fixture...")
            
            # Display cards information for both teams
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{fixture['home_team']} Cards**")
                st.dataframe(pd.DataFrame({
                    "Card Type": ["Yellow", "Red", "Total"],
                    "Season Avg": ["1.8", "0.2", "2.0"]
                }))
            
            with col2:
                st.markdown(f"**{fixture['away_team']} Cards**")
                st.dataframe(pd.DataFrame({
                    "Card Type": ["Yellow", "Red", "Total"],
                    "Season Avg": ["2.1", "0.1", "2.2"]
                }))

        elif st.session_state.stats_type == "goals":
            st.markdown("### Goals Analysis")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            st.info("Loading goals data for this fixture...")
            
            # Display goals information for both teams
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{fixture['home_team']} Goals**")
                st.dataframe(pd.DataFrame({
                    "Goals": ["Scored", "Conceded"],
                    "Home": ["1.8", "0.9"],
                    "Away": ["1.3", "1.2"],
                    "Total": ["1.6", "1.0"]
                }))
            
            with col2:
                st.markdown(f"**{fixture['away_team']} Goals**")
                st.dataframe(pd.DataFrame({
                    "Goals": ["Scored", "Conceded"],
                    "Home": ["1.7", "0.8"],
                    "Away": ["1.2", "1.4"],
                    "Total": ["1.5", "1.1"]
                }))
            
        elif st.session_state.stats_type == "form":
            st.markdown("### Team Form Analysis")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{fixture['home_team']} Form**")
                home_form = fetch_team_form(fixture['home_id'])
                if home_form:
                    st.dataframe(pd.DataFrame(home_form), hide_index=True)
                else:
                    st.info("No form data available.")
            
            with col2:
                st.markdown(f"**{fixture['away_team']} Form**")
                away_form = fetch_team_form(fixture['away_id'])
                if away_form:
                    st.dataframe(pd.DataFrame(away_form), hide_index=True)
                else:
                    st.info("No form data available.")
        
        elif st.session_state.stats_type == "h2h":
            st.markdown("### Head-to-Head Analysis")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            h2h_data = fetch_head_to_head(fixture['home_id'], fixture['away_id'])
            if h2h_data:
                st.dataframe(pd.DataFrame(h2h_data), hide_index=True)
            else:
                st.info("No head-to-head data available.")

        elif st.session_state.stats_type == "players":
            st.markdown("### Player Information")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{fixture['home_team']} Players**")
                home_players = fetch_players(fixture['home_id'])
                if home_players:
                    st.dataframe(pd.DataFrame(home_players), hide_index=True)
                else:
                    st.info("No player information available.")
            
            with col2:
                st.markdown(f"**{fixture['away_team']} Players**")
                away_players = fetch_players(fixture['away_id'])
                if away_players:
                    st.dataframe(pd.DataFrame(away_players), hide_index=True)
                else:
                    st.info("No player information available.")

        elif st.session_state.stats_type == "stats":
            st.markdown("### Team Statistics")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{fixture['home_team']} Statistics**")
                # Use default league_id if not available
                league_id = 39  # Default to Premier League
                home_stats = fetch_team_statistics(fixture['home_id'], league_id)
                if home_stats:
                    st.dataframe(pd.DataFrame([home_stats]), hide_index=True)
                else:
                    st.info("No statistics available.")
            
            with col2:
                st.markdown(f"**{fixture['away_team']} Statistics**")
                away_stats = fetch_team_statistics(fixture['away_id'], league_id)
                if away_stats:
                    st.dataframe(pd.DataFrame([away_stats]), hide_index=True)
                else:
                    st.info("No statistics available.")

        elif st.session_state.stats_type == "lineups":
            st.markdown("### Team Lineups")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            # We need a fixture ID for this, which we might not have
            st.info("Lineup information is only available once a match is scheduled with a fixture ID.")
            
        elif st.session_state.stats_type == "venue":
            st.markdown("### Venue Information")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            # We need venue info for this
            st.info("Venue information is only available once a match is scheduled with venue details.")
            
        elif st.session_state.stats_type == "injuries":
            st.markdown("### Team Injuries")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{fixture['home_team']} Injuries**")
                # Use default league_id if not available
                league_id = 39  # Default to Premier League
                home_injuries = fetch_injuries(fixture['home_id'], league_id)
                if home_injuries:
                    st.dataframe(pd.DataFrame(home_injuries), hide_index=True)
                else:
                    st.info("No injury information available.")
            
            with col2:
                st.markdown(f"**{fixture['away_team']} Injuries**")
                away_injuries = fetch_injuries(fixture['away_id'], league_id)
                if away_injuries:
                    st.dataframe(pd.DataFrame(away_injuries), hide_index=True)
                else:
                    st.info("No injury information available.")
        
        elif st.session_state.stats_type == "more":
            st.markdown("### Additional Statistics")
            st.markdown(f"#### {fixture['home_team']} vs {fixture['away_team']}")
            
            stat_option = st.selectbox(
                "Select Statistics",
                [
                    "Team Statistics",
                    "Player Information",
                    "Lineups",
                    "Venue Information",
                    "Injuries",
                    "Team Form"
                ]
            )
            
            if stat_option == "Team Statistics":
                st.markdown("##### Team Statistics")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**{fixture['home_team']}**")
                    # Use default league_id if not available
                    league_id = 39  # Default to Premier League
                    home_stats = fetch_team_statistics(fixture['home_id'], league_id)
                    if home_stats:
                        st.dataframe(pd.DataFrame([home_stats]), hide_index=True)
                    else:
                        st.info("No statistics available.")
                
                with col2:
                    st.markdown(f"**{fixture['away_team']}**")
                    away_stats = fetch_team_statistics(fixture['away_id'], league_id)
                    if away_stats:
                        st.dataframe(pd.DataFrame([away_stats]), hide_index=True)
                    else:
                        st.info("No statistics available.")
        
        # Add close button
        if st.button("Close"):
            st.session_state.stats_type = None
            st.session_state.current_fixture = None
            st.rerun()

# Display selected fixtures and analysis
if st.session_state.selected_fixtures:
    # Display selected fixtures using our custom table format
    display_selected_fixtures()

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
            batch_size = 5  # Increased batch size
            total_fixtures = len(analysis_df)
            progress_bar = st.progress(0)

            # Initialize prediction lists
            home_win_pcts = []
            draw_pcts = []
            away_win_pcts = []
            predictions_source = []
            prediction_details = []

            # Pre-fetch all team stats and form data
            team_stats_cache = {}
            team_form_cache = {}

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
                        try:
                            if str(row['league']).isdigit():
                                league_id = int(row['league'])
                            else:
                                print(f"Invalid league: {row['league']} for {fixture_key}")
                                league_id = 39  # Use Premier League as fallback
                        except:
                            st.warning(f"League '{row['league']}' not recognized for {fixture_key}. Using fallback predictions.")
                            league_id = 39  # Use Premier League as fallback
                    
                    if not league_id:
                        st.error(f"Invalid league: {row['league']} for {fixture_key}")
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
                
                # Reduced delay between batches
                time.sleep(0.1)
            
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
            use_container_width=True,
            key=editor_key,
            column_config={
                "Date": st.column_config.TextColumn("Date", width="small"),
                "Home Team": st.column_config.TextColumn("Home", width="medium"),
                "Away Team": st.column_config.TextColumn("Away", width="medium"),
                "Home Win %": st.column_config.TextColumn("H%", width="small"),
                "Draw %": st.column_config.TextColumn("D%", width="small"),
                "Away Win %": st.column_config.TextColumn("A%", width="small"),
                "Prediction": st.column_config.TextColumn("Pred", width="small"),
                "Predicted Result": st.column_config.TextColumn("Result", width="small"),
                "View Details": st.column_config.TextColumn(
                    "Additional Analysis",
                    width="medium"
                ),
                "Prediction Details": st.column_config.TextColumn(
                    "Details", 
                    width="medium"
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
        
        # Add alternative selection method with regular selectboxes
        st.write("### Select Analysis for Fixtures")
        for idx, row in analysis_df.iterrows():
            fixture_key = f"{row['Home Team']} vs {row['Away Team']} ({row['Date']})"
            current_selection = st.session_state.analysis_selections.get(fixture_key, "Select Analysis")
            
            st.write(f"**{row['Home Team']} vs {row['Away Team']}**")
            analysis_options = [
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
            ]
            
            analysis_selection = st.selectbox(
                "Analysis Type", 
                options=analysis_options,
                index=analysis_options.index(current_selection) if current_selection in analysis_options else 0,
                key=f"analysis_select_{idx}"
            )
            
            if analysis_selection != current_selection:
                st.session_state.analysis_selections[fixture_key] = analysis_selection
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
                    # Use columns to display analysis side by side
                    col1, col2 = st.columns([2, 3])
                    
                    with col1:
                        st.write(f"### {row['Home Team']} vs {row['Away Team']}")
                        st.write(f"**Date:** {row['Date']}")
                        st.write(f"**Prediction:** {row['Prediction']}")
                        st.write(f"**Predicted Result:** {row['Predicted Result']}")
                        
                        # Show basic prediction percentages
                        st.write("##### Probabilities")
                        st.write(f"Home Win: {row['Home Win %']}")
                        st.write(f"Draw: {row['Draw %']}")
                        st.write(f"Away Win: {row['Away Win %']}")
                        
                        # Display prediction details if available
                        if 'Prediction Details' in row:
                            st.write("##### Details")
                            st.write(row['Prediction Details'].replace('\n', '<br>'), unsafe_allow_html=True)
                    
                    with col2:
                        # Fetch and display the selected analysis type
                        if analysis_type in ["Head-to-Head", "All Data"]:
                            st.subheader("Head-to-Head Statistics")
                            if 'home_team_id' in row and 'away_team_id' in row and row['home_team_id'] and row['away_team_id']:
                                h2h_data = fetch_head_to_head(row['home_team_id'], row['away_team_id'])
                                if h2h_data:
                                    h2h_df = pd.DataFrame(h2h_data)
                                    st.dataframe(h2h_df, hide_index=True, use_container_width=True)
                                else:
                                    st.info("No head-to-head data available.")
                            else:
                                st.warning("Team IDs not available for head-to-head analysis.")
                        elif analysis_type in ["Team Statistics", "All Data"]:
                            st.subheader("Team Statistics")
                            sub_col1, sub_col2 = st.columns(2)
                            with sub_col1:
                                st.write(f"**{row['Home Team']} Statistics**")
                                if 'home_team_id' in row and 'league' in row and row['home_team_id'] and row['league']:
                                    home_stats = fetch_team_statistics(row['home_team_id'], row['league'])
                                    if home_stats:
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
                            with sub_col2:
                                st.write(f"**{row['Away Team']} Statistics**")
                                if 'away_team_id' in row and 'league' in row and row['away_team_id'] and row['league']:
                                    away_stats = fetch_team_statistics(row['away_team_id'], row['league'])
                                    if away_stats:
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
                        elif analysis_type in ["Player Information", "All Data"]:
                            st.subheader("Player Information")
                            sub_col1, sub_col2 = st.columns(2)
                            with sub_col1:
                                st.write(f"**{row['Home Team']} Players**")
                                home_players = fetch_players(row['home_team_id'])
                                if home_players:
                                    st.dataframe(pd.DataFrame(home_players), hide_index=True)
                                else:
                                    st.info("No player information available for home team.")
                            with sub_col2:
                                st.write(f"**{row['Away Team']} Players**")
                                away_players = fetch_players(row['away_team_id'])
                                if away_players:
                                    st.dataframe(pd.DataFrame(away_players), hide_index=True)
                                else:
                                    st.info("No player information available for away team.")
                        elif analysis_type in ["Lineups", "All Data"]:
                            st.subheader("Lineups")
                            lineups = fetch_lineups(row['fixture_id'])
                            if lineups:
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
                        elif analysis_type in ["Venue Information", "All Data"]:
                            st.subheader("Venue Information")
                            venue_info = fetch_venue_info(row['venue'])
                            if venue_info:
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
                        elif analysis_type in ["Injuries", "All Data"]:
                            st.subheader("Injuries")
                            sub_col1, sub_col2 = st.columns(2)
                            with sub_col1:
                                st.write(f"**{row['Home Team']} Injuries**")
                                home_injuries = fetch_injuries(row['home_team_id'], row['league'])
                                if home_injuries:
                                    st.dataframe(pd.DataFrame(home_injuries), hide_index=True)
                                else:
                                    st.info("No injury information available for home team.")
                            with sub_col2:
                                st.write(f"**{row['Away Team']} Injuries**")
                                away_injuries = fetch_injuries(row['away_team_id'], row['league'])
                                if away_injuries:
                                    st.dataframe(pd.DataFrame(away_injuries), hide_index=True)
                                else:
                                    st.info("No injury information available for away team.")
                        elif analysis_type in ["Team Form", "All Data"]:
                            st.subheader("Team Form")
                            sub_col1, sub_col2 = st.columns(2)
                            with sub_col1:
                                st.write(f"**{row['Home Team']} Recent Form**")
                                home_form = fetch_team_form(row['home_team_id'])
                                if home_form:
                                    st.dataframe(pd.DataFrame(home_form), hide_index=True)
                                else:
                                    st.info("No form data available for home team.")
                            with sub_col2:
                                st.write(f"**{row['Away Team']} Recent Form**")
                                away_form = fetch_team_form(row['away_team_id'])
                                if away_form:
                                    st.dataframe(pd.DataFrame(away_form), hide_index=True)
                                else:
                                    st.info("No form data available for away team.")
                        elif analysis_type in ["Weather", "All Data"]:
                            st.subheader("Weather Information")
                            weather = fetch_weather_for_fixture(row['fixture_id'])
                            if weather:
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
                        elif analysis_type in ["Referee Information", "All Data"]:
                            st.subheader("Referee Information")
                            referee = fetch_referee_info(row['fixture_id'])
                            if referee:
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
    # Silently handle missing standings data without showing warning
    pass
    
# Close the main content div at the end
st.markdown("</div>", unsafe_allow_html=True) 

# Comment out or remove the JavaScript sections at the end of the file that are causing syntax errors
# Add JavaScript for fixture selection
st.markdown("", unsafe_allow_html=True)

# Instead of the problematic JavaScript section
# Let's just have a simple comment explaining that we've removed it
# to fix the rendering issues

# The following JavaScript code was commented out to fix rendering issues:
# - Event listeners for fixture selection
# - Functions for displaying team form and head-to-head data

# Add JavaScript for tab navigation
st.markdown("""
    <script>
        // Function to scroll tabs
        function scrollTabs(direction) {
            const tabsContainer = document.querySelector('.stTabs [data-testid="stVerticalBlock"]');
            if (tabsContainer) {
                const scrollAmount = 200; // Adjust this value to control scroll distance
                tabsContainer.scrollBy({
                    left: direction * scrollAmount,
                    behavior: 'smooth'
                });
            }
        }

        // Add navigation buttons
        function addTabNavigation() {
            const tabsContainer = document.querySelector('.stTabs [data-testid="stVerticalBlock"]');
            if (tabsContainer) {
                // Remove existing buttons if any
                const existingButtons = document.querySelectorAll('.tab-nav-button');
                existingButtons.forEach(button => button.remove());

                // Create left button
                const leftButton = document.createElement('button');
                leftButton.className = 'tab-nav-button tab-nav-left';
                leftButton.innerHTML = '←';
                leftButton.onclick = () => scrollTabs(-1);
                
                // Create right button
                const rightButton = document.createElement('button');
                rightButton.className = 'tab-nav-button tab-nav-right';
                rightButton.innerHTML = '→';
                rightButton.onclick = () => scrollTabs(1);
                
                // Add buttons to document body
                document.body.appendChild(leftButton);
                document.body.appendChild(rightButton);

                // Show/hide buttons based on scroll position
                tabsContainer.addEventListener('scroll', () => {
                    const showLeft = tabsContainer.scrollLeft > 0;
                    const showRight = tabsContainer.scrollLeft < (tabsContainer.scrollWidth - tabsContainer.clientWidth);
                    
                    leftButton.style.display = showLeft ? 'flex' : 'none';
                    rightButton.style.display = showRight ? 'flex' : 'none';
                });

                // Initial check for button visibility
                leftButton.style.display = tabsContainer.scrollLeft > 0 ? 'flex' : 'none';
                rightButton.style.display = tabsContainer.scrollLeft < (tabsContainer.scrollWidth - tabsContainer.clientWidth) ? 'flex' : 'none';
            }
        }

        // Run when the page loads
        window.addEventListener('load', addTabNavigation);
        
        // Also run when Streamlit reruns
        document.addEventListener('DOMContentLoaded', addTabNavigation);

        // Run after a short delay to ensure elements are loaded
        setTimeout(addTabNavigation, 1000);
    </script>
""", unsafe_allow_html=True)

# Add tab navigation
st.markdown("""
    <style>
        .stTabs [data-testid="stVerticalBlock"] {
            overflow-x: auto !important;
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
        }
        .stTabs [data-testid="stVerticalBlock"]::-webkit-scrollbar {
            display: none !important;
        }
        .tab-nav-button {
            position: fixed !important;
            top: 50% !important;
            transform: translateY(-50%) !important;
            background-color: rgba(0, 0, 0, 0.8) !important;
            color: white !important;
            border: none !important;
            padding: 10px !important;
            cursor: pointer !important;
            z-index: 9999 !important;
            border-radius: 50% !important;
            width: 40px !important;
            height: 40px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 20px !important;
            transition: background-color 0.3s !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2) !important;
        }
        .tab-nav-button:hover {
            background-color: rgba(0, 0, 0, 0.9) !important;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important;
        }
        .tab-nav-left {
            left: 10px !important;
        }
        .tab-nav-right {
            right: 10px !important;
        }
    </style>
    <script>
        function scrollTabs(direction) {
            const tabsContainer = document.querySelector('.stTabs [data-testid="stVerticalBlock"]');
            if (tabsContainer) {
                const scrollAmount = 200;
                tabsContainer.scrollBy({
                    left: direction * scrollAmount,
                    behavior: 'smooth'
                });
            }
        }

        function addTabNavigation() {
            const tabsContainer = document.querySelector('.stTabs [data-testid="stVerticalBlock"]');
            if (tabsContainer) {
                // Remove existing buttons if any
                const existingButtons = document.querySelectorAll('.tab-nav-button');
                existingButtons.forEach(button => button.remove());

                // Create left button
                const leftButton = document.createElement('button');
                leftButton.className = 'tab-nav-button tab-nav-left';
                leftButton.innerHTML = '←';
                leftButton.onclick = () => scrollTabs(-1);
                
                // Create right button
                const rightButton = document.createElement('button');
                rightButton.className = 'tab-nav-button tab-nav-right';
                rightButton.innerHTML = '→';
                rightButton.onclick = () => scrollTabs(1);
                
                // Add buttons to document body
                document.body.appendChild(leftButton);
                document.body.appendChild(rightButton);

                // Show/hide buttons based on scroll position
                tabsContainer.addEventListener('scroll', () => {
                    const showLeft = tabsContainer.scrollLeft > 0;
                    const showRight = tabsContainer.scrollLeft < (tabsContainer.scrollWidth - tabsContainer.clientWidth);
                    
                    leftButton.style.display = showLeft ? 'flex' : 'none';
                    rightButton.style.display = showRight ? 'flex' : 'none';
                });

                // Initial check for button visibility
                leftButton.style.display = tabsContainer.scrollLeft > 0 ? 'flex' : 'none';
                rightButton.style.display = tabsContainer.scrollLeft < (tabsContainer.scrollWidth - tabsContainer.clientWidth) ? 'flex' : 'none';
            }
        }

        // Run when the page loads
        window.addEventListener('load', addTabNavigation);
        
        // Also run when Streamlit reruns
        document.addEventListener('DOMContentLoaded', addTabNavigation);

        // Run after a short delay to ensure elements are loaded
        setTimeout(addTabNavigation, 1000);
    </script>
""", unsafe_allow_html=True)

# Create the tabs
league_tabs = st.tabs(LEAGUES.keys())

# ... existing code ...