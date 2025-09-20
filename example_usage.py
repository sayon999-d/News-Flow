"""
Example usage of API keys with the installed packages
"""
import requests
import google.generativeai as genai
from config import NEWSAPI_KEY, GOOGLE_API_KEY

def test_newsapi():
    """Test NewsAPI functionality"""
    print("Testing NewsAPI...")
    
    # Example: Get top headlines
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": NEWSAPI_KEY,
        "country": "us",
        "pageSize": 5
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ NewsAPI working! Found {data['totalResults']} articles")
            for article in data['articles'][:2]:
                print(f"  - {article['title']}")
        else:
            print(f"❌ NewsAPI error: {response.status_code}")
    except Exception as e:
        print(f"❌ NewsAPI error: {e}")

def test_google_ai():
    """Test Google Generative AI functionality"""
    print("\nTesting Google Generative AI...")
    
    try:
        # Configure the API key
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Initialize the model (updated model name)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Generate content
        response = model.generate_content("Hello, how are you?")
        print(f"✅ Google AI working! Response: {response.text[:100]}...")
        
    except Exception as e:
        print(f"❌ Google AI error: {e}")

if __name__ == "__main__":
    test_newsapi()
    test_google_ai()
