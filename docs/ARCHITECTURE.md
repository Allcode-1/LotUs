# Architecture

LotUs is structured as a normal backend service first, with WebSockets layered on top for live auction events. PostgreSQL remains the source of truth; WebSocket messages are a delivery mechanism for state changes that are already persisted by REST commands.

## Layers

The request path is intentionally simple:

```text
FastAPI route -> service -> repository -> SQLAlchemy/PostgreSQL
```

- `app/api/v1`: HTTP and WebSocket entry points. Routes stay thin: parse dependencies, call a service, and schedule live broadcasts when needed.
- `app/auth`: JWT auth, current-user dependencies, login/register/refresh/logout.
- `app/services`: domain behavior and transaction boundaries.
- `app/repositories`: SQLAlchemy query helpers.
- `app/models`: SQLAlchemy models, relationships, enums, and database constraints.
- `app/schemas`: Pydantic request/response contracts.
- `app/redis`: Redis connection plumbing only.
- `app/rate_limit`: generic Redis-backed counters and endpoint policies.
- `app/cache`: cache-aside adapters and entity-specific cache keys.
- `app/ws`: in-memory WebSocket connection manager.
- `app/tasks`: Celery tasks for auction lifecycle sync, delayed sale confirmation, cleanup, and notification stubs.
- `app/celery_app.py`: Celery application and Beat schedule.
- `app/core`: settings, domain errors, and global exception handlers.
- `app/storage`: S3-compatible object storage adapter.

For aggregate commands like bidding and settlement, services own `commit` and `rollback`. That keeps multi-model changes atomic: lot state, bid record, item owner/status, and balances move together.

Redis-backed and Celery-backed concerns stay outside the domain services. Routes compose rate-limit policies, cache invalidation, Pub/Sub events, and task enqueueing around service calls; the domain service still only knows SQLAlchemy and domain errors.

## Domain Boundaries

The core entities are:

- `User`: account and role.
- `Balance`: account balance plus reserved funds.
- `Item`: object owned by a user.
- `ItemImage`: uploaded media metadata stored outside the database.
- `Auction`: seller-owned auction event.
- `Lot`: one item inside one auction, with per-lot pricing state.
- `Bid`: immutable bid event for a lot.

`Inventory` and `Profile` are frontend views, not backend domain tables. "My inventory" is currently represented by `GET /items/me`.

## Auction Lifecycle

Auction statuses:

- `scheduled`: created but not accepting bids.
- `active`: started manually by seller/admin.
- `finished`: terminal state after manual finish or all lots become terminal.
- `cancelled`: terminal state before any bids exist.

Lot statuses:

- `pending`: created under a scheduled auction.
- `active`: accepts bids while auction is active.
- `sold`: settled to a winning bidder.
- `unsold`: finished without a winner.
- `cancelled`: cancelled with the parent auction.

Manual start/finish remains available for seller/admin control. Celery Beat also runs lifecycle synchronization: due scheduled auctions can be started automatically, due active auctions can be finished automatically, and due sale-confirmation windows can be settled by the worker.

## Bidding And Settlement

Bid placement is a transactional command:

1. Lock the lot and load its auction/item.
2. Reject seller bids, inactive auctions, inactive lots, too-low bids, and already-highest-bidder repeats.
3. Lock bidder balance.
4. Verify `available_amount >= bid amount`.
5. Release the previous winner's reservation when outbid.
6. Reserve the new winner's bid amount.
7. Store the bid record and update lot price/winner/timestamps.
8. Commit.
9. Broadcast `bid_placed` after persistence.

Sale confirmation is also transactional:

1. Seller/admin confirms the lot sale, or the Celery delayed task calls the same settlement logic after the confirmation window.
2. Winner reserved funds are captured.
3. Seller balance increases.
4. Item ownership moves to the winner.
5. Lot becomes `sold`.
6. Auction becomes `finished` when all lots are terminal.

## Invariants

Service-level invariants:

- Only the current item owner can add an item to an auction.
- Only mutable items can be edited, deleted, or receive new images.
- A scheduled auction can be started only by seller/admin.
- A cancelled or finished auction cannot accept bids.
- A seller cannot bid on their own lot.
- A bidder must beat the required amount: start price first, then current price plus increment.
- A highest bidder cannot immediately outbid themselves.
- A bidder must have enough available balance.
- Auctions with existing bids cannot be cancelled.

Database-level invariants:

- Balance `amount` and `reserved_amount` cannot be negative.
- `reserved_amount` cannot exceed `amount`.
- Auction `ends_at` must be after `starts_at`.
- Auction and lot bid increments must be positive.
- Lot prices must be positive, and `current_price` cannot be below `start_price`.
- Sold lot price and sold timestamp must be set together.
- Sale confirmation timestamp requires a last bid timestamp and cannot be before it.
- One item can be attached to only one open lot at a time.
- Item image size and sort order must be valid, and sort order is unique per item.
- Bid amount must be positive.

These rules are split intentionally. Services provide useful API errors; database constraints protect against impossible states if a future code path misses a check.

## Concurrency

The critical concurrency boundary is bidding and settlement. The service uses row locks through repository queries where needed:

- auction/lots during lifecycle transitions;
- lot during bid placement;
- item rows when creating auctions;
- balance rows when reserving, releasing, or settling funds.

The current implementation is still an MVP. It protects the core transaction path, but production-grade contention testing and observability should be added later.

## WebSocket Model

REST commands change state. WebSocket broadcasts the resulting state.

Auction events use Redis Pub/Sub for cross-process fanout:

```text
REST command -> DB commit -> Redis publish -> every API process receives event -> local WebSocket broadcast
```

Each API process still owns only its local WebSocket connections. Redis Pub/Sub is the bridge between processes.

Current auction-room flow:

```text
REST snapshot -> WebSocket connect -> connected -> auction_snapshot -> live events
```

Supported client message:

- `ping` -> `pong`

Server events currently include:

- `auction_started`
- `auction_cancelled`
- `auction_finished`
- `bid_placed`
- `lot_sold`

On reconnect, the client should fetch a fresh REST snapshot. Redis Pub/Sub does not replay missed events, and the in-memory manager does not store them.

## Redis Usage

Redis is currently used for three concerns:

- rate limiting;
- cache-aside auction snapshots;
- WebSocket auction event fanout.

Rate limiting uses fixed windows with atomic Redis `INCR` plus `EXPIRE`:

- register: per client IP;
- login: per client IP and per username+IP;
- bids: per bidder and per lot.

Rate limiting is fail-closed by default. If Redis is unavailable, protected commands return a service-unavailable error instead of silently allowing unlimited traffic. This can be changed through configuration for local experiments.

Auction snapshot caching follows cache-aside:

```text
GET auction -> Redis lookup -> DB on miss -> serialize AuctionRead -> set TTL
mutation -> commit DB changes -> delete cached auction snapshot
```

The cached snapshot TTL is intentionally short because auction responses include presigned item image URLs. Current invalidation points include auction start/cancel/finish, lot sale confirmation, and bid placement.

WebSocket fanout publishes auction events to one Redis channel:

```text
lotus:v1:auction-events
```

Messages contain the auction id and the event payload. Every API process subscribes to the channel on startup and forwards matching events to its local WebSocket connections. If Pub/Sub is disabled locally, the publisher falls back to direct in-process broadcast. If Redis publish fails, local fallback can keep single-process development usable, but multi-worker delivery depends on Redis being healthy.

## Celery And RabbitMQ

RabbitMQ is used as the Celery broker for durable background tasks. The API process enqueues tasks; Celery workers consume them; Celery Beat schedules periodic tasks.

Current tasks:

- `lotus.auctions.auto_confirm_lot_sale`: delayed task scheduled after a bid's sale-confirmation window.
- `lotus.auctions.sync_lifecycle`: Beat task that starts due auctions, confirms due lot sales, and finishes due auctions.
- `lotus.cleanup.expired_refresh_sessions`: periodic cleanup for old expired refresh sessions.
- `lotus.notifications.registration_email`: email stub after registration.
- `lotus.notifications.auction_started_telegram`: Telegram stub for users interested in an auction.
- `lotus.notifications.auction_finished_telegram`: Telegram stub for auction completion.

The worker uses the same service functions as HTTP commands where possible, so database locks and domain invariants stay in one domain layer. Celery tasks invalidate auction cache and publish WebSocket events after successful DB changes.

Notification tasks are intentionally stubbed for now. They log the intended event and will later be wired to SMTP and the Telegram bot.

## Logging and Observability

Logging is configured in `app/core/logging.py` and attached through `RequestContextMiddleware`.

The current logging layer provides:

- request-scoped `X-Request-ID`;
- HTTP completion logs with method, path, status, duration, client IP, and user agent;
- application error logs from the global exception handlers;
- focused domain event logs for auth, balance top-up, auction lifecycle, bids, lot settlement, Redis rate-limit/cache failures, Celery tasks, and WebSocket room connection flow;
- `LOG_LEVEL` and `LOG_FORMAT` configuration.

By default logs use a readable console format:

```text
2026-07-16 12:00:00 | INFO     | app.services.auction | req=... | bid placed | event="bid_placed" auction_id="..." lot_id="..."
```

For containerized deployments, set:

```text
LOG_FORMAT=json
```

JSON logs are intended for collectors such as Filebeat, Fluent Bit, Vector, Promtail, or a cloud logging agent. The application writes logs to stdout; Docker, systemd, Kubernetes, or the host logging agent is responsible for storing and shipping them. File-based log rotation is intentionally not part of the app layer yet because stdout works better for multi-process/container deployments.

ELK/Loki-style log aggregation can be added around the existing logger without changing service code:

```text
app stdout -> container/host log collector -> Elasticsearch or Loki -> dashboards/search
```

Prometheus is a separate concern. It should not scrape application logs. When metrics are added, expose numeric counters/histograms through a `/metrics` endpoint, for example request count, request latency, bid count, rate-limit hits, Redis failures, and WebSocket connection counts.

## Testing Strategy

Tests are integration-oriented:

- HTTP tests cover auth, item upload, balance top-up, auction lifecycle, bidding, settlement, permissions, and negative paths.
- WebSocket tests open an ASGI WebSocket connection, assert snapshot/ping behavior, reject invalid tokens, and verify that an HTTP bid broadcasts `bid_placed`.
- Rate-limit tests use a fake Redis and assert `429` responses without requiring a live Redis process.
- Cache tests use fake Redis to prove cache-aside reads and mutation invalidation.
- DB invariant tests intentionally try to write impossible states and expect `IntegrityError`.

External object storage is faked in tests, Redis is faked in tests, Celery enqueueing is disabled in HTTP tests, password hashing is shortened, and each test runs inside an isolated database transaction.

## Known MVP Limits

- WebSocket manager is process-local, with Redis Pub/Sub fanout between processes.
- Celery worker and Beat must be running for automatic lifecycle behavior.
- Notification tasks are stubs until SMTP and Telegram bot integrations are implemented.
- No payment integration yet.
- No production observability/audit trail yet.

These are deliberate next layers, not hidden production claims.
