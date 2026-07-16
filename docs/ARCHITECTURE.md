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
- `app/core`: settings, domain errors, and global exception handlers.
- `app/storage`: S3-compatible object storage adapter.

For aggregate commands like bidding and settlement, services own `commit` and `rollback`. That keeps multi-model changes atomic: lot state, bid record, item owner/status, and balances move together.

Redis-backed concerns stay outside the domain services. Routes compose rate-limit policies and cache invalidation around service calls; the domain service still only knows SQLAlchemy and domain errors.

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

The MVP uses manual start/finish. Auto-start and durable timers belong to the future background-job layer.

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

1. Seller/admin confirms the lot sale, or the timer path calls the same settlement logic after the confirmation window.
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

On reconnect, the client should fetch a fresh REST snapshot. The in-memory manager does not store missed events.

## Redis Usage

Redis is currently used for two concerns:

- rate limiting;
- cache-aside auction snapshots.

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

## Testing Strategy

Tests are integration-oriented:

- HTTP tests cover auth, item upload, balance top-up, auction lifecycle, bidding, settlement, permissions, and negative paths.
- WebSocket tests open an ASGI WebSocket connection, assert snapshot/ping behavior, reject invalid tokens, and verify that an HTTP bid broadcasts `bid_placed`.
- Rate-limit tests use a fake Redis and assert `429` responses without requiring a live Redis process.
- Cache tests use fake Redis to prove cache-aside reads and mutation invalidation.
- DB invariant tests intentionally try to write impossible states and expect `IntegrityError`.

External object storage is faked in tests, Redis is faked in tests, password hashing is shortened, the in-memory sale timer is disabled, and each test runs inside an isolated database transaction.

## Known MVP Limits

- WebSocket manager is process-local.
- Sale timer is process-local and not durable.
- No Redis pub/sub layer yet.
- No background job worker yet.
- No payment integration yet.
- No production observability/audit trail yet.

These are deliberate next layers, not hidden production claims.
