# Comedy Mothership Notifier

Discord notifier for new show listings on `comedymothership.com`. A local scraper writes new events to DynamoDB; a Lambda posts Discord notifications on INSERT via DynamoDB Streams.

## How It Works

1. **`scripts/scrape.py`** runs locally on a cron (every 5 min) — scrapes `comedymothership.com/shows`, deduplicates against DynamoDB, writes new events to `MothershipEventsTable`
2. **DynamoDB Stream** triggers **SendNotificationFunction** Lambda on INSERT
3. **SendNotificationFunction** checks `MothershipFilteredTitlesTable` and posts to Discord

Discord button interactions ("Filter This Show") are handled by **DiscordInteractionFunction** Lambda behind API Gateway.

## Architecture

### Single Docker Image, Multiple Handlers

Both Lambdas share one Docker image. The `HANDLER` env var selects which task runs:

| `HANDLER` | Module |
|-----------|--------|
| `SEND_NOTIFICATION` | `src/mothership/tasks/send_discord_message.py` |
| `HANDLE_DISCORD_INTERACTION` | `src/mothership/tasks/handle_discord_interaction.py` |

### Key Files

| File | Purpose |
|------|---------|
| `src/mothership/main.py` | Lambda entrypoint, routes by `HANDLER` |
| `src/mothership/tasks/send_discord_message.py` | DynamoDB stream → Discord notification |
| `src/mothership/tasks/handle_discord_interaction.py` | Discord button interactions |
| `src/mothership/tasks/get_new_mothership_events.py` | Scraping + DynamoDB deduplication |
| `src/mothership/models/__init__.py` | `MothershipEvent` Pydantic model + hash/message formatting |
| `src/mothership/environment.py` | Shared `Environment` Pydantic config + boto3 session/logging |
| `src/mothership/wrappers/discord_wrapper.py` | Discord API client |
| `lib/stacks/mothership-stack.ts` | All CDK infrastructure |
| `scripts/scrape.py` | Local scraper runner |

### Infrastructure (CDK)

- **DynamoDB**: `MothershipEventsTable` (hash-keyed, stream enabled), `MothershipFilteredTitlesTable`
- **Lambda**: two Docker image functions sharing one image asset
- **API Gateway**: REST API proxying `DiscordInteractionFunction`
- **Secrets Manager**: `mothership/discord-bot-token`, `mothership/discord-public-key`

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
pre-commit run --all-files
```
