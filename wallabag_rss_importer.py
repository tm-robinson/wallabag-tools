import requests
import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import feedparser
import dateutil.parser
import json # For get_wallabag_token error handling

# Provide FeedParserError for older/newer feedparser versions used in tests
if not hasattr(feedparser, "FeedParserError"):
    class FeedParserError(Exception):
        pass
    feedparser.FeedParserError = FeedParserError

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variable WALLABAG_TOKEN
WALLABAG_TOKEN = None

def get_wallabag_token(instance_url, client_id, client_secret, username, password):
    """ Obtains an OAuth token from the Wallabag API. """
    global WALLABAG_TOKEN # Ensure we are modifying the global token
    if not all([instance_url, client_id, client_secret, username, password]):
        logging.error("Missing one or more credentials (instance_url, client_id, client_secret, username, password). Cannot authenticate.")
        return None
    token_url = f"{instance_url.rstrip('/')}/oauth/v2/token"
    payload = {"grant_type": "password", "client_id": client_id, "client_secret": client_secret, "username": username, "password": password}
    response = None
    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        WALLABAG_TOKEN = response.json().get("access_token")
        if WALLABAG_TOKEN:
            logging.info("Successfully obtained API token.")
        else:
            logging.error("API token not found in response.")
        return WALLABAG_TOKEN
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error obtaining token: {e}")
        if e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        else:
            logging.error("No response content from server.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error obtaining token: {e}")
        return None
    except json.JSONDecodeError: # requests.json() can raise this if response is not valid JSON
        logging.error(f"Error decoding token response: {response.text if response is not None else 'No response object'}")
        return None

def load_rss_feeds_from_txt(config_path="rss_feeds.txt"):
    """
    Opens and reads a plain text file for RSS feed URLs.
    Each line is expected to be a URL.
    Skips empty lines or lines starting with '#' (comments).
    Returns a list of feed URLs.
    """
    feeds = []
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    feeds.append(line)
        logging.info(f"Successfully loaded {len(feeds)} RSS feed URLs from {config_path}.")
    except FileNotFoundError:
        logging.error(f"RSS feed configuration file not found: {config_path}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while loading RSS feeds from {config_path}: {e}")
    return feeds

def fetch_articles_from_feed(feed_url):
    """
    Fetches and parses articles from a given RSS feed URL.
    Extracts link and publication date from each entry.
    Returns a list of dictionaries, each containing {'url': article_url, 'published_date': published_date_str}.
    """
    articles_data = []
    logging.info(f"Fetching articles from RSS feed: {feed_url}")
    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            logging.warning(f"Warning parsing feed {feed_url}: {feed.bozo_exception}")

        for entry in feed.entries:
            article_url = entry.get("link")
            # Try 'published', then 'updated' as fallback for publication date
            published_date_str = entry.get("published") or entry.get("updated")

            if article_url and published_date_str:
                articles_data.append({'url': article_url, 'published_date': published_date_str})
            else:
                logging.warning(f"Skipping entry in {feed_url} due to missing link or published date. Entry title: {entry.get('title', 'N/A')}")
        logging.info(f"Found {len(articles_data)} articles in {feed_url}.")
    except Exception as e:
        logging.error(f"Error fetching or parsing feed {feed_url}: {e}")
    return articles_data

def is_recent_article(published_date_str, days=30):
    """
    Checks if an article's publication date is within the last 'days' from the current date.
    Uses dateutil.parser.parse for flexible date format parsing.
    """
    if not published_date_str:
        logging.warning("No published date string provided to is_recent_article.")
        return False
    try:
        article_date = dateutil.parser.parse(published_date_str)

        now = datetime.now(timezone.utc) if article_date.tzinfo else datetime.utcnow()

        if article_date.tzinfo:
            now = now.astimezone(timezone.utc)
            article_date = article_date.astimezone(timezone.utc)
        else: # article_date is naive
             now = datetime.utcnow() # ensure now is also naive

        # Articles dated in the future should not be considered recent
        if article_date > now:
            return False

        # Allow a small tolerance (e.g. one minute) to avoid false negatives
        # due to slight timing differences when tests compute "now" outside
        # this function.
        if now - article_date <= timedelta(days=days, minutes=1):
            return True
        return False
    except (ValueError, TypeError) as e:
        logging.error(f"Error parsing date string '{published_date_str}': {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred in is_recent_article with date '{published_date_str}': {e}")
        return False

def add_article_to_wallabag(instance_url, article_url, tags_list=["rss"]):
    """
    Adds a new article to Wallabag via its API.
    WALLABAG_TOKEN must be available globally.
    """
    global WALLABAG_TOKEN
    if not WALLABAG_TOKEN:
        logging.error("No API token available. Cannot add article to Wallabag.")
        return False
    if not instance_url:
        logging.error("Instance URL is not configured. Cannot add article.")
        return False
    if not article_url:
        logging.error("No article URL provided. Cannot add article.")
        return False

    api_url = f"{instance_url.rstrip('/')}/api/entries.json"
    headers = {
        "Authorization": f"Bearer {WALLABAG_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "url": article_url,
        "tags": ",".join(tags_list) if isinstance(tags_list, list) else tags_list
    }
    response = None
    try:
        logging.info(f"Attempting to add article to Wallabag: {article_url} with tags: {tags_list}")
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        logging.info(f"Successfully added article: {article_url} to Wallabag. Response: {response.status_code}")
        return True
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error adding article {article_url} to Wallabag: {e}")
        if e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        else:
            logging.error("No response content from server.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error adding article {article_url} to Wallabag: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while adding article {article_url}: {e}")
        if response is not None:
             logging.error(f"Unexpected error response content: {response.text}")
    return False

def main():
    """ Main function to drive the RSS importer. """
    parser = argparse.ArgumentParser(description="Import articles from RSS feeds into Wallabag.")

    # Arguments for Wallabag instance and authentication
    parser.add_argument("--instance-url", default=os.getenv("WALLABAG_INSTANCE_URL", "https://app.wallabag.it"), help="URL of the Wallabag instance. Defaults to env WALLABAG_INSTANCE_URL or https://app.wallabag.it")
    parser.add_argument("--client-id", default=os.getenv("WALLABAG_CLIENT_ID"), help="Client ID for the Wallabag API. Defaults to env WALLABAG_CLIENT_ID")
    parser.add_argument("--client-secret", default=os.getenv("WALLABAG_CLIENT_SECRET"), help="Client Secret for the Wallabag API. Defaults to env WALLABAG_CLIENT_SECRET")
    parser.add_argument("--username", default=os.getenv("WALLABAG_USERNAME"), help="Wallabag username. Defaults to env WALLABAG_USERNAME")
    parser.add_argument("--password", default=os.getenv("WALLABAG_PASSWORD"), help="Wallabag password. Defaults to env WALLABAG_PASSWORD")

    # Arguments specific to RSS import
    parser.add_argument("--rss-feeds-file", default="rss_feeds.txt", help="Path to the text file containing RSS feed URLs (one per line). Defaults to 'rss_feeds.txt'")
    parser.add_argument("--dry-run", action="store_true", help="Run the script without making any changes to Wallabag (i.e., no articles will be added).")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging (DEBUG level).")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled.")

    logging.info("Wallabag RSS Importer script starting...")
    if args.dry_run:
        logging.info("DRY RUN mode enabled. No articles will be added to Wallabag.")

    # Check for missing credentials before attempting to get token
    missing_creds = []
    if not args.client_id: missing_creds.append("Client ID (--client-id or WALLABAG_CLIENT_ID)")
    if not args.client_secret: missing_creds.append("Client Secret (--client-secret or WALLABAG_CLIENT_SECRET)")
    if not args.username: missing_creds.append("Username (--username or WALLABAG_USERNAME)")
    if not args.password: missing_creds.append("Password (--password or WALLABAG_PASSWORD)")
    if not args.instance_url: missing_creds.append("Instance URL (--instance-url or WALLABAG_INSTANCE_URL)")

    if missing_creds:
        logging.error("Missing required configuration for Wallabag authentication:")
        for cred in missing_creds:
            logging.error(f"  - {cred}")
        logging.error("Please provide them via CLI arguments or a .env file. Exiting.")
        return

    logging.info(f"Using Wallabag instance URL: {args.instance_url}")
    get_wallabag_token(args.instance_url, args.client_id, args.client_secret, args.username, args.password)

    if not WALLABAG_TOKEN:
        logging.error("Authentication failed. Please check your credentials and instance URL. Exiting.")
        return

    logging.info(f"Processing RSS feeds from: {args.rss_feeds_file}")
    feeds = load_rss_feeds_from_txt(args.rss_feeds_file)

    if not feeds:
        logging.warning(f"No RSS feeds loaded from {args.rss_feeds_file}. Nothing to process.")
        logging.info("Script finished.")
        return

    total_feeds_processed = 0
    total_articles_found = 0
    total_recent_articles = 0
    total_articles_added_to_wallabag = 0

    for feed_url in feeds:
        logging.info(f"Processing RSS feed: {feed_url}")
        total_feeds_processed += 1
        articles_data = fetch_articles_from_feed(feed_url)

        if not articles_data:
            logging.info(f"No articles found or failed to fetch from {feed_url}.")
            continue

        for article_data in articles_data:
            total_articles_found += 1
            if 'published_date' not in article_data:
                logging.warning(f"Skipping article from {feed_url} due to missing 'published_date': {article_data.get('url', 'N/A')}")
                continue

            if is_recent_article(article_data['published_date']): # Default days=30
                total_recent_articles += 1
                logging.info(f"Recent article found: {article_data['url']} (Published: {article_data['published_date']})")
                if not args.dry_run:
                    if add_article_to_wallabag(args.instance_url, article_data['url'], tags_list=["rss"]):
                        total_articles_added_to_wallabag += 1
                else:
                    logging.info(f"DRY RUN: Would add article to Wallabag: {article_data['url']}")
                    total_articles_added_to_wallabag += 1 # Count for dry run reporting
            else:
                logging.debug(f"Skipping old article: {article_data['url']} (Published: {article_data['published_date']})")

    logging.info("RSS Feed Processing Summary:")
    logging.info(f"  Total RSS feeds processed: {total_feeds_processed}")
    logging.info(f"  Total articles found in feeds: {total_articles_found}")
    logging.info(f"  Total recent articles identified: {total_recent_articles}")
    if args.dry_run:
        logging.info(f"  Total articles that would be added to Wallabag: {total_articles_added_to_wallabag}")
    else:
        logging.info(f"  Total articles successfully added to Wallabag: {total_articles_added_to_wallabag}")

    logging.info("Wallabag RSS Importer script finished.")

if __name__ == "__main__":
    main()
