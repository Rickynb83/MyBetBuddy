from lib.predictions import predict_batch_matches

def main():
    # List of fixtures to predict
    fixtures = [
        {
            'home_team_id': 50,  # Crystal Palace
            'away_team_id': 51,  # Ipswich
            'league_id': 39
        },
        {
            'home_team_id': 55,  # Brentford
            'away_team_id': 66,  # Aston Villa
            'league_id': 39
        }
    ]
    
    # Get predictions for all fixtures
    results = predict_batch_matches(fixtures)
    
    # Print results
    for result in results:
        fixture = result['fixture']
        print(f"\nMatch: {fixture['home_team_id']} vs {fixture['away_team_id']}")
        print("Probabilities:")
        print(f"Home Win: {result['probabilities']['home_win']*100:.1f}%")
        print(f"Draw: {result['probabilities']['draw']*100:.1f}%")
        print(f"Away Win: {result['probabilities']['away_win']*100:.1f}%")
        
        print("\nExpected Goals:")
        print(f"Home: {result['expected_goals']['home']:.2f}")
        print(f"Away: {result['expected_goals']['away']:.2f}")
        
        if 'cards' in result:
            print("\nExpected Cards:")
            print(f"Total: {result['cards']['total']:.1f}")
            print(f"Over 2.5: {result['cards']['over_2.5']*100:.1f}%")
            print(f"Over 3.5: {result['cards']['over_3.5']*100:.1f}%")
            print(f"Over 4.5: {result['cards']['over_4.5']*100:.1f}%")
        
        print("\nConfidence:", result['metadata']['confidence'])
        print("-" * 50)

if __name__ == "__main__":
    main() 