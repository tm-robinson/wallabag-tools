import requests
import argparse
import logging
import os
import urllib.parse
import json
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

WALLABAG_TOKEN = None

DEFAULT_PAYWALLED_HOSTS = [
    "wsj.com",
    "ft.com",
    "bloomberg.com",
    "nytimes.com",
    "washingtonpost.com",
    "economist.com"
]

def get_wallabag_token(instance_url, client_id, client_secret, username, password):
    global WALLABAG_TOKEN
    if not all([instance_url, client_id, client_secret, username, password]):
        logging.error("Missing one or more credentials (instance_url, client_id, client_secret, username, password). Cannot authenticate.")
        return None
    token_url = f"{instance_url.rstrip('/')}/oauth/v2/token"
    payload = {
        "grant_type": "password",
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "password": password
    }
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
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error obtaining token: {e}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Error decoding token response: {response.text if response is not None else 'No response object'}")
        return None

def get_unread_articles(instance_url):
    global WALLABAG_TOKEN
    if not WALLABAG_TOKEN:
        logging.error("No API token available. Please authenticate first.")
        return []
    if not instance_url:
        logging.error("Instance URL is not configured. Cannot fetch articles.")
        return []
    articles_url = f"{instance_url.rstrip('/')}/api/entries.json"
    headers = {"Authorization": f"Bearer {WALLABAG_TOKEN}"}
    params = {"page": 1, "perPage": 50, "archive": 0}
    all_articles = []
    while True:
        try:
            response = requests.get(articles_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            if "_embedded" in data and "items" in data["_embedded"]:
                items = data["_embedded"]["items"]
                all_articles.extend(items)
                if not items or params["page"] >= data.get("pages", 0):
                    break
                params["page"] += 1
            else:
                break
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching articles: {e}")
            break
        except json.JSONDecodeError:
            logging.error(f"Error decoding articles response: {response.text if response is not None else 'No response object'}")
            break
    logging.info(f"Fetched {len(all_articles)} unread articles from Wallabag")
    return all_articles

def add_article_to_wallabag(instance_url, article_url, tags_list=None):
    global WALLABAG_TOKEN
    if tags_list is None:
        tags_list = []
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
    headers = {"Authorization": f"Bearer {WALLABAG_TOKEN}", "Content-Type": "application/json"}
    payload = {"url": article_url}
    if tags_list:
        payload["tags"] = ",".join(tags_list)
    response = None
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        logging.info(f"Successfully added article {article_url}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error adding article {article_url}: {e}")
        if response is not None:
            logging.error(f"Response content: {response.text}")
    return False

def delete_article_from_wallabag(instance_url, article_id):
    global WALLABAG_TOKEN
    if not WALLABAG_TOKEN:
        logging.error("No API token available. Cannot delete article from Wallabag.")
        return False
    if not instance_url:
        logging.error("Instance URL is not configured. Cannot delete article.")
        return False
    delete_url = f"{instance_url.rstrip('/')}/api/entries/{article_id}.json"
    headers = {"Authorization": f"Bearer {WALLABAG_TOKEN}"}
    response = None
    try:
        response = requests.delete(delete_url, headers=headers)
        response.raise_for_status()
        logging.info(f"Deleted original article ID {article_id} from Wallabag")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error deleting article ID {article_id}: {e}")
        if response is not None:
            logging.error(f"Response content: {response.text}")
    return False

def get_existing_archive(article_url):
    check_url = f"https://archive.is/newest/{article_url}"
    try:
        resp = requests.get(check_url, allow_redirects=False, timeout=15)
        if resp.status_code in (301, 302) and 'Location' in resp.headers:
            loc = resp.headers['Location']
            if not loc.startswith('/newest/'):
                return urllib.parse.urljoin("https://archive.is", loc)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking archive.is for {article_url}: {e}")
    return None

def submit_to_archive(article_url):
    submit_url = "https://archive.is/submit/"
    try:
        resp = requests.post(submit_url, data={'url': article_url}, allow_redirects=False, timeout=15)
        if resp.status_code in (301, 302) and 'Location' in resp.headers:
            archive_url = resp.headers['Location']
            if not archive_url.startswith('http'):
                archive_url = urllib.parse.urljoin("https://archive.is", archive_url)
            return archive_url
    except requests.exceptions.RequestException as e:
        logging.error(f"Error submitting {article_url} to archive.is: {e}")
    return None

def process_articles(instance_url, paywall_hosts, dry_run=False):
    articles = get_unread_articles(instance_url)
    processed = 0
    for article in articles:
        article_url = article.get('url') or article.get('origin_url')
        if not article_url:
            continue
        hostname = urllib.parse.urlparse(article_url).hostname or ''
        if not any(hostname.endswith(h) for h in paywall_hosts):
            continue
        reading_time = article.get('reading_time', 0)
        if reading_time is None or reading_time > 2:
            continue
        article_id = article.get('id')
        processed += 1
        logging.info(f"Attempting to find archive for paywalled article {article_url} (ID {article_id})")
        archive_url = get_existing_archive(article_url)
        if not archive_url:
            logging.info("No existing archive found, submitting to archive.is")
            archive_url = submit_to_archive(article_url)
        if not archive_url:
            logging.warning(f"Failed to archive {article_url}")
            continue
        logging.info(f"Archived version found: {archive_url}")
        if not dry_run:
            if add_article_to_wallabag(instance_url, archive_url, tags_list=['archived']):
                new_articles = get_unread_articles(instance_url)
                new_item = next((a for a in new_articles if a.get('url') == archive_url or a.get('origin_url') == archive_url), None)
                if new_item and new_item.get('reading_time', 0) > 2:
                    delete_article_from_wallabag(instance_url, article_id)
        else:
            logging.info(f"DRY RUN: Would add {archive_url} and potentially delete ID {article_id}")
    logging.info(f"Processed {processed} paywalled articles")

def main():
    parser = argparse.ArgumentParser(description="Replace paywalled articles in Wallabag with archived versions")
    parser.add_argument("--instance-url", default=os.getenv("WALLABAG_INSTANCE_URL", "https://app.wallabag.it"), help="URL of Wallabag instance")
    parser.add_argument("--client-id", default=os.getenv("WALLABAG_CLIENT_ID"), help="Wallabag client ID")
    parser.add_argument("--client-secret", default=os.getenv("WALLABAG_CLIENT_SECRET"), help="Wallabag client secret")
    parser.add_argument("--username", default=os.getenv("WALLABAG_USERNAME"), help="Wallabag username")
    parser.add_argument("--password", default=os.getenv("WALLABAG_PASSWORD"), help="Wallabag password")
    parser.add_argument("--paywalled-sites", help="Comma separated list of paywalled hostnames", default=os.getenv("PAYWALLED_SITES"))
    parser.add_argument("--dry-run", action="store_true", help="Run without modifying Wallabag")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    paywall_hosts = DEFAULT_PAYWALLED_HOSTS
    if args.paywalled_sites:
        paywall_hosts = [h.strip() for h in args.paywalled_sites.split(',') if h.strip()]
    logging.info(f"Using paywalled hosts list: {paywall_hosts}")
    get_wallabag_token(args.instance_url, args.client_id, args.client_secret, args.username, args.password)
    if not WALLABAG_TOKEN:
        logging.error("Authentication failed")
        return
    process_articles(args.instance_url, paywall_hosts, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
