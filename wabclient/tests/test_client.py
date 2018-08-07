import responses
import json
import tempfile
import requests
import iso8601
from base64 import b64encode
from datetime import datetime
from unittest import TestCase
from wabclient.client import (
    Client, GroupManager, fail)
from wabclient.commands import (
    MediaCommand, TextCommand, BackupCommand, RestoreBackupCommand,
    ContactsCommand, RegistrationCommand, VerifyCommand, AboutCommand,
    ApplicationSettingsCommand, BusinessProfileCommand,
    CreateGroupCommand, UpdateGroupCommand, RevokeGroupInviteLink,
    AddGroupAdminCommand, RemoveGroupAdminCommand,
    RemoveGroupParticipantCommand, LeaveGroupCommand, HSMCommand,
    UpdatePasswordCommand, CreateUserCommand, SetShardingCommand,
    InitialPasswordCommand)
from wabclient.exceptions import AddressException
from wabclient.constants import (
    MESSAGE_TYPE_AUDIO, MESSAGE_TYPE_IMAGE, MESSAGE_TYPE_DOCUMENT,
    RECIPIENT_TYPE_GROUP)
from wabclient import exceptions
from wabclient.tests.utils import WhatsAppTestClientMixin


class WhatsAppClientTest(WhatsAppTestClientMixin, TestCase):

    BASE_URL = 'http://127.0.0.1:1234'

    def setUp(self):
        session = requests.Session()
        session.headers.update({
            'Authorization': 'Bearer token',
            'Content-Type': 'application/json',
        })
        self.client = Client(self.BASE_URL, session=session)


class ClientTest(WhatsAppClientTest):

    @responses.activate
    def test_client(self):
        self.assertTrue(self.client)
        self.assertIsInstance(self.client.groups, GroupManager)

    def test_failures(self):
        self.assertEqual(
            exceptions.RequestRateLimitingException,
            fail({'error': {'errorcode': 429}}).__class__)

        self.assertEqual(
            exceptions.ConcurrencyRateLimitingException,
            fail({'error': {'errorcode': 503}}).__class__)

    @responses.activate
    def test_send_audio(self):
        self.expectMediaUpload('token', 'audio/mpeg', 'the-media-id')
        self.expectCommand(
            'token',
            '/v1/messages',
            MediaCommand(
                to="to_addr",
                message_type=MESSAGE_TYPE_AUDIO,
                media_id='the-media-id',
            ))

        with self.mk_tempfile() as fp:
            self.client.send_audio(
                "to_addr", "audio.mp3", fp)

    @responses.activate
    def test_send_image(self):
        self.expectMediaUpload('token', 'image/jpeg', 'the-media-id')
        self.expectCommand(
            'token',
            '/v1/messages',
            MediaCommand(
                to="to_addr",
                message_type=MESSAGE_TYPE_IMAGE,
                media_id='the-media-id',
                caption="the caption"
            ))

        with self.mk_tempfile() as fp:
            self.client.send_image(
                "to_addr", "image.jpg", fp,
                "the caption")

    @responses.activate
    def test_send_document(self):
        self.expectMediaUpload('token', 'application/pdf', 'the-media-id')
        self.expectCommand(
            'token',
            '/v1/messages',
            MediaCommand(
                to="to_addr",
                message_type=MESSAGE_TYPE_DOCUMENT,
                media_id='the-media-id',
                caption="the caption",
            ))

        with self.mk_tempfile() as fp:
            self.client.send_document(
                "to_addr", "document.pdf", fp,
                "the caption")

    @responses.activate
    def test_send_hsm(self):
        self.expectCommand(
            'token',
            '/v1/messages',
            HSMCommand(
                to="to_addr",
                namespace="namespace",
                element_name="element_name",
                language_code="en",
                language_policy="fallback",
                localizable_params=[{"default": "10"}],
            ))

        self.client.send_hsm(
            "to_addr", namespace="namespace", element_name="element_name",
            language_code="en", params=[{"default": "10"}])

    @responses.activate
    def test_send_message(self):
        self.expectCommand(
            'token',
            '/v1/messages',
            TextCommand(
                to="to_addr",
                text="hello world",
                preview_url=False,
            ))

        self.client.send_message(
            "to_addr", "hello world")

    @responses.activate
    def test_send_message_with_url(self):
        self.expectCommand(
            'token',
            '/v1/messages',
            TextCommand(
                to="to_addr",
                text="the body https://www.example.org/",
                preview_url=True,
            ))

        self.client.send_message(
            "to_addr", "the body https://www.example.org/")

    @responses.activate
    def test_send_group_message(self):
        self.expectCommand(
            'token',
            '/v1/messages',
            TextCommand(
                to="group_addr",
                text="the body",
                recipient_type=RECIPIENT_TYPE_GROUP,
                render_mentions=True,
            ))

        self.client.send_message(
            "group_addr", "the body",
            recipient_type=Client.GROUP_RECIPIENT)

    @responses.activate
    def test_create_backup(self):
        self.expectCommand(
            'token',
            '/v1/settings/backup',
            BackupCommand('the-password'), {
                'settings': {
                    'data': 'foo'
                }
            })

        self.assertEqual(
            self.client.create_backup('the-password'), 'foo')

    @responses.activate
    def test_restore_backup(self):
        self.expectCommand(
            'token',
            '/v1/settings/restore',
            RestoreBackupCommand('the-password', 'foo'), {})

        self.assertEqual(
            self.client.restore_backup('the-password', 'foo'), {})

    @responses.activate
    def test_get_address_exists(self):
        self.expectCommand(
            'token',
            '/v1/contacts',
            ContactsCommand(
                contacts=['+27123456789'],
                blocking=ContactsCommand.WAIT),
            response={
                "contacts": [{
                    "input": "+27123456789",
                    "status": "valid",
                    "wa_id": "27123456789",
                }]
            }
        )

        self.assertEqual(
            self.client.get_address('+27123456789'), '27123456789')

    @responses.activate
    def test_request_code(self):
        self.expectCommand(
            'token',
            '/v1/account',
            RegistrationCommand(
                cc='27',
                phone_number='123456789',
                cert='vname',
                method=RegistrationCommand.SMS,
            ), {
                "account": [{
                    "vname": "vname"
                }]
            })
        self.assertEqual(
            self.client.config.request_code('+27123456789', 'vname'),
            {"vname": "vname"})

    @responses.activate
    def test_register(self):
        self.expectCommand(
            'token',
            '/v1/account/verify',
            VerifyCommand('1234'), {
                "the": "response"
            })

        self.assertEqual(
            self.client.config.register('1234'),
            {"the": "response"})

    @responses.activate
    def test_get_address_not_exists(self):

        self.expectCommand(
            'token',
            '/v1/contacts',
            ContactsCommand(
                contacts=['+27123456789'],
                blocking=ContactsCommand.WAIT),
            response={
                "contacts": [{
                    "input": "+27123456789",
                    "status": "invalid",
                    "wa_id": "27123456789",
                }]
            }
        )

        self.assertRaises(
            AddressException,
            self.client.get_address, '+27123456789')

    @responses.activate
    def test_health(self):
        self.expectGet('token', '/v1/health', {'health': {
            'gateway_status': 'connected',
        }})

        self.assertEqual(self.client.healthcheck(), {
            'health': {
                'gateway_status': 'connected'
            }
        })


class SettingsTest(WhatsAppClientTest):

    @responses.activate
    def test_set_about(self):
        self.expectCommand(
            'token',
            '/v1/settings/profile/about',
            AboutCommand("hi there"), {})

        self.assertEqual(
            self.client.config.set_about('hi there'),
            {})

    @responses.activate
    def test_get_about(self):
        self.expectGet('token', '/v1/settings/profile/about', {
            "settings": {
                "profile": {
                    "about": {
                        "text": "hi there"
                    }
                }
            }
        })

        self.assertEqual(
            self.client.config.get_about(), "hi there")

    @responses.activate
    def test_set_settings(self):
        self.expectCommand(
            'token', '/v1/settings/application',
            ApplicationSettingsCommand(
                on_call_pager='311234567789',
                sent_status=True,
                pass_through=True,
                webhooks={
                    'url': 'http://127.0.0.1/callback'
                },
            ))
        self.client.config.set_settings(
            on_call_pager='311234567789',
            sent_status=True,
            pass_through=True,
            webhook='http://127.0.0.1/callback')

    @responses.activate
    def test_set_business_profile(self):
        self.expectCommand(
            'token', '/v1/settings/business/profile',
            BusinessProfileCommand(
                address='address',
                description='description',
                vertical='vertical',
                email='email',
                websites=['websites']))
        self.client.config.set_business_profile(
            'address', 'description', 'vertical', 'email', ['websites'])

    @responses.activate
    def test_get_business_profile(self):
        self.expectGet('token', '/v1/settings/business/profile', {
            "settings": {
                "business": {
                    "profile": {
                        "address": "Address of Business",
                        "description": "Business description",
                        "email": "Email id of business contact",
                        "vertical": "Business vertical / industry",
                        "websites": ["web_site_1", "web_site_2"]
                    }
                }
            }
        })

        self.assertEqual(
            self.client.config.get_business_profile(),
            {
                "profile": {
                    "address": "Address of Business",
                    "description": "Business description",
                    "email": "Email id of business contact",
                    "vertical": "Business vertical / industry",
                    "websites": ["web_site_1", "web_site_2"]
                }
            })

    @responses.activate
    def test_set_password(self):
        self.expectCommand(
            'token',
            '/v1/users/username',
            UpdatePasswordCommand('username', 'password'))
        self.client.config.set_password('username', 'password')

    @responses.activate
    def test_set_initial_password(self):
        self.expectCommand(
            'token',
            '/v1/users/login',
            InitialPasswordCommand('the-password'))
        self.client.config.set_initial_password('the-password')

    @responses.activate
    def test_login(self):
        timestamp = datetime.now()

        def callback(request):
            auth = request.headers['Authorization']
            self.assertEqual(
                auth, 'Basic %s' % (b64encode(b'username:password').decode(),))
            return (200, {}, json.dumps({
                'users': [{
                    'token': 'new-token',
                    'expires_after': timestamp.isoformat(),
                }]
            }))

        responses.add_callback(
            responses.POST,
            '%s/v1/users/login' % (self.BASE_URL,),
            callback=callback, content_type='application/json')
        self.assertEqual(
            self.client.session.headers['Authorization'],
            'Bearer token')
        self.assertEqual(
            self.client.config.login('username', 'password'),
            ('new-token', iso8601.parse_date(timestamp.isoformat())))
        self.assertEqual(
            self.client.session.headers['Authorization'],
            'Bearer new-token')

    @responses.activate
    def test_create_user(self):
        self.expectCommand(
            'token',
            '/v1/users',
            CreateUserCommand('username', 'password'))

        self.client.config.create_user('username', 'password')

    @responses.activate
    def test_set_shards(self):
        self.expectCommand(
            'token',
            '/v1/account/shards',
            SetShardingCommand(
                cc='27',
                phone_number='123456789',
                shards=4,
                pin=None))
        self.client.config.setup_shards('+27123456789', 4)


class GroupTest(WhatsAppClientTest):

    @responses.activate
    def test_group_create(self):
        self.expectUpload(
            'token', '/v1/groups/the-group-id/icon', 'image/jpeg')
        self.expectCommand(
            'token', '/v1/groups',
            CreateGroupCommand(subject='my group name'),
            {
                "groups": [{
                    "creation_time": 1234567890,
                    "id": "the-group-id"
                }]
            })

        with tempfile.NamedTemporaryFile(suffix='.txt') as fp:
            fp.write('this is the content!'.encode('utf-8'))
            fp.seek(0)
            group = self.client.groups.create('my group name', fp, 'image.jpg')

        self.assertEqual(group.id, 'the-group-id')
        self.assertEqual(group.subject, 'my group name')
        self.assertEqual(
            group.creation_time, datetime.fromtimestamp(1234567890))

    @responses.activate
    def test_set_group_subject(self):
        self.expectCommand('token', '/v1/groups/group-id', UpdateGroupCommand(
            group_id='group-id',
            subject='new-subject'))

        self.client.groups.update_group('group-id', 'new-subject')

    @responses.activate
    def test_set_group_profile_photo(self):
        self.expectUpload(
            'token', '/v1/groups/the-group-id/icon', 'image/png')

        with tempfile.NamedTemporaryFile(suffix='.txt') as fp:
            fp.write('this is the content!'.encode('utf-8'))
            fp.seek(0)
            self.client.groups.set_profile_photo(
                'the-group-id', fp, 'flash.png')

    @responses.activate
    def test_group_get_invite_link(self):
        self.expectGet('token', '/v1/groups/group-id/invite', {
            "groups": [{
                "link": "group_invite_link"
            }]
        })

        self.assertEqual(
            self.client.groups.get_invite_link('group-id'),
            "group_invite_link")

    @responses.activate
    def test_group_revoke_invite_link(self):
        self.expectCommand(
            'token', '/v1/groups/group-id/invite',
            RevokeGroupInviteLink(group_id='group-id'))

        self.assertEqual(
            self.client.groups.revoke_invite_link('group-id'),
            {})

    @responses.activate
    def test_group_add_admins(self):
        self.expectCommand(
            'token', '/v1/groups/group-id/admins',
            AddGroupAdminCommand(
                group_id='group-id', wa_ids=['27123456789']))

        self.client.groups.add_admins('group-id', ['27123456789'])

    @responses.activate
    def test_group_remove_admins(self):
        self.expectCommand(
            'token', '/v1/groups/group-id/admins',
            RemoveGroupAdminCommand(
                group_id='group-id', wa_ids=['27123456789']))

        self.client.groups.remove_admins('group-id', ['27123456789'])

    @responses.activate
    def test_group_remove_participants(self):
        self.expectCommand(
            'token', '/v1/groups/group-id/participants',
            RemoveGroupParticipantCommand(
                group_id='group-id', wa_ids=['27123456789']))

        self.client.groups.remove_participants('group-id', ['27123456789'])

    @responses.activate
    def test_group_leave(self):
        self.expectCommand(
            'token', '/v1/groups/group-id/leave',
            LeaveGroupCommand(group_id='group-id'))

        self.client.groups.leave('group-id')


class ConnectionTest(WhatsAppClientTest):

    def test_session(self):
        session = requests.Session()
        session.verify = 'path/to/some.cert'
        client = Client(self.BASE_URL, session=session)
        self.assertEqual(client.connection.session.verify, 'path/to/some.cert')
