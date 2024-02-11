import hashlib
import logging
import os
from dataclasses import asdict, dataclass, fields
from typing import Any, List, Mapping, Optional

import boto3
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from playwright.sync_api import sync_playwright
from playwright.sync_api._generated import ElementHandle
from twilio.rest import Client as TwilioClient

from utils.environment import _get_default_or_mapping_item
from utils.logging import configure_logging
from wrappers.twilio_wrapper import TwilioClientWrapper

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    events_table_name: str
    twilio_account_sid_secret_name: str
    twilio_auth_token_secret_name: str
    twilio_from_phone_number_secret_name: str
    twilio_to_phone_number_secret_name: str
    _session: Optional[boto3.Session] = None
    _twilio_client: Optional[TwilioClient] = None
    _twilio_client_wrapper: Optional[TwilioClientWrapper] = None

    @classmethod
    def from_environment(
        cls, env: Mapping[str, Any] = os.environ
    ) -> "EnvironmentConfig":
        kwargs = {
            field.name: _get_default_or_mapping_item(field, env)
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
                self.get_secret(self.twilio_to_phone_number_secret_name),
            )
        return self._twilio_client_wrapper


@dataclass(frozen=True)
class MothershipEvent:
    date: str
    title: str
    time: str
    room: str
    ticket_type: str

    def make_hash(self) -> str:
        data = ":".join([self.date, self.title, self.time, self.room, self.ticket_type])
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


def get_text_from_element_if_exists(element: Optional[ElementHandle]):
    if element:
        return element.text_content()
    return None


def process_event_card(event_card: ElementHandle) -> Optional[MothershipEvent]:
    try:
        title = get_text_from_element_if_exists(event_card.query_selector("h3"))
        dt = get_text_from_element_if_exists(event_card.query_selector(".h6"))

        details = event_card.query_selector('ul[class^="EventCard_detailsWrapper"]')
        if not details:
            return None

        list_items = details.query_selector_all("li")

        time = get_text_from_element_if_exists(list_items[0])
        room = get_text_from_element_if_exists(list_items[1])
        ticket_type = get_text_from_element_if_exists(list_items[2])

        mothership_event = MothershipEvent(
            date=dt, title=title, time=time, room=room, ticket_type=ticket_type
        )
        logger.info("Created MothershipEvent: %s", mothership_event)
        return mothership_event
    # This is overly broad, but I don't want one potential failure to tank the entire
    # lambda invocation
    except Exception:
        logger.exception("Caught exception processing event card: ")
        return None


def generate_sms_message_body(event: MothershipEvent):
    msg = "New Mothership Event:\n\n"
    msg += f"Title: {event.title}\n"
    msg += f"Date: {event.date}\n"
    msg += f"Time: {event.time}\n"
    msg += f"Room: {event.room}\n"
    return msg


def process_mothership_events(
    table, twilio_wrapper: TwilioClientWrapper, mothership_events: List[MothershipEvent]
):
    with table.batch_writer() as batch:
        for event in mothership_events:
            key = {
                "Hash": event.make_hash(),
            }
            resp = table.get_item(Key=key)

            # We only want to do anything for shows we haven't
            # encountere before
            if "Item" not in resp:
                twilio_wrapper.send_sms_message(generate_sms_message_body(event))

                batch.put_item(Item={**key, **asdict(event)})

            logger.info(resp)


def check_for_new_shows(env_config: EnvironmentConfig):

    env_config = EnvironmentConfig.from_environment()

    ddb: DynamoDBServiceResource = env_config.get_session().resource("dynamodb")
    table: Table = ddb.Table(env_config.events_table_name)

    seen = set()
    mothership_events: List[MothershipEvent] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-gpu", "--single-process"])
        page = browser.new_page()
        page.goto("https://comedymothership.com/shows")

        event_cards = page.query_selector_all('div[class^="EventCard_eventCard"]')
        for event_card in event_cards:
            mothership_event = process_event_card(event_card)
            if not mothership_event:
                continue

            hsh = mothership_event.make_hash()
            if hsh not in seen:
                mothership_events.append(mothership_event)

            seen.add(hsh)

        browser.close()

    twilio_wrapper = env_config.get_twilio_wrapper()
    process_mothership_events(table, twilio_wrapper, mothership_events)


def lambda_handler(event: Mapping[str, Any], context):

    env_config = EnvironmentConfig.from_environment()
    check_for_new_shows(env_config)
    logger.info("Finished!")
