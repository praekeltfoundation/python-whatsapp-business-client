import requests
import mimetypes
import phonenumbers
import attr
import iso8601
from functools import wraps
from datetime import datetime
from six.moves import urllib_parse
from wabclient.exceptions import (
    RequestRateLimitingException, ConcurrencyRateLimitingException,
    WhatsAppAPIException, AddressException, GroupException)
from wabclient import constants as c
from wabclient.commands import (
    MediaCommand, TextCommand, BackupCommand, RestoreBackupCommand,
    ContactsCommand, RegistrationCommand, VerifyCommand, AboutCommand,
    ApplicationSettingsCommand, BusinessProfileCommand, CreateGroupCommand,
    UpdateGroupCommand, RevokeGroupInviteLink, AddGroupAdminCommand,
    RemoveGroupAdminCommand, RemoveGroupParticipantCommand, LeaveGroupCommand,
    HSMCommand, UpdatePasswordCommand, CreateUserCommand, RetrieveGroups,
    SetShardingCommand, InitialPasswordCommand)

DEFAULT_TIMEOUT = 10


def json_or_death(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        resp = func(*args, **kwargs)
        resp.raise_for_status()
        return resp.json()
    return decorator


def guess_content_type(filename, fallback):
    (content_type, encoding) = mimetypes.guess_type(filename)
    return content_type or fallback


def has_url(content):
    return (content is not None) and (
        'http://' in content or
        'https://' in content)


error_map = {
    429: RequestRateLimitingException,
    503: ConcurrencyRateLimitingException,
}

default_exception = WhatsAppAPIException


def fail(data):
    error = data.get('error', {})
    exception_class = error_map.get(
        error.get('errorcode'), default_exception)
    return exception_class(data)


class Connection(object):
    def __init__(self, url, timeout=DEFAULT_TIMEOUT, session=None):
        self.url = url
        self.session = session or requests.Session()
        self.timeout = timeout

    @json_or_death
    def upload(self, path, fp, content_type):
        return self.session.post(
            urllib_parse.urljoin(self.url, path),
            data=fp.read(),
            headers={'Content-Type': content_type})

    def upload_media(self, fp, content_type):
        data = self.upload('/v1/media', fp, content_type)
        [media] = data["media"]
        return media["id"]

    def download(self, filename):
        response = self.session.get(
            urllib_parse.urljoin(self.url, filename),
            stream=True)
        response.raise_for_status()
        response.raw.decode_content = True
        return (
            int(response.headers['content-length']), response.raw)

    def download_media(self, media_id):
        response = self.session.get(
            urllib_parse.urljoin(self.url, '/v1/media/%s' % (media_id,)),
            stream=True)
        response.raise_for_status()
        response.raw.decode_content = True
        return (
            int(response.headers['content-length']), response.raw)

    @json_or_death
    def get(self, path, params={}):
        return self.session.get(
            urllib_parse.urljoin(self.url, path), params=params)

    def post(self, path, *args, **kwargs):
        return self.session.post(
            urllib_parse.urljoin(
                self.url, path), *args, **kwargs)

    @json_or_death
    def send(self, command):
        return self.session.request(
            command.get_method(),
            urllib_parse.urljoin(self.url, command.get_endpoint()),
            json=command.render())

    def set_token(self, token):
        self.session.headers.update({
            'Authorization': 'Bearer %s' % (token,)
        })


@attr.s
class Group(object):
    id = attr.ib(type=str)
    creation_time = attr.ib(
        type=int, default=None, convert=datetime.fromtimestamp)
    subject = attr.ib(type=str, default=None)
    creator = attr.ib(type=str, default=None)
    admins = attr.ib(default=attr.Factory(list))
    participants = attr.ib(default=attr.Factory(list))


class GroupManager(object):

    def __init__(self, url, timeout=DEFAULT_TIMEOUT, session=None):
        self.url = url
        self.connection = Connection(
            self.url, timeout=timeout, session=session)

    def create(self, subject, profile_photo=None, profile_photo_name=None):
        """
        Create a new group

        :param str subject:
            The mandatory subject to set for the group. Must be <= 25 chars.
        :param file profile_photo:
            The optional image to use as a profile photo.
        :param str profile_photo_name:
            The name for the profile photo, mandatory if a profile photo
            is supplied.
        :return: Group
        """
        if not subject:
            raise GroupException('Subjects are required')
        elif len(subject) > 25:
            raise GroupException('Subject length must be <= 25 characters')

        data = self.connection.send(CreateGroupCommand(subject=subject))
        [group_data] = data["groups"]
        group_data.update({
            'subject': subject,
        })
        group = Group(**group_data)

        if profile_photo:
            if not profile_photo_name:
                raise GroupException('Profile photo name is mandatory.')
            self.set_profile_photo(
                group.id, profile_photo, profile_photo_name)
        return group

    def update_group(self, group_id, subject):
        """
        Updates a group's subject

        :param str subject:
            The subject
        """
        return self.connection.send(UpdateGroupCommand(group_id, subject))

    def set_profile_photo(self, group_id, fp, file_name):
        """
        :param str group_id:
            The group id
        :param file profile_photo:
            The image to use as a profile photo.
        :param str profile_photo_name:
            The name for the profile photo.
        """
        self.connection.upload(
            '/v1/groups/%s/icon' % (group_id,),
            fp, guess_content_type(file_name, 'image/jpeg'))

    def get_invite_link(self, group_id):
        """
        Returns the invite link URL through which people can join
        a group.

        :param str group_id:
            The group id
        :return: The URL
        """
        response = self.connection.get('/v1/groups/%s/invite' % (group_id,))
        [group_data] = response['groups']
        return group_data['link']

    def revoke_invite_link(self, group_id):
        """
        Revokes the previous invite link URL and creates a new one
        through which people can join a group.

        :param str group_id:
            The group id
        """
        return self.connection.send(RevokeGroupInviteLink(group_id))

    def add_admins(self, group_id, participants):
        """
        :param str group_id:
            The group id
        :param list participants:
            The list of WA ids that should be promoted to admins.
        :return: Group
        """
        return self.connection.send(AddGroupAdminCommand(
            group_id=group_id, wa_ids=participants))

    def remove_admins(self, group_id, participants):
        """
        :param str group_id:
            The group id
        :param list participants:
            The list of WA ids that should be revoked as admins.
        :return: Group
        """
        return self.connection.send(RemoveGroupAdminCommand(
            group_id=group_id, wa_ids=participants))

    def remove_participants(self, group_id, participants):
        """
        :param str group_id:
            The group id
        :param list participants:
            The list of WA ids that should be removed from the group
        :return: Group
        """
        return self.connection.send(RemoveGroupParticipantCommand(
            group_id=group_id, wa_ids=participants))

    def leave(self, group_id):
        """
        Leaves a group

        :param str group_id:
            The group id
        :return: Group
        """
        return self.connection.send(LeaveGroupCommand(group_id))

    def list(self):
        """
        Return the list of groups

        :return: list
        """
        response = self.connection.send(RetrieveGroups())
        return response['groups']


class ConfigurationManager(object):

    CODE_REQUEST_SMS = 'sms'
    CODE_REQUEST_VOICE = 'voice'

    def __init__(self, url, timeout=DEFAULT_TIMEOUT, session=None):
        self.url = url
        self.connection = Connection(self.url, timeout=timeout,
                                     session=session)

    def setup_shards(self, phonenumber, shard_count, pin=None):
        pn = phonenumbers.parse(phonenumber)
        return self.connection.send(
            SetShardingCommand(
                cc=str(pn.country_code),
                phone_number=str(pn.national_number),
                shards=shard_count,
                pin=pin))

    def request_code(self, phonenumber, vname,
                     method=CODE_REQUEST_SMS):
        """
        Get a code request for registering a new number.

        :param str phonenumber:
            The phone number with leading "+".
        :param str vname:
            Base64 encoded vname for the number as received
            from WhatsApp.
        :param str method:
            The method of requesting a code request,
            can be either "sms" or "voice"
        """
        pn = phonenumbers.parse(phonenumber)
        data = self.connection.send(
            RegistrationCommand(
                cc=str(pn.country_code),
                phone_number=str(pn.national_number),
                method=method,
                cert=vname))
        return data['account'][0]

    def register(self, code):
        """
        Register a number after having received a code

        :param str code:
            The registration code received
        """
        return self.connection.send(VerifyCommand(code))

    def get_profile_photo(self):
        """
        Returns the profile photo's bytes data.

        :return: bytes
        """
        (size, data) = self.connection.download('/v1/settings/profile/photo')
        return data

    def set_profile_photo(self, fp, file_name):
        """
        Set the profile photo

        :param file fp:
            A thing that implements read() to return a bytestream
        :parm str file_name:
            The file name, used to guess the mimetype
        """
        return self.connection.upload(
            '/v1/settings/profile/photo', fp,
            guess_content_type(file_name, 'image/jpeg'))

    def get_about(self):
        """
        Gets the accounts about / status

        :return: str
        """
        data = self.connection.get('/v1/settings/profile/about')
        return data['settings']['profile']['about']['text']

    def set_about(self, about):
        """
        Sets the accounts about / status
        :param str about:
            The about message. Must be < 139 characters.
        """
        return self.connection.send(AboutCommand(about))

    def get_business_profile(self):
        """
        Gets the business profile for this account

        :return: dict
        """
        data = self.connection.get('/v1/settings/business/profile')
        return data['settings']['business']

    def set_business_profile(self, address=None, description=None,
                             vertical=None, email=None, websites=None):
        """
        Sets the business profile for this account

        :param str address:
            Address of the business. Must be < 256 characters.
        :param str description:
            Description of the business. Must be < 256 characters.
        :param str vertical:
            Industry of the business. Must be < 128 characters.
        :param str email:
            Email address to contact the business.
            Must be < 128 characters.
        :param list websites:
            List of URLs associated with business. Max of 4.
            Each must be < 256 characters.
        """
        return self.connection.send(BusinessProfileCommand(
            address=address,
            description=description,
            vertical=vertical,
            email=email,
            websites=websites or [],
        ))

    def get_settings(self):
        """
        Get the settings for this account

        :return: dict
        """
        data = self.connection.get('/v1/settings/application')
        return data['settings']['application']

    def set_settings(
            self, on_call_pager, webhook,
            tcp_listen_address="any",
            pass_through=False,
            callback_persist=True,
            sent_status=False,
            callback_backoff_delay_ms=3000,
            max_callback_backoff_delay_ms=900000):
        """
        :param str on_call_pager:
            Valid WhatsApp number that the client will contact with
            critical errors and messages
        :param str webhook:
            Endpoint for incoming message and event callbacks
        :param str tcp_listen_address:
            TCP listen address. Defaults to "any".
        :param bool pass_through:
            Removes message from local storage when delivered.
            Defaults to False.
        :param bool callback_persist:
            Store callbacks on disk until they are successfully
            acknowledged by webhook.
            Defaults to True.
        :param bool sent_status:
            Receive message sent to server callback.
            Defaults to False.
        :param int callback_backoff_delay_ms:
            Backoff delay for failed callback. Defaults to ``3000``.
        :param int max_callback_backoff_delay_ms:
            Maximum delay for failed callback. Defaults to ``900000``.
        """
        return self.connection.send(
            ApplicationSettingsCommand(
                on_call_pager,
                webhooks={
                    'url': webhook
                },
                tcp_listen_address=tcp_listen_address,
                pass_through=pass_through,
                sent_status=sent_status,
                callback_persist=callback_persist,
                callback_backoff_delay_ms=str(
                    callback_backoff_delay_ms),
                max_callback_backoff_delay_ms=str(
                    max_callback_backoff_delay_ms),
            )
        )

    def login(self, username, password):
        """
        Login as a user, returns a new client instance
        with the new login credentials set for the session

        :param str username:
            The username
        :param str password:
            The password
        """
        response = self.connection.post(
            '/v1/users/login', auth=(username, password))
        response.raise_for_status()
        data = response.json()
        [user] = data["users"]
        token = user["token"]
        expires_at = iso8601.parse_date(user["expires_after"])
        self.connection.set_token(token)
        return (token, expires_at)

    def set_initial_password(self, password):
        """
        Sets the initial password, should only need to be done
        right after a new number has been set up

        :param str password:
            The password
        """
        return self.connection.send(InitialPasswordCommand(password))

    def set_password(self, username, password):
        """
        Updates a users' password

        :param str username:
            The username
        :param str password:
            The password
        """
        return self.connection.send(
            UpdatePasswordCommand(username, password))

    def create_user(self, username, password):
        """
        Creates a new user

        :param str username:
            The username
        :param str password:
            The password
        """
        return self.connection.send(
            CreateUserCommand(username, password))


class Client(object):

    DIRECT_RECIPIENT = c.RECIPIENT_TYPE_DEFAULT
    GROUP_RECIPIENT = c.RECIPIENT_TYPE_GROUP

    def __init__(self, url, timeout=DEFAULT_TIMEOUT, session=None):
        self.url = url
        self.timeout = timeout
        self.session = session
        self.connection = Connection(
            self.url, timeout=self.timeout, session=session)
        self.config = ConfigurationManager(
            self.url, timeout=self.timeout, session=session)

    @property
    def groups(self):
        return GroupManager(
            self.url, timeout=self.timeout, session=self.session)

    def upload(self, path, fp, content_type):
        """
        :param str path:
            The path to upload to
        :param file fp:
            A thing that implements read() which
            returns the bytes needed to be uploaded.
        :param str content_type:
            The content type of the bytes being uploaded
        :return: dict
        """
        return self.connection.upload(path, fp, content_type)

    def download(self, file_name):
        """
        :param str file_name:
            The file to download from the container's incoming media
            directory
        :return: tuple(content-length, file-object)
        """
        return self.connection.download(file_name)

    def download_media(self, media_id):
        """
        :param str media_id:
            The ID of the media resource to download
        :return: tuple(content-length, file-object)
        """
        return self.connection.download_media(media_id)

    def get_address(self, to_addr):
        """
        Get the WhatsApp username for a to_addr.
        Raises ``AddressException`` if not whatsappable.

        :param str to_addr:
            The address to check
        :return: str
        """
        response = self.check_contacts([to_addr], wait=True)
        [result] = response['contacts']
        if result['status'] == ContactsCommand.VALID:
            return result['wa_id']
        raise AddressException(
            '%s is not a whatsappable contact' % (to_addr,))

    def check_contacts(self, addresses, wait=False):
        """
        Checks a contact or their whatsapp contact ids

        :param list addresses:
            list of E164 formatted address strings
        :param bool wait:
            Whether or not to synchronously wait for the
            results. Defaults to ``False``
        :return: list of dictionaries with results
        """
        return self.connection.send(ContactsCommand(
            blocking=ContactsCommand.WAIT if wait else ContactsCommand.NO_WAIT,
            contacts=addresses))

    def send_audio(
            self, to_addr, file_name,
            audio_attachment,
            recipient_type=c.RECIPIENT_TYPE_DEFAULT,
            check_address=False):
        """
        :param str to_addr:
            The WhatsApp ID
        :param str file_name:
            The file name
        :param file audio_attachment:
            The file object to send
        :param str recipient_type:
            The recipient type to set, defaults to RECIPIENT_TYPE_DEFAULT
        :param bool check_address:
            Whether or not to verify that the address is whatsapp-able before
            sending. Defaults to ``False``.
        """
        media_id = self.connection.upload_media(
            audio_attachment, guess_content_type(file_name, 'audio/mpeg'))
        return self.connection.send(
            MediaCommand(
                to=self.get_address(to_addr) if check_address else to_addr,
                media_id=media_id,
                recipient_type=recipient_type,
                message_type=c.MESSAGE_TYPE_AUDIO,
            ))

    def send_image(
            self, to_addr, file_name,
            image_attachment, image_attachment_caption=None,
            recipient_type=c.RECIPIENT_TYPE_DEFAULT,
            render_mentions=False,
            check_address=False):
        """
        :param str to_addr:
            The WhatsApp ID
        :param str file_name:
            The file name
        :param file image_attachment:
            The file object to send
        :param str image_attachment_caption:
            The caption for the image, defaults to ``None``
        :param str recipient_type:
            The recipient type to set, defaults to RECIPIENT_TYPE_DEFAULT
        :param bool render_mentions:
            Whether or not to render @mentions in messages. Defaults to False.
        :param bool check_address:
            Whether or not to verify that the address is whatsapp-able before
            sending. Defaults to ``False``.
        """
        media_id = self.connection.upload_media(
            image_attachment, guess_content_type(file_name, 'image/jpeg'))
        return self.connection.send(
            MediaCommand(
                to=self.get_address(to_addr) if check_address else to_addr,
                media_id=media_id,
                caption=image_attachment_caption,
                render_mentions=render_mentions,
                recipient_type=recipient_type,
                message_type=c.MESSAGE_TYPE_IMAGE,
            ))

    def send_document(
            self, to_addr, file_name,
            document_attachment, document_attachment_caption,
            recipient_type=c.RECIPIENT_TYPE_DEFAULT,
            render_mentions=False,
            check_address=False):
        """
        :param str to_addr:
            The WhatsApp ID
        :param str file_name:
            The file name
        :param file document_attachment:
            The file object to send
        :param str document_attachment_caption:
            The caption for the document, defaults to ``None``
        :param str recipient_type:
            The recipient type to set, defaults to RECIPIENT_TYPE_DEFAULT
        :param bool render_mentions:
            Whether or not to render @mentions in messages. Defaults to False.
        :param bool check_address:
            Whether or not to verify that the address is whatsapp-able before
            sending. Defaults to ``False``.
        """
        media_id = self.connection.upload_media(
            document_attachment,
            guess_content_type(file_name, 'application/pdf'))
        return self.connection.send(
            MediaCommand(
                to=self.get_address(to_addr) if check_address else to_addr,
                media_id=media_id,
                caption=document_attachment_caption,
                render_mentions=render_mentions,
                recipient_type=recipient_type,
                message_type=c.MESSAGE_TYPE_DOCUMENT,
            ))

    def send_message(
            self, to_addr, body,
            recipient_type=c.RECIPIENT_TYPE_DEFAULT,
            preview_url=True,
            render_mentions=False,
            check_address=False):
        """
        :param str to_addr:
            The WhatsApp ID
        :param str body:
            The text to send, must be < 4096 characters
        :param str recipient_type:
            The recipient type to set, defaults to RECIPIENT_TYPE_DEFAULT
        :param bool preview_url:
            Whether or not to load a preview for the URL in the message
        :param bool render_mentions:
            Whether or not to render @mentions in messages. Defaults to False.
        :param bool check_address:
            Whether or not to verify that the address is whatsapp-able before
            sending. Defaults to ``False``.
        """
        return self.connection.send(
            TextCommand(
                to=self.get_address(to_addr) if check_address else to_addr,
                text=body,
                recipient_type=recipient_type,
                preview_url=preview_url and has_url(body),
                render_mentions=render_mentions))

    def send_hsm(
            self, to_addr, namespace, element_name, language_code, params,
            language_policy="fallback", check_address=False):
        """
        :param str to_addr:
            The WhatsApp ID
        :param str namespace:
            The HSM namespace
        :param str element_name:
            The HSM element name
        :param str language_code:
            The HSM language
        :param str language_policy:
            The HSM policy, "fallback" (default) or "deterministic"
        :param list params:
            A list with {"default | currency | date_time" => "value"} pairs
            which can be used for localisation
        :param bool check_address:
            Whether or not to verify that the address is whatsapp-able before
            sending. Defaults to ``False``.
        """
        return self.connection.send(
            HSMCommand(
                to=self.get_address(to_addr) if check_address else to_addr,
                namespace=namespace,
                element_name=element_name,
                language_code=language_code,
                language_policy=language_policy,
                localizable_params=params))

    def healthcheck(self):
        """
        Returns the dictionary with the health check results

        :return: dict
        """
        return self.connection.get('/v1/health')

    def create_backup(self, password):
        """
        Create a backup

        :param str password:
            The password you want to set for the backup
        :return: str, base64 encoded export
        """
        data = self.connection.send(BackupCommand(password))
        return data['settings']['data']

    def restore_backup(self, password, export):
        """
        Restore a backup

        :param str password:
            The password for the backup
        :param str export:
            The export returned by the create_backup call
        """
        return self.connection.send(RestoreBackupCommand(password, export))
