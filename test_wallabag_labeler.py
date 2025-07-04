import unittest
from unittest.mock import patch, MagicMock, mock_open
import os # Import os for environment variable manipulation
import wallabag_labeler # Import the script to be tested
import argparse # Import argparse to create Namespace objects for mocking

# Save the original os.getenv to restore it later if necessary, though patch.dict is cleaner
# _original_getenv = os.getenv

from datetime import datetime, timedelta


class TestWallabagLabeler(unittest.TestCase):

    def setUp(self):
        # Reset WALLABAG_TOKEN before each test for isolation
        wallabag_labeler.WALLABAG_TOKEN = None
        # Clear relevant environment variables before each test
        # Using patch.dict on os.environ allows control over environment variables for each test
        self.env_patcher = patch.dict(os.environ, {}, clear=True) # Start with an empty environment
        self.env_patcher.start()
        # Ensure load_dotenv is patched for all tests in this class to avoid actual .env loading
        self.load_dotenv_patcher = patch('wallabag_labeler.load_dotenv')
        self.mock_load_dotenv = self.load_dotenv_patcher.start()


    def tearDown(self):
        self.env_patcher.stop()
        self.load_dotenv_patcher.stop()
        wallabag_labeler.WALLABAG_TOKEN = None # Clean up global state

    @patch('wallabag_labeler.requests.post')
    def test_get_wallabag_token_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test_token"}
        mock_post.return_value = mock_response
        token = wallabag_labeler.get_wallabag_token("http://fake-instance.com", "cid", "csec", "user", "pass")
        self.assertEqual(token, "test_token")
        self.assertEqual(wallabag_labeler.WALLABAG_TOKEN, "test_token")

    @patch('wallabag_labeler.requests.post')
    def test_get_wallabag_token_failure_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        # Create an HTTPError instance and attach the mock_response to its response attribute
        http_error_instance = wallabag_labeler.requests.exceptions.HTTPError("Bad Request")
        http_error_instance.response = mock_response
        mock_response.raise_for_status.side_effect = http_error_instance
        mock_post.return_value = mock_response
        token = wallabag_labeler.get_wallabag_token("http://fake-instance.com", "cid", "csec", "user", "pass")
        self.assertIsNone(token)

    @patch('wallabag_labeler.requests.post')
    def test_get_wallabag_token_missing_credentials(self, mock_post):
        token = wallabag_labeler.get_wallabag_token(None, "cid", "csec", "user", "pass")
        self.assertIsNone(token)
        mock_post.assert_not_called()


    @patch('wallabag_labeler.requests.get')
    def test_get_all_articles_success_pagination(self, mock_get):
        wallabag_labeler.WALLABAG_TOKEN = "fake_token"
        mock_response_pg1 = MagicMock()
        mock_response_pg1.status_code = 200
        mock_response_pg1.json.return_value = {"page": 1, "pages": 2, "_embedded": {"items": [{"id": 1}]}}
        mock_response_pg2 = MagicMock()
        mock_response_pg2.status_code = 200
        mock_response_pg2.json.return_value = {"page": 2, "pages": 2, "_embedded": {"items": [{"id": 2}]}}
        mock_get.side_effect = [mock_response_pg1, mock_response_pg2]

        articles = wallabag_labeler.get_all_articles("http://fake-instance.com")
        self.assertEqual(len(articles), 2)
        self.assertEqual(mock_get.call_count, 2)

    @patch('wallabag_labeler.requests.get')
    def test_get_all_articles_no_token(self, mock_get):
        wallabag_labeler.WALLABAG_TOKEN = None
        articles = wallabag_labeler.get_all_articles("http://fake-instance.com")
        self.assertEqual(articles, [])
        mock_get.assert_not_called()

    @patch('wallabag_labeler.requests.get')
    def test_get_all_articles_http_error(self, mock_get):
        wallabag_labeler.WALLABAG_TOKEN = "fake_token"
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        http_error_instance = wallabag_labeler.requests.exceptions.HTTPError("Server Error")
        http_error_instance.response = mock_response
        mock_response.raise_for_status.side_effect = http_error_instance
        mock_get.return_value = mock_response
        articles = wallabag_labeler.get_all_articles("http://fake-instance.com")
        self.assertEqual(articles, [])


    @patch('wallabag_labeler.requests.post')
    def test_label_broken_articles_various_conditions(self, mock_post_label):
        wallabag_labeler.WALLABAG_TOKEN = "fake_token"
        articles_data = [
            {"id": 1, "title": "Broken by pages", "pages": 0, "size": 20000, "reading_time": 5},
            {"id": 2, "title": "Broken by size", "pages": 10, "size": 5000, "reading_time": 5},
            {"id": 3, "title": "Broken by reading_time", "pages": 10, "size": 20000, "reading_time": 0},
            {"id": 4, "title": "OK Article", "pages": 10, "size": 20000, "reading_time": 5},
            {"id": 5, "title": "Broken all conditions", "pages": 0, "size": 100, "reading_time": 0},
            {"id": 6, "title": "Article no ID"}, # No ID, should be skipped
            {"id": 7, "title": "OK (pages is None)", "pages": None, "size": 20000, "reading_time": 5},
            {"id": 8, "title": "OK (size is None)", "pages": 10, "size": None, "reading_time": 5},
            {"id": 9, "title": "OK (reading_time is None)", "pages": 10, "size": 20000, "reading_time": None},
            {"id": 10, "title": "Broken (size just under)", "pages": 1, "size": 10239, "reading_time": 1},
        ]
        mock_label_response = MagicMock()
        mock_label_response.status_code = 200
        mock_post_label.return_value = mock_label_response

        labeled_count = wallabag_labeler.label_broken_articles("http://fake-instance.com", articles_data, dry_run=False)

        # Expected labeled: 1, 2, 3, 5, 10
        self.assertEqual(labeled_count, 5)
        self.assertEqual(mock_post_label.call_count, 5)
        # Check one call as an example
        mock_post_label.assert_any_call(
            "http://fake-instance.com/api/entries/1/tags",
            headers={"Authorization": "Bearer fake_token", "Content-Type": "application/json"},
            data='{"tags": "broken"}'
        )

    @patch('wallabag_labeler.requests.post')
    def test_label_broken_articles_dry_run(self, mock_post_label):
        wallabag_labeler.WALLABAG_TOKEN = "fake_token"
        articles_data = [{"id": 1, "title": "Broken by pages", "pages": 0, "size": 20000, "reading_time": 5}]
        labeled_count = wallabag_labeler.label_broken_articles("http://fake-instance.com", articles_data, dry_run=True)
        self.assertEqual(labeled_count, 1)
        mock_post_label.assert_not_called()

    # Tests for main function, .env and CLI args precedence
    @patch('wallabag_labeler.get_wallabag_token')
    @patch('wallabag_labeler.get_all_articles')
    @patch('wallabag_labeler.label_broken_articles')
    @patch('argparse.ArgumentParser.parse_args') # Patch parse_args on the class used in wallabag_labeler
    def run_main_test(self, mock_parse_args, mock_label_articles, mock_get_all_articles, mock_get_token,
                      cli_args_dict, env_vars, expected_token_args,
                      expected_articles_url, expected_label_url, expect_label_call=True):

        # mock_get_token.return_value = "mock_token_val" # Original line
        # New side effect to simulate global WALLABAG_TOKEN being set
        def mock_get_token_side_effect(*args, **kwargs):
            wallabag_labeler.WALLABAG_TOKEN = "mock_token_val" # Simulate setting the global token
            return "mock_token_val"
        mock_get_token.side_effect = mock_get_token_side_effect

        mock_get_all_articles.return_value = [{"id":1, "pages":0, "size":100, "reading_time":0}]
        mock_label_articles.return_value = 1

        # Set up environment variables for this specific test run
        # patch.dict is used here directly rather than relying on setUp's self.env_patcher
        # if we need fine-grained control per run_main_test call.
        # However, for these tests, assuming self.env_patcher in setUp correctly clears and sets os.environ
        # for the duration of the test method calling run_main_test is also valid.
        # Here, we'll ensure env_vars are applied specifically for this execution context.
        with patch.dict(os.environ, env_vars, clear=True):
             # Mock CLI arguments returned by parse_args
            # argparse.Namespace is a simple way to create an object with attributes
            mock_parse_args.return_value = argparse.Namespace(**cli_args_dict)

            wallabag_labeler.main()

            mock_get_token.assert_called_once_with(*expected_token_args)
            if mock_get_token.return_value and expect_label_call:
                mock_get_all_articles.assert_called_once_with(expected_articles_url)
                mock_label_articles.assert_called_once_with(
                    expected_label_url,
                    mock_get_all_articles.return_value,
                    dry_run=cli_args_dict.get("dry_run", False)
                )
            elif not expect_label_call:
                mock_get_all_articles.assert_not_called()
                mock_label_articles.assert_not_called()


    def test_main_cli_args_only(self):
        cli_args = {
            "instance_url": "cli_url", "client_id": "cli_cid", "client_secret": "cli_csec",
            "username": "cli_user", "password": "cli_pass", "dry_run": False, "verbose": False
        }
        # No env vars for this test, self.env_patcher (from setUp) ensures os.environ is empty
        self.run_main_test(
            cli_args_dict=cli_args,
            env_vars={}, # Explicitly empty
            expected_token_args=("cli_url", "cli_cid", "cli_csec", "cli_user", "cli_pass"),
            expected_articles_url="cli_url",
            expected_label_url="cli_url"
        )

    def test_main_env_vars_only(self):
        env = {
            "WALLABAG_INSTANCE_URL": "env_url", "WALLABAG_CLIENT_ID": "env_cid",
            "WALLABAG_CLIENT_SECRET": "env_csec", "WALLABAG_USERNAME": "env_user",
            "WALLABAG_PASSWORD": "env_pass"
        }
        # When only .env vars are used, argparse defaults are used for CLI,
        # which then pick up .env values because os.getenv is part of the default value expression.
        # So, the Namespace object from parse_args will have these values.
        cli_args_for_parsing = {
            "instance_url": "env_url", "client_id": "env_cid", "client_secret": "env_csec",
            "username": "env_user", "password": "env_pass", "dry_run": False, "verbose": False
        }
        self.run_main_test(
            cli_args_dict=cli_args_for_parsing,
            env_vars=env,
            expected_token_args=("env_url", "env_cid", "env_csec", "env_user", "env_pass"),
            expected_articles_url="env_url",
            expected_label_url="env_url"
        )

    def test_main_cli_overrides_env(self):
        cli_args = {
            "instance_url": "cli_url", "client_id": "cli_cid", "client_secret": "cli_csec",
            "username": "cli_user", "password": "cli_pass", "dry_run": False, "verbose": False
        }
        env = { # These should be ignored because CLI provides values
            "WALLABAG_INSTANCE_URL": "env_url", "WALLABAG_CLIENT_ID": "env_cid",
            "WALLABAG_CLIENT_SECRET": "env_csec", "WALLABAG_USERNAME": "env_user",
            "WALLABAG_PASSWORD": "env_pass"
        }
        self.run_main_test(
            cli_args_dict=cli_args,
            env_vars=env,
            expected_token_args=("cli_url", "cli_cid", "cli_csec", "cli_user", "cli_pass"),
            expected_articles_url="cli_url",
            expected_label_url="cli_url"
        )

    def test_main_default_instance_url(self):
        # No instance_url in CLI (will use default from argparse) or env.
        # Other creds are provided to allow the script to proceed further.
        default_url = "https://app.wallabag.it"
        cli_args = {
            "instance_url": default_url, # This is what argparse provides when CLI doesn't specify and no .env for it
            "client_id": "cid", "client_secret": "csec",
            "username": "user", "password": "pass", "dry_run": True, "verbose": False
        }
        # Env vars provide other credentials
        env = {"WALLABAG_CLIENT_ID": "cid", "WALLABAG_CLIENT_SECRET": "csec",
               "WALLABAG_USERNAME": "user", "WALLABAG_PASSWORD": "pass"}
        self.run_main_test(
            cli_args_dict=cli_args,
            env_vars=env,
            expected_token_args=(default_url, "cid", "csec", "user", "pass"),
            expected_articles_url=default_url,
            expected_label_url=default_url
        )

    @patch('wallabag_labeler.logging.error') # Patch logging.error to check its calls
    @patch('argparse.ArgumentParser.parse_args')
    @patch('wallabag_labeler.get_wallabag_token') # To prevent actual token call
    def test_main_missing_required_credentials(self, mock_get_token, mock_parse_args, mock_logging_error):
        # Simulate missing client_id (neither in CLI nor .env)
        # self.env_patcher from setUp ensures a clean os.environ

        # argparse.Namespace will have client_id=None because its default is os.getenv which returns None
        # when WALLABAG_CLIENT_ID is not in the (cleared) environment.
        mock_parse_args.return_value = argparse.Namespace(
            instance_url="http://some.url", client_id=None, client_secret="some_secret",
            username="some_user", password="some_password", dry_run=False, verbose=False
        )

        wallabag_labeler.main()

        # Check that an error about missing credentials was logged
        self.assertTrue(any("Missing required configuration:" in call_args[0][0] for call_args in mock_logging_error.call_args_list))
        self.assertTrue(any("Client ID" in call_args[0][0] for call_args in mock_logging_error.call_args_list))
        mock_get_token.assert_not_called() # Should not attempt to get token


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)


class TestLabelOldArticles(unittest.TestCase):
    def setUp(self):
        """Set up for test methods."""
        # Set a dummy token for tests that require authentication
        wallabag_labeler.WALLABAG_TOKEN = "test_dummy_token"
        self.instance_url = "http://fake-instance.com"
        # It's good practice to also patch load_dotenv if your main script calls it globally,
        # to prevent .env files from interfering with tests.
        self.load_dotenv_patcher = patch('wallabag_labeler.load_dotenv')
        self.mock_load_dotenv = self.load_dotenv_patcher.start()

    def tearDown(self):
        """Clean up after test methods."""
        wallabag_labeler.WALLABAG_TOKEN = None # Reset global token
        self.load_dotenv_patcher.stop()

    @patch('wallabag_labeler.requests.post')
    def test_label_old_articles_identifies_old(self, mock_post):
        """Test that an old article is correctly identified and an API call is made."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None # Simulate successful post
        mock_post.return_value = mock_response

        now = datetime.utcnow()
        articles = [
            {"id": 1, "title": "Old Article", "created_at": (now - timedelta(days=100)).isoformat() + 'Z'},
            {"id": 2, "title": "New Article", "created_at": (now - timedelta(days=30)).isoformat() + 'Z'}
        ]

        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=False)

        self.assertEqual(labeled_count, 1)
        mock_post.assert_called_once_with(
            f"{self.instance_url}/api/entries/1/tags",
            headers={"Authorization": f"Bearer {wallabag_labeler.WALLABAG_TOKEN}", "Content-Type": "application/json"},
            data='{"tags": "old"}'
        )

    @patch('wallabag_labeler.requests.post')
    def test_label_old_articles_dry_run(self, mock_post):
        """Test dry_run mode identifies an old article but does not call API."""
        now = datetime.utcnow()
        articles = [
            {"id": 1, "title": "Old Article", "created_at": (now - timedelta(days=100)).isoformat() + 'Z'},
            {"id": 2, "title": "New Article", "created_at": (now - timedelta(days=30)).isoformat() + 'Z'}
        ]

        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=True)

        self.assertEqual(labeled_count, 1)
        mock_post.assert_not_called()

    @patch('wallabag_labeler.requests.post')
    def test_label_old_articles_no_old_articles(self, mock_post):
        """Test no API calls are made if no articles are old."""
        now = datetime.utcnow()
        articles = [
            {"id": 1, "title": "New Article 1", "created_at": (now - timedelta(days=30)).isoformat() + 'Z'},
            {"id": 2, "title": "New Article 2", "created_at": (now - timedelta(days=60)).isoformat() + 'Z'} # Still less than ~90 days
        ]

        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=False)

        self.assertEqual(labeled_count, 0)
        mock_post.assert_not_called()

    @patch('wallabag_labeler.requests.post')
    def test_label_old_articles_missing_created_at(self, mock_post):
        """Test articles with missing 'created_at' are skipped."""
        now = datetime.utcnow()
        articles = [
            {"id": 1, "title": "Missing Created At"},
            {"id": 2, "title": "Null Created At", "created_at": None},
            {"id": 3, "title": "Old Article", "created_at": (now - timedelta(days=100)).isoformat() + 'Z'}
        ]

        # Expect only article 3 to be processed for labeling
        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=True)
        self.assertEqual(labeled_count, 1) # Only the valid old article
        mock_post.assert_not_called() # Dry run

        # Test actual call for the valid one
        labeled_count_actual_run = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=False)
        self.assertEqual(labeled_count_actual_run, 1)
        mock_post.assert_called_once_with(
            f"{self.instance_url}/api/entries/3/tags",
            headers={"Authorization": f"Bearer {wallabag_labeler.WALLABAG_TOKEN}", "Content-Type": "application/json"},
            data='{"tags": "old"}'
        )

    @patch('wallabag_labeler.requests.post')
    def test_label_old_articles_bad_date_format(self, mock_post):
        """Test articles with invalid 'created_at' format are skipped."""
        now = datetime.utcnow()
        articles = [
            {"id": 1, "title": "Bad Date Format", "created_at": "not-a-date-string"},
            {"id": 2, "title": "Another Bad Format", "created_at": "2023/01/01"},
            {"id": 3, "title": "Old Article", "created_at": (now - timedelta(days=100)).isoformat() + 'Z'}
        ]

        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=True)
        self.assertEqual(labeled_count, 1) # Only the valid old article
        mock_post.assert_not_called() # Dry run

        labeled_count_actual_run = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=False)
        self.assertEqual(labeled_count_actual_run, 1)
        mock_post.assert_called_once_with(
            f"{self.instance_url}/api/entries/3/tags",
            headers={"Authorization": f"Bearer {wallabag_labeler.WALLABAG_TOKEN}", "Content-Type": "application/json"},
            data='{"tags": "old"}'
        )

    @patch('wallabag_labeler.requests.post')
    def test_label_old_articles_api_error_during_labeling(self, mock_post):
        """Test that if API call fails, the article is not counted as labeled."""
        now = datetime.utcnow()
        articles = [
            {"id": 1, "title": "Old Article", "created_at": (now - timedelta(days=100)).isoformat() + 'Z'}
        ]

        # Configure mock_post to raise an HTTPError
        mock_post.side_effect = wallabag_labeler.requests.exceptions.HTTPError("API Error")

        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=False)

        self.assertEqual(labeled_count, 0) # Labeling failed
        mock_post.assert_called_once() # Ensure it was attempted

    def test_label_old_articles_no_articles(self):
        """Test behavior with an empty list of articles."""
        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, [], dry_run=False)
        self.assertEqual(labeled_count, 0)

    def test_label_old_articles_no_token(self):
        """Test behavior when no API token is set."""
        wallabag_labeler.WALLABAG_TOKEN = None
        articles = [{"id": 1, "title": "Old Article", "created_at": (datetime.utcnow() - timedelta(days=100)).isoformat() + 'Z'}]
        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=False)
        self.assertEqual(labeled_count, 0)

    def test_label_old_articles_no_instance_url(self):
        """Test behavior when no instance_url is provided."""
        articles = [{"id": 1, "title": "Old Article", "created_at": (datetime.utcnow() - timedelta(days=100)).isoformat() + 'Z'}]
        labeled_count = wallabag_labeler.label_old_articles(None, articles, dry_run=False)
        self.assertEqual(labeled_count, 0)

    # Example of a date format that the function should handle (e.g. with +0000 timezone)
    @patch('wallabag_labeler.requests.post')
    def test_label_old_articles_handles_timezone_formats(self, mock_post):
        """Test handling of various ISO 8601 date formats."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        now = datetime.utcnow()
        three_months_ago_exact = now - timedelta(days=3*30) # Approximation used in main script

        articles = [
            {"id": 1, "title": "Old Article with Z", "created_at": (three_months_ago_exact - timedelta(days=1)).isoformat() + 'Z'},
            {"id": 2, "title": "Old Article with +00:00", "created_at": (three_months_ago_exact - timedelta(days=1)).isoformat() + "+00:00"},
            {"id": 3, "title": "Old Article with +0000", "created_at": (three_months_ago_exact - timedelta(days=1)).replace(microsecond=0).isoformat() + "+0000"}, # fromisoformat needs seconds
            {"id": 4, "title": "New Article with Z", "created_at": (now - timedelta(days=1)).isoformat() + 'Z'},
            # This date is tricky because fromisoformat in Python < 3.11 doesn't like "YYYY-MM-DDTHH:MM:SS-HHMM" without colon in offset
            # The implemented stripping logic should handle "YYYY-MM-DDTHH:MM:SS" before passing to fromisoformat if an offset is detected
            {"id": 5, "title": "Old Article with -05:00", "created_at": (three_months_ago_exact - timedelta(days=1)).isoformat() + "-05:00"},
        ]

        labeled_count = wallabag_labeler.label_old_articles(self.instance_url, articles, dry_run=False)

        self.assertEqual(labeled_count, 4) # Expect 1, 2, 3, 5 to be labeled
        self.assertEqual(mock_post.call_count, 4)
        mock_post.assert_any_call(f"{self.instance_url}/api/entries/1/tags", headers=unittest.mock.ANY, data='{"tags": "old"}')
        mock_post.assert_any_call(f"{self.instance_url}/api/entries/2/tags", headers=unittest.mock.ANY, data='{"tags": "old"}')
        mock_post.assert_any_call(f"{self.instance_url}/api/entries/3/tags", headers=unittest.mock.ANY, data='{"tags": "old"}')
        mock_post.assert_any_call(f"{self.instance_url}/api/entries/5/tags", headers=unittest.mock.ANY, data='{"tags": "old"}')

unittest.main(argv=['first-arg-is-ignored'], exit=False)

# TestRSSFunctionality class and its specific imports (json, feedparser, dateutil.parser, timezone) have been removed.
