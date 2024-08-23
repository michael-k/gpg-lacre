from aiosmtpd.smtp import Envelope
from email import message_from_bytes
from email.message import EmailMessage
from email.parser import BytesHeaderParser
from email.policy import SMTPUTF8

class LazyMessage:
    def __init__(self, recipients, content_provider):
        self._content_provider = content_provider
        self._recipients = recipients
        self._headers = None
        self._message = None

    def get_original_content(self) -> bytes:
        return self._content_provider()

    def get_recipients(self):
        return self._recipients

    def get_headers(self) -> EmailMessage:
        if self._message:
            return self._message

        if not self._headers:
            self._headers = BytesHeaderParser(policy=SMTPUTF8).parsebytes(self.get_original_content())

        return self._headers

    def get_message(self) -> EmailMessage:
        if not self._message:
            self._message = message_from_bytes(self.get_original_content(), policy=SMTPUTF8)

        return self._message
