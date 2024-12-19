import logging
import os
from dataclasses import dataclass, fields
from typing import Any, Mapping, Optional

import boto3
from twilio.rest import Client as TwilioClient

from mothership.utils.environment import get_default_or_mapping_item
from mothership.utils.logging import configure_logging
from mothership.wrappers.twilio_wrapper import TwilioClientWrapper
from mothership.models import MothershipEvent

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    twilio_account_sid_secret_name: str
    twilio_auth_token_secret_name: str
    twilio_from_phone_number_secret_name: str
    _session: Optional[boto3.Session] = None
    _twilio_client: Optional[TwilioClient] = None
    _twilio_client_wrapper: Optional[TwilioClientWrapper] = None

    @classmethod
    def from_environment(
        cls, env: Mapping[str, Any] = os.environ
    ) -> "EnvironmentConfig":
        kwargs = {
            field.name: get_default_or_mapping_item(field, env)
            for field in fields(cls)
        }
        return cls(**kwargs)  # type:ignore

    def get_session(self) -> boto3.Session:
        if self._session is None:
            self._session = boto3.Session()

        return self._session

    def get_secret(self, secret_name: str) -> str:
        client_secrets = self.get_session().client("secretsmanager")

        response = client_secrets.get_secret_value(SecretId=secret_name)

        return response["SecretString"]

    def get_twilio_client(self) -> TwilioClient:
        if not self._twilio_client:
            self._twilio_client = TwilioClient(
                self.get_secret(self.twilio_account_sid_secret_name),
                self.get_secret(self.twilio_auth_token_secret_name),
            )
        return self._twilio_client

    def get_twilio_wrapper(self) -> TwilioClientWrapper:
        if not self._twilio_client_wrapper:
            self._twilio_client_wrapper = TwilioClientWrapper(
                self.get_twilio_client(),
                self.get_secret(self.twilio_from_phone_number_secret_name),
            )
        return self._twilio_client_wrapper


def lambda_handler(event: Mapping[str, Any], context):
    env_config = EnvironmentConfig.from_environment()

    twilio_wrapper = env_config.get_twilio_wrapper()

    to_number = event["phone_number"]

    for e in event["events"]:
        mothership_event = MothershipEvent(**e)
        logger.info(f"Sending message for event: {mothership_event}")
        twilio_wrapper.send_sms_message(
            to_number=to_number, msg=mothership_event.make_event_notification_message()
        )

    logger.info("Finished!")

    return
