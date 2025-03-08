from lib.predictions import predict_match

def main():
    # Predict Crystal Palace (50) vs Ipswich (51)
    result = predict_match(50, 51, 39)
    
    print("\nMatch Prediction:")
    print(f"Home Win: {result['probabilities']['home_win']*100:.1f}%")
    print(f"Draw: {result['probabilities']['draw']*100:.1f}%")
    print(f"Away Win: {result['probabilities']['away_win']*100:.1f}%")
    
    print("\nExpected Goals:")
    print(f"Home: {result['expected_goals']['home']:.2f}")
    print(f"Away: {result['expected_goals']['away']:.2f}")
    
    print("\nExpected Cards:")
    print(f"Total: {result['cards']['total']:.1f}")
    print(f"Over 2.5: {result['cards']['over_2.5']*100:.1f}%")
    print(f"Over 3.5: {result['cards']['over_3.5']*100:.1f}%")
    print(f"Over 4.5: {result['cards']['over_4.5']*100:.1f}%")
    
    if 'metadata' in result:
        print("\nPrediction Confidence:", result['metadata']['confidence'])

if __name__ == "__main__":
    main() 