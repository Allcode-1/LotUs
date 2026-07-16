# LotUs

LotUs is a FastAPI backend for an auction-style marketplace. The project is built as a backend engineering MVP: users upload owned items, create auctions with lots, start auctions manually, accept bids in real time, reserve bidder balances, and settle sold lots.

This is not a production marketplace yet. The current focus is a correct domain core with REST commands, WebSocket updates, database invariants, migrations, and tests. Redis, durable background jobs, rate limiting, payment integration, Telegram notifications, and deployment hardening are planned as later layers.

## Engineering Focus

- FastAPI REST API with thin routers and service-layer domain logic.
- PostgreSQL, SQLAlchemy, Alembic migrations, and explicit database constraints.
- RS256 JWT auth with access/refresh tokens and role-based admin actions.
- Item image upload through S3-compatible object storage with presigned read URLs.
- Auction, lot, bid, item, and balance invariants backed by service checks and database constraints.
- WebSocket auction rooms for live events over REST/DB truth.
- Pytest integration coverage for auth, items, balances, auctions, bidding, WebSocket flow, and DB-level impossible states.

## Current Capabilities

- Auth: register, login, refresh, logout, current user, admin user listing.
- Items: upload items with 1-10 images, list all items, list my items, update/delete owned mutable items, manage item images.
- Balance: users have an account balance and reserved amount; admins can top up users.
- Auctions: owners create auctions from owned items, seller/admin can start, cancel, finish, and confirm lot sale.
- Bids: active users can bid on active lots if they are not the seller and have enough available balance.
- Settlement: winning bidder funds are reserved during bidding and transferred to the seller when the lot is sold.
- Realtime: auction WebSocket clients receive connection confirmation, snapshot, ping/pong, and live auction events.

## Domain Model

- `User`: authenticated account with `user` or `admin` role.
- `Balance`: money account with `amount`, `reserved_amount`, and computed `available_amount`.
- `Item`: owned object that can be uploaded, edited while mutable, added to an auction, sold, and later owned by the buyer.
- `ItemImage`: S3-backed image metadata for an item.
- `Auction`: event created by a seller, with shared settings and lifecycle status.
- `Lot`: auction line item that links one item to one auction and stores lot-specific bid settings.
- `Bid`: immutable bid record for a lot.

## Core Flow

1. A user registers and uploads an item with images.
2. The owner creates an auction and selects one or more owned items as lots.
3. The item becomes `in_auction`, preventing mutation and duplicate open listings.
4. Seller or admin manually starts the auction.
5. Bidders connect to the auction room through WebSocket and place bids through REST.
6. The service validates bid amount, lot status, bidder permissions, and available balance.
7. The current winner's bid amount is reserved; the previous winner's reservation is released.
8. Seller/admin confirms sale, or the timer path can confirm after the sale window.
9. The item owner changes to the winning bidder, bidder funds are captured, seller balance increases, and the lot becomes sold.

## API Overview

The app exposes grouped routes under `/api/v1`:

- `/auth` for registration, login, refresh, logout, and user identity.
- `/items` for owned item and image management.
- `/balance` for current balance and admin top-ups.
- `/auctions` for auction lifecycle, lots, bids, and settlement.
- `/ws/auctions/{auction_id}` for auction-room live updates.

Use FastAPI docs for exact request/response schemas:

```text
http://127.0.0.1:8000/docs
```

## WebSocket Flow

WebSocket is used as a live event channel, not as the source of truth.

The durable client flow is:

1. Fetch auction state through REST.
2. Open `/api/v1/ws/auctions/{auction_id}?token=<access_token>`.
3. Receive `connected`.
4. Receive `auction_snapshot`.
5. Apply later events such as `auction_started`, `bid_placed`, `lot_sold`, and `auction_finished`.
6. On reconnect, fetch a fresh REST snapshot before trusting new live events.

The current WebSocket manager is in memory. It is fine for the MVP and tests, but it is not multi-worker-safe. Redis pub/sub is the planned next step for production-like fanout.

## Setup

Install dependencies:

```bash
uv sync
```

Copy environment settings:

```bash
cp .env.example .env
```

Create JWT keys if `certs/private.pem` and `certs/public.pem` are missing:

```bash
mkdir -p certs
openssl genrsa -out certs/private.pem 2048
openssl rsa -in certs/private.pem -pubout -out certs/public.pem
```

Configure `DATABASE_URL`, `TEST_DATABASE_URL`, and S3-compatible storage settings in `.env`.

Apply migrations:

```bash
uv run alembic upgrade head
```

Run the API:

```bash
uv run uvicorn app.main:app --reload
```

For local or VPS MinIO setup, see [docs/MINIO.md](docs/MINIO.md).

## Tests And Checks

`TEST_DATABASE_URL` must point to a dedicated test database whose name contains `test`. The test setup refuses to run against the main database.

```bash
uv run ruff check app tests alembic
uv run pytest -q
uv run python -m compileall -q app tests alembic
uv run alembic check
```

Current coverage is integration-heavy: HTTP flows, WebSocket behavior, and database invariant checks are tested through the real FastAPI app and SQLAlchemy session.

## Current Limits

- WebSocket connections and sale timers are in memory.
- Auto-start, durable auto-confirm, email/TG notifications, and payment integration are not implemented yet.
- Rate limiting and abuse controls are not implemented yet.
- Admin bootstrap is still operational/manual, not a polished onboarding flow.
- Docker files exist, but production deployment hardening is still a roadmap item.

## Roadmap

- Redis for WebSocket fanout, cache, and rate limiting.
- Background jobs for auto-start, auto-finish, sale confirmation, and notifications.
- Telegram bot integration and notification workflows.
- Payment integration and stronger ledger/audit modeling.
- Containerized test deployment with documented operational commands.
- Broader security pass: CORS policy, secrets handling, upload scanning, audit logs, and abuse controls.

## What This Project Is Not

LotUs is not trying to be a finished commercial auction platform yet. The current value is the backend core: transactional domain behavior, database-backed invariants, WebSocket event flow, migrations, and tests that make future infrastructure work safer.
