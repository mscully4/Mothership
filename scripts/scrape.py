#!/usr/bin/env python3
"""Scrape Comedy Mothership shows and write new events to DynamoDB.

Run every 5 minutes via cron:
  */5 * * * * cd /path/to/Mothership && AWS_PROFILE=default python3 scripts/scrape.py

New events written to DynamoDB automatically trigger the SendNotificationFunction
Lambda via DynamoDB Streams, which posts to Discord.

Required env vars (or set in .envrc):
  AWS_PROFILE or AWS_DEFAULT_PROFILE
  EVENTS_TABLE_NAME         (default: MothershipEventsTable)
  FILTERED_TITLES_TABLE_NAME (default: MothershipFilteredTitlesTable)
  AWS_DEFAULT_REGION        (default: us-east-2)
"""

import os
import sys

# Defaults so you don't need to export these every time
os.environ.setdefault("EVENTS_TABLE_NAME", "MothershipEventsTable")
os.environ.setdefault("FILTERED_TITLES_TABLE_NAME", "MothershipFilteredTitlesTable")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")

# Add repo root to path so mothership package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mothership.tasks.get_new_mothership_events import lambda_handler

if __name__ == "__main__":
    new_events = lambda_handler()
    print(f"New events written to DynamoDB: {len(new_events)}")
