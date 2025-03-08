from lib.predictions import predict_match

def main():
    # Predict Brentford (55) vs Aston Villa (66)
    result = predict_match(55, 66, 39)
    
    print("Match Prediction:")
    print(f"Home Win: {result['probabilities']['home_win']*100:.2f}%")
    print(f"Draw: {result['probabilities']['draw']*100:.2f}%")
    print(f"Away Win: {result['probabilities']['away_win']*100:.2f}%")
    
    print("\nExpected Goals:")
    print(f"Home: {result['expected_goals']['home']:.2f}")
    print(f"Away: {result['expected_goals']['away']:.2f}")
    
    print("\nExpected Cards:")
    print(f"Total: {result['cards']['total']:.1f}")
    print(f"Over 2.5: {result['cards']['over_2.5']*100:.1f}%")
    print(f"Over 3.5: {result['cards']['over_3.5']*100:.1f}%")
    print(f"Over 4.5: {result['cards']['over_4.5']*100:.1f}%")

if __name__ == "__main__":
    main() 