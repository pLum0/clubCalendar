from django.conf import settings
from django.test import Client, TestCase

from calendar_app.models import CalendarUser, Tag


def _url(path):
    if settings.SECRET_PATH:
        return f'/{settings.SECRET_PATH}{path}'
    return path


class LoginTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Test Team', color='#ff0000')

    def setUp(self):
        self.client = Client()
        self.url = _url('/login/')

    def test_login_creates_new_user(self):
        resp = self.client.post(self.url, {
            'name': 'Alice',
            'team_id': self.team.id,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['created'])
        self.assertEqual(data['name'], 'Alice')
        self.assertEqual(data['team'], 'Test Team')
        self.assertIn('calendar_user_id', resp.cookies)

    def test_login_returns_existing_user(self):
        user = CalendarUser.objects.create(name='Bob', team=self.team)
        resp = self.client.post(self.url, {
            'name': 'Bob',
            'team_id': self.team.id,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['created'])
        self.assertEqual(data['user_id'], user.id)

    def test_login_name_required(self):
        resp = self.client.post(self.url, {'team_id': self.team.id})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.json())

    def test_login_team_required(self):
        resp = self.client.post(self.url, {'name': 'Alice'})
        self.assertEqual(resp.status_code, 400)

    def test_login_invalid_team(self):
        resp = self.client.post(self.url, {'name': 'Alice', 'team_id': 99999})
        self.assertEqual(resp.status_code, 400)

    def test_login_non_numeric_team(self):
        resp = self.client.post(self.url, {'name': 'Alice', 'team_id': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_login_sets_language_cookie(self):
        resp = self.client.post(self.url, {
            'name': 'Alice',
            'team_id': self.team.id,
        })
        self.assertIn(settings.LANGUAGE_COOKIE_NAME, resp.cookies)

    def test_login_respects_existing_language_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'de'
        resp = self.client.post(self.url, {
            'name': 'Alice',
            'team_id': self.team.id,
        })
        self.assertEqual(resp.status_code, 200)
        user = CalendarUser.objects.get(name='Alice', team=self.team)
        self.assertEqual(user.language, 'de')

    def test_login_get_rejected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_same_name_different_team(self):
        team2 = Tag.objects.create(name='Team2', color='#00ff00')
        CalendarUser.objects.create(name='Alice', team=self.team)

        resp = self.client.post(self.url, {
            'name': 'Alice',
            'team_id': team2.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['created'])
        self.assertEqual(CalendarUser.objects.filter(name='Alice').count(), 2)


class UserPreferencesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    def test_get_user_preferences_with_cookie(self):
        from django.test import RequestFactory

        from calendar_app.views import get_user_preferences

        user = CalendarUser.objects.create(name='Alice', team=self.team)
        factory = RequestFactory()
        request = factory.get('/')
        request.COOKIES['calendar_user_id'] = str(user.id)
        prefs = get_user_preferences(request)
        self.assertEqual(prefs['calendar_user'], user)

    def test_get_user_preferences_invalid_cookie(self):
        from django.test import RequestFactory

        from calendar_app.views import get_user_preferences

        factory = RequestFactory()
        request = factory.get('/')
        request.COOKIES['calendar_user_id'] = '99999'
        prefs = get_user_preferences(request)
        self.assertIsNone(prefs['calendar_user'])

    def test_get_user_preferences_no_cookie(self):
        from django.test import RequestFactory

        from calendar_app.views import get_user_preferences

        factory = RequestFactory()
        request = factory.get('/')
        prefs = get_user_preferences(request)
        self.assertIsNone(prefs['calendar_user'])

    def test_preferred_tags_from_cookie(self):
        from django.test import RequestFactory

        from calendar_app.views import get_user_preferences

        factory = RequestFactory()
        request = factory.get('/')
        request.COOKIES['preferred_tags'] = 'Team1%2CTeam2'
        prefs = get_user_preferences(request)
        self.assertEqual(prefs['preferred_tags'], ['Team1', 'Team2'])

    def test_preferred_tags_empty(self):
        from django.test import RequestFactory

        from calendar_app.views import get_user_preferences

        factory = RequestFactory()
        request = factory.get('/')
        prefs = get_user_preferences(request)
        self.assertEqual(prefs['preferred_tags'], [])


class UpdateUserSettingsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    def setUp(self):
        self.client = Client()
        self.user = CalendarUser.objects.create(name='Alice', team=self.team)
        self.url = _url('/user/settings/')

    def test_update_ntfy_enabled(self):
        self.client.cookies['calendar_user_id'] = str(self.user.id)
        resp = self.client.post(self.url, {'ntfy_enabled': 'true'})
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.ntfy_enabled)

    def test_update_ntfy_server(self):
        self.client.cookies['calendar_user_id'] = str(self.user.id)
        resp = self.client.post(self.url, {'ntfy_enabled': 'true', 'ntfy_server': 'ntfy.sh'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('ntfy_url', data)

    def test_invalid_ntfy_server_rejected(self):
        self.client.cookies['calendar_user_id'] = str(self.user.id)
        resp = self.client.post(self.url, {'ntfy_server': 'evil.com'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.json())

    def test_update_language(self):
        self.client.cookies['calendar_user_id'] = str(self.user.id)
        resp = self.client.post(self.url, {'language': 'de'})
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, 'de')

    def test_not_logged_in(self):
        resp = self.client.post(self.url, {'ntfy_enabled': 'true'})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_user_cookie(self):
        self.client.cookies['calendar_user_id'] = '99999'
        resp = self.client.post(self.url, {'ntfy_enabled': 'true'})
        self.assertEqual(resp.status_code, 400)


class SavePreferencesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = _url('/preferences/')

    def test_save_preferred_tags(self):
        resp = self.client.post(self.url, {'preferred_tags': 'Team1,Team2'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('preferred_tags', resp.cookies)

    def test_get_rejected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)
