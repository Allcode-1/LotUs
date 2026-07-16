# RBAC

LotUs currently has two roles:

- `user`: normal authenticated account.
- `admin`: operational role with platform-level permissions.

Authentication uses RS256 JWT access tokens and refresh tokens. Access tokens authorize normal requests. Refresh token sessions are stored in the database and can be revoked on logout/refresh rotation.

## Permission Matrix

| Capability | Anonymous | User | Seller | Admin |
| --- | --- | --- | --- | --- |
| Register/login | Yes | Yes | Yes | Yes |
| Refresh/logout with refresh token | Yes | Yes | Yes | Yes |
| Read own user profile | No | Yes | Yes | Yes |
| List all users | No | No | No | Yes |
| Create item | No | Yes | Yes | Yes |
| List items | No | Yes | Yes | Yes |
| List own items | No | Yes | Yes | Yes |
| Update/delete own mutable item | No | Owner only | Owner only | Owner only |
| Add/delete images on own mutable item | No | Owner only | Owner only | Owner only |
| Read own balance | No | Yes | Yes | Yes |
| Top up any user balance | No | No | No | Yes |
| Create auction from owned items | No | Owner only | Owner only | Owner only |
| Start own auction | No | No | Yes | Yes |
| Cancel own auction before bids | No | No | Yes | Yes |
| Finish own active auction | No | No | Yes | Yes |
| Confirm lot sale in own auction | No | No | Yes | Yes |
| Bid on active lot | No | Yes, except seller | No on own auction | Yes, except own auction if seller |
| Read auction/lots/bids | No | Yes | Yes | Yes |
| Connect to auction WebSocket | No | Yes | Yes | Yes |

`Seller` is not a separate database role. It means the user whose `id` equals `auction.seller_id`.

## Auth Rules

- Missing or invalid access token returns `401`.
- Inactive user returns `403`.
- Non-admin user calling an admin endpoint returns `403`.
- WebSocket connections require `?token=<access_token>`.
- Invalid WebSocket token or missing auction closes the connection with policy violation code `1008`.

## Item Rules

- Any active user can create an item with valid images.
- Only the current item owner can mutate/delete the item or manage its images.
- Items can be mutated only while their status is mutable: `draft` or `available`.
- When an item is added to an auction, it becomes `in_auction`.
- `in_auction` items cannot be edited, deleted, or added to another open lot.
- After a successful sale, the item owner becomes the winning bidder and the item becomes `available`.

## Auction Rules

- Only the current owner of every selected item can create an auction.
- The same item cannot appear twice in one auction.
- The same item cannot be attached to two open lots at the database boundary.
- Auction time window must be valid and end in the future.
- Seller/admin can start a scheduled auction.
- Seller/admin can cancel an auction only while it has no bids.
- Seller/admin can finish an active auction.
- Seller/admin can confirm sale for a lot with a winner.

## Bid Rules

- Auction must be active.
- Lot must be active.
- Seller cannot bid on their own auction.
- Highest bidder cannot immediately outbid themselves.
- First bid must meet the lot start price.
- Later bids must meet current price plus lot-level increment, or auction-level increment if the lot has no override.
- Bidder must have enough available balance.
- Previous winner reservation is released when outbid.
- Current winner reservation is captured when the lot is sold.

## Admin Scope

Admins are operational users, not all-powerful object owners.

Admins can:

- list users;
- top up balances;
- start/cancel/finish auctions;
- confirm lot sales.

Admins do not currently bypass item ownership for editing/deleting items or adding someone else's item to a new auction.

## Current Gaps

- There is no public admin bootstrap endpoint.
- There is no rate limiting yet.
- There is no per-action audit log yet.
- There is no fine-grained permission table; role checks are coded directly in services/dependencies.
- There is no object-level admin override for item mutation.

These gaps are acceptable for the current MVP and should be revisited during the security/rate-limiting phase.
