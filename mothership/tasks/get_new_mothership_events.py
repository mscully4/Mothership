import logging
import os
from dataclasses import asdict, dataclass, fields
from functools import cached_property
from typing import Any, List, Mapping, Optional, Set

import boto3
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from playwright.sync_api import sync_playwright

from mothership.models import MothershipEvent
from mothership.utils.environment import get_default_or_mapping_item
from mothership.utils.logging import configure_logging

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    aws_region: str
    events_table_name: str
    filtered_titles_table_name: str
    _session: Optional[boto3.Session] = None

    @classmethod
    def from_environment(cls, env: Mapping[str, Any] = os.environ) -> "EnvironmentConfig":
        kwargs = {field.name: get_default_or_mapping_item(field, env) for field in fields(cls)}
        return cls(**kwargs)

    def get_session(self) -> boto3.Session:
        if self._session is None:
            self._session = boto3.Session(region_name=self.aws_region)
        return self._session

    @cached_property
    def events_table(self) -> Table:
        ddb: DynamoDBServiceResource = self.get_session().resource("dynamodb")
        return ddb.Table(self.events_table_name)

    @cached_property
    def filtered_titles_table(self) -> Table:
        ddb: DynamoDBServiceResource = self.get_session().resource("dynamodb")
        return ddb.Table(self.filtered_titles_table_name)


def get_filtered_titles(table: Table) -> set[str]:
    resp = table.scan(ProjectionExpression="Title")
    return {item["Title"] for item in resp.get("Items", [])}


def get_all_events() -> list[MothershipEvent]:
    url = "https://comedymothership.com/shows"
    mothership_events: list[MothershipEvent] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--no-zygote",
            ]
        )
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        elements = page.query_selector_all('[class^="EventCard_textWrapper"]')
        for el in elements:
            title_el = el.query_selector('[class^="EventCard_titleWrapper"]')
            if not title_el:
                continue

            date_div = title_el.query_selector("div")
            title_h3 = title_el.query_selector("h3")
            if not date_div or not title_h3:
                continue

            event_date = date_div.inner_text().strip()
            event_title = title_h3.inner_text().strip()

            details_el = el.query_selector('[class^="EventCard_detailsWrapper"]')
            if not details_el:
                continue

            detail_items = details_el.query_selector_all("li")
            if len(detail_items) < 2:
                continue

            event_time = detail_items[0].inner_text().strip()
            event_room = detail_items[1].inner_text().strip()

            mothership_events.append(
                MothershipEvent(
                    title=event_title,
                    dt=event_date,
                    time=event_time,
                    room=event_room,
                )
            )

        browser.close()

    return mothership_events


def process_new_mothership_events(
    table: Table,
    mothership_events: List[MothershipEvent],
    filtered_titles: set[str],
) -> Set[MothershipEvent]:
    new_events: Set[MothershipEvent] = set()
    with table.batch_writer() as batch:
        for event in mothership_events:
            key = {"Hash": event.make_hash()}
            resp = table.get_item(Key=key)

            if "Item" not in resp:
                batch.put_item(Item={**key, **asdict(event)})
                if event.title not in filtered_titles:
                    new_events.add(event)

    return new_events


def lambda_handler(event: Any = None, context: Any = None) -> list[dict[str, Any]]:
    env_config = EnvironmentConfig.from_environment()

    filtered_titles = get_filtered_titles(env_config.filtered_titles_table)
    all_events: list[MothershipEvent] = get_all_events()
    new_events: set[MothershipEvent] = process_new_mothership_events(
        env_config.events_table, all_events, filtered_titles
    )
    logger.info("Finished!")

    return [asdict(mothership_event) for mothership_event in new_events]
