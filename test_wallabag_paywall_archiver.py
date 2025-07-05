import unittest
from unittest.mock import patch, MagicMock
import wallabag_paywall_archiver

class TestPaywallArchiver(unittest.TestCase):
    @patch('wallabag_paywall_archiver.requests.get')
    def test_get_existing_archive_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {'Location': '/abcd'}
        mock_get.return_value = mock_response
        url = wallabag_paywall_archiver.get_existing_archive('http://example.com/article')
        self.assertEqual(url, 'https://archive.is/abcd')
        mock_get.assert_called_once_with('https://archive.is/newest/http://example.com/article', allow_redirects=False, timeout=15)

    @patch('wallabag_paywall_archiver.requests.get')
    def test_get_existing_archive_none(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_get.return_value = mock_response
        url = wallabag_paywall_archiver.get_existing_archive('http://example.com/article')
        self.assertIsNone(url)

    @patch('wallabag_paywall_archiver.requests.post')
    def test_submit_to_archive_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {'Location': '/abcd'}
        mock_post.return_value = mock_response
        url = wallabag_paywall_archiver.submit_to_archive('http://example.com/article')
        self.assertEqual(url, 'https://archive.is/abcd')
        mock_post.assert_called_once_with('https://archive.is/submit/', data={'url': 'http://example.com/article'}, allow_redirects=False, timeout=15)

    @patch('wallabag_paywall_archiver.requests.post')
    def test_submit_to_archive_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_post.return_value = mock_response
        url = wallabag_paywall_archiver.submit_to_archive('http://example.com/article')
        self.assertIsNone(url)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
