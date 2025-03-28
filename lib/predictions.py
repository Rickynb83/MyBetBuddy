import numpy as np
from scipy.stats import poisson
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime, timedelta
from lib.fetch_fixtures import api_football_request
import warnings
import math
from concurrent.futures import ThreadPoolExecutor
import time
from lib.cache import cache

# Suppress warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning)

def calculate_team_stats(team_id: int, matches: Dict[str, List[Dict]]) -> Dict:
    """
    Calculate comprehensive team statistics based on historical matches.
    
    Args:
        team_id: The ID of the team
        matches: Dict containing matches from current and other leagues
        
    Returns:
        Dict containing detailed team statistics and performance metrics
    """
    stats = {
        'current_league': {
            'games_played': 0,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'goals_scored': 0,
            'goals_conceded': 0,
            'clean_sheets': 0,
            'failed_to_score': 0,
            'home_games': 0,
            'away_games': 0,
            'home_goals_scored': 0,
            'away_goals_scored': 0,
            'home_goals_conceded': 0,
            'away_goals_conceded': 0,
            'home_wins': 0,
            'home_draws': 0,
            'home_losses': 0,
            'away_wins': 0,
            'away_draws': 0,
            'away_losses': 0,
            'form_sequence': [],  # Last 5 matches: W, D, L
            'goals_scored_by_minute': {
                '0-15': 0, '16-30': 0, '31-45': 0,
                '46-60': 0, '61-75': 0, '76-90': 0
            },
            'goals_conceded_by_minute': {
                '0-15': 0, '16-30': 0, '31-45': 0,
                '46-60': 0, '61-75': 0, '76-90': 0
            }
        },
        'other_leagues': {
            'games_played': 0,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'goals_scored': 0,
            'goals_conceded': 0,
            'clean_sheets': 0,
            'failed_to_score': 0
        },
        'recent_form': {
            'last_8_games': [],
            'goals_scored_last_8': 0,
            'goals_conceded_last_8': 0,
            'points_last_8': 0,
            'form_rating': 0.0,
            'clean_sheets_last_8': 0,
            'failed_to_score_last_8': 0
        }
    }
    
    # Process current league matches
    current_league_matches = sorted(matches['current_league'], 
                                  key=lambda x: datetime.strptime(x['date'], '%Y-%m-%dT%H:%M:%S%z'))
    
    for match in current_league_matches:
        is_home = match['home_team'] == team_id
        team_goals = match['home_goals'] if is_home else match['away_goals']
        opponent_goals = match['away_goals'] if is_home else match['home_goals']
        
        # Update basic stats
        stats['current_league']['games_played'] += 1
        stats['current_league']['goals_scored'] += team_goals
        stats['current_league']['goals_conceded'] += opponent_goals
        
        # Update home/away specific stats
        if is_home:
            stats['current_league']['home_games'] += 1
            stats['current_league']['home_goals_scored'] += team_goals
            stats['current_league']['home_goals_conceded'] += opponent_goals
            
            if team_goals > opponent_goals:
                stats['current_league']['home_wins'] += 1
                stats['current_league']['wins'] += 1
                stats['current_league']['form_sequence'].append('W')
            elif team_goals == opponent_goals:
                stats['current_league']['home_draws'] += 1
                stats['current_league']['draws'] += 1
                stats['current_league']['form_sequence'].append('D')
            else:
                stats['current_league']['home_losses'] += 1
                stats['current_league']['losses'] += 1
                stats['current_league']['form_sequence'].append('L')
        else:
            stats['current_league']['away_games'] += 1
            stats['current_league']['away_goals_scored'] += team_goals
            stats['current_league']['away_goals_conceded'] += opponent_goals
            
            if team_goals > opponent_goals:
                stats['current_league']['away_wins'] += 1
                stats['current_league']['wins'] += 1
                stats['current_league']['form_sequence'].append('W')
            elif team_goals == opponent_goals:
                stats['current_league']['away_draws'] += 1
                stats['current_league']['draws'] += 1
                stats['current_league']['form_sequence'].append('D')
            else:
                stats['current_league']['away_losses'] += 1
                stats['current_league']['losses'] += 1
                stats['current_league']['form_sequence'].append('L')
        
        # Update clean sheets and failed to score
        if opponent_goals == 0:
            stats['current_league']['clean_sheets'] += 1
        if team_goals == 0:
            stats['current_league']['failed_to_score'] += 1
    
    # Process other leagues matches with lower weighting
    for match in matches['other_leagues']:
        is_home = match['home_team'] == team_id
        team_goals = match['home_goals'] if is_home else match['away_goals']
        opponent_goals = match['away_goals'] if is_home else match['home_goals']
        
        stats['other_leagues']['games_played'] += 1
        stats['other_leagues']['goals_scored'] += team_goals
        stats['other_leagues']['goals_conceded'] += opponent_goals
        
        if team_goals > opponent_goals:
            stats['other_leagues']['wins'] += 1
        elif team_goals == opponent_goals:
            stats['other_leagues']['draws'] += 1
        else:
            stats['other_leagues']['losses'] += 1
            
        if opponent_goals == 0:
            stats['other_leagues']['clean_sheets'] += 1
        if team_goals == 0:
            stats['other_leagues']['failed_to_score'] += 1
    
    # Calculate recent form (last 8 matches)
    last_8_matches = current_league_matches[-8:] if len(current_league_matches) >= 8 else current_league_matches
    
    stats['recent_form'] = {
        'last_8_games': [],
        'goals_scored_last_8': 0,
        'goals_conceded_last_8': 0,
        'points_last_8': 0,
        'form_rating': 0.0,
        'clean_sheets_last_8': 0,
        'failed_to_score_last_8': 0
    }
    
    for match in last_8_matches:
        is_home = match['home_team'] == team_id
        team_goals = match['home_goals'] if is_home else match['away_goals']
        opponent_goals = match['away_goals'] if is_home else match['home_goals']
        
        stats['recent_form']['goals_scored_last_8'] += team_goals
        stats['recent_form']['goals_conceded_last_8'] += opponent_goals
        
        if opponent_goals == 0:
            stats['recent_form']['clean_sheets_last_8'] += 1
        if team_goals == 0:
            stats['recent_form']['failed_to_score_last_8'] += 1
        
        if team_goals > opponent_goals:
            stats['recent_form']['points_last_8'] += 3
            stats['recent_form']['last_8_games'].append('W')
        elif team_goals == opponent_goals:
            stats['recent_form']['points_last_8'] += 1
            stats['recent_form']['last_8_games'].append('D')
        else:
            stats['recent_form']['last_8_games'].append('L')
    
    # Calculate form rating (0-100)
    max_points_possible = len(last_8_matches) * 3
    if max_points_possible > 0:
        stats['recent_form']['form_rating'] = (stats['recent_form']['points_last_8'] / max_points_possible) * 100
    
    # Calculate performance metrics
    if stats['current_league']['games_played'] > 0:
        stats['performance_metrics'] = {
            'points_per_game': (stats['current_league']['wins'] * 3 + stats['current_league']['draws']) / 
                              stats['current_league']['games_played'],
            'goals_scored_per_game': stats['current_league']['goals_scored'] / 
                                    stats['current_league']['games_played'],
            'goals_conceded_per_game': stats['current_league']['goals_conceded'] / 
                                      stats['current_league']['games_played'],
            'clean_sheet_percentage': (stats['current_league']['clean_sheets'] / 
                                     stats['current_league']['games_played']) * 100,
            'win_percentage': (stats['current_league']['wins'] / 
                             stats['current_league']['games_played']) * 100,
            'home_win_percentage': (stats['current_league']['home_wins'] / 
                                  stats['current_league']['home_games']) * 100 
                                  if stats['current_league']['home_games'] > 0 else 0,
            'away_win_percentage': (stats['current_league']['away_wins'] / 
                                  stats['current_league']['away_games']) * 100 
                                  if stats['current_league']['away_games'] > 0 else 0,
            'scoring_consistency': (1 - (stats['current_league']['failed_to_score'] / 
                                      stats['current_league']['games_played'])) * 100,
            'defensive_stability': (stats['current_league']['clean_sheets'] / 
                                  stats['current_league']['games_played']) * 100
        }
    else:
        # If no current league data, use other leagues data with adjustment
        other_games = stats['other_leagues']['games_played']
        if other_games > 0:
            adjustment_factor = 0.85  # Reduce strength due to league change
            stats['performance_metrics'] = {
                'points_per_game': ((stats['other_leagues']['wins'] * 3 + 
                                   stats['other_leagues']['draws']) / other_games) * adjustment_factor,
                'goals_scored_per_game': (stats['other_leagues']['goals_scored'] / 
                                        other_games) * adjustment_factor,
                'goals_conceded_per_game': (stats['other_leagues']['goals_conceded'] / 
                                          other_games) / adjustment_factor,
                'clean_sheet_percentage': (stats['other_leagues']['clean_sheets'] / 
                                         other_games) * 100 * adjustment_factor,
                'win_percentage': (stats['other_leagues']['wins'] / other_games) * 
                                100 * adjustment_factor,
                'scoring_consistency': (1 - (stats['other_leagues']['failed_to_score'] / 
                                          other_games)) * 100 * adjustment_factor,
                'defensive_stability': (stats['other_leagues']['clean_sheets'] / 
                                      other_games) * 100 * adjustment_factor
            }
        else:
            # No data at all - use league averages
            stats['performance_metrics'] = {
                'points_per_game': 1.5,
                'goals_scored_per_game': 1.5,
                'goals_conceded_per_game': 1.5,
                'clean_sheet_percentage': 30,
                'win_percentage': 33,
                'home_win_percentage': 40,
                'away_win_percentage': 26,
                'scoring_consistency': 70,
                'defensive_stability': 30
            }
    
    return stats

def calculate_poisson_probabilities(home_team_stats, away_team_stats, h2h_stats):
    """
    Calculate match outcome probabilities using Poisson distribution.
    """
    # Base expected goals calculation using correct metrics path
    home_base_xg = home_team_stats.get('metrics', {}).get('goals_per_game', 1.5)
    away_base_xg = away_team_stats.get('metrics', {}).get('goals_per_game', 1.5)
    
    # Get team strengths with safe defaults
    home_attack = home_team_stats.get('strength', {}).get('attack_strength', 1.0)
    home_defense = home_team_stats.get('strength', {}).get('defense_strength', 1.0)
    away_attack = away_team_stats.get('strength', {}).get('attack_strength', 1.0)
    away_defense = away_team_stats.get('strength', {}).get('defense_strength', 1.0)
    
    # Check if teams are closely matched based on multiple factors
    strength_diff = abs(home_attack - away_attack)
    position_diff = abs(home_team_stats.get('position', 0) - away_team_stats.get('position', 0))
    points_diff = abs(home_team_stats.get('points', 0) - away_team_stats.get('points', 0))
    
    # Teams are considered closely matched if:
    # 1. Strength difference is small AND
    # 2. Position difference is small (within 5 places) AND
    # 3. Points difference is small (within 10 points)
    is_close_match = (strength_diff < 0.2 and 
                     position_diff <= 5 and 
                     points_diff <= 10)
    
    # Apply home/away adjustments based on whether teams are closely matched
    if is_close_match:
        home_xg = home_base_xg * 1.01  # Minimal home advantage for close matches
        away_xg = away_base_xg * 0.99  # Minimal away penalty for close matches
    else:
        home_xg = home_base_xg * 1.02   # Reduced home advantage
        away_xg = away_base_xg * 0.98   # Reduced away penalty
    
    # Apply attack vs defense adjustments with more balanced weighting
    if is_close_match:
        home_xg *= min(1.1, max(0.9, home_attack / away_defense))  # Reduced adjustment range
        away_xg *= min(1.1, max(0.9, away_attack / home_defense))  # Reduced adjustment range
    else:
        home_xg *= min(1.2, max(0.8, home_attack / away_defense))    # Reduced adjustment range
        away_xg *= min(1.2, max(0.8, away_attack / home_defense))    # Reduced adjustment range
    
    # Apply h2h adjustment if available
    if h2h_stats and 'h2h_factor' in h2h_stats:
        h2h_factor = min(1.1, max(0.9, h2h_stats['h2h_factor']))  # Reduced h2h impact
        home_xg *= h2h_factor
        away_xg /= h2h_factor
    
    # Calculate score probabilities
    max_goals = 10
    score_probs = np.zeros((max_goals + 1, max_goals + 1))
    
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            score_probs[i, j] = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
    
    # Calculate outcome probabilities
    home_win_prob = np.sum(np.tril(score_probs, -1))
    away_win_prob = np.sum(np.triu(score_probs, 1))
    draw_prob = np.sum(np.diag(score_probs))
    
    # Cap maximum probabilities to ensure realistic values
    if home_win_prob > 0.75:
        excess = home_win_prob - 0.75
        home_win_prob = 0.75
        draw_prob += excess * 0.6
        away_win_prob += excess * 0.4
    
    if away_win_prob > 0.65:
        excess = away_win_prob - 0.65
        away_win_prob = 0.65
        draw_prob += excess * 0.6
        home_win_prob += excess * 0.4
    
    # Ensure minimum probabilities
    if draw_prob < 0.15:
        shortage = 0.15 - draw_prob
        draw_prob = 0.15
        if home_win_prob > away_win_prob:
            home_win_prob -= shortage
        else:
            away_win_prob -= shortage
    
    if away_win_prob < 0.10:
        shortage = 0.10 - away_win_prob
        away_win_prob = 0.10
        home_win_prob -= shortage
    
    # Final normalization
    total = home_win_prob + away_win_prob + draw_prob
    home_win_prob /= total
    away_win_prob /= total
    draw_prob /= total
    
    return {
        'probabilities': {
            'home_win': home_win_prob,
            'draw': draw_prob,
            'away_win': away_win_prob
        },
        'expected_goals': {
            'home': home_xg,
            'away': away_xg,
            'total': home_xg + away_xg
        }
    }

def calculate_form_factor(recent_matches: List[Dict], team_id: int) -> Dict:
    """
    Calculate team's form based on last 8 matches with enhanced analysis.
    """
    if not recent_matches:
        return {
            'form_factor': 1.0,
            'form_rating': 50.0,
            'trend': 'neutral',
            'goals_trend': 'neutral',
            'confidence': 'low'
        }
    
    # Take last 8 matches
    last_8 = recent_matches[-8:] if len(recent_matches) >= 8 else recent_matches
    num_matches = len(last_8)
    
    # Initialize counters
    points = 0
    goals_scored = 0
    goals_conceded = 0
    wins = 0
    draws = 0
    losses = 0
    clean_sheets = 0
    failed_to_score = 0
    
    # Weight more recent matches higher (less extreme decay)
    weights = [1.3, 1.25, 1.2, 1.15, 1.1, 1.05, 1.0, 0.95][:num_matches]
    total_weight = sum(weights)
    
    # Track match-by-match performance
    performance_trend = []
    goal_differences = []
    
    for match, weight in zip(last_8, weights):
        is_home = match['home_team'] == team_id
        team_goals = match['home_goals'] if is_home else match['away_goals']
        opponent_goals = match['away_goals'] if is_home else match['home_goals']
        
        # Calculate match performance (0-100)
        goal_diff = team_goals - opponent_goals
        goal_differences.append(goal_diff)
        
        match_performance = 50  # Base performance
        if team_goals > opponent_goals:
            match_performance = 75 + min(goal_diff * 3, 15)  # Win bonus (capped)
            points += 3 * weight
            wins += 1
        elif team_goals == opponent_goals:
            match_performance = 60  # Draw is still positive
            points += 1 * weight
            draws += 1
        else:
            match_performance = 40 + max(goal_diff * 3, -30)  # Loss penalty (capped)
            losses += 1
        
        performance_trend.append(match_performance)
        
        # Track goals
        goals_scored += team_goals * weight
        goals_conceded += opponent_goals * weight
        
        if opponent_goals == 0:
            clean_sheets += 1
            match_performance += 5  # Clean sheet bonus
        if team_goals == 0:
            failed_to_score += 1
            match_performance -= 5  # Failed to score penalty
    
    # Calculate weighted averages
    weighted_points = points / total_weight
    max_weighted_points = 3 * total_weight
    form_rating = (weighted_points / max_weighted_points) * 100
    
    # Calculate goal averages
    goals_scored_avg = goals_scored / total_weight
    goals_conceded_avg = goals_conceded / total_weight
    
    # Calculate performance consistency
    performance_std = np.std(performance_trend) if len(performance_trend) > 1 else 0
    consistency_rating = max(0, 100 - (performance_std / 2))
    
    # Calculate momentum (based on last 3 matches vs previous 3)
    recent_perf = np.mean(performance_trend[-3:]) if len(performance_trend) >= 3 else np.mean(performance_trend)
    earlier_perf = np.mean(performance_trend[:-3]) if len(performance_trend) >= 6 else np.mean(performance_trend)
    momentum = recent_perf - earlier_perf
    
    # Determine form factor (centered around 1.0 with narrower range)
    base_form = 0.8 + (form_rating / 100) * 0.4  # 0.8 to 1.2
    momentum_adj = max(-0.1, min(0.1, momentum / 200))  # -0.1 to +0.1
    consistency_adj = (consistency_rating / 100) * 0.1  # 0 to 0.1
    form_factor = base_form + momentum_adj + consistency_adj  # Range: 0.7 to 1.4
    
    # Analyze trends
    first_half = last_8[:num_matches//2]
    second_half = last_8[num_matches//2:]
    
    first_half_goals = sum(m['home_goals'] if m['home_team'] == team_id else m['away_goals'] for m in first_half)
    second_half_goals = sum(m['home_goals'] if m['home_team'] == team_id else m['away_goals'] for m in second_half)
    
    first_half_points = sum(3 if (m['home_team'] == team_id and m['home_goals'] > m['away_goals']) or 
                              (m['away_team'] == team_id and m['away_goals'] > m['home_goals'])
                           else 1 if m['home_goals'] == m['away_goals'] else 0 
                           for m in first_half)
    
    second_half_points = sum(3 if (m['home_team'] == team_id and m['home_goals'] > m['away_goals']) or 
                               (m['away_team'] == team_id and m['away_goals'] > m['home_goals'])
                            else 1 if m['home_goals'] == m['away_goals'] else 0 
                            for m in second_half)
    
    # More nuanced trend analysis
    point_diff = second_half_points - first_half_points
    if point_diff > 3:
        trend = 'strongly_improving'
    elif point_diff > 0:
        trend = 'slightly_improving'
    elif point_diff < -3:
        trend = 'strongly_declining'
    elif point_diff < 0:
        trend = 'slightly_declining'
    else:
        trend = 'stable'
    
    goals_diff = second_half_goals - first_half_goals
    if goals_diff > 2:
        goals_trend = 'strongly_improving'
    elif goals_diff > 0:
        goals_trend = 'slightly_improving'
    elif goals_diff < -2:
        goals_trend = 'strongly_declining'
    elif goals_diff < 0:
        goals_trend = 'slightly_declining'
    else:
        goals_trend = 'stable'
    
    return {
        'form_factor': form_factor,
        'form_rating': form_rating,
        'metrics': {
            'weighted_points': weighted_points,
            'points_per_game': points / num_matches,
            'goals_scored_avg': goals_scored_avg,
            'goals_conceded_avg': goals_conceded_avg,
            'clean_sheet_ratio': clean_sheets / num_matches,
            'failed_to_score_ratio': failed_to_score / num_matches
        },
        'results': {
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'clean_sheets': clean_sheets,
            'failed_to_score': failed_to_score,
            'goal_differences': goal_differences
        },
        'performance': {
            'trend': trend,
            'goals_trend': goals_trend,
            'last_8_performances': performance_trend,
            'consistency': consistency_rating
        },
        'confidence': 'high' if num_matches >= 6 else 'medium' if num_matches >= 4 else 'low',
        'matches_analyzed': num_matches
    }

def analyze_head_to_head(h2h_matches: List[Dict], team1_id: int, team2_id: int) -> Dict:
    """
    Analyze head-to-head record between two teams.
    
    Args:
        h2h_matches: List of previous meetings between the teams
        team1_id: ID of the first team
        team2_id: ID of the second team
        
    Returns:
        Dict containing h2h statistics and factors
    """
    if not h2h_matches:
        return {
            'h2h_factor': 1.0,
            'dominance_rating': 0.0,
            'confidence': 'low',
            'matches_analyzed': 0
        }
    
    # Initialize counters
    stats = {
        'team1_wins': 0,
        'team2_wins': 0,
        'draws': 0,
        'team1_goals': 0,
        'team2_goals': 0,
        'total_matches': len(h2h_matches),
        'recent_matches': []
    }
    
    # Weight more recent matches higher
    max_weight = 2.0
    weight_decay = 0.8
    current_weight = max_weight
    total_weight = 0
    weighted_goal_diff = 0
    
    # Track performance trends
    goal_differences = []
    match_dominance = []  # Track which team was more dominant in each match
    
    for match in h2h_matches:
        team1_home = match['home_team'] == team1_id
        team1_goals = match['home_goals'] if team1_home else match['away_goals']
        team2_goals = match['away_goals'] if team1_home else match['home_goals']
        
        # Update basic stats
        stats['team1_goals'] += team1_goals
        stats['team2_goals'] += team2_goals
        
        if team1_goals > team2_goals:
            stats['team1_wins'] += 1
        elif team2_goals > team1_goals:
            stats['team2_wins'] += 1
        else:
            stats['draws'] += 1
        
        # Calculate weighted goal difference
        goal_diff = team1_goals - team2_goals
        weighted_goal_diff += goal_diff * current_weight
        total_weight += current_weight
        
        # Track goal differences for consistency analysis
        goal_differences.append(goal_diff)
        
        # Calculate match dominance (-1 to 1, positive means team1 dominated)
        dominance = goal_diff / max(3, abs(goal_diff))  # Cap at ±3 goals
        match_dominance.append(dominance)
        
        # Store recent match info
        stats['recent_matches'].append({
            'date': match['date'],
            'team1_goals': team1_goals,
            'team2_goals': team2_goals,
            'venue': 'home' if team1_home else 'away',
            'goal_difference': goal_diff,
            'dominance': dominance
        })
        
        # Decay weight for older matches
        current_weight *= weight_decay
    
    # Calculate averages and trends
    stats['avg_team1_goals'] = stats['team1_goals'] / stats['total_matches']
    stats['avg_team2_goals'] = stats['team2_goals'] / stats['total_matches']
    
    # Calculate weighted dominance
    weighted_dominance = weighted_goal_diff / total_weight if total_weight > 0 else 0
    
    # Calculate consistency in results
    goal_diff_std = np.std(goal_differences) if len(goal_differences) > 1 else 1.0
    result_consistency = max(0, 100 - (goal_diff_std * 20))
    
    # Calculate recent form (last 3 matches vs all matches)
    recent_dominance = np.mean(match_dominance[-3:]) if len(match_dominance) >= 3 else np.mean(match_dominance)
    overall_dominance = team1_wins / total_matches if total_matches > 0 else 0.5
    weighted_dominance = (recent_dominance * 0.6) + (overall_dominance * 0.4)
    
    # Calculate venue advantage
    home_matches = [match for match in h2h_matches if match['home_team'] == home_team_id]
    home_wins = sum(1 for match in home_matches if match['home_goals'] > match['away_goals'])
    venue_advantage = (home_wins / len(home_matches)) * 2 if home_matches else 1.0
    
    # Calculate result consistency
    if total_matches >= 3:
        results = [(match['home_team'] == home_team_id and match['home_goals'] > match['away_goals']) or
                  (match['away_team'] == home_team_id and match['away_goals'] > match['home_goals'])
                  for match in h2h_matches[-3:]]
        consistency = sum(1 for i in range(len(results)-1) if results[i] == results[i+1]) / (len(results)-1)
    else:
        consistency = 0.5
    
    # Calculate h2h factor
    h2h_factor = (weighted_dominance * 0.4 + venue_advantage * 0.4 + consistency * 0.2) * 1.5
    
    h2h_stats = {
        'h2h_factor': h2h_factor,
        'stats': {
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'draws': draws,
            'total_matches': total_matches,
            'avg_team1_goals': avg_team1_goals,
            'avg_team2_goals': avg_team2_goals
        },
        'analysis': {
            'weighted_dominance': weighted_dominance,
            'recent_dominance': recent_dominance,
            'overall_dominance': overall_dominance,
            'result_consistency': consistency,
            'venue_advantage': venue_advantage
        },
        'trends': {
            'goal_differences': [
                match['home_goals'] - match['away_goals'] 
                if match['home_team'] == home_team_id
                else match['away_goals'] - match['home_goals']
                for match in h2h_matches[-5:]
            ],
            'match_dominance': [
                1 if (match['home_team'] == home_team_id and match['home_goals'] > match['away_goals']) or
                     (match['away_team'] == home_team_id and match['away_goals'] > match['home_goals'])
                else 0 if match['home_goals'] != match['away_goals']
                else 0.5
                for match in h2h_matches[-5:]
            ],
            'recent_matches': [
                {
                    'date': match['date'],
                    'team1_goals': match['home_goals'] if match['home_team'] == home_team_id else match['away_goals'],
                    'team2_goals': match['away_goals'] if match['home_team'] == home_team_id else match['home_goals'],
                    'venue': 'home' if match['home_team'] == home_team_id else 'away',
                    'goal_difference': match['home_goals'] - match['away_goals'] 
                        if match['home_team'] == home_team_id
                        else match['away_goals'] - match['home_goals'],
                    'dominance': 1 if (match['home_team'] == home_team_id and match['home_goals'] > match['away_goals']) or
                                    (match['away_team'] == home_team_id and match['away_goals'] > match['home_goals'])
                                else 0 if match['home_goals'] != match['away_goals']
                                else 0.5
                }
                for match in h2h_matches[-5:]
            ]
        },
        'confidence': 'high' if total_matches >= 5 else 'medium' if total_matches >= 3 else 'low',
        'matches_analyzed': total_matches
    }
    
    # Cache the h2h stats
    cache.set('h2h_stats', cache_params, h2h_stats)
    
    return h2h_stats

def calculate_team_strength_index(team_stats: Dict) -> Dict:
    """
    Calculate overall team strength index based on various statistics.
    
    Args:
        team_stats: Dict containing team statistics
        
    Returns:
        Dict containing team strength indices and component scores
    """
    if not team_stats:
        return {
            'overall_strength': 1.0,
            'attack_strength': 1.0,
            'defense_strength': 1.0,
            'confidence': 'low'
        }
    
    # Initialize component scores
    attack_components = {}
    defense_components = {}
    form_components = {}
    
    # Calculate attacking strength components
    if 'performance_metrics' in team_stats:
        metrics = team_stats['performance_metrics']
        
        # Scoring ability (0-2 scale centered at 1.0)
        goals_per_game = metrics.get('goals_scored_per_game', 1.5)
        attack_components['scoring_rate'] = min(2.0, goals_per_game / 1.5)
        
        # Scoring consistency (0-1 scale)
        attack_components['consistency'] = metrics.get('scoring_consistency', 70) / 100
        
        # Home/Away attacking balance
        home_strength = metrics.get('home_win_percentage', 40) / 100
        away_strength = metrics.get('away_win_percentage', 26) / 100
        attack_components['venue_balance'] = (home_strength + away_strength) / 2
    
    # Calculate defensive strength components
    if 'performance_metrics' in team_stats:
        metrics = team_stats['performance_metrics']
        
        # Defensive solidity (inverse of goals conceded, 0-2 scale centered at 1.0)
        goals_conceded = metrics.get('goals_conceded_per_game', 1.5)
        defense_components['defensive_solidity'] = min(2.0, 1.5 / max(0.5, goals_conceded))
        
        # Clean sheet ratio
        defense_components['clean_sheet_ratio'] = metrics.get('clean_sheet_percentage', 30) / 100
        
        # Defensive stability
        defense_components['stability'] = metrics.get('defensive_stability', 30) / 100
    
    # Calculate form components
    if 'recent_form' in team_stats:
        form = team_stats['recent_form']
        
        # Recent results
        max_points = len(form.get('last_8_games', [])) * 3
        if max_points > 0:
            form_components['recent_points'] = form.get('points_last_8', 0) / max_points
        
        # Recent defensive record
        form_components['recent_defense'] = form.get('clean_sheets_last_8', 0) / 8
        
        # Recent attacking record
        games_failed = form.get('failed_to_score_last_8', 0)
        form_components['recent_attack'] = 1 - (games_failed / 8)
    
    # Calculate weighted component scores
    attack_score = 0
    if attack_components:
        attack_score = (
            attack_components.get('scoring_rate', 1.0) * 0.5 +
            attack_components.get('consistency', 0.5) * 0.3 +
            attack_components.get('venue_balance', 0.5) * 0.2
        )
    
    defense_score = 0
    if defense_components:
        defense_score = (
            defense_components.get('defensive_solidity', 1.0) * 0.5 +
            defense_components.get('clean_sheet_ratio', 0.3) * 0.3 +
            defense_components.get('stability', 0.3) * 0.2
        )
    
    form_score = 0
    if form_components:
        form_score = (
            form_components.get('recent_points', 0.5) * 0.4 +
            form_components.get('recent_defense', 0.3) * 0.3 +
            form_components.get('recent_attack', 0.3) * 0.3
        )
    
    # Calculate overall attack and defense strengths
    attack_strength = (attack_score * 0.6 + form_score * 0.4)
    defense_strength = (defense_score * 0.6 + form_score * 0.4)
    
    # Normalize strengths to be centered around 1.0
    attack_strength = 0.5 + attack_strength
    defense_strength = 0.5 + defense_strength
    
    # Calculate overall strength index
    overall_strength = (attack_strength + defense_strength) / 2
    
    # Determine confidence level
    if 'performance_metrics' in team_stats and 'recent_form' in team_stats:
        games_played = team_stats.get('current_league', {}).get('games_played', 0)
        confidence = 'high' if games_played >= 10 else \
                    'medium' if games_played >= 5 else 'low'
    else:
        confidence = 'low'
    
    # Calculate strength variability
    if 'recent_form' in team_stats and 'performance_metrics' in team_stats:
        recent_variance = np.std([
            form_components.get('recent_points', 0.5),
            form_components.get('recent_attack', 0.5),
            form_components.get('recent_defense', 0.5)
        ])
        
        season_variance = np.std([
            attack_components.get('scoring_rate', 1.0) - 1,
            attack_components.get('consistency', 0.5),
            defense_components.get('defensive_solidity', 1.0) - 1,
            defense_components.get('stability', 0.5)
        ])
        
        variability = (recent_variance + season_variance) / 2
    else:
        variability = 0.5
    
    return {
        'overall_strength': overall_strength,
        'attack_strength': attack_strength,
        'defense_strength': defense_strength,
        'components': {
            'attack': attack_components,
            'defense': defense_components,
            'form': form_components
        },
        'metrics': {
            'variability': variability,
            'attack_score': attack_score,
            'defense_score': defense_score,
            'form_score': form_score
        },
        'confidence': confidence
    }

def analyze_cards(team_id: int, matches: List[Dict], h2h_matches: List[Dict] = None) -> Dict:
    """
    Analyze card patterns for a team based on recent matches and head-to-head history.
    
    Args:
        team_id: Team ID
        matches: List of recent matches
        h2h_matches: Optional list of head-to-head matches
        
    Returns:
        Dict containing card statistics and predictions
    """
    card_stats = {
        'last_8_matches': {
            'yellow_cards': 0,
            'red_cards': 0,
            'matches_analyzed': 0,
            'yellow_per_game': 0,
            'cards_by_minute': {
                '0-15': 0, '16-30': 0, '31-45': 0,
                '46-60': 0, '61-75': 0, '76-90': 0
            }
        },
        'h2h_cards': {
            'yellow_cards': 0,
            'red_cards': 0,
            'matches_analyzed': 0,
            'yellow_per_game': 0
        },
        'card_trend': 'stable',
        'high_risk_periods': []
    }
    
    # Analyze last 8 matches
    recent_matches = matches[-8:] if len(matches) >= 8 else matches
    card_stats['last_8_matches']['matches_analyzed'] = len(recent_matches)
    
    first_half_yellows = 0
    second_half_yellows = 0
    
    # Since we don't have detailed card data, we'll use estimated values
    estimated_cards_per_match = 2  # Average cards per match
    for match in recent_matches:
        # Estimate cards based on match result and venue
        is_home = match['home_team'] == team_id
        opponent_goals = match['away_goals'] if is_home else match['home_goals']
        team_goals = match['home_goals'] if is_home else match['away_goals']
        
        # More cards likely in losses or high-scoring games
        estimated_yellows = estimated_cards_per_match
        if team_goals < opponent_goals:
            estimated_yellows += 1
        if team_goals + opponent_goals >= 4:
            estimated_yellows += 0.5
            
        card_stats['last_8_matches']['yellow_cards'] += estimated_yellows
        
        # Distribute cards across periods (more likely in second half)
        for period in ['61-75', '76-90']:
            if estimated_yellows > 0:
                card_stats['last_8_matches']['cards_by_minute'][period] += 0.4
                estimated_yellows -= 0.4
        for period in ['31-45', '46-60']:
            if estimated_yellows > 0:
                card_stats['last_8_matches']['cards_by_minute'][period] += 0.3
                estimated_yellows -= 0.3
        for period in ['0-15', '16-30']:
            if estimated_yellows > 0:
                card_stats['last_8_matches']['cards_by_minute'][period] += 0.2
                estimated_yellows -= 0.2
    
    # Calculate averages and trends
    if card_stats['last_8_matches']['matches_analyzed'] > 0:
        card_stats['last_8_matches']['yellow_per_game'] = (
            card_stats['last_8_matches']['yellow_cards'] / 
            card_stats['last_8_matches']['matches_analyzed']
        )
        
        # Identify high-risk periods
        avg_cards_per_period = card_stats['last_8_matches']['yellow_cards'] / 6
        for period, count in card_stats['last_8_matches']['cards_by_minute'].items():
            if count >= avg_cards_per_period * 1.5:
                card_stats['high_risk_periods'].append(period)
    
    # Analyze head-to-head cards if available
    if h2h_matches:
        card_stats['h2h_cards']['matches_analyzed'] = len(h2h_matches)
        
        for match in h2h_matches:
            # Use the same estimation logic for h2h matches
            is_home = match['home_team'] == team_id
            opponent_goals = match['away_goals'] if is_home else match['home_goals']
            team_goals = match['home_goals'] if is_home else match['away_goals']
            
            estimated_yellows = estimated_cards_per_match
            if team_goals < opponent_goals:
                estimated_yellows += 1
            if team_goals + opponent_goals >= 4:
                estimated_yellows += 0.5
                
            card_stats['h2h_cards']['yellow_cards'] += estimated_yellows
        
        if card_stats['h2h_cards']['matches_analyzed'] > 0:
            card_stats['h2h_cards']['yellow_per_game'] = (
                card_stats['h2h_cards']['yellow_cards'] / 
                card_stats['h2h_cards']['matches_analyzed']
            )
    
    # Determine card trend based on recent vs earlier matches
    if card_stats['last_8_matches']['matches_analyzed'] >= 4:
        recent_4_matches = matches[-4:]
        earlier_4_matches = matches[-8:-4]
        
        recent_yellows = sum(2 if m['home_team'] == team_id and m['home_goals'] < m['away_goals'] or
                           m['away_team'] == team_id and m['away_goals'] < m['home_goals']
                           else 1.5 for m in recent_4_matches)
        
        earlier_yellows = sum(2 if m['home_team'] == team_id and m['home_goals'] < m['away_goals'] or
                            m['away_team'] == team_id and m['away_goals'] < m['home_goals']
                            else 1.5 for m in earlier_4_matches)
        
        if recent_yellows > earlier_yellows * 1.3:
            card_stats['card_trend'] = 'increasing'
        elif recent_yellows * 1.3 < earlier_yellows:
            card_stats['card_trend'] = 'decreasing'
    
    return card_stats

def predict_match(home_team_id: int, away_team_id: int, league_id: int) -> Dict:
    """
    Predict the outcome of a match between two teams.
    Optimized version with better error handling and reduced API calls.
    """
    try:
        # Get team statistics with error handling
        home_team_stats = get_team_statistics(home_team_id, league_id)
        if not home_team_stats.get('available', False):
            home_team_stats = create_default_stats()
            
        away_team_stats = get_team_statistics(away_team_id, league_id)
        if not away_team_stats.get('available', False):
            away_team_stats = create_default_stats()
        
        # Calculate team strengths
        home_team_stats['strength'] = calculate_team_strength_index(home_team_stats)
        away_team_stats['strength'] = calculate_team_strength_index(away_team_stats)
        
        # Get h2h stats with timeout protection
        try:
            h2h_stats = get_h2h_statistics(home_team_id, away_team_id)
        except Exception as e:
            print(f"H2H stats unavailable: {str(e)}")
            h2h_stats = {'h2h_factor': 1.0}
        
        # Calculate probabilities using Poisson distribution
        prediction = calculate_poisson_probabilities(home_team_stats, away_team_stats, h2h_stats)
        
        # Add metadata
        prediction['metadata'] = {
            'confidence': min(home_team_stats.get('strength', {}).get('confidence', 'low'),
                            away_team_stats.get('strength', {}).get('confidence', 'low')),
            'home_games_analyzed': home_team_stats.get('fixtures', {}).get('played', 0),
            'away_games_analyzed': away_team_stats.get('fixtures', {}).get('played', 0)
        }
        
        # Add team analysis
        prediction['team_analysis'] = {
            'home': {
                'form': home_team_stats.get('form', 'Unknown'),
                'recent_performance': home_team_stats.get('recent_form', {}),
                'strength_index': home_team_stats.get('strength', {})
            },
            'away': {
                'form': away_team_stats.get('form', 'Unknown'),
                'recent_performance': away_team_stats.get('recent_form', {}),
                'strength_index': away_team_stats.get('strength', {})
            }
        }
        
        # Calculate cards prediction
        try:
            home_cards = analyze_cards(home_team_id, 
                                     home_team_stats.get('matches', []),
                                     h2h_stats.get('matches', []))
            away_cards = analyze_cards(away_team_id,
                                     away_team_stats.get('matches', []),
                                     h2h_stats.get('matches', []))
            
            base_cards = 3.5
            intensity_factor = 1.0
            
            # Adjust for expected game intensity
            if abs(prediction['expected_goals']['home'] - prediction['expected_goals']['away']) < 0.5:
                intensity_factor = 1.2
            elif abs(prediction['expected_goals']['home'] - prediction['expected_goals']['away']) > 1.0:
                intensity_factor = 0.9
            
            expected_cards = base_cards * intensity_factor
            
            prediction['cards'] = {
                'total': float(expected_cards),
                'home': float(expected_cards * 0.45),
                'away': float(expected_cards * 0.55),
                'over_2.5': float(1 - poisson.cdf(2, expected_cards)),
                'over_3.5': float(1 - poisson.cdf(3, expected_cards)),
                'over_4.5': float(1 - poisson.cdf(4, expected_cards))
            }
        except Exception as e:
            print(f"Cards prediction unavailable: {str(e)}")
            prediction['cards'] = create_default_cards()
        
        return prediction
        
    except Exception as e:
        print(f"Error in prediction: {str(e)}")
        return create_fallback_prediction()

def create_default_stats():
    """Create default stats when API data is unavailable."""
    return {
        'available': False,
        'fixtures': {
            'played': 0,
            'wins': 0,
            'draws': 0,
            'losses': 0
        },
        'goals': {
            'for': {'total': 0, 'average': 1.5},
            'against': {'total': 0, 'average': 1.5}
        },
        'form': 'UNKNOWN'
    }

def create_default_cards():
    """Create default card predictions."""
    return {
        'total': 3.5,
        'home': 1.6,
        'away': 1.9,
        'over_2.5': 0.70,
        'over_3.5': 0.45,
        'over_4.5': 0.25
    }

def create_fallback_prediction():
    """Create fallback prediction when errors occur."""
    return {
        'probabilities': {
            'home_win': 0.40,
            'draw': 0.25,
            'away_win': 0.35
        },
        'expected_goals': {
            'home': 1.5,
            'away': 1.3
        },
        'cards': create_default_cards(),
        'metadata': {
            'confidence': 'low',
            'error': 'Fallback prediction used'
        }
    }

def calculate_exact_score_probabilities(home_expected: float, away_expected: float) -> Dict[str, float]:
    """Calculate probabilities for exact scorelines."""
    max_goals = 4
    probabilities = {}
    
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            prob = poisson.pmf(i, home_expected) * poisson.pmf(j, away_expected)
            probabilities[f"{i}-{j}"] = prob
    
    return dict(sorted(probabilities.items(), key=lambda x: x[1], reverse=True)[:5])

def calculate_under_probability(expected_goals: float, threshold: float) -> float:
    """Calculate probability of total goals being under a threshold."""
    prob = 0
    for i in range(int(threshold)):
        prob += poisson.pmf(i, expected_goals)
    return prob

def calculate_over_probability(expected_goals: float, threshold: float) -> float:
    """Calculate probability of total goals being over a threshold."""
    return 1 - calculate_under_probability(expected_goals, threshold + 0.1)

def calculate_btts_probability(home_expected: float, away_expected: float) -> float:
    """Calculate both teams to score probability."""
    no_home_goals = poisson.pmf(0, home_expected)
    no_away_goals = poisson.pmf(0, away_expected)
    return (1 - no_home_goals) * (1 - no_away_goals)

def calculate_volatility(home_team_stats: Dict, away_team_stats: Dict) -> float:
    """
    Calculate prediction volatility based on team statistics.
    """
    # Get strength variability with safe defaults
    home_variability = home_team_stats.get('strength', {}).get('metrics', {}).get('variability', 0.5)
    away_variability = away_team_stats.get('strength', {}).get('metrics', {}).get('variability', 0.5)
    
    # Get form consistency with safe defaults
    home_consistency = home_team_stats.get('recent_form', {}).get('form_rating', 50) / 100
    away_consistency = away_team_stats.get('recent_form', {}).get('form_rating', 50) / 100
    
    # Calculate volatility (0-1 scale)
    volatility = (
        (home_variability + away_variability) * 0.4 +  # Strength variability (40% weight)
        (2 - home_consistency - away_consistency) * 0.6  # Form inconsistency (60% weight)
    ) / 2
    
    return max(0.1, min(1.0, volatility))  # Ensure result is between 0.1 and 1.0

def identify_value_bets(prediction: Dict) -> List[Dict]:
    """
    Identify potential value bets based on prediction.
    """
    value_bets = []
    
    # Get probabilities and expected goals
    home_win_prob = prediction['probabilities']['home_win']
    away_win_prob = prediction['probabilities']['away_win']
    draw_prob = prediction['probabilities']['draw']
    home_xg = prediction['expected_goals']['home']
    away_xg = prediction['expected_goals']['away']
    total_xg = prediction['expected_goals']['total']
    
    # Check for strong home win probability
    if home_win_prob > 0.6:
        value_bets.append({
            'type': 'Home Win',
            'confidence': 'high' if home_win_prob > 0.7 else 'medium',
            'reason': 'Strong home team advantage and form'
        })
    
    # Check for strong away win probability
    if away_win_prob > 0.45:
        value_bets.append({
            'type': 'Away Win',
            'confidence': 'high' if away_win_prob > 0.55 else 'medium',
            'reason': 'Superior away team strength despite venue disadvantage'
        })
    
    # Check for draw probability
    if abs(home_win_prob - away_win_prob) < 0.1 and draw_prob > 0.25:
        value_bets.append({
            'type': 'Draw',
            'confidence': 'medium',
            'reason': 'Evenly matched teams with balanced strengths'
        })
    
    # Check for goals-based bets
    if total_xg > 3.0:
        value_bets.append({
            'type': 'Over 2.5 Goals',
            'confidence': 'high' if total_xg > 3.5 else 'medium',
            'reason': 'High expected goals'
        })
    elif total_xg < 2.0:
        value_bets.append({
            'type': 'Under 2.5 Goals',
            'confidence': 'high' if total_xg < 1.5 else 'medium',
            'reason': 'Low expected goals'
        })
    
    return value_bets

def calculate_alternative_predictions(home_xg: float, away_xg: float, 
                                   home_team_stats: Dict, away_team_stats: Dict) -> Dict:
    """
    Calculate alternative predictions like exact scores and BTTS.
    """
    return {
        'exact_score_probabilities': calculate_exact_score_probabilities(home_xg, away_xg),
        'total_goals_probabilities': {
            'under_1.5': calculate_under_probability(home_xg + away_xg, 1.5),
            'under_2.5': calculate_under_probability(home_xg + away_xg, 2.5),
            'under_3.5': calculate_under_probability(home_xg + away_xg, 3.5),
            'over_1.5': calculate_over_probability(home_xg + away_xg, 1.5),
            'over_2.5': calculate_over_probability(home_xg + away_xg, 2.5),
            'over_3.5': calculate_over_probability(home_xg + away_xg, 3.5)
        },
        'both_teams_to_score': calculate_btts_probability(home_xg, away_xg),
        'cards': analyze_cards(home_team_stats, away_team_stats)
    }

def get_league_context(league_id: int) -> Dict:
    """
    Get league context including averages and trends.
    """
    return {
        'averages': {
            'avg_goals_per_game': 2.5,  # Default values
            'avg_home_goals': 1.4,
            'avg_away_goals': 1.1
        }
    }

# Helper functions for data processing
def get_historical_matches(team_id: int, league: str, seasons: List[int] = None) -> Dict[str, List[Dict]]:
    """
    Fetch historical matches for a team across multiple seasons, including data from other leagues.
    
    Args:
        team_id: Team ID
        league: Current league name/ID
        seasons: List of seasons to fetch (e.g., [2023, 2022]). If None, fetches last 2 seasons.
        
    Returns:
        Dict containing:
        - 'current_league': List of matches in current league
        - 'other_leagues': List of matches in other leagues
        - 'metadata': Information about data quality and context
    """
    if seasons is None:
        current_year = datetime.now().year
        seasons = [current_year, current_year - 1]
    
    matches = {
        'current_league': [],
        'other_leagues': [],
        'metadata': {
            'seasons_analyzed': seasons,
            'total_matches': 0,
            'leagues_played': set(),
            'data_quality': 'high',  # Will be adjusted based on data availability
            'api_errors': []
        }
    }
    
    def safe_process_match(match: Dict) -> Optional[Dict]:
        """Safely process a match dictionary, returning None if required fields are missing."""
        try:
            if not all(key in match for key in ['fixture', 'teams', 'goals', 'league']):
                return None
                
            return {
                'date': match['fixture'].get('date', '2024-01-01T00:00:00+00:00'),  # Default date if missing
                'home_team': match['teams'].get('home', {}).get('id'),
                'away_team': match['teams'].get('away', {}).get('id'),
                'home_goals': match['goals'].get('home', 0),
                'away_goals': match['goals'].get('away', 0),
                'league': match['league'].get('id'),
                'season': match['league'].get('season'),
                'venue': match['fixture'].get('venue', {}).get('name'),
                'result': 'H' if match['goals'].get('home', 0) > match['goals'].get('away', 0)
                         else 'D' if match['goals'].get('home', 0) == match['goals'].get('away', 0)
                         else 'A'
            }
        except Exception as e:
            matches['metadata']['api_errors'].append(f"Error processing match: {str(e)}")
            return None
    
    for season in seasons:
        # First try to get matches from current league
        try:
            current_league_data = api_football_request('fixtures', {
                'team': team_id,
                'league': league,
                'season': season,
                'status': 'FT'  # Only completed matches
            })
            
            if current_league_data and 'response' in current_league_data:
                processed_matches = []
                for match in current_league_data['response']:
                    processed_match = safe_process_match(match)
                    if processed_match:
                        processed_matches.append(processed_match)
                
                matches['current_league'].extend(processed_matches)
                matches['metadata']['leagues_played'].add(league)
            else:
                matches['metadata']['api_errors'].append(f"No response data for season {season}")
                
        except Exception as e:
            matches['metadata']['api_errors'].append(f"API error for season {season}: {str(e)}")
        
        # Get all matches for the team in this season (to catch games in other leagues)
        try:
            all_season_data = api_football_request('fixtures', {
                'team': team_id,
                'season': season,
                'status': 'FT'
            })
            
            if all_season_data and 'response' in all_season_data:
                for match in all_season_data['response']:
                    if match.get('league', {}).get('id') != league:
                        processed_match = safe_process_match(match)
                        if processed_match:
                            matches['other_leagues'].append(processed_match)
                            matches['metadata']['leagues_played'].add(processed_match['league'])
                            
        except Exception as e:
            matches['metadata']['api_errors'].append(f"API error for all matches in season {season}: {str(e)}")
    
    # Update metadata
    matches['metadata']['total_matches'] = len(matches['current_league']) + len(matches['other_leagues'])
    matches['metadata']['leagues_played'] = list(matches['metadata']['leagues_played'])
    
    # Sort matches by date
    try:
        for category in ['current_league', 'other_leagues']:
            matches[category] = sorted(
                matches[category],
                key=lambda x: datetime.strptime(x['date'], '%Y-%m-%dT%H:%M:%S%z')
            )
    except Exception as e:
        matches['metadata']['api_errors'].append(f"Error sorting matches: {str(e)}")
        # If date sorting fails, maintain original order
    
    # Assess data quality
    if len(matches['current_league']) < 5:
        matches['metadata']['data_quality'] = 'low'
        matches['metadata']['quality_note'] = 'Very limited data in current league'
    elif len(matches['current_league']) < 10:
        matches['metadata']['data_quality'] = 'low'
        matches['metadata']['quality_note'] = 'Limited data in current league'
    elif len(matches['current_league']) < 20:
        matches['metadata']['data_quality'] = 'medium'
        matches['metadata']['quality_note'] = 'Moderate data in current league'
    
    if matches['metadata']['api_errors']:
        matches['metadata']['quality_note'] = (matches['metadata'].get('quality_note', '') + 
                                             '; Some data retrieval errors occurred')
    
    return matches

def get_team_statistics(team_id: int, league: str) -> Dict:
    """
    Fetch current season statistics for a team with caching.
    """
    # Try to get from cache first
    cache_params = {
        'team_id': team_id,
        'league': league
    }
    cached_data = cache.get('team_stats', cache_params, max_age_hours=24)
    if cached_data:
        return cached_data
    
    current_year = datetime.now().year
    season = current_year if datetime.now().month > 6 else current_year - 1
    
    # Fetch team statistics
    team_stats_data = api_football_request('teams/statistics', {
        'team': team_id,
        'league': league,
        'season': season
    })
    
    if not team_stats_data or 'response' not in team_stats_data:
        return {
            'available': False,
            'error': 'No statistics available',
            'season': season
        }
    
    stats = team_stats_data['response']
    
    # Process and organize statistics
    processed_stats = {
        'available': True,
        'season': season,
        'fixtures': {
            'played': stats.get('fixtures', {}).get('played', {}).get('total', 0),
            'wins': stats.get('fixtures', {}).get('wins', {}).get('total', 0),
            'draws': stats.get('fixtures', {}).get('draws', {}).get('total', 0),
            'losses': stats.get('fixtures', {}).get('loses', {}).get('total', 0)
        },
        'goals': {
            'for': {
                'total': stats.get('goals', {}).get('for', {}).get('total', {}).get('total', 0),
                'average': stats.get('goals', {}).get('for', {}).get('average', {}).get('total', 0),
                'minute_distribution': stats.get('goals', {}).get('for', {}).get('minute', {})
            },
            'against': {
                'total': stats.get('goals', {}).get('against', {}).get('total', {}).get('total', 0),
                'average': stats.get('goals', {}).get('against', {}).get('average', {}).get('total', 0),
                'minute_distribution': stats.get('goals', {}).get('against', {}).get('minute', {})
            }
        },
        'home': {
            'played': stats.get('fixtures', {}).get('played', {}).get('home', 0),
            'wins': stats.get('fixtures', {}).get('wins', {}).get('home', 0),
            'draws': stats.get('fixtures', {}).get('draws', {}).get('home', 0),
            'losses': stats.get('fixtures', {}).get('loses', {}).get('home', 0),
            'goals_for': stats.get('goals', {}).get('for', {}).get('total', {}).get('home', 0),
            'goals_against': stats.get('goals', {}).get('against', {}).get('total', {}).get('home', 0)
        },
        'away': {
            'played': stats.get('fixtures', {}).get('played', {}).get('away', 0),
            'wins': stats.get('fixtures', {}).get('wins', {}).get('away', 0),
            'draws': stats.get('fixtures', {}).get('draws', {}).get('away', 0),
            'losses': stats.get('fixtures', {}).get('loses', {}).get('away', 0),
            'goals_for': stats.get('goals', {}).get('for', {}).get('total', {}).get('away', 0),
            'goals_against': stats.get('goals', {}).get('against', {}).get('total', {}).get('away', 0)
        },
        'clean_sheets': {
            'total': stats.get('clean_sheets', {}).get('total', 0),
            'home': stats.get('clean_sheets', {}).get('home', 0),
            'away': stats.get('clean_sheets', {}).get('away', 0)
        },
        'failed_to_score': {
            'total': stats.get('failed_to_score', {}).get('total', 0),
            'home': stats.get('failed_to_score', {}).get('home', 0),
            'away': stats.get('failed_to_score', {}).get('away', 0)
        },
        'penalty': {
            'scored': stats.get('penalty', {}).get('scored', {}).get('total', 0),
            'missed': stats.get('penalty', {}).get('missed', {}).get('total', 0)
        },
        'cards': {
            'yellow': stats.get('cards', {}).get('yellow', {}),
            'red': stats.get('cards', {}).get('red', {})
        },
        'form': stats.get('form', ''),
        'biggest': {
            'streak': {
                'wins': stats.get('biggest', {}).get('streak', {}).get('wins', 0),
                'draws': stats.get('biggest', {}).get('streak', {}).get('draws', 0),
                'losses': stats.get('biggest', {}).get('streak', {}).get('loses', 0)
            },
            'wins': {
                'home': stats.get('biggest', {}).get('wins', {}).get('home', ''),
                'away': stats.get('biggest', {}).get('wins', {}).get('away', '')
            },
            'losses': {
                'home': stats.get('biggest', {}).get('loses', {}).get('home', ''),
                'away': stats.get('biggest', {}).get('loses', {}).get('away', '')
            },
            'goals': {
                'for': stats.get('biggest', {}).get('goals', {}).get('for', {}).get('total', 0),
                'against': stats.get('biggest', {}).get('goals', {}).get('against', {}).get('total', 0)
            }
        }
    }
    
    # Calculate additional metrics
    if processed_stats['fixtures']['played'] > 0:
        processed_stats['metrics'] = {
            'points_per_game': (processed_stats['fixtures']['wins'] * 3 + 
                              processed_stats['fixtures']['draws']) / 
                              processed_stats['fixtures']['played'],
            'goals_per_game': processed_stats['goals']['for']['total'] / 
                             processed_stats['fixtures']['played'],
            'goals_against_per_game': processed_stats['goals']['against']['total'] / 
                                    processed_stats['fixtures']['played'],
            'clean_sheet_percentage': (processed_stats['clean_sheets']['total'] / 
                                     processed_stats['fixtures']['played']) * 100,
            'scoring_rate': (1 - (processed_stats['failed_to_score']['total'] / 
                                processed_stats['fixtures']['played'])) * 100
        }
    
    # Cache the processed stats
    cache.set('team_stats', cache_params, processed_stats)
    
    return processed_stats

def get_head_to_head(team1_id: int, team2_id: int, num_matches: int = 5) -> List[Dict]:
    """
    Fetch head-to-head matches between two teams.
    
    Args:
        team1_id: First team ID
        team2_id: Second team ID
        num_matches: Number of previous meetings to fetch
        
    Returns:
        List of previous meetings data
    """
    # Fetch head-to-head fixtures
    h2h_data = api_football_request('fixtures/headtohead', {
        'h2h': f"{team1_id}-{team2_id}",
        'last': str(num_matches),
        'status': 'FT'  # Only completed matches
    })
    
    if not h2h_data or 'response' not in h2h_data:
        return []
    
    # Process and extract relevant match data
    matches = []
    for fixture in h2h_data['response']:
        # Initialize default statistics
        stats = {
            'shots_on_goal': {'home': 0, 'away': 0},
            'possession': {'home': '50%', 'away': '50%'}
        }
        
        # Extract statistics if available
        if 'statistics' in fixture:
            for team_stats in fixture['statistics']:
                side = 'home' if team_stats.get('team', {}).get('id') == fixture['teams']['home']['id'] else 'away'
                for stat in team_stats.get('statistics', []):
                    if stat['type'] == 'Shots on Goal':
                        stats['shots_on_goal'][side] = stat['value'] or 0
                    elif stat['type'] == 'Ball Possession':
                        stats['possession'][side] = stat['value'] or '50%'
        
        match_data = {
            'date': fixture['fixture']['date'],
            'home_team': fixture['teams']['home']['id'],
            'away_team': fixture['teams']['away']['id'],
            'home_goals': fixture['goals']['home'],
            'away_goals': fixture['goals']['away'],
            'league': fixture['league']['id'],
            'season': fixture['league']['season'],
            'venue': fixture['fixture']['venue']['name'] if fixture['fixture'].get('venue') else None,
            'result': 'H' if fixture['goals']['home'] > fixture['goals']['away']
                     else 'D' if fixture['goals']['home'] == fixture['goals']['away']
                     else 'A',
            'stats': stats
        }
        matches.append(match_data)
    
    return sorted(matches, key=lambda x: datetime.strptime(x['date'], '%Y-%m-%dT%H:%M:%S%z'), reverse=True)

def calculate_league_averages(matches: List[Dict]) -> Dict[str, float]:
    """
    Calculate league-wide averages for various metrics.
    
    Args:
        matches: List of matches in the league
        
    Returns:
        Dict containing average goals scored, conceded, etc.
    """
    if not matches:
        return {
            'avg_goals_per_game': 2.5,  # Fallback to typical average
            'avg_home_goals': 1.4,
            'avg_away_goals': 1.1
        }
    
    total_games = len(matches)
    total_goals = sum(match['home_goals'] + match['away_goals'] for match in matches)
    total_home_goals = sum(match['home_goals'] for match in matches)
    total_away_goals = sum(match['away_goals'] for match in matches)
    
    return {
        'avg_goals_per_game': total_goals / total_games,
        'avg_home_goals': total_home_goals / total_games,
        'avg_away_goals': total_away_goals / total_games
    }

def get_h2h_statistics(home_team_id: int, away_team_id: int) -> Dict:
    """
    Get head-to-head statistics between two teams with caching.
    """
    # Try to get from cache first
    cache_params = {
        'home_team_id': home_team_id,
        'away_team_id': away_team_id
    }
    cached_data = cache.get('h2h_stats', cache_params, max_age_hours=24)
    if cached_data:
        return cached_data
    
    # Get head-to-head matches
    h2h_matches = get_head_to_head(home_team_id, away_team_id)
    
    # Calculate basic stats
    team1_wins = sum(1 for match in h2h_matches 
                    if (match['home_team'] == home_team_id and match['home_goals'] > match['away_goals']) or
                       (match['away_team'] == home_team_id and match['away_goals'] > match['home_goals']))
    team2_wins = sum(1 for match in h2h_matches 
                    if (match['home_team'] == away_team_id and match['home_goals'] > match['away_goals']) or
                       (match['away_team'] == away_team_id and match['away_goals'] > match['home_goals']))
    draws = sum(1 for match in h2h_matches if match['home_goals'] == match['away_goals'])
    total_matches = len(h2h_matches)
    
    # Calculate average goals
    team1_goals = sum(match['home_goals'] if match['home_team'] == home_team_id 
                     else match['away_goals'] for match in h2h_matches)
    team2_goals = sum(match['home_goals'] if match['home_team'] == away_team_id 
                     else match['away_goals'] for match in h2h_matches)
    
    avg_team1_goals = team1_goals / total_matches if total_matches > 0 else 0
    avg_team2_goals = team2_goals / total_matches if total_matches > 0 else 0
    
    # Calculate weighted dominance
    recent_matches = h2h_matches[:min(5, total_matches)]
    recent_dominance = sum(1 for match in recent_matches 
                         if (match['home_team'] == home_team_id and match['home_goals'] > match['away_goals']) or
                            (match['away_team'] == home_team_id and match['away_goals'] > match['home_goals'])) / len(recent_matches) if recent_matches else 0.5
    overall_dominance = team1_wins / total_matches if total_matches > 0 else 0.5
    weighted_dominance = (recent_dominance * 0.6) + (overall_dominance * 0.4)
    
    # Calculate venue advantage
    home_matches = [match for match in h2h_matches if match['home_team'] == home_team_id]
    home_wins = sum(1 for match in home_matches if match['home_goals'] > match['away_goals'])
    venue_advantage = (home_wins / len(home_matches)) * 2 if home_matches else 1.0
    
    # Calculate result consistency
    if total_matches >= 3:
        results = [(match['home_team'] == home_team_id and match['home_goals'] > match['away_goals']) or
                  (match['away_team'] == home_team_id and match['away_goals'] > match['home_goals'])
                  for match in h2h_matches[-3:]]
        consistency = sum(1 for i in range(len(results)-1) if results[i] == results[i+1]) / (len(results)-1)
    else:
        consistency = 0.5
    
    # Calculate h2h factor
    h2h_factor = (weighted_dominance * 0.4 + venue_advantage * 0.4 + consistency * 0.2) * 1.5
    
    h2h_stats = {
        'h2h_factor': h2h_factor,
        'stats': {
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'draws': draws,
            'total_matches': total_matches,
            'avg_team1_goals': avg_team1_goals,
            'avg_team2_goals': avg_team2_goals
        },
        'analysis': {
            'weighted_dominance': weighted_dominance,
            'recent_dominance': recent_dominance,
            'overall_dominance': overall_dominance,
            'result_consistency': consistency,
            'venue_advantage': venue_advantage
        },
        'trends': {
            'goal_differences': [
                match['home_goals'] - match['away_goals'] 
                if match['home_team'] == home_team_id
                else match['away_goals'] - match['home_goals']
                for match in h2h_matches[-5:]
            ],
            'match_dominance': [
                1 if (match['home_team'] == home_team_id and match['home_goals'] > match['away_goals']) or
                     (match['away_team'] == home_team_id and match['away_goals'] > match['home_goals'])
                else 0 if match['home_goals'] != match['away_goals']
                else 0.5
                for match in h2h_matches[-5:]
            ],
            'recent_matches': [
                {
                    'date': match['date'],
                    'team1_goals': match['home_goals'] if match['home_team'] == home_team_id else match['away_goals'],
                    'team2_goals': match['away_goals'] if match['home_team'] == home_team_id else match['home_goals'],
                    'venue': 'home' if match['home_team'] == home_team_id else 'away',
                    'goal_difference': match['home_goals'] - match['away_goals'] 
                        if match['home_team'] == home_team_id
                        else match['away_goals'] - match['home_goals'],
                    'dominance': 1 if (match['home_team'] == home_team_id and match['home_goals'] > match['away_goals']) or
                                    (match['away_team'] == home_team_id and match['away_goals'] > match['home_goals'])
                                else 0 if match['home_goals'] != match['away_goals']
                                else 0.5
                }
                for match in h2h_matches[-5:]
            ]
        },
        'confidence': 'high' if total_matches >= 5 else 'medium' if total_matches >= 3 else 'low',
        'matches_analyzed': total_matches
    } 
    
    # Cache the h2h stats
    cache.set('h2h_stats', cache_params, h2h_stats)
    
    return h2h_stats

def simple_predict_match(home_team_id: int, away_team_id: int, league_id: int) -> Dict:
    """
    A simplified and more robust version of match prediction.
    Focuses on core prediction logic with minimal external dependencies.
    
    Args:
        home_team_id: ID of home team
        away_team_id: ID of away team
        league_id: ID of the league
        
    Returns:
        Dict containing match prediction probabilities and expected goals
    """
    try:
        # Get basic team statistics with error handling
        home_stats = get_team_statistics(home_team_id, league_id)
        away_stats = get_team_statistics(away_team_id, league_id)
        
        # Default values if stats are not available
        default_stats = {
            'metrics': {
                'goals_per_game': 1.5,
                'goals_against_per_game': 1.5
            },
            'fixtures': {
                'played': 0,
                'wins': 0,
                'draws': 0,
                'losses': 0
            }
        }
        
        # Use stats if available, otherwise use defaults
        home_stats = home_stats if home_stats.get('available', False) else default_stats
        away_stats = away_stats if away_stats.get('available', False) else default_stats
        
        # Calculate basic attacking and defensive strengths
        home_attack = home_stats['metrics'].get('goals_per_game', 1.5)
        home_defense = 2 - home_stats['metrics'].get('goals_against_per_game', 1.5)
        away_attack = away_stats['metrics'].get('goals_per_game', 1.5)
        away_defense = 2 - away_stats['metrics'].get('goals_against_per_game', 1.5)
        
        # Apply home advantage
        home_advantage = 1.2
        
        # Calculate expected goals
        home_xg = home_attack * away_defense * home_advantage
        away_xg = away_attack * home_defense
        
        # Ensure expected goals are within reasonable bounds
        home_xg = max(0.3, min(4.0, home_xg))
        away_xg = max(0.3, min(4.0, away_xg))
        
        # Calculate probabilities using Poisson distribution
        max_goals = 5
        score_probs = np.zeros((max_goals + 1, max_goals + 1))
        
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                score_probs[i, j] = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
        
        # Calculate outcome probabilities
        home_win_prob = np.sum(np.tril(score_probs, -1))
        away_win_prob = np.sum(np.triu(score_probs, 1))
        draw_prob = np.sum(np.diag(score_probs))
        
        # Normalize probabilities
        total_prob = home_win_prob + away_win_prob + draw_prob
        home_win_prob /= total_prob
        away_win_prob /= total_prob
        draw_prob /= total_prob
        
        # Calculate confidence based on available data
        home_games = home_stats['fixtures'].get('played', 0)
        away_games = away_stats['fixtures'].get('played', 0)
        confidence = 'high' if min(home_games, away_games) >= 10 else \
                    'medium' if min(home_games, away_games) >= 5 else 'low'
        
        return {
            'probabilities': {
                'home_win': float(home_win_prob),
                'draw': float(draw_prob),
                'away_win': float(away_win_prob)
            },
            'expected_goals': {
                'home': float(home_xg),
                'away': float(away_xg)
            },
            'metadata': {
                'confidence': confidence,
                'home_games_analyzed': home_games,
                'away_games_analyzed': away_games
            }
        }
        
    except Exception as e:
        # Return a balanced prediction if something goes wrong
        return {
            'probabilities': {
                'home_win': 0.4,
                'draw': 0.25,
                'away_win': 0.35
            },
            'expected_goals': {
                'home': 1.3,
                'away': 1.1
            },
            'metadata': {
                'confidence': 'low',
                'error': str(e)
            }
        }

def test_predict_match(home_team_id: int, away_team_id: int, league_id: int) -> Dict:
    """
    A test prediction function that uses only basic calculations.
    No API calls or external data required.
    """
    # Basic prediction with default values
    home_xg = 1.5
    away_xg = 1.2
    
    # Simple Poisson calculation
    max_goals = 5
    score_probs = np.zeros((max_goals + 1, max_goals + 1))
    
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            score_probs[i, j] = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
    
    # Calculate outcome probabilities
    home_win_prob = float(np.sum(np.tril(score_probs, -1)))
    away_win_prob = float(np.sum(np.triu(score_probs, 1)))
    draw_prob = float(np.sum(np.diag(score_probs)))
    
    # Normalize probabilities
    total_prob = home_win_prob + away_win_prob + draw_prob
    home_win_prob /= total_prob
    away_win_prob /= total_prob
    draw_prob /= total_prob
    
    # Calculate expected cards
    base_cards = 3.5  # Average cards per game
    intensity_factor = 1.0
    
    # Adjust for expected game intensity
    if abs(home_xg - away_xg) < 0.5:  # Close game
        intensity_factor = 1.2
    elif abs(home_xg - away_xg) > 1.0:  # One-sided game
        intensity_factor = 0.9
        
    # Adjust for expected goals
    if home_xg + away_xg > 3.0:  # High-scoring game
        intensity_factor *= 1.1
        
    expected_cards = base_cards * intensity_factor
    
    # Split cards between teams (home teams typically get slightly fewer cards)
    home_cards = expected_cards * 0.45
    away_cards = expected_cards * 0.55
    
    return {
        'probabilities': {
            'home_win': home_win_prob,
            'draw': draw_prob,
            'away_win': away_win_prob
        },
        'expected_goals': {
            'home': home_xg,
            'away': away_xg
        },
        'expected_cards': {
            'total': float(expected_cards),
            'home': float(home_cards),
            'away': float(away_cards),
            'over_2.5_cards': float(1 - poisson.cdf(2, expected_cards)),
            'over_3.5_cards': float(1 - poisson.cdf(3, expected_cards)),
            'over_4.5_cards': float(1 - poisson.cdf(4, expected_cards))
        }
    }

def calculate_over_probability(expected: float, threshold: float) -> float:
    """Calculate the probability of over X goals/cards."""
    return float(1 - poisson.cdf(threshold, expected))

def calculate_under_probability(expected: float, threshold: float) -> float:
    """Calculate the probability of under X goals/cards."""
    return float(poisson.cdf(threshold, expected))

def predict_batch_matches(fixtures: List[Dict], max_workers: int = 3) -> List[Dict]:
    """
    Predict multiple matches in parallel with rate limiting.
    
    Args:
        fixtures: List of dictionaries containing fixture information
                 Each dict should have: home_team_id, away_team_id, league_id
        max_workers: Maximum number of parallel predictions
        
    Returns:
        List of prediction results
    """
    results = []
    rate_limit_delay = 0.5  # 500ms between API calls
    
    def predict_single_match(fixture):
        try:
            # Add rate limiting
            time.sleep(rate_limit_delay)
            
            # Use simple prediction for better performance
            result = simple_predict_match(
                fixture['home_team_id'],
                fixture['away_team_id'],
                fixture['league_id']
            )
            
            # Add fixture information to result
            result['fixture'] = {
                'home_team_id': fixture['home_team_id'],
                'away_team_id': fixture['away_team_id'],
                'league_id': fixture['league_id']
            }
            
            return result
            
        except Exception as e:
            print(f"Error predicting match: {str(e)}")
            return create_fallback_prediction()
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(predict_single_match, fixtures))
    
    return results

# Initialize the prediction cache
_prediction_cache = {}
_cache_ttl = 60  # Cache for 1 minute

def get_cached_prediction(home_team_id, away_team_id, league_id):
    """
    Get a cached prediction for a match, or calculate a new one if not cached.
    Disables caching on Heroku environments.
    """
    import os
    
    # Detect if running on Heroku (DYNO environment variable is set)
    is_heroku = os.environ.get('DYNO') is not None
    
    try:
        # Ensure proper types for all IDs
        home_id = int(home_team_id)
        away_id = int(away_team_id)
        league = int(league_id)
        
        if not all([home_id, away_id, league]):
            print(f"Invalid team or league ID: {home_id}, {away_id}, {league}")
            return create_fallback_prediction()
        
        # On Heroku, don't try to use cache
        if is_heroku:
            # Add a unique key to the prediction to avoid all being the same
            result = predict_match(home_id, away_id, league)
            
            # Validate result
            if not result or not isinstance(result, dict):
                print(f"Invalid prediction result type: {type(result)}")
                return create_fallback_prediction()
                
            return result
        
        # For local development, use cache
        # Create a unique cache key
        cache_key = f"{home_id}_{away_id}_{league}"
        
        # Get from cache
        cached_result = cache.cache_get(cache_key)
        if cached_result:
            return cached_result
        
        # Call prediction function with proper types
        result = predict_match(home_id, away_id, league)
        
        # Validate result
        if not result or not isinstance(result, dict):
            print(f"Invalid prediction result type: {type(result)}")
            return create_fallback_prediction()
        
        # Store in cache
        cache.cache_set(cache_key, result)
        
        return result
    except Exception as e:
        print(f"Prediction error in cache function: {str(e)}")
        return create_fallback_prediction()