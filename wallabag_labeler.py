import requests
import json
import argparse
import logging
import os
from dotenv import load_dotenv

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
    except json.JSONDecodeError:
        logging.error(f"Error decoding token response: {response.text if response is not None else 'No response object'}")
        return None

def get_all_articles(instance_url):
    """ Fetches all articles from the Wallabag API. """
    global WALLABAG_TOKEN
    if not WALLABAG_TOKEN:
        logging.error("No API token available. Please authenticate first.")
        return []
    if not instance_url:
        logging.error("Instance URL is not configured. Cannot fetch articles.")
        return []

    articles_url = f"{instance_url.rstrip('/')}/api/entries.json"
    headers = {"Authorization": f"Bearer {WALLABAG_TOKEN}"}
    params = {"page": 1, "perPage": 50}
    all_articles = []
    page_num_requested = 0
    response = None

    logging.info(f"Starting to fetch articles from {instance_url}...")
    try:
        while True:
            page_num_requested +=1
            params["page"] = page_num_requested
            logging.debug(f"Fetching page {params['page']}...") # Changed to debug for less verbosity by default
            response = requests.get(articles_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if "_embedded" in data and "items" in data["_embedded"]:
                articles_on_page = data["_embedded"]["items"]
                if not articles_on_page and params["page"] == 1:
                    logging.info("No articles found on the first page.")
                    break
                if not articles_on_page:
                    logging.info(f"No more articles found on page {params['page']}. Expected if it's the last page.")
                    break

                all_articles.extend(articles_on_page)
                logging.info(f"Fetched {len(articles_on_page)} articles from page {params['page']}. Total fetched so far: {len(all_articles)}.")

                current_page_api = data.get("page")
                total_pages_api = data.get("pages")

                if current_page_api and total_pages_api and current_page_api < total_pages_api:
                    continue
                else:
                    logging.info("All pages fetched according to API pagination info.")
                    break
            else:
                logging.warning(f"No '_embedded' or 'items' key in API response on page {params['page']}, or no articles found.")
                break

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error fetching articles: {e}")
        if e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        else:
            logging.error("No response content from server.")
        return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error fetching articles: {e}")
        return []
    except json.JSONDecodeError:
        logging.error(f"Error decoding articles response: {response.text if response is not None else 'No response object'}")
        return []
    except KeyError as e:
        logging.error(f"Unexpected API response structure. Missing key: {e}")
        if 'data' in locals():
             logging.error(f"Response sample: {str(data)[:200]}")
        return []

    logging.info(f"Finished fetching articles. Total articles retrieved: {len(all_articles)} from {page_num_requested} API call(s)/page(s).")
    return all_articles

def label_broken_articles(instance_url, articles, dry_run=False):
    """ Filters articles and labels those that are considered 'broken'. """
    global WALLABAG_TOKEN
    if not WALLABAG_TOKEN:
        logging.error("No API token available for labeling. Please authenticate first.")
        return 0
    if not instance_url:
        logging.error("Instance URL is not configured. Cannot label articles.")
        return 0

    if not articles:
        logging.info("No articles to process.")
        return 0

    labeled_count = 0
    processed_count = 0
    headers = {"Authorization": f"Bearer {WALLABAG_TOKEN}", "Content-Type": "application/json"}

    logging.info(f"Processing {len(articles)} articles for instance {instance_url}...")
    for article in articles:
        processed_count += 1
        article_id = article.get("id")
        article_title = article.get("title", f"ID: {article_id}")

        if not article_id:
            logging.warning(f"Skipping article due to missing ID: {article_title}")
            continue

        page_count = article.get("pages")
        file_size_bytes = article.get("size")
        reading_time_minutes = article.get("reading_time") # Assuming this field exists

        is_broken = False
        reasons = [] # Collect multiple reasons

        if page_count == 0:
            is_broken = True
            reasons.append("zero pages")

        if file_size_bytes is not None and file_size_bytes < (10 * 1024): # 10KB
            is_broken = True
            reasons.append("filesize below 10KB")

        if reading_time_minutes == 0: # Check for zero reading time
            is_broken = True
            reasons.append("zero reading time")

        if is_broken:
            reason_str = ", ".join(reasons)
            logging.info(f"Article '{article_title}' (ID: {article_id}) identified as broken ({reason_str}).")
            if not dry_run:
                label_url = f"{instance_url.rstrip('/')}/api/entries/{article_id}/tags"
                payload = json.dumps({"tags": "broken"})
                response_label = None
                try:
                    response_label = requests.post(label_url, headers=headers, data=payload)
                    response_label.raise_for_status()
                    logging.info(f"  Successfully labeled article ID {article_id} as 'broken'.")
                    labeled_count += 1
                except requests.exceptions.HTTPError as e:
                    logging.error(f"  HTTP error labeling article ID {article_id}: {e}")
                    if e.response is not None:
                        logging.error(f"  Response content: {e.response.text}")
                    else:
                        logging.error("  No response content from server.")
                except requests.exceptions.RequestException as e:
                    logging.error(f"  Request error labeling article ID {article_id}: {e}")
                except json.JSONDecodeError:
                    logging.error(f"  Error decoding labeling response for article ID {article_id}: {response_label.text if response_label is not None else 'No response object'}")
            else:
                logging.info(f"  DRY RUN: Would label article ID {article_id} as 'broken'.")
                labeled_count +=1

        if processed_count > 0 and processed_count % 100 == 0 and processed_count < len(articles):
            logging.info(f"Processed {processed_count}/{len(articles)} articles...")

    logging.info(f"Finished processing articles. Identified {labeled_count} broken articles out of {len(articles)} processed.")
    return labeled_count

def main():
    # Global keyword is not needed here for WALLABAG_TOKEN as we are passing it to functions
    # or functions are accessing the global var directly.
    # The main change is that get_wallabag_token will set the global WALLABAG_TOKEN.

    parser = argparse.ArgumentParser(description="Label broken articles in Wallabag.")

    parser.add_argument("--instance-url", default=os.getenv("WALLABAG_INSTANCE_URL", "https://app.wallabag.it"), help="URL of the Wallabag instance. Defaults to env WALLABAG_INSTANCE_URL or https://app.wallabag.it")
    parser.add_argument("--client-id", default=os.getenv("WALLABAG_CLIENT_ID"), help="Client ID for the Wallabag API. Defaults to env WALLABAG_CLIENT_ID")
    parser.add_argument("--client-secret", default=os.getenv("WALLABAG_CLIENT_SECRET"), help="Client Secret for the Wallabag API. Defaults to env WALLABAG_CLIENT_SECRET")
    parser.add_argument("--username", default=os.getenv("WALLABAG_USERNAME"), help="Wallabag username. Defaults to env WALLABAG_USERNAME")
    parser.add_argument("--password", default=os.getenv("WALLABAG_PASSWORD"), help="Wallabag password. Defaults to env WALLABAG_PASSWORD")

    parser.add_argument("--dry-run", action="store_true", help="Run the script without making any changes to Wallabag articles.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging (DEBUG level).")

    args = parser.parse_args()

    instance_url = args.instance_url
    client_id = args.client_id
    client_secret = args.client_secret
    username = args.username
    password = args.password

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled.")

    logging.info("Script starting...")
    if args.dry_run:
        logging.info("DRY RUN mode enabled. No changes will be made to Wallabag.")

    missing_creds = []
    if not client_id: missing_creds.append("Client ID (WALLABAG_CLIENT_ID or --client-id)")
    if not client_secret: missing_creds.append("Client Secret (WALLABAG_CLIENT_SECRET or --client-secret)")
    if not username: missing_creds.append("Username (WALLABAG_USERNAME or --username)")
    if not password: missing_creds.append("Password (WALLABAG_PASSWORD or --password)")
    if not instance_url: missing_creds.append("Instance URL (WALLABAG_INSTANCE_URL or --instance-url)")


    if missing_creds:
        logging.error("Missing required configuration:")
        for cred in missing_creds:
            logging.error(f"  - {cred}")
        logging.error("Please provide them via CLI arguments or a .env file. Exiting.")
    else:
        logging.info(f"Using Wallabag instance URL: {instance_url}")

        # get_wallabag_token sets the global WALLABAG_TOKEN
        get_wallabag_token(instance_url, client_id, client_secret, username, password)

        if WALLABAG_TOKEN: # Check if the global token was successfully set
            articles = get_all_articles(instance_url)

            if articles is not None:
                labeled_count = label_broken_articles(instance_url, articles, dry_run=args.dry_run)

                if args.dry_run:
                    logging.info(f"DRY RUN COMPLETE: Identified {labeled_count} articles that would be labeled 'broken'.")
                else:
                    logging.info(f"Processing complete. Labeled {labeled_count} articles as 'broken'.")
            else:
                logging.error("Failed to fetch articles or no articles found (function returned None). Cannot proceed with labeling.")
        else:
            logging.error("Authentication failed. Please check your credentials and instance URL. Exiting.")

    logging.info("Script finished.")

if __name__ == "__main__":
    main()
```
