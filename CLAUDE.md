# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Discord notifier for new Comedy Mothership show listings. A local script scrapes `comedymothership.com/shows`, deduplicates against DynamoDB, and Discord notifications are sent via a Lambda triggered by DynamoDB Streams.

## Commands

**Python (uv)**
```bash
uv sync --no-install-project   # install deps
uvx ruff check .               # lint
uvx ruff format .              # format
uvx mypy mothership            # type check
uv run --no-project python3 scripts/scrape.py  # run scraper locally
```

**CDK (TypeScript)**
```bash
npm install
tsc                     # compile TS
cdk synth               # synthesize CloudFormation
cdk deploy              # deploy to AWS
cdk diff                # diff against deployed stack
```

**Pre-commit**
```bash
pre-commit run --all-files     # run all hooks manually
```

## Architecture

### Execution Flow

1. **`scripts/scrape.py`** runs locally (cron every 5 min) — scrapes site, writes new events to DynamoDB `MothershipEventsTable` (hash-keyed)
2. **DynamoDB Stream** on `MothershipEventsTable` triggers **SendNotificationFunction Lambda** on INSERT
3. **SendNotificationFunction** checks `MothershipFilteredTitlesTable` and posts to Discord channel

Discord interactions (e.g. "Filter This Show" button) are handled by a separate **DiscordInteractionFunction** Lambda behind API Gateway.

### Single Docker Image, Multiple Handlers

Both Lambdas share one Docker image (`Dockerfile` → `mothership.main.process_event`). The `HANDLER` env var selects which task runs:
- `SEND_NOTIFICATION` → `src/mothership/tasks/send_discord_message.py`
- `HANDLE_DISCORD_INTERACTION` → `src/mothership/tasks/handle_discord_interaction.py`

`src/mothership/main.py` routes based on `HANDLER`.

### Environment Config Pattern

`src/mothership/environment.py` defines a shared `Environment` Pydantic model. Fields are populated from env vars by uppercasing the field name — see `_get_default_or_mapping_item`. Fields without a default require the env var to be set. The `Environment` class also provides cached `boto3_session`, `dynamodb_resource`, `filtered_titles_table` properties and a `create_logger` factory.

### Infrastructure

`lib/stacks/mothership-stack.ts` defines all AWS resources: two DynamoDB tables (`MothershipEventsTable` with stream, `MothershipFilteredTitlesTable`), two Lambda functions, API Gateway, and IAM roles. Discord secrets are stored in Secrets Manager (`mothership/discord-bot-token`, `mothership/discord-public-key`).

### Key Files

| File | Purpose |
|------|---------|
| `src/mothership/main.py` | Lambda entrypoint, handler routing |
| `src/mothership/tasks/send_discord_message.py` | DynamoDB stream → Discord notification |
| `src/mothership/tasks/handle_discord_interaction.py` | Discord button interactions |
| `src/mothership/tasks/get_new_mothership_events.py` | Scraping + DynamoDB deduplication |
| `src/mothership/models/__init__.py` | `MothershipEvent` Pydantic model + hash/message formatting |
| `src/mothership/environment.py` | Shared `Environment` Pydantic config + boto3/logging setup |
| `src/mothership/wrappers/discord_wrapper.py` | Discord API client |
| `lib/stacks/mothership-stack.ts` | All CDK infrastructure |
| `scripts/scrape.py` | Local scraper runner |
