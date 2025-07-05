import unittest
from unittest.mock import patch, MagicMock
import requests
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

    @patch('wallabag_paywall_archiver.delete_article_from_wallabag')
    @patch('wallabag_paywall_archiver.add_article_to_wallabag')
    @patch('wallabag_paywall_archiver.submit_to_archive')
    @patch('wallabag_paywall_archiver.get_existing_archive')
    @patch('wallabag_paywall_archiver.get_unread_articles')
    def test_process_articles_replaces_and_deletes(self, mock_get_unread, mock_get_archive, mock_submit, mock_add, mock_delete):
        mock_get_unread.side_effect = [
            [{'id': 1, 'url': 'http://wsj.com/a', 'reading_time': 1}],
            [{'id': 1, 'url': 'http://wsj.com/a', 'reading_time': 1}, {'id': 2, 'url': 'https://archive.is/abcd', 'reading_time': 5}]
        ]
        mock_get_archive.return_value = None
        mock_submit.return_value = 'https://archive.is/abcd'
        mock_add.return_value = True
        wallabag_paywall_archiver.process_articles('http://bag', ['wsj.com'], reading_threshold=2, dry_run=False)
        mock_add.assert_called_once_with('http://bag', 'https://archive.is/abcd', tags_list=['archived'])
        mock_delete.assert_called_once_with('http://bag', 1)

    @patch('wallabag_paywall_archiver.delete_article_from_wallabag')
    @patch('wallabag_paywall_archiver.add_article_to_wallabag')
    @patch('wallabag_paywall_archiver.submit_to_archive')
    @patch('wallabag_paywall_archiver.get_existing_archive')
    @patch('wallabag_paywall_archiver.get_unread_articles')
    def test_process_articles_no_delete_when_still_short(self, mock_get_unread, mock_get_archive, mock_submit, mock_add, mock_delete):
        mock_get_unread.side_effect = [
            [{'id': 1, 'url': 'http://ft.com/a', 'reading_time': 1}],
            [{'id': 1, 'url': 'http://ft.com/a', 'reading_time': 1}, {'id': 2, 'url': 'https://archive.is/abcd', 'reading_time': 1}]
        ]
        mock_get_archive.return_value = None
        mock_submit.return_value = 'https://archive.is/abcd'
        mock_add.return_value = True
        wallabag_paywall_archiver.process_articles('http://bag', ['ft.com'], reading_threshold=2, dry_run=False)
        mock_add.assert_called_once_with('http://bag', 'https://archive.is/abcd', tags_list=['archived'])
        mock_delete.assert_not_called()

class TestPaywallArchiverReal(unittest.TestCase):
    """Tests that contact the real archive.is service."""

    def setUp(self):
        try:
            resp = requests.get("https://archive.is", timeout=5)
            if resp.status_code >= 400:
                self.skipTest(f"archive.is returned status {resp.status_code}")
        except Exception as e:  # noqa: broad-except - network errors should skip
            self.skipTest(f"archive.is not reachable: {e}")

    def test_get_existing_archive_real(self):
        url = wallabag_paywall_archiver.get_existing_archive("http://example.com/")
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith("https://archive.is/"))

    def test_submit_to_archive_real(self):
        url = wallabag_paywall_archiver.submit_to_archive("http://example.com/")
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith("https://archive.is/"))

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
