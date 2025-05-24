import time
import requests
import smtplib
import json
import os
import hashlib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, NEWSAPI_KEY, GITHUB_TOKEN, GITHUB_REPO
)

# Configuration for query cache
QUERY_CACHE_FILE = "search_query_cache.json"

def load_query_cache():
    """
    Load existing query translations from cache file
    """
    if os.path.exists(QUERY_CACHE_FILE):
        try:
            with open(QUERY_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                print(f"Loaded query cache with {len(cache)} entries")
                return cache
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading cache file: {e}")
            return {}
    else:
        print("No existing cache file found, starting fresh")
        return {}

def save_query_cache(cache):
    """
    Save query translations to cache file with readable formatting
    """
    try:
        with open(QUERY_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False, sort_keys=True)
        print(f"Saved query cache with {len(cache)} entries")
        return True
    except IOError as e:
        print(f"Error saving cache file: {e}")
        return False

def create_cache_key(user_query, max_queries):
    """
    Create a consistent cache key for the query + parameters
    """
    # Normalize the query (lowercase, strip whitespace)
    normalized_query = user_query.lower().strip()
    
    # Create a hash to handle very long queries
    cache_input = f"{normalized_query}|max_queries:{max_queries}"
    cache_key = hashlib.md5(cache_input.encode('utf-8')).hexdigest()
    
    return cache_key, normalized_query

def generate_search_strategy(user_query, max_queries=5):
    """
    Step 1: Use Claude to convert user request into effective search queries
    Now with caching to avoid redundant API calls
    """
    # Load existing cache
    cache = load_query_cache()
    
    # Create cache key
    cache_key, normalized_query = create_cache_key(user_query, max_queries)
    
    # Check if we already have this translation
    if cache_key in cache:
        cached_entry = cache[cache_key]
        print(f"Using cached search queries for: '{user_query}'")
        print(f"   Cached on: {cached_entry.get('created_at', 'unknown date')}")
        print(f"   Queries: {cached_entry['search_queries']}")
        return cached_entry['search_queries']
    
    # Not in cache - need to call Claude
    print(f"Generating new search strategy for: '{user_query}'")
    
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
        search_queries = []
        
        if '[' in response_text and ']' in response_text:
            start = response_text.find('[')
            end = response_text.find(']') + 1
            list_str = response_text[start:end]
            search_queries = eval(list_str)  # Note: In production, use ast.literal_eval
        else:
            lines = [line.strip(' -"\'') for line in response_text.split('\n') if line.strip()]
            search_queries = lines[:max_queries]
        
        # Save to cache with readable structure
        cache_entry = {
            "original_query": user_query,
            "normalized_query": normalized_query,
            "max_queries": max_queries,
            "search_queries": search_queries,
            "created_at": datetime.now().isoformat(),
            "claude_response": response_text
        }
        
        cache[cache_key] = cache_entry
        save_query_cache(cache)
        
        print(f"Generated and cached {len(search_queries)} search queries")
        return search_queries
            
    except Exception as e:
        print(f"Error generating search strategy: {e}")
        # Fallback to simple query splitting
        fallback_queries = [user_query.replace(" news", "").replace(" headlines", "")]
        
        # Still cache the fallback to avoid repeated failures
        cache_entry = {
            "original_query": user_query,
            "normalized_query": normalized_query,
            "max_queries": max_queries,
            "search_queries": fallback_queries,
            "created_at": datetime.now().isoformat(),
            "claude_response": None,
            "error": str(e),
            "fallback": True
        }
        
        cache[cache_key] = cache_entry
        save_query_cache(cache)
        
        return fallback_queries

def view_cache_stats():
    """
    Utility function to view cache statistics
    """
    cache = load_query_cache()
    
    if not cache:
        print("Cache is empty")
        return
    
    print(f"Cache Statistics:")
    print(f"   Total entries: {len(cache)}")
    
    # Group by original queries
    unique_queries = set()
    fallback_count = 0
    oldest_date = None
    newest_date = None
    
    for key, entry in cache.items():
        unique_queries.add(entry.get('normalized_query', 'unknown'))
        
        if entry.get('fallback'):
            fallback_count += 1
        
        created_at = entry.get('created_at')
        if created_at:
            try:
                date_obj = datetime.fromisoformat(created_at)
                if oldest_date is None or date_obj < oldest_date:
                    oldest_date = date_obj
                if newest_date is None or date_obj > newest_date:
                    newest_date = date_obj
            except:
                pass
    
    print(f"   Unique query types: {len(unique_queries)}")
    print(f"   Successful Claude calls: {len(cache) - fallback_count}")
    print(f"   Fallback entries: {fallback_count}")
    
    if oldest_date and newest_date:
        print(f"   Date range: {oldest_date.strftime('%Y-%m-%d')} to {newest_date.strftime('%Y-%m-%d')}")
    
    print(f"\nRecent queries:")
    # Show most recent 5 entries
    sorted_entries = sorted(cache.items(), 
                          key=lambda x: x[1].get('created_at', ''), 
                          reverse=True)
    
    for i, (key, entry) in enumerate(sorted_entries[:5]):
        original = entry.get('original_query', 'unknown')[:50]
        queries = entry.get('search_queries', [])
        created = entry.get('created_at', 'unknown')[:10]  # Just date part
        status = "OK" if not entry.get('fallback') else "FALLBACK"
        print(f"   {status} {created}: '{original}' -> {len(queries)} queries")
    
    print(f"\nTo edit search queries, modify the 'search_queries' arrays in: {QUERY_CACHE_FILE}")
    print("The cache file is human-readable JSON - just edit the search terms and save.")

def clear_cache():
    """
    Utility function to clear the cache (use with caution)
    """
    confirmation = input("Are you sure you want to clear the entire cache? (yes/no): ")
    if confirmation.lower() in ['yes', 'y']:
        try:
            os.remove(QUERY_CACHE_FILE)
            print("Cache cleared successfully")
        except FileNotFoundError:
            print("No cache file to clear")
        except OSError as e:
            print(f"Error clearing cache: {e}")
    else:
        print("Cache clearing cancelled")

def search_news(queries, days_back=1, sources=None, language="en"):
    """
    Step 2: Execute searches using NewsAPI
    (Unchanged from original)
    """
    all_articles = []
    from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    newsapi_base = "https://newsapi.org/v2"
    
    print(f"Searching from date: {from_date}")
    
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
        print("Sample headlines found:")
        for i, article in enumerate(unique_articles[:3]):
            print(f"   {i+1}. {article.get('title', 'No title')[:80]}...")
    
    return unique_articles

def synthesize_news(articles, original_query, max_headlines=10):
    """
    Step 3: Use Claude to synthesize articles into structured summary with URLs
    """
    if not articles:
        return "No recent news articles found for your query."
    
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    article_summaries = []
    for i, article in enumerate(articles[:25]):
        summary = f"""
        Article {i+1}:
        Headline: {article.get('title', 'No title')}
        URL: {article.get('url', 'No URL')}
        Description: {article.get('description', 'No description')}
        Source: {article.get('source', {}).get('name', 'Unknown')}
        Published: {article.get('publishedAt', 'Unknown')}
        Content Preview: {article.get('content', 'No content')[:200]}
        """
        article_summaries.append(summary.strip())
    
    articles_text = "\n\n".join(article_summaries)
    
    system_prompt = f"""You are a news analyst. Synthesize the provided articles into a clean summary with clickable links.

    Requirements:
    - Return the top {max_headlines} most important/relevant headlines
    - For each headline, provide exactly 2 sentences of summary
    - Include the article URL as a clickable link after each summary
    - Include specific numbers, percentages, dollar amounts when mentioned
    - Focus on the most newsworthy and recent information
    - Use this EXACT format:

    **[Headline]**
    [2-sentence summary with numbers if available]
    [Article URL]

    **[Next Headline]**
    [2-sentence summary with numbers if available]
    [Article URL]
    
    Do not include any other text, explanations, or meta-commentary.
    Make sure to include the URL for each story you summarize."""
    
    user_prompt = f"""
    Original request: "{original_query}"
    
    Here are the news articles to synthesize:
    
    {articles_text}
    
    Please provide the top {max_headlines} headlines with summaries and URLs as specified.
    """
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        # Get Claude's response
        claude_summary = response.content[0].text.strip()
        
        # Post-process to ensure URLs are properly formatted as clickable links
        # This helps in case Claude doesn't format them perfectly
        processed_summary = format_urls_as_links(claude_summary, articles[:max_headlines])
        
        return processed_summary
        
    except Exception as e:
        print(f"Error synthesizing news: {e}")
        return "Error processing news articles."

def format_urls_as_links(summary_text, articles):
    """
    Helper function to ensure URLs are properly formatted as clickable links
    """
    import re
    
    # Find URLs in the text that aren't already formatted as markdown links
    url_pattern = re.compile(r'(?<![\(\[])(https?://[^\s\)]+)(?![\)\]])')
    
    def replace_url(match):
        url = match.group(1)
        # Find matching article to get title for better link text
        for article in articles:
            if article.get('url') == url:
                title = article.get('title', 'Read More')[:50]  # Truncate long titles
                return f"[{title}]({url})"
        return f"[Read More]({url})"
    
    # Replace bare URLs with markdown links
    formatted_text = url_pattern.sub(replace_url, summary_text)
    
    return formatted_text

def create_github_issue(title, body, labels=None, assignees=None):
    """
    Create a GitHub issue with the news summary
    (Unchanged from original)
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
        "assignees": assignees or []
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

def add_issue_comment(issue_number, comment_body, mention_users=None):
    """
    Add a comment to an existing issue to trigger additional notifications
    (Unchanged from original)
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}/comments"
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
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
    print("Email delivery handled by GitHub notifications")
    return True

def format_for_github(content, query, mention_users=None):
    """
    Format the news summary for GitHub
    (Unchanged from original)
    """
    mentions = ""
    if mention_users:
        mentions = " ".join([f"@{user}" for user in mention_users]) + "\n\n"
    
    github_content = f"""{mentions}## Daily News Intelligence: {query.title()}

**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}

---

{content}

---

<details>
<summary>About this report</summary>

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
    Main execution function with enhanced caching
    """
    # Show cache stats at startup
    view_cache_stats()
    
    news_topics = [
        "consumer behavior, marketing, and advertising",
        "gaming, xbox, and electronics", 
        "chicago bears and the NFL",
        "Yale and Penn State College Football",
        "Mixed Martial Arts, the UFC, and Brazilian Jiu Jitsu"
    ]
    
    for topic in news_topics: 
        NEWS_QUERY = topic
        DAYS_BACK = 1
        MAX_HEADLINES = 5
        TRUSTED_SOURCES = None
        
        # GitHub notification settings
        MENTION_USERS = []
        ASSIGNEES = []
        USE_SINGLE_ISSUE = False
        EXISTING_ISSUE_NUMBER = 1
        
        print(f"\n{'='*60}")
        print(f"Starting news intelligence pipeline for: '{NEWS_QUERY}'")
        print(f"Looking back {DAYS_BACK} day(s)")
        
        # Step 1: Generate search strategy (now with caching)
        print("\n1. Generating search strategy...")
        search_queries = generate_search_strategy(NEWS_QUERY)
        print(f"Search queries: {search_queries}")
        
        # Step 2: Search news
        print("\n2. Searching news sources...")
        articles = search_news(search_queries, days_back=DAYS_BACK, sources=TRUSTED_SOURCES)
        print(f"Found {len(articles)} unique articles")
        
        # Step 3: Synthesize with Claude
        print("\n3. Synthesizing with Claude...")
        summary = synthesize_news(articles, NEWS_QUERY, max_headlines=MAX_HEADLINES)
        
        # Step 4: GitHub notification strategy
        if len(articles) == 0:
            print("No articles found - skipping GitHub issue creation")
            print("Troubleshooting tips:")
            print("   • Check your NewsAPI key is valid")
            print("   • Try increasing DAYS_BACK to 3-7 days")  
            print("   • Remove TRUSTED_SOURCES restriction")
            print("   • Try broader search terms")
            continue
        
        print("\n4. Creating GitHub notification...")
        if USE_SINGLE_ISSUE:
            comment_body = format_for_github(summary, NEWS_QUERY, mention_users=MENTION_USERS)
            result = add_issue_comment(EXISTING_ISSUE_NUMBER, comment_body, mention_users=MENTION_USERS)
            notification_method = f"Comment on issue #{EXISTING_ISSUE_NUMBER}"
        else:
            issue_title = f"{NEWS_QUERY.title()} - {datetime.now().strftime('%Y-%m-%d')}"
            issue_body = format_for_github(summary, NEWS_QUERY, mention_users=MENTION_USERS)
            result = create_github_issue(issue_title, issue_body, assignees=ASSIGNEES)
            notification_method = "New daily issue"
        
        # Step 5: Confirmation
        print("\nNews intelligence pipeline completed!")
        print(f"   • Search queries: {len(search_queries)}")
        print(f"   • Articles found: {len(articles)}")
        print(f"   • GitHub notification: {notification_method}")
        print(f"   • Email delivery: Handled by GitHub")

if __name__ == "__main__":
    # Uncomment these lines for cache management:
    # view_cache_stats()  # View cache before running
    # clear_cache()       # Clear cache if needed
    
    main()
