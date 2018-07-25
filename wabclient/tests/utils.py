import responses
import mock
import contextlib
import tempfile
import json

from six.moves import urllib_parse


class WhatsAppTestClientMixin(object):

    def expectGet(self, oauth_token, url, response={}):
        fake = mock.MagicMock()

        def callback(request):
            self.assertEqual(
                request.headers['Authorization'],
                'Bearer %s' % (oauth_token,))
            fake(oauth_token, url)
            return (
                200,
                {'Content-Type': 'application/json'},
                json.dumps(response))

        responses.add_callback(
            responses.GET,
            urllib_parse.urljoin(self.BASE_URL, url),
            callback=callback, content_type='application/json')

        self.addCleanup(fake.assert_called_once_with, oauth_token, url)

    def expectCommand(self, oauth_token, url, command, response={},
                      status_code=200):

        fake = mock.MagicMock()

        def callback(request):
            found_payload = json.loads(request.body)
            self.assertEqual(found_payload, command.render())
            self.assertEqual(
                request.headers['Authorization'],
                'Bearer %s' % (oauth_token,))
            fake(oauth_token, url, command, response)
            return (
                status_code,
                {'Content-Type': 'application/json'},
                json.dumps(response))

        responses.add_callback(
            command.command_method,
            urllib_parse.urljoin(self.BASE_URL, url),
            callback=callback, content_type='application/json')

        self.addCleanup(
            fake.assert_called_once_with,
            oauth_token, url, command, response)

    def expectUpload(self, oauth_token, path, content_type, response={}):

        fake = mock.MagicMock()

        def callback(request):
            print(request.url)
            print(request.headers)
            self.assertEqual(
                request.headers['Authorization'],
                'Bearer %s' % (oauth_token,))
            self.assertEqual(
                request.headers['Content-Type'],
                content_type)
            fake(oauth_token, path, content_type)
            return (
                200,
                {'Content-Type': 'application/json'},
                json.dumps(response))

        responses.add_callback(
            responses.POST,
            urllib_parse.urljoin(self.BASE_URL, path),
            callback=callback,
            content_type='application/json')
        return self.addCleanup(
            fake.assert_called_once_with,
            oauth_token, path, content_type)

    def expectMediaUpload(self, oauth_token, content_type, media_id):

        fake = mock.MagicMock()

        def callback(request):
            self.assertEqual(
                request.headers['Authorization'],
                'Bearer %s' % (oauth_token,))
            self.assertEqual(
                request.headers['Content-Type'],
                content_type)
            fake(oauth_token, content_type, media_id)
            return (
                200,
                {'Content-Type': 'application/json'},
                json.dumps({
                    'media': [{
                        'id': media_id,
                    }]
                }))

        responses.add_callback(
            responses.POST,
            urllib_parse.urljoin(self.BASE_URL, '/v1/media'),
            callback=callback,
            content_type='application/json')
        return self.addCleanup(
            fake.assert_called_once_with,
            oauth_token, content_type, media_id)

    @contextlib.contextmanager
    def mk_tempfile(self, suffix='.txt', content=None):
        fp = tempfile.NamedTemporaryFile(suffix='.txt')
        fp.write(content or 'this is content'.encode('utf8'))
        fp.seek(0)
        yield fp
        fp.close()
