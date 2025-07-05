# Wallabag Utilities: Labeler and RSS Importer

This project provides a suite of Python scripts to help manage your Wallabag instance. Currently, it includes three main utilities:
1.  **Wallabag Article Labeler (`wallabag_labeler.py`)**: Identifies and tags 'broken' or 'old'/'very-old' articles in your Wallabag instance.
2.  **Wallabag RSS Importer (`wallabag_rss_importer.py`)**: Fetches new articles from specified RSS feeds and adds them to your Wallabag instance.
3.  **Paywalled Article Archiver (`wallabag_paywall_archiver.py`)**: Replaces short paywalled articles with archived versions from archive.is.

## Common Setup

The following setup instructions apply to both scripts.

### Prerequisites

- Python 3.6+
- Required Python libraries are listed in `requirements.txt`. These include `requests`, `python-dotenv`, `feedparser` (for the RSS importer), and `python-dateutil`.

Install required libraries using `requirements.txt`:
```bash
pip install -r requirements.txt
```

- A Wallabag instance and API credentials.

### Wallabag API Credentials

To use these scripts, you need to create API client credentials in your Wallabag instance:
1.  Log in to your Wallabag instance.
2.  Go to `Developer` -> `Create a new client`.
3.  Fill in a `Client name` (e.g., "Wallabag Scripts").
4.  The `Client URI` can be a placeholder like `http://localhost`.
5.  After creation, you will receive a `Client ID` and `Client secret`. Keep these safe.

### Configuration using `.env` file (Recommended)

Both scripts can be configured using a `.env` file for common settings, especially credentials. Create a file named `.env` in the same directory as the scripts with the following content:

```env
WALLABAG_INSTANCE_URL=https://your.wallabag.instance.com
WALLABAG_CLIENT_ID=your_client_id_here
WALLABAG_CLIENT_SECRET=your_client_secret_here
WALLABAG_USERNAME=your_wallabag_username
WALLABAG_PASSWORD=your_wallabag_password
```
Replace the placeholder values with your actual Wallabag details.

### Configuration Precedence

For shared arguments (like Wallabag credentials), the scripts use the following order of precedence:
1.  Command-line arguments (highest precedence)
2.  Values from the `.env` file
3.  Default values (lowest precedence, e.g., for instance URL)

---

## Wallabag Article Labeler (`wallabag_labeler.py`)

This script connects to your Wallabag instance, fetches all articles, and applies labels based on defined criteria.

**Features:**
-   **Broken Article Tagging**: Identifies articles that are potentially 'broken' (e.g., zero pages, small file size, zero reading time) and tags them with 'broken'.
-   **Old/Very-Old Article Tagging**: Tags articles older than 3 months as 'old' and articles older than 1 year as 'very-old'.

### Usage: `wallabag_labeler.py`

```bash
python wallabag_labeler.py [OPTIONS]
```

#### Arguments for `wallabag_labeler.py`:

-   `--instance-url URL`: The full URL of your Wallabag instance.
    -   Default (if not provided via CLI or `.env`): `https://app.wallabag.it`
    -   Environment variable: `WALLABAG_INSTANCE_URL`
-   `--client-id ID`: Your Wallabag API client ID.
    -   Environment variable: `WALLABAG_CLIENT_ID`
-   `--client-secret SECRET`: Your Wallabag API client secret.
    -   Environment variable: `WALLABAG_CLIENT_SECRET`
-   `--username USER`: Your Wallabag username.
    -   Environment variable: `WALLABAG_USERNAME`
-   `--password PASS`: Your Wallabag password.
    -   Environment variable: `WALLABAG_PASSWORD`
-   `--dry-run`: (Optional) If provided, the script will identify and report articles but will not make any changes (i.e., will not add tags).
-   `--verbose` or `-v`: (Optional) Enable verbose logging (DEBUG level).

#### Example: `wallabag_labeler.py`

Using command-line arguments:
```bash
python wallabag_labeler.py --instance-url https://my.wallabag.server \
                           --client-id 'my_client_id' \
                           --client-secret 'my_client_secret' \
                           --username 'my_user' \
                           --password 'my_pass'
```

Using a `.env` file for credentials:
```bash
# Assuming .env file is configured
python wallabag_labeler.py
```

To perform a dry run (assuming `.env` is configured):
```bash
python wallabag_labeler.py --dry-run
```

### Notes on Article Fields (for `wallabag_labeler.py`)

-   The script's labeling logic assumes that the Wallabag API response for articles includes:
    -   `pages`: Number of pages.
    -   `size`: Content size in bytes.
    -   `reading_time`: Estimated reading time in minutes.
    -   `created_at`: Article's creation date (ISO 8601 format).
-   Discrepancies in these field names or formats in your Wallabag instance might affect labeling accuracy.
-   The interpretation of "zero pages" or "zero reading time" can be ambiguous.
-   The `created_at` field is crucial for old/very-old tagging. Verify its name and format if issues arise.

---

## Wallabag RSS Importer (`wallabag_rss_importer.py`)

This script fetches new articles from a list of specified RSS/Atom feeds and adds them to your Wallabag instance.

**Features:**
-   Imports articles published within the last 30 days (by default).
-   Tags newly imported articles with "rss" (by default).

### Configuration for RSS Feeds (for `wallabag_rss_importer.py`)

The list of RSS feeds to process is defined in a plain text file. By default, the script looks for `rss_feeds.txt` in its directory.
-   Each line in the file should be a valid URL to an RSS or Atom feed.
-   Lines starting with a `#` (hash symbol) are treated as comments and ignored.
-   Empty lines are also ignored.

**Example `rss_feeds.txt`:**
```txt
# My Favorite News Feeds
http://example.com/news.xml
https://blog.example.org/feed.rss

# Tech Blogs
# http://tech.example.dev/commented_out.xml
http://another.tech.blog/atom.xml
```

### Usage: `wallabag_rss_importer.py`

```bash
python wallabag_rss_importer.py [OPTIONS]
```

#### Arguments for `wallabag_rss_importer.py`:

-   `--instance-url URL`: (Shared with Labeler - see Common Setup)
-   `--client-id ID`: (Shared with Labeler - see Common Setup)
-   `--client-secret SECRET`: (Shared with Labeler - see Common Setup)
-   `--username USER`: (Shared with Labeler - see Common Setup)
-   `--password PASS`: (Shared with Labeler - see Common Setup)
-   `--rss-feeds-file FILEPATH`: Path to the text file containing RSS feed URLs.
    -   Default: `rss_feeds.txt`
-   `--dry-run`: (Optional) If provided, the script will identify articles to add but will not actually add them to Wallabag.
-   `--verbose` or `-v`: (Optional) Enable verbose logging (DEBUG level).

#### Example: `wallabag_rss_importer.py`

Assuming `.env` is configured with credentials and `rss_feeds.txt` exists in the default location:
```bash
python wallabag_rss_importer.py
```

Using a specific feed file path and performing a dry run:
```bash
python wallabag_rss_importer.py --rss-feeds-file ./config/my_personal_feeds.txt --dry-run
```

---

## Paywalled Article Archiver (`wallabag_paywall_archiver.py`)

This tool searches your unread list for short articles from paywalled sites. If an archived version exists on `archive.is`, it adds that to Wallabag and removes the original.

### Usage

```bash
python wallabag_paywall_archiver.py [OPTIONS]
```

#### Key Options

- `--paywalled-sites` &mdash; comma separated hostnames treated as paywalled. Defaults to common sites like `wsj.com` and `ft.com`.
- `--dry-run` &mdash; perform a trial run without modifying Wallabag.
- `--verbose` or `-v` &mdash; enable verbose logging.

---

## Disclaimer

Use these scripts at your own risk. Always perform a `--dry-run` first to understand what changes will be made, especially with the `wallabag_labeler.py` script. Ensure you have backups of your Wallabag data if you are concerned about accidental modifications.
