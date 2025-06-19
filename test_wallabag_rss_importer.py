import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import argparse # For creating Namespace objects for mocking main if needed
from datetime import datetime, timedelta, timezone

# Imports for the module being tested and its dependencies
import wallabag_rss_importer
import feedparser # For mocking feedparser.parse output
# dateutil.parser might be needed if the main code uses it, or for constructing test dates
import dateutil.parser

class TestRSSFunctionality(unittest.TestCase):
    def setUp(self):
        # Reset WALLABAG_TOKEN before each test for isolation in the tested module
        wallabag_rss_importer.WALLABAG_TOKEN = None
        # Patch load_dotenv to prevent actual .env loading during these tests
        # Target the load_dotenv used by wallabag_rss_importer
        self.load_dotenv_patcher = patch('wallabag_rss_importer.load_dotenv')
        self.mock_load_dotenv = self.load_dotenv_patcher.start()
        self.test_token = "test_rss_token"
        self.instance_url = "http://fake-rss-instance.com"

    def tearDown(self):
        self.load_dotenv_patcher.stop()
        wallabag_rss_importer.WALLABAG_TOKEN = None # Clean up global state

    @patch("builtins.open", new_callable=mock_open, read_data="http://url1.com/feed\n# A comment\nhttp://url2.com/feed\n\nhttp://url3.com/feed")
    def test_load_rss_feeds_from_txt_success(self, mock_file_open):
        feeds = wallabag_rss_importer.load_rss_feeds_from_txt("dummy_path.txt")
        self.assertEqual(feeds, ["http://url1.com/feed", "http://url2.com/feed", "http://url3.com/feed"])
        mock_file_open.assert_called_once_with("dummy_path.txt", 'r')

    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    def test_load_rss_feeds_from_txt_file_not_found(self, mock_file_open):
        feeds = wallabag_rss_importer.load_rss_feeds_from_txt("nonexistent.txt")
        self.assertEqual(feeds, [])
        mock_file_open.assert_called_once_with("nonexistent.txt", 'r')

    @patch('wallabag_rss_importer.feedparser.parse')
    def test_fetch_articles_from_feed_success(self, mock_feedparser_parse):
        mock_feed = MagicMock()
        mock_feed.bozo = 0
        mock_entry1 = MagicMock()
        mock_entry1.link = 'http://example.com/article1'
        mock_entry1.published = '2023-01-01T12:00:00Z'
        # Simulate .get() behavior for mock_entry1
        def side_effect_for_entry1(key, default=None):
            if key == 'published': return mock_entry1.published
            if key == 'link': return mock_entry1.link
            # Add other attributes if entry.get is used for them
            return default
        mock_entry1.get.side_effect = side_effect_for_entry1

        mock_entry2 = MagicMock()
        mock_entry2.link = 'http://example.com/article2'
        mock_entry2.published = None # Test fallback to 'updated'
        mock_entry2.updated = '2023-01-02T12:00:00Z'
        def side_effect_for_entry2(key, default=None):
            if key == 'published': return mock_entry2.published
            if key == 'updated': return mock_entry2.updated
            if key == 'link': return mock_entry2.link
            return default
        mock_entry2.get.side_effect = side_effect_for_entry2

        mock_feed.entries = [mock_entry1, mock_entry2]
        mock_feedparser_parse.return_value = mock_feed

        articles = wallabag_rss_importer.fetch_articles_from_feed("http://testfeed.com/rss")
        expected_articles = [
            {'url': 'http://example.com/article1', 'published_date': '2023-01-01T12:00:00Z'},
            {'url': 'http://example.com/article2', 'published_date': '2023-01-02T12:00:00Z'}
        ]
        self.assertEqual(articles, expected_articles)
        mock_feedparser_parse.assert_called_once_with("http://testfeed.com/rss")

    @patch('wallabag_rss_importer.feedparser.parse')
    def test_fetch_articles_from_feed_parser_bozo_error(self, mock_feedparser_parse):
        mock_feed = MagicMock()
        mock_feed.bozo = 1
        mock_feed.bozo_exception = feedparser.FeedParserError("Test feed error")
        mock_feed.entries = []
        mock_feedparser_parse.return_value = mock_feed
        with patch('wallabag_rss_importer.logging.warning') as mock_log_warning:
            articles = wallabag_rss_importer.fetch_articles_from_feed("http://brokenfeed.com/rss")
            self.assertEqual(articles, [])
            mock_log_warning.assert_called_once()
            self.assertIn("Test feed error", mock_log_warning.call_args[0][0])

    @patch('wallabag_rss_importer.feedparser.parse', side_effect=Exception("Generic feedparser error"))
    def test_fetch_articles_from_feed_generic_exception(self, mock_feedparser_parse):
        with patch('wallabag_rss_importer.logging.error') as mock_log_error:
            articles = wallabag_rss_importer.fetch_articles_from_feed("http://exceptionfeed.com/rss")
            self.assertEqual(articles, [])
            mock_log_error.assert_called_once()
            self.assertIn("Generic feedparser error", mock_log_error.call_args[0][0])

    def test_is_recent_article(self):
        now = datetime.now(timezone.utc)
        recent_date_str_1 = (now - timedelta(days=1)).isoformat()
        recent_date_str_29 = (now - timedelta(days=29)).isoformat()
        recent_date_str_30 = (now - timedelta(days=30)).isoformat()
        old_date_str_31 = (now - timedelta(days=31)).isoformat()
        naive_recent_str = (datetime.utcnow() - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%S")
        future_date_str = (now + timedelta(days=5)).isoformat()
        invalid_date_str = "not a real date"

        self.assertTrue(wallabag_rss_importer.is_recent_article(recent_date_str_1, days=30))
        self.assertTrue(wallabag_rss_importer.is_recent_article(recent_date_str_29, days=30))
        self.assertTrue(wallabag_rss_importer.is_recent_article(recent_date_str_30, days=30))
        self.assertFalse(wallabag_rss_importer.is_recent_article(old_date_str_31, days=30))
        self.assertTrue(wallabag_rss_importer.is_recent_article(naive_recent_str, days=30))
        self.assertFalse(wallabag_rss_importer.is_recent_article(future_date_str, days=30))

        with patch('wallabag_rss_importer.logging.error') as mock_log_error:
            self.assertFalse(wallabag_rss_importer.is_recent_article(invalid_date_str, days=30))
            mock_log_error.assert_called_once()

        self.assertFalse(wallabag_rss_importer.is_recent_article(None, days=30))
        self.assertFalse(wallabag_rss_importer.is_recent_article("", days=30))

    @patch('wallabag_rss_importer.requests.post')
    def test_add_article_to_wallabag_success(self, mock_requests_post):
        wallabag_rss_importer.WALLABAG_TOKEN = self.test_token
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        article_url = "http://newarticle.com/article"
        tags = ["rss", "test"]

        result = wallabag_rss_importer.add_article_to_wallabag(self.instance_url, article_url, tags_list=tags)
        self.assertTrue(result)
        expected_payload = {"url": article_url, "tags": "rss,test"}
        expected_headers = {
            "Authorization": f"Bearer {self.test_token}",
            "Content-Type": "application/json"
        }
        mock_requests_post.assert_called_once_with(
            f"{self.instance_url.rstrip('/')}/api/entries.json",
            headers=expected_headers,
            json=expected_payload
        )

    @patch('wallabag_rss_importer.requests.post')
    def test_add_article_to_wallabag_api_error(self, mock_requests_post):
        wallabag_rss_importer.WALLABAG_TOKEN = self.test_token
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        http_error = wallabag_rss_importer.requests.exceptions.HTTPError("Server Error")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_requests_post.return_value = mock_response

        with patch('wallabag_rss_importer.logging.error') as mock_log_error:
            result = wallabag_rss_importer.add_article_to_wallabag(self.instance_url, "http://newarticle.com/article")
            self.assertFalse(result)
            mock_requests_post.assert_called_once()
            self.assertTrue(any("HTTP error adding article" in str(call_args) for call_args in mock_log_error.call_args_list))

    @patch('wallabag_rss_importer.requests.post')
    def test_add_article_to_wallabag_no_token(self, mock_requests_post):
        wallabag_rss_importer.WALLABAG_TOKEN = None
        with patch('wallabag_rss_importer.logging.error') as mock_log_error:
            result = wallabag_rss_importer.add_article_to_wallabag(self.instance_url, "http://newarticle.com/article")
            self.assertFalse(result)
            mock_requests_post.assert_not_called()
            self.assertTrue(any("No API token available" in str(call_args) for call_args in mock_log_error.call_args_list))

    @patch('wallabag_rss_importer.requests.post')
    def test_add_article_to_wallabag_no_instance_url(self, mock_requests_post):
        wallabag_rss_importer.WALLABAG_TOKEN = self.test_token
        with patch('wallabag_rss_importer.logging.error') as mock_log_error:
            result = wallabag_rss_importer.add_article_to_wallabag(None, "http://newarticle.com/article")
            self.assertFalse(result)
            mock_requests_post.assert_not_called()
            self.assertTrue(any("Instance URL is not configured" in str(call_args) for call_args in mock_log_error.call_args_list))

    @patch('wallabag_rss_importer.requests.post')
    def test_add_article_to_wallabag_no_article_url(self, mock_requests_post):
        wallabag_rss_importer.WALLABAG_TOKEN = self.test_token
        with patch('wallabag_rss_importer.logging.error') as mock_log_error:
            result = wallabag_rss_importer.add_article_to_wallabag(self.instance_url, None)
            self.assertFalse(result)
            mock_requests_post.assert_not_called()
            self.assertTrue(any("No article URL provided" in str(call_args) for call_args in mock_log_error.call_args_list))

    # It would also be good to add tests for the main() function of wallabag_rss_importer.py
    # similar to how test_wallabag_labeler.py tests its main().
    # This would involve mocking args, get_token, load_rss_feeds_from_txt, etc.
    # For brevity in this example, these are omitted but recommended for full coverage.

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
