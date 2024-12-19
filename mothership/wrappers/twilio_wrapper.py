import logging

from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)


class TwilioClientWrapper:
    def __init__(self, twilio_client: TwilioClient, from_number: str):
        self._twilio_client = twilio_client
        self._from_number = from_number

    def send_sms_message(self, to_number: str, msg: str) -> None:
        self._twilio_client.messages.create(
            to=to_number, from_=self._from_number, body=msg
        )
        return
