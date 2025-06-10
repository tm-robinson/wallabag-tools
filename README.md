# Wallabag Article Labeler

This script connects to a Wallabag instance, fetches all articles, and identifies articles that are potentially 'broken'. An article is considered broken if it meets one or more of the following criteria:
- It has zero pages (based on the `pages` field in the API response).
- Its file size is less than 10KB (based on the `size` field in the API response, assumed to be in bytes).
- Its reading time is zero minutes (based on the `reading_time` field in the API response).

Identified articles will be tagged with the label 'broken'.

## Prerequisites

- Python 3.6+
- `requests` library
- `python-dotenv` library

Install required libraries:
```bash
pip install requests python-dotenv
```
Alternatively, if a `requirements.txt` file is present:
```bash
pip install -r requirements.txt
```

- A Wallabag instance and API credentials.

## Wallabag API Credentials

To use this script, you need to create API client credentials in your Wallabag instance:
1. Log in to your Wallabag instance.
2. Go to `Developer` -> `Create a new client`.
3. Fill in a `Client name` (e.g., "Article Labeler Script").
4. The `Client URI` can be a placeholder like `http://localhost`.
5. After creation, you will receive a `Client ID` and `Client secret`. Keep these safe.

## Configuration

You can configure the script using command-line arguments or a `.env` file.

### Using a `.env` file (Recommended for credentials)

Create a file named `.env` in the same directory as the script with the following content:

```env
WALLABAG_INSTANCE_URL=https://your.wallabag.instance.com
WALLABAG_CLIENT_ID=your_client_id_here
WALLABAG_CLIENT_SECRET=your_client_secret_here
WALLABAG_USERNAME=your_wallabag_username
WALLABAG_PASSWORD=your_wallabag_password
```

Replace the placeholder values with your actual Wallabag details.

### Configuration Precedence

The script uses the following order of precedence for configuration values:
1. Command-line arguments (highest precedence)
2. Values from the `.env` file
3. Default values (lowest precedence, e.g., for instance URL)

## Usage

Run the script from your terminal:

```bash
python wallabag_labeler.py [OPTIONS]
```

### Arguments

- `--instance-url URL`: The full URL of your Wallabag instance.
  - Default (if not provided via CLI or `.env`): `https://app.wallabag.it`
  - Environment variable: `WALLABAG_INSTANCE_URL`
- `--client-id ID`: Your Wallabag API client ID.
  - Environment variable: `WALLABAG_CLIENT_ID`
- `--client-secret SECRET`: Your Wallabag API client secret.
  - Environment variable: `WALLABAG_CLIENT_SECRET`
- `--username USER`: Your Wallabag username.
  - Environment variable: `WALLABAG_USERNAME`
- `--password PASS`: Your Wallabag password.
  - Environment variable: `WALLABAG_PASSWORD`
- `--dry-run`: (Optional) If provided, the script will identify and report broken articles but will not make any changes (i.e., will not add the 'broken' tag).
- `--verbose` or `-v`: (Optional) Enable verbose logging, which includes DEBUG level messages. This can be helpful for troubleshooting.

If credential arguments (`--client-id`, `--client-secret`, `--username`, `--password`) are not provided on the command line, the script will attempt to load them from the `.env` file. The `--instance-url` will also be loaded from `.env` if not specified on the command line, and if not in `.env` either, it will default to `https://app.wallabag.it`.

### Example

Using command-line arguments:
```bash
python wallabag_labeler.py --instance-url https://my.wallabag.server                            --client-id 'my_client_id'                            --client-secret 'my_client_secret'                            --username 'my_user'                            --password 'my_pass'
```

Using a `.env` file (and potentially overriding the instance URL via CLI):
```bash
# Assuming .env file is configured with credentials
python wallabag_labeler.py --instance-url https://another.wallabag.server
```

To perform a dry run (assuming `.env` is configured):
```bash
python wallabag_labeler.py --dry-run
```

## Notes on Article Fields

- The script currently assumes that the Wallabag API response for articles includes a `pages` field for the number of pages, a `size` field for the content size in bytes, and a `reading_time` field for the estimated reading time in minutes.
- If your Wallabag version or a custom theme uses different field names, or if these fields are not available for all article types, the script's ability to identify broken articles may be affected.
- The interpretation of "zero pages" or "zero reading time" can be ambiguous. Wallabag articles might not always have these fields populated accurately for all content types. The script relies on the presence and values of these fields as reported by the API.

## Disclaimer

Use this script at your own risk. Always perform a `--dry-run` first to understand what changes will be made. Ensure you have backups of your Wallabag data if you are concerned about accidental modifications.
```
