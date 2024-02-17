import logging
import os
from dataclasses import asdict, dataclass, fields
from typing import Any, List, Mapping, Optional, Set

import boto3
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from playwright.sync_api import sync_playwright
from playwright.sync_api._generated import ElementHandle

from utils.environment import _get_default_or_mapping_item
from utils.logging import configure_logging
from models import MothershipEvent

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    events_table_name: str
    _session: Optional[boto3.Session] = None

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
        return mothership_event
    # This is overly broad, but I don't want one potential failure to tank the entire
    # lambda invocation
    except Exception:
        logger.exception("Caught exception processing event card: ")
        return None


def process_new_mothership_events(
    table, mothership_events: List[MothershipEvent]
) -> Set[MothershipEvent]:
    new_events: Set[MothershipEvent] = set()
    with table.batch_writer() as batch:
        for event in mothership_events:
            key = {
                "Hash": event.make_hash(),
            }
            resp = table.get_item(Key=key)

            # We only want to do anything for shows we haven't
            # encountered before
            if "Item" not in resp:
                new_events.add(event)
                batch.put_item(Item={**key, **asdict(event)})

            logger.info(resp)

    return new_events


def check_for_new_shows(env_config: EnvironmentConfig) -> Set[MothershipEvent]:

    env_config = EnvironmentConfig.from_environment()

    ddb: DynamoDBServiceResource = env_config.get_session().resource("dynamodb")
    table: Table = ddb.Table(env_config.events_table_name)

    seen = set()
    mothership_events: List[MothershipEvent] = []
    with sync_playwright() as p:
        # Launch a browser and navigate to the Mothership page
        browser = p.chromium.launch(args=["--disable-gpu", "--single-process"])
        page = browser.new_page()
        page.goto("https://comedymothership.com/shows")

        # Get all the event cards
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

    return process_new_mothership_events(table, mothership_events)


def lambda_handler(event: Mapping[str, Any], context) -> List[MothershipEvent]:

    env_config = EnvironmentConfig.from_environment()
    new_events: Set[MothershipEvent] = check_for_new_shows(env_config)
    logger.info("Finished!")

    return [asdict(mothership_event) for mothership_event in new_events]
