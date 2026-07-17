# LotUs

LotUs is a FastAPI backend API for an auction-style marketplace.

This project is built as a backend engineering portfolio project, focused on
auction domain modeling, transactional bidding, balance reservation, WebSocket
live updates, PostgreSQL invariants, Redis, Celery/RabbitMQ, S3-compatible item
images, and integration testing.

## Engineering Focus

- RS256 JWT authentication with access and refresh tokens.
- User/admin roles with admin-only balance top-ups.
- Owned item management with image uploads through S3-compatible storage.
- Auction lifecycle: scheduled, active, finished, cancelled.
- Lot lifecycle: pending, active, sold, unsold, cancelled.
- Bid workflow with balance reservation and previous-winner release.
- Seller/admin auction management: start, cancel, finish, confirm lot sale.
- Transaction boundaries in the service layer.
- Row-level locks for bidding, settlement, lifecycle changes, items, and balances.
- PostgreSQL schema with SQLAlchemy 2, Alembic migrations, constraints, and indexes.
- Redis-backed rate limiting for auth and bid commands.
- Redis cache-aside for auction snapshots.
- Redis Pub/Sub fanout for WebSocket auction events.
- Celery + RabbitMQ background jobs for auction lifecycle, delayed settlement,
  cleanup, and notification stubs.
- Request-scoped logging with domain event metadata.
- Pytest integration coverage for HTTP, WebSocket, cache, Pub/Sub, Celery
  registration, and database invariants.

## Domain Model

LotUs models a marketplace where users upload owned items, combine one or more
items into auction lots, start an auction, accept bids in real time, reserve the
current winner's funds, and settle sold lots by moving money and item ownership
inside one transactional domain flow.

Core entities:

- `User`: authenticated account with `user` or `admin` role.
- `Balance`: user money account with `amount`, `reserved_amount`, and computed
  `available_amount`.
- `Item`: owned object that can be uploaded, listed, placed into an auction,
  sold, and later owned by the buyer.
- `ItemImage`: database metadata for images stored in S3-compatible object
  storage.
- `Auction`: seller-owned auction event with shared timing and bid settings.
- `Lot`: one auction position linking one item to one auction, with optional
  lot-specific bid settings.
- `Bid`: immutable bid record for a lot.

`Inventory` and `Profile` are intentionally not backend tables. A user's
inventory is currently represented by the owned-item read model, mainly
`GET /items/me`, while profile-style screens can be built from user and balance
responses.

Auction workflow:

```text
SCHEDULED -> ACTIVE -> FINISHED
SCHEDULED -> CANCELLED
```

Lot workflow:

```text
PENDING -> ACTIVE -> SOLD
PENDING -> ACTIVE -> UNSOLD
PENDING -> CANCELLED
```

## Backend Design

The main request path is intentionally simple:

```text
FastAPI route -> service -> repository -> SQLAlchemy/PostgreSQL
```

Routes stay thin: they parse dependencies, call services, invalidate cache, and
schedule live events or background tasks around committed domain changes.
Services own business rules and transaction boundaries. Repositories isolate
SQLAlchemy queries and locking details. Models define relationships, enums, and
database-level invariants.

Redis and Celery are used around the domain rather than inside every business
rule: Redis protects hot endpoints, stores short-lived auction snapshots, and
fans out WebSocket events; Celery handles delayed or periodic work that should
not depend on a single HTTP request staying alive.

## Engineering Decisions

**Why separate `Item`, `Auction`, and `Lot`?**
An item is an owned object. An auction is an event. A lot is the auction position
that connects one item to that event and stores bidding state. This keeps the
model ready for auctions with one item or many items without overloading `Item`
with temporary auction-specific fields.

**Why keep transactions in services?**
Bidding and settlement touch several aggregates at once: lot state, bid record,
winner balance, previous winner balance, seller balance, and item ownership.
Keeping `commit`/`rollback` in the service layer makes those changes atomic and
keeps route handlers thin.

**Why REST plus WebSocket instead of WebSocket-only bidding?**
REST remains the command and source-of-truth path. WebSocket is the live delivery
channel for already-persisted changes. This makes reconnect behavior simpler:
the client can always fetch a fresh REST snapshot and then resume listening for
events.

**Why Redis Pub/Sub?**
Each API process owns only its local WebSocket connections. Redis Pub/Sub lets
one committed auction event reach every API process, and each process forwards
the event to its local clients.

**Why cache-aside only for auction snapshots?**
Auction snapshots are useful read targets and easy to rebuild from PostgreSQL.
Cache-aside keeps PostgreSQL as the source of truth and makes invalidation
explicit after bid, lifecycle, and settlement mutations.

## Authentication

The authentication flow includes user registration, login, bcrypt password
hashing, RS256 access/refresh JWTs, refresh sessions stored in PostgreSQL,
refresh-token rotation, logout/revoke, and a current-user endpoint.

Registration can enqueue a notification task. The notification task is currently
a stub and logs the intended event instead of sending real email.

## Items And Storage

Users can upload items with images. Item images are stored outside PostgreSQL in
S3-compatible storage such as MinIO, AWS S3, or Cloudflare R2. The database keeps
metadata such as storage key, content type, size, and sort order.

Current image rules:

- item creation requires images;
- an item can have at most 10 images;
- supported content types are JPEG, PNG, and WebP;
- the backend returns presigned read URLs.

For local MinIO setup, see [docs/MINIO.md](docs/MINIO.md).

## Auction And Bidding

The auction core supports:

- creating an auction from one or more owned available items;
- moving selected items into `in_auction` status;
- manual start by seller/admin;
- manual cancel before bids exist;
- manual finish by seller/admin;
- bidding on active lots;
- automatic release of the previous highest bidder's reserved funds;
- manual lot sale confirmation;
- delayed lot sale confirmation after the bid window;
- automatic auction finish when all lots become terminal.

Bid placement is transactional:

```text
lock lot -> validate auction/lot/bidder/amount -> lock balances
-> release previous reservation -> reserve new bid -> write bid
-> update lot -> commit -> publish live event
```

Settlement is also transactional:

```text
lock auction/lots -> lock seller and winner balances
-> capture reserved funds -> credit seller -> move item ownership
-> mark lot sold -> maybe finish auction -> commit
```

## WebSocket Flow

WebSocket is used for live auction rooms, not for durable state.

Client flow:

```text
REST snapshot -> WebSocket connect -> connected -> auction_snapshot -> live events
```

Connection URL:

```text
/api/v1/ws/auctions/{auction_id}?token=<access_token>
```

Supported client message:

- `ping` -> `pong`

Server events currently include:

- `auction_started`
- `auction_cancelled`
- `auction_finished`
- `bid_placed`
- `lot_sold`

On reconnect, the client should fetch a fresh REST snapshot. Redis Pub/Sub does
not replay missed events, and the in-memory WebSocket manager does not store
event history.

## Redis

Redis is used in three places:

- fixed-window rate limiting;
- cache-aside auction snapshots;
- Pub/Sub fanout for auction WebSocket events.

Rate limiting covers:

- registration by client IP;
- login by client IP and username+IP;
- bids by bidder and lot.

Cache reads are designed to fail open by default. Rate limiting is fail-closed
by default so protected commands do not silently become unlimited when Redis is
unavailable.

## Celery / Background Jobs

RabbitMQ is used as the Celery broker. The API process enqueues tasks, workers
consume tasks, and Celery Beat schedules periodic maintenance.

Current tasks:

- `lotus.auctions.auto_confirm_lot_sale`: delayed settlement after the current
  bid window.
- `lotus.auctions.sync_lifecycle`: periodic auction lifecycle synchronization.
- `lotus.cleanup.expired_refresh_sessions`: cleanup for old expired refresh
  sessions.
- `lotus.notifications.registration_email`: registration email stub.
- `lotus.notifications.auction_started_telegram`: auction-start Telegram stub.
- `lotus.notifications.auction_finished_telegram`: auction-finished Telegram
  stub.

Notification tasks are intentionally placeholders for now. Real SMTP and
Telegram bot delivery are planned as later integrations.

## Logging

The logging layer provides request-scoped metadata and domain event logs for
auth, balances, auctions, bids, Redis, Celery, and WebSocket flow.

By default logs are printed to stdout in a readable local format. For container
or log-collector environments, use:

```env
LOG_FORMAT=json
```

This keeps the application compatible with ELK/Loki-style collection without
binding the codebase to a specific logging vendor.

## API Overview

The API covers these main areas:

- Auth: register, login, refresh, logout, current user, admin user list.
- Items: create items with images, list items, list my items, update/delete
  mutable owned items, manage item images.
- Balance: current user balance and admin top-ups.
- Auctions: create, list, start, cancel, finish, confirm sale, read lot bids.
- WebSocket: auction-room snapshot and live events.

See the interactive OpenAPI documentation for exact schemas and endpoint list:

```text
http://127.0.0.1:8000/docs
```

## Local Development

Install dependencies:

```bash
uv sync
```

Create environment file:

```bash
cp .env.example .env
```

Generate JWT keys if they are missing:

```bash
mkdir -p certs
openssl genrsa -out certs/private.pem 2048
openssl rsa -in certs/private.pem -pubout -out certs/public.pem
```

Start local infrastructure:

```bash
docker compose up -d postgres redis rabbitmq
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Run the API:

```bash
uv run uvicorn app.main:app --reload
```

Run Celery worker and Beat in separate terminals when testing background jobs:

```bash
uv run celery -A app.celery_app:celery_app worker -l info
uv run celery -A app.celery_app:celery_app beat -l info
```

RabbitMQ management UI:

```text
http://127.0.0.1:15672
```

The current `docker-compose.yml` starts infrastructure services only. API,
worker, and Beat containers are not fully packaged yet because production Docker
hardening is still roadmap work.

## Testing

`TEST_DATABASE_URL` must point to a dedicated test database whose name contains
`test`. The test setup refuses to run against the main database.

Run the main checks:

```bash
uv run ruff check app tests alembic
uv run pytest -q
uv run python -m compileall -q app tests alembic
uv run alembic check
```

The test suite covers:

- auth HTTP flows;
- item and balance HTTP flows;
- auction happy paths and negative paths;
- bid invariants and balance reservation;
- WebSocket snapshot and live bid events;
- Redis cache and Pub/Sub behavior through fakes;
- Celery task registration and disabled-enqueue behavior;
- database-level impossible states.

Tests do not require live Redis or RabbitMQ. Redis is isolated through fakes and
Celery enqueueing is disabled where HTTP tests need deterministic behavior.

## Current Status

LotUs is an MVP / backend portfolio project.

Currently implemented:

- auth and refresh sessions;
- item/image management;
- balance top-up and reservation model;
- auction, lot, bid, and settlement domain core;
- WebSocket auction rooms;
- Redis rate limiting, cache-aside, and Pub/Sub fanout;
- Celery/RabbitMQ tasks for auction lifecycle and cleanup;
- logging and request IDs;
- Alembic migrations;
- integration tests for the main flows.

Prepared but not fully implemented:

- notification task boundaries for email and Telegram;
- auction-interest/watch behavior for pre-start notifications;
- delayed and periodic job infrastructure;
- MinIO/S3-compatible storage wiring;
- JSON logging for container log collectors.

Needs hardening:

- outbox pattern for durable event/task dispatch after DB commits;
- idempotency keys for sensitive commands such as bids and balance operations;
- stronger WebSocket authentication transport than query-string tokens;
- full concurrency/load tests for high-contention bidding;
- broader permission matrix tests;
- payment integration and ledger/audit modeling;
- production Dockerfile and deploy documentation;
- dependency/security audit and CI.

## Roadmap

### v0.2

- Auction watch/interest model.
- Pre-start Telegram reminders.
- Real registration email delivery.
- Real Telegram bot integration.
- More WebSocket reconnect and stale-event handling tests.
- Broader auction permission matrix.
- Fix strict `mypy` issues and add type-check configuration.

### v0.3

- Outbox table for durable notifications and WebSocket event dispatch.
- Payment provider integration.
- Ledger-style financial audit trail.
- Idempotency keys for bid and payment commands.
- Containerized API/worker/beat deployment.
- CI pipeline with tests, lint, migrations, and security checks.

## What This Project Is Not

- Not a production-ready auction marketplace.
- Not a full payment platform.
- Not a complete Telegram bot project yet.
- Not a microservice system.
- Not a high-traffic/load-tested realtime auction engine yet.
- Not a frontend application.
