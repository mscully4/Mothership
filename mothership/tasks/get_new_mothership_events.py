import logging
import os
from dataclasses import asdict, dataclass, fields
from typing import Any, List, Mapping, Optional, Set

import boto3
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from bs4 import BeautifulSoup
import requests
import json

from mothership.utils.environment import get_default_or_mapping_item
from mothership.utils.logging import configure_logging
from mothership.models import MothershipEvent
from functools import cached_property

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    aws_region: str
    events_table_name: str
    _session: Optional[boto3.Session] = None

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
            self._session = boto3.Session(region_name=self.aws_region)

        return self._session
    
    @cached_property
    def events_table(self):
        ddb: DynamoDBServiceResource = self.get_session().resource("dynamodb")
        return ddb.Table(self.events_table_name)


def get_all_events() -> list[MothershipEvent]:
    url = 'https://comedymothership.com/shows'
    response = requests.get(url)

    soup = BeautifulSoup(response.content, 'html.parser')

    # There will be a script tag with id __NEXT_DATA__ that has all
    # the shows as a json blob
    script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
    data = json.loads(script_tag.string)

    mothership_events: list[MothershipEvent] = []
    for event in data['props']['pageProps']['data']['events']:
        modeled_event = MothershipEvent(
            _id=event['_id'],
            dt=event['start'],
            title=event['title'],
            ticket_availability=event['ticketAvailability'],
            url=event['url'],
            room=event['room']['title']
        )

        if modeled_event.ticket_availability == 'presale':
            continue

        mothership_events.append(modeled_event)

    return mothership_events


def process_new_mothership_events(
    table, mothership_events: List[MothershipEvent]
) -> Set[MothershipEvent]:
    new_events: Set[MothershipEvent] = set()
    with table.batch_writer() as batch:
        for event in mothership_events:
            key = {
                "Hash": event._id,
            }
            resp = table.get_item(Key=key)

            # We only want to do anything for shows we haven't
            # encountered before
            if "Item" not in resp:
                new_events.add(event)
                batch.put_item(Item={**key, **asdict(event)})

            logger.info(resp)

    return new_events


def lambda_handler(event: Mapping[str, Any] = os.environ, context = None) -> list[dict[str, Any]]:
    env_config = EnvironmentConfig.from_environment()

    all_events: list[MothershipEvent] = get_all_events()
    new_events: set[MothershipEvent] = process_new_mothership_events(env_config.events_table, all_events)
    logger.info("Finished!")

    return [asdict(mothership_event) for mothership_event in new_events]
