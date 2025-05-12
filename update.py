import time
from datetime import datetime
import os
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY

if __name__ == "__main__":
    # Initialize the client with your API key
    try: 
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        response = client.messages.create(
        model="claude-3-7-sonnet-20250219",  # Use the latest model
        max_tokens=1000,  # Maximum tokens in the response
        #temperature=0.7,  # Controls randomness (0-1)
        system="You are a news gathering bot, that returns only html or text",  # Optional system prompt
        messages=[
            {
                "role": "user",
                "content": '''
                what are the biggest news headlines with respect to marketing and advertising
                in the last 24 hours? Please provide a short 2 sentence summary of each news
                story after the headline, trying to include the any numbers cited in the headlines.
                Please provide the news headlines in a list format.
                Please do not include any other information other than the news headlines 
                and their sentence summary.'''
            }
        ]
        )
        # Access the response
        print(response.content[0].text)
    except Exception as e:
            print(f"Error running the script: {e}")