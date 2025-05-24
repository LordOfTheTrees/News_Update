# News Intelligence Pipeline

An automated news aggregation and analysis system that uses Claude AI to generate targeted search queries, fetches articles from NewsAPI, synthesizes summaries, and delivers reports via GitHub Issues.

## Features

- **Smart Query Generation**: Uses Claude AI to convert broad topics into effective NewsAPI search queries
- **Intelligent Caching**: Saves Claude API translations to avoid redundant calls and reduce costs
- **Multi-Source News Aggregation**: Fetches from 150k+ news sources via NewsAPI
- **AI-Powered Synthesis**: Claude analyzes and summarizes articles into clean, structured reports
- **GitHub Integration**: Automatically creates issues or comments for team notifications
- **Email Notifications**: Leverages GitHub's built-in email system for stakeholder updates

## Quick Start

### 1. Clone and Install Dependencies

```bash
git clone <your-repo-url>
cd news-intelligence
pip install requests anthropic
```

### 2. Configure API Keys

Create a `config.py` file with your API credentials:

```python
# config.py - REQUIRED: Replace with your actual keys

# Anthropic Claude API Key
# Get yours at: https://console.anthropic.com/
ANTHROPIC_API_KEY = "your-anthropic-api-key-here"

# NewsAPI Key 
# Get yours at: https://newsapi.org/register
NEWSAPI_KEY = "your-newsapi-key-here"

# GitHub Token (for creating issues/notifications)
# Create at: GitHub Settings > Developer settings > Personal access tokens
GITHUB_TOKEN = "your-github-token-here"

# GitHub Repository (format: "username/repository-name")
GITHUB_REPO = "your-username/your-repo-name"
```

### 3. Customize News Topics

Edit the `news_topics` list in the `main()` function:

```python
def main():
    # CUSTOMIZE THESE TOPICS FOR YOUR NEEDS
    news_topics = [
        "your first topic here",
        "your second topic here", 
        "your third topic here",
        # Add as many topics as you want
    ]
```

**Example topics:**
- "artificial intelligence and machine learning"
- "cryptocurrency and blockchain"
- "climate change and renewable energy"
- "cybersecurity and data privacy"
- "startup funding and venture capital"

### 4. Run the Pipeline

```bash
python news_intelligence.py
```

## How It Works

### 1. Query Cache System
The script maintains a smart cache (`search_query_cache.json`) that:
- Stores Claude's search query translations
- Only calls Claude API for genuinely new topics
- Uses MD5 hashing for consistent cache keys
- Saves API costs and improves performance

### 2. News Processing Pipeline
1. **Query Generation**: Claude converts your broad topics into specific NewsAPI search terms
2. **News Fetching**: Searches multiple sources and deduplicates results
3. **AI Synthesis**: Claude analyzes articles and creates structured summaries
4. **Delivery**: Posts results to GitHub Issues with automatic email notifications

### 3. GitHub Integration
- Creates daily issues for each news topic
- Sends automatic email notifications to repository watchers
- Supports @mentions for specific team members
- Alternative: Can comment on existing issues for ongoing updates

## Configuration Options

### News Settings
```python
DAYS_BACK = 1              # How many days back to search
MAX_HEADLINES = 5          # Number of top stories to include
TRUSTED_SOURCES = None     # Limit to specific sources (optional)
```

### GitHub Notification Settings
```python
MENTION_USERS = ["username1", "username2"]  # Users to @mention
ASSIGNEES = ["username1"]                   # Users to assign issues to
USE_SINGLE_ISSUE = False                    # True = update one issue, False = daily issues
EXISTING_ISSUE_NUMBER = 1                   # Issue number if using single issue mode
```

## Cache Management

### View Cache Statistics
```python
# Uncomment in main() to see cache stats
view_cache_stats()
```

### Clear Cache (if needed)
```python
# Uncomment in main() to clear cache
clear_cache()
```

### Cache File Structure
The cache stores:
- Original user queries
- Generated search terms
- Creation timestamps
- Full Claude responses
- Error information

## API Requirements

### Anthropic Claude API
- **Purpose**: Query generation and article synthesis
- **Model**: Claude-3.5-Sonnet
- **Usage**: ~200-2000 tokens per topic per run
- **Get Key**: [console.anthropic.com](https://console.anthropic.com/)

### NewsAPI
- **Purpose**: News article fetching
- **Limits**: 1000 requests/day (free tier)
- **Usage**: ~5-10 requests per topic per run
- **Get Key**: [newsapi.org/register](https://newsapi.org/register)

### GitHub Token
- **Purpose**: Creating issues and notifications
- **Permissions**: `repo` scope required
- **Get Token**: GitHub Settings > Developer settings > Personal access tokens

## Troubleshooting

### No Articles Found
- Check your NewsAPI key is valid and has remaining quota
- Increase `DAYS_BACK` to search more days (try 3-7)
- Remove `TRUSTED_SOURCES` restriction initially
- Try broader search terms in your topics

### Claude API Errors
- Verify your Anthropic API key is correct
- Check you have sufficient credits
- Fallback queries will be cached to avoid repeated failures

### GitHub Issues Not Created
- Ensure GitHub token has `repo` permissions
- Verify repository name format: "username/repository-name"
- Check repository exists and token has access

## Automation

### GitHub Actions (Recommended)
Create `.github/workflows/news-intelligence.yml`:

```yaml
name: Daily News Intelligence
on:
  schedule:
    - cron: '0 9 * * *'  # Run daily at 9 AM UTC
  workflow_dispatch:     # Manual trigger

jobs:
  news-intelligence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: pip install requests anthropic
      
      - name: Run news intelligence
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          NEWSAPI_KEY: ${{ secrets.NEWSAPI_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python news_intelligence.py
```

### Cron Job (Linux/Mac)
```bash
# Edit crontab
crontab -e

# Add line for daily 9 AM execution
0 9 * * * cd /path/to/news-intelligence && python news_intelligence.py
```

## File Structure

```
news-intelligence/
├── news_intelligence.py      # Main script
├── config.py                 # API keys and settings (YOU MUST CREATE THIS)
├── search_query_cache.json   # Auto-generated cache file
├── README.md                 # This file
└── .github/
    └── workflows/
        └── news-intelligence.yml  # Optional automation
```

## Cost Estimation

**Daily costs for 5 topics:**
- Claude API: ~$0.01-0.05 per day
- NewsAPI: Free (up to 1000 requests/day)
- GitHub: Free

**Monthly estimate: $0.30-1.50**

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with your own API keys
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- Check the troubleshooting section above
- Review API documentation for rate limits
- Ensure all API keys are valid and have sufficient quota
- Test with a single topic first before running multiple topics
