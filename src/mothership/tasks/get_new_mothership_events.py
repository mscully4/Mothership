import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any

from playwright.sync_api import sync_playwright

from mothership.environment import Environment
from mothership.models import MothershipEvent

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table


class GetNewMothershipEventsEnvironment(Environment):
    events_table_name: str

    @cached_property
    def events_table(self) -> "Table":
        return self.dynamodb_resource.Table(self.events_table_name)


def get_filtered_titles(env: GetNewMothershipEventsEnvironment) -> set[str]:
    resp = env.filtered_titles_table.scan(ProjectionExpression="Title")
    return {str(item["Title"]) for item in resp.get("Items", [])}


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
    env: GetNewMothershipEventsEnvironment,
    mothership_events: list[MothershipEvent],
    filtered_titles: set[str],
) -> set[MothershipEvent]:
    new_events: set[MothershipEvent] = set()
    with env.events_table.batch_writer() as batch:
        for event in mothership_events:
            key = {"Hash": event.make_hash()}
            resp = env.events_table.get_item(Key=key)

            if "Item" not in resp:
                batch.put_item(Item={**key, **event.model_dump()})
                if event.title not in filtered_titles:
                    new_events.add(event)

    return new_events


def lambda_handler(event: Any = None, context: Any = None) -> list[dict[str, Any]]:
    env = GetNewMothershipEventsEnvironment.from_environment()
    logger = env.create_logger(__name__, logging.INFO)

    filtered_titles = get_filtered_titles(env)
    all_events: list[MothershipEvent] = get_all_events()
    new_events = process_new_mothership_events(env, all_events, filtered_titles)
    logger.info("Finished!")

    return [mothership_event.model_dump() for mothership_event in new_events]
