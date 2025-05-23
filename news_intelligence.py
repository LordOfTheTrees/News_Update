import time
import requests
import smtplib
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, NEWSAPI_KEY, GITHUB_TOKEN, GITHUB_REPO
)

def generate_search_strategy(user_query, max_queries=5):
    """
    Step 1: Use Claude to convert user request into effective search queries
    """
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    system_prompt = """You are a search strategy expert. Convert user requests into effective news search queries.
    
    Rules:
    - Return ONLY a Python list of strings, no other text
    - Each query should be 2-4 words max for NewsAPI
    - Focus on different angles of the topic
    - Include industry-specific terms when relevant
    - Avoid overly broad or specific terms
    """
    
    user_prompt = f"""
    Convert this request into {max_queries} effective NewsAPI search queries:
    "{user_query}"
    
    Return format: ["query1", "query2", "query3", "query4", "query5"]
    """
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        response_text = response.content[0].text.strip()
        if '[' in response_text and ']' in response_text:
            start = response_text.find('[')
            end = response_text.find(']') + 1
            list_str = response_text[start:end]
            return eval(list_str)  # Note: In production, use ast.literal_eval
        else:
            lines = [line.strip(' -"\'') for line in response_text.split('\n') if line.strip()]
            return lines[:max_queries]
            
    except Exception as e:
        print(f"Error generating search strategy: {e}")
        return [user_query.replace(" news", "").replace(" headlines", "")]

def search_news(queries, days_back=1, sources=None, language="en"):
    """
    Step 2: Execute searches using NewsAPI
    """
    all_articles = []
    from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    newsapi_base = "https://newsapi.org/v2"
    
    print(f"🔍 Searching from date: {from_date}")
    
    for query in queries:
        try:
            params = {
                'q': query,
                'from': from_date,
                'language': language,
                'sortBy': 'publishedAt',
                'pageSize': 20,
                'apiKey': NEWSAPI_KEY
            }
            
            if sources:
                params['sources'] = sources
            
            print(f"   Searching: '{query}'...")
            response = requests.get(f"{newsapi_base}/everything", params=params)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                total_results = data.get('totalResults', 0)
                
                print(f"   → Found {len(articles)} articles (total available: {total_results})")
                
                for article in articles:
                    article['search_query'] = query
                
                all_articles.extend(articles)
                time.sleep(0.1)  # Rate limiting
            else:
                print(f"   NewsAPI error for query '{query}': {response.status_code}")
                if response.status_code == 401:
                    print("   Check your NewsAPI key!")
                elif response.status_code == 429:
                    print("   Rate limit exceeded - try again later")
                else:
                    print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"   Error searching for '{query}': {e}")
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article.get('url') and article['url'] not in seen_urls:
            seen_urls.add(article['url'])
            unique_articles.append(article)
    
    print(f"Total unique articles after deduplication: {len(unique_articles)}")
    
    # Debug: Show some article titles if found
    if unique_articles:
        print("📰 Sample headlines found:")
        for i, article in enumerate(unique_articles[:3]):
            print(f"   {i+1}. {article.get('title', 'No title')[:80]}...")
    
    return unique_articles

def synthesize_news(articles, original_query, max_headlines=10):
    """
    Step 3: Use Claude to synthesize articles into structured summary
    """
    if not articles:
        return "No recent news articles found for your query."
    
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    article_summaries = []
    for i, article in enumerate(articles[:25]):
        summary = f"""
        Article {i+1}:
        Headline: {article.get('title', 'No title')}
        Description: {article.get('description', 'No description')}
        Source: {article.get('source', {}).get('name', 'Unknown')}
        Published: {article.get('publishedAt', 'Unknown')}
        Content Preview: {article.get('content', 'No content')[:200]}
        """
        article_summaries.append(summary.strip())
    
    articles_text = "\n\n".join(article_summaries)
    
    system_prompt = f"""You are a news analyst. Synthesize the provided articles into a clean summary.

    Requirements:
    - Return the top {max_headlines} most important/relevant headlines
    - For each headline, provide exactly 2 sentences of summary
    - Include specific numbers, percentages, dollar amounts when mentioned
    - Focus on the most newsworthy and recent information
    - Use this format:

    **[Headline]**
    [2-sentence summary with numbers if available]

    **[Next Headline]**
    [2-sentence summary with numbers if available]
    
    Do not include any other text, explanations, or meta-commentary."""
    
    user_prompt = f"""
    Original request: "{original_query}"
    
    Here are the news articles to synthesize:
    
    {articles_text}
    
    Please provide the top {max_headlines} headlines with summaries as specified.
    """
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        return response.content[0].text.strip()
        
    except Exception as e:
        print(f"Error synthesizing news: {e}")
        return "Error processing news articles."

def create_github_issue(title, body, labels=None, assignees=None):
    """
    Create a GitHub issue with the news summary
    GitHub will automatically send email notifications to:
    - Repository owner
    - Anyone watching the repository  
    - Anyone assigned to the issue
    - Anyone mentioned in the issue body
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "title": title,
        "body": body,
        "labels": labels or ["news-summary", "automated"],
        "assignees": assignees or []  # GitHub usernames to assign and notify
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            issue_data = response.json()
            print(f"GitHub issue created: {issue_data['html_url']}")
            print(f"Email notifications sent via GitHub to watchers/assignees")
            return issue_data
        else:
            print(f"Failed to create GitHub issue: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Error creating GitHub issue: {e}")
        return None

def create_github_discussion(title, body, category="General"):
    """
    Alternative: Create a GitHub Discussion instead of an issue
    Discussions are better for ongoing topics and also send notifications
    """
    # Note: Discussions API requires GraphQL - simplified version here
    # For full implementation, you'd use GitHub's GraphQL API
    print(f"Would create discussion: '{title}' in category '{category}'")
    return None

def add_issue_comment(issue_number, comment_body, mention_users=None):
    """
    Add a comment to an existing issue to trigger additional notifications
    Useful for daily updates to a single ongoing issue
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}/comments"
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Add @mentions to trigger notifications to specific users
    if mention_users:
        mentions = " ".join([f"@{user}" for user in mention_users])
        comment_body = f"{mentions}\n\n{comment_body}"
    
    data = {"body": comment_body}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            comment_data = response.json()
            print(f" Comment added to issue #{issue_number}")
            print(f" Email notifications sent to mentioned users and watchers")
            return comment_data
        else:
            print(f" Failed to add comment: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error adding comment: {e}")
        return None

def send_email(subject, body, is_html=False):
    """
    REMOVED: Using GitHub's built-in email system instead
    GitHub automatically sends emails for:
    - New issues (to watchers/assignees)
    - Issue comments (to participants/watchers)  
    - Mentions (to mentioned users)
    """
    print("📧 Email delivery handled by GitHub notifications")
    return True

def format_for_github(content, query, mention_users=None):
    """
    Format the news summary for GitHub (Issues/Discussions)
    """
    mentions = ""
    if mention_users:
        mentions = " ".join([f"@{user}" for user in mention_users]) + "\n\n"
    
    github_content = f"""{mentions}## 📰 Daily News Intelligence: {query.title()}

**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}

---

{content}

---

<details>
<summary>ℹ️ About this report</summary>

This summary was automatically generated using:
- **Claude AI** for query planning and synthesis  
- **NewsAPI** for content aggregation from 150k+ sources
- **GitHub Actions** for automation

To modify the news topics, edit the `NEWS_QUERY` variable in `news_intelligence.py`
</details>
"""
    return github_content

def main():
    """
    Main execution function - can be customized for different news types
    """
    news_topics = "consumer behavior, marketing, and advertising", "gaming, xbox, and electronics", "chicago bears and the NFL", "Yale and Penn State College Football", "Mixed Martial Arts, the UFC, and Brazilian Jiu Jitsu"
    for topic in news_topics: 
	    NEWS_QUERY = topic  # Changes this for different news types
	    DAYS_BACK = 1  # Increase to 2 days to get more results
	    MAX_HEADLINES = 5
	    TRUSTED_SOURCES = None  # Remove source restriction to get more results initially
	    # TRUSTED_SOURCES = "reuters,bloomberg,bbc-news,associated-press,the-wall-street-journal"  # Re-enable later
	    
	    # GitHub notification settings - replace with those for any user you want included on the info
	    MENTION_USERS = []  # ["your-actual-github-username"] - Add your real username here
	    ASSIGNEES = []      # ["your-actual-github-username"] - Add your real username here
	    USE_SINGLE_ISSUE = False  # True = comment on existing issue, False = create new issue daily
	    EXISTING_ISSUE_NUMBER = 1  # If USE_SINGLE_ISSUE=True, specify issue number
	    
	    print(f"Starting news intelligence pipeline for: '{NEWS_QUERY}'")
	    print(f"Looking back {DAYS_BACK} day(s)")
	    
	    # Step 1: Generate search strategy
	    print("Generating search strategy...")
	    search_queries = generate_search_strategy(NEWS_QUERY)
	    print(f"Search queries: {search_queries}")
	    
	    # Step 2: Search news
	    print("Searching news sources...")
	    articles = search_news(search_queries, days_back=DAYS_BACK, sources=TRUSTED_SOURCES)
	    print(f"Found {len(articles)} unique articles")
	    
	    # Step 3: Synthesize with Claude
	    print("Synthesizing with Claude...")
	    summary = synthesize_news(articles, NEWS_QUERY, max_headlines=MAX_HEADLINES)
	    
	    # Step 4: GitHub notification strategy (only if we have content)
	    if len(articles) == 0:
	        print(" No articles found - skipping GitHub issue creation")
	        print("Troubleshooting tips:")
	        print("   • Check your NewsAPI key is valid")
	        print("   • Try increasing DAYS_BACK to 3-7 days")  
	        print("   • Remove TRUSTED_SOURCES restriction")
	        print("   • Try broader search terms")
	        return
	    
	    if USE_SINGLE_ISSUE:
	        # Option 1: Add comment to existing issue (ongoing updates)
	        comment_body = format_for_github(summary, NEWS_QUERY, mention_users=MENTION_USERS)
	        result = add_issue_comment(EXISTING_ISSUE_NUMBER, comment_body, mention_users=MENTION_USERS)
	        notification_method = f"Comment on issue #{EXISTING_ISSUE_NUMBER}"
	    else:
	        # Option 2: Create new issue daily (separate reports)
	        issue_title = f"📰 {NEWS_QUERY.title()} - {datetime.now().strftime('%Y-%m-%d')}"
	        issue_body = format_for_github(summary, NEWS_QUERY, mention_users=MENTION_USERS)
	        result = create_github_issue(issue_title, issue_body, assignees=ASSIGNEES)
	        notification_method = "New daily issue"
	    
	    # Step 5: Confirmation (no separate email needed)
	    print("News intelligence pipeline completed!")
	    print(f"\n Summary:")
	    print(f"   • Search queries: {len(search_queries)}")
	    print(f"   • Articles found: {len(articles)}")
	    print(f"   • GitHub notification: {notification_method}")
	    print(f"   • Email delivery: Handled by GitHub")
	    print(f"   • Recipients: Repository watchers + assigned users + mentioned users")
	
if __name__ == "__main__":
    main()