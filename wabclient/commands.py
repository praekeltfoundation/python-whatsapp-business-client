import attr

from wabclient import constants as c

GET = 'GET'
PUT = 'PUT'
PATCH = 'PATCH'
POST = 'POST'
DELETE = 'DELETE'


def validate_caption(instance, attribute, value):
    if value and instance.message_type not in [
            c.MESSAGE_TYPE_DOCUMENT, c.MESSAGE_TYPE_IMAGE]:
        raise ValueError(
            "captions not valid for message type %s" % (
                instance.message_type))


def validate_render_mentions(instance, attribute, value):
    if value and instance.recipient_type is not c.RECIPIENT_TYPE_GROUP:
        raise ValueError(
            "render_mentions is only possible for groups")


def validate_websites(instance, attribute, value):
    if len(value) > 2:
        raise ValueError('Only a maximum of 2 websites allowed')


def min_max(min_value, max_value):
    def wrapped(instance, attribute, value):
        if not (min_value <= len(value) <= max_value):
            raise ValueError('%s length (%s) must be between %s and %s' % (
                attribute.name, len(value), min_value, max_value
            ))
    return wrapped


class BaseCommand(object):

    def get_endpoint(self):
        return self.command_endpoint

    def get_method(self):
        return self.command_method

    def render(self):
        return attr.asdict(self)

    def __repr__(self):
        return "<%s method=%r endpoint=%r json=%r >" % (
            self.__class__.__name__,
            self.command_method,
            self.command_endpoint,
            self.render())


@attr.s
class TextCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/messages'

    to = attr.ib(type=str)
    text = attr.ib(type=str)
    preview_url = attr.ib(type=bool, default=False)
    render_mentions = attr.ib(
        type=bool, default=False,
        validator=validate_render_mentions)
    recipient_type = attr.ib(
        default=c.RECIPIENT_TYPE_DEFAULT,
        validator=attr.validators.in_(
            [c.RECIPIENT_TYPE_GROUP, c.RECIPIENT_TYPE_INDIVIDUAL]))

    def render(self):
        return {
            "preview_url": self.preview_url,
            "recipient_type": self.recipient_type,
            "to": self.to,
            "type": c.MESSAGE_TYPE_TEXT,
            "text": {
                "body": self.text,
            }
        }

@attr.s
class HSMCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/messages'

    to = attr.ib()
    namespace = attr.ib()
    element_name = attr.ib()
    language_code = attr.ib()
    language_policy = attr.ib(
        default="fallback",
        validator=attr.validators.in_(["fallback", "deterministic"]))

    localizable_params = attr.ib(default=attr.Factory(list))

    def render(self):
        return {
            "to": self.to,
            "type": c.MESSAGE_TYPE_HSM,
            "hsm": {
                "namespace": self.namespace,
                "element_name": self.element_name,
                "language": {
                    "code": self.language_code,
                    "policy": self.language_policy
                },
                "localizable_params": self.localizable_params,
            }
        }


@attr.s
class MediaCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/messages'

    to = attr.ib()
    message_type = attr.ib(
        validator=attr.validators.in_(
            [c.MESSAGE_TYPE_AUDIO,
             c.MESSAGE_TYPE_DOCUMENT,
             c.MESSAGE_TYPE_IMAGE]))
    media_id = attr.ib()
    render_mentions = attr.ib(
        type=bool, default=False,
        validator=validate_render_mentions)
    caption = attr.ib(
        default=None,
        validator=validate_caption)
    recipient_type = attr.ib(
        default=c.RECIPIENT_TYPE_DEFAULT,
        validator=attr.validators.in_(
            [c.RECIPIENT_TYPE_GROUP, c.RECIPIENT_TYPE_INDIVIDUAL]))

    def render(self):
        doc = {
            "recipient_type": self.recipient_type,
            "to": self.to,
            "type": self.message_type,
        }

        if self.message_type == c.MESSAGE_TYPE_AUDIO:
            doc.update({
                "audio": {
                    "id": self.media_id
                }
            })
        elif self.message_type == c.MESSAGE_TYPE_DOCUMENT:
            doc.update({
                "document": {
                    "id": self.media_id,
                    "caption": self.caption,
                }
            })
        elif self.message_type == c.MESSAGE_TYPE_IMAGE:
            doc.update({
                "image": {
                    "id": self.media_id,
                    "caption": self.caption
                }
            })
        return doc


@attr.s
class BackupCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/settings/backup'

    password = attr.ib()


@attr.s
class RestoreBackupCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/settings/restore'

    password = attr.ib()
    data = attr.ib()


@attr.s
class ContactsCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/contacts'

    WAIT = 'wait'
    NO_WAIT = 'no_wait'
    DEFAULT = NO_WAIT

    VALID = "valid"
    PROCESSING = "processing"
    INVALID = "invalid"

    contacts = attr.ib(default=attr.Factory(list))
    blocking = attr.ib(
        default=NO_WAIT,
        validator=attr.validators.in_([WAIT, NO_WAIT]))


@attr.s
class RegistrationCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/account'

    SMS = 'sms'
    VOICE = 'voice'

    cc = attr.ib(type=str)
    phone_number = attr.ib(type=str)
    method = attr.ib(validator=attr.validators.in_([SMS, VOICE]))
    cert = attr.ib(type=str)
    pin = attr.ib(default=None, type=str)

    def render(self):
        data = attr.asdict(self)
        if data['pin'] is None:
            data.pop('pin')
        return data


@attr.s
class VerifyCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/account/verify'

    code = attr.ib(type=str)


@attr.s
class AboutCommand(BaseCommand):
    command_method = PATCH
    command_endpoint = '/v1/settings/profile/about'

    text = attr.ib(type=str)


@attr.s
class Webhooks():
    url = attr.ib(default=None)


@attr.s
class ApplicationSettingsCommand(BaseCommand):
    command_method = PATCH
    command_endpoint = '/v1/settings/application'

    on_call_pager = attr.ib(type=str)
    webhooks = attr.ib(
        converter=lambda value: Webhooks(**value), default={})
    callback_persist = attr.ib(type=bool, default=True)
    callback_backoff_delay_ms = attr.ib(type=str, default="3000")
    max_callback_backoff_delay_ms = attr.ib(type=str, default="900000")
    pass_through = attr.ib(type=bool, default=False)
    sent_status = attr.ib(type=bool, default=False)
    tcp_listen_address = attr.ib(type=str, default="any")
    heartbeat_interval = attr.ib(type=int, default=5)
    unhealthy_interval = attr.ib(type=int, default=30)


@attr.s
class BusinessProfileCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/settings/business/profile'

    address = attr.ib(type=str)
    description = attr.ib(type=str)
    email = attr.ib(type=str)
    vertical = attr.ib(type=str)
    websites = attr.ib(default=attr.Factory(list), validator=validate_websites)


@attr.s
class CreateGroupCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/groups'

    subject = attr.ib()


@attr.s
class UpdateGroupCommand(BaseCommand):
    command_method = PUT

    group_id = attr.ib()
    subject = attr.ib()

    def get_endpoint(self):
        return '/v1/groups/%s' % (self.group_id,)


@attr.s
class RetrieveGroups(BaseCommand):
    command_method = GET
    command_endpoint = '/v1/groups'


@attr.s
class RevokeGroupInviteLink(BaseCommand):
    command_method = DELETE

    group_id = attr.ib()

    def get_endpoint(self):
        return '/v1/groups/%s/invite' % (self.group_id,)


@attr.s
class AddGroupAdminCommand(BaseCommand):
    command_method = PATCH

    group_id = attr.ib(type=str)
    wa_ids = attr.ib(default=attr.Factory(list))

    def get_endpoint(self):
        return '/v1/groups/%s/admins' % (self.group_id,)

    def render(self):
        return {
            'wa_ids': self.wa_ids,
        }


@attr.s
class RemoveGroupAdminCommand(AddGroupAdminCommand):
    command_method = DELETE


@attr.s
class RemoveGroupParticipantCommand(AddGroupAdminCommand):
    command_method = DELETE

    def get_endpoint(self):
        return '/v1/groups/%s/participants' % (self.group_id,)


@attr.s
class LeaveGroupCommand(BaseCommand):
    command_method = POST

    group_id = attr.ib(type=str)

    def get_endpoint(self):
        return '/v1/groups/%s/leave' % (self.group_id,)


@attr.s
class UpdatePasswordCommand(BaseCommand):
    command_method = PUT

    username = attr.ib(validator=min_max(4, 32))
    password = attr.ib(validator=min_max(8, 64))

    def get_endpoint(self):
        return '/v1/users/%s' % (self.username,)

    def render(self):
        return {
            "password": self.password,
        }


@attr.s
class CreateUserCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/users'

    username = attr.ib(validator=min_max(4, 32))
    password = attr.ib(validator=min_max(8, 64))


@attr.s
class SetShardingCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/account/shards'

    VALID_SHARDS = [1, 2, 4, 8, 16, 32]

    cc = attr.ib(type=str)
    phone_number = attr.ib(type=str)
    shards = attr.ib(
        type=int, validator=attr.validators.in_(VALID_SHARDS))
    pin = attr.ib(type=str, default=None)


@attr.s
class InitialPasswordCommand(BaseCommand):
    command_method = POST
    command_endpoint = '/v1/users/login'

    new_password = attr.ib(type=str, validator=min_max(8, 64))
