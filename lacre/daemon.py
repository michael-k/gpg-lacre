"""Lacre Daemon, the Advanced Mail Filter message dispatcher."""

from aiosmtpd.controller import Controller

import lacre.config as conf
# import lacre.mailgate as gate


RESULT_OK = '250 OK'
RESULT_ERROR = '500 Could not process your message'
RESULT_NOT_IMPLEMENTED = '500 Not implemented yet'


class MailEncryptionProxy:
    """A mail handler dispatching to appropriate mail operation."""

    async def handle_DATA(self, server, session, envelope):
        """Accept a message and either encrypt it or forward as-is."""
        # for now, just return an error because we're not ready to handle mail
        return RESULT_NOT_IMPLEMENTED


if __name__ == '__main__':
    proxy = MailEncryptionProxy()
    host, port = conf.relay_params()
    controller = Controller(proxy, hostname=host, port=port)

    # starts the controller in a new thread
    controller.start()

    # _this_ thread now continues operation, so it may be used to control key
    # and certificate cache

    controller.stop()
