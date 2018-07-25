
class WhatsAppException(Exception):
    pass


class WhatsAppAPIException(WhatsAppException):
    pass


class GroupException(WhatsAppException):
    pass


class AddressException(WhatsAppException):
    pass


class ThrottlingException(WhatsAppAPIException):
    pass


class RequestRateLimitingException(WhatsAppAPIException):
    pass


class ConcurrencyRateLimitingException(WhatsAppAPIException):
    pass
