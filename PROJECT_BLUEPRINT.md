# BidKori: Master Project Blueprint & Architecture

## 1. Executive Summary
BidKori is a real-time online auction marketplace for Bangladesh, transforming fragmented social-media bidding into a structured, automated, and secure digital platform[cite: 1]. It serves individual sellers (C2C), commercial/refurbished electronics dealers (B2C), and active bidders through synchronized live auctions[cite: 1].

---

## 2. Global Architecture Diagram



             ┌───────────────────────────────────────────────┐
             │       Client UI (Tailwind CSS + JS)           │
             └───────────────┬───────────────────────────────┘
                             │
              HTTP / REST    │        WebSocket
             ┌───────────────┴───────────────┐
             ▼                               ▼
 ┌───────────────────────┐       ┌───────────────────────┐
 │   Django REST (WSGI)  │       │ Django Channels(ASGI) │
 └───────────┬───────────┘       └───────────┬───────────┘
             │                               │
             ├───────────────┬───────────────┤
             ▼               ▼               ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │  PostgreSQL  │ │ Redis Pub/Sub│ │ Celery Worker│
     │  (Master DB) │ │   & Cache    │ │  (AI Engine) │
     └──────────────┘ └──────┬───────┘ └──────┬───────┘
                             │                │
                             │         ┌──────┴──────┐
                             └────────►│  Gemini API │
                                       └─────────────┘


---

## 3. Core Database Entities (PostgreSQL Schema)

### `users.User`
- `id`: UUID (Primary Key)
- `email`: VARCHAR(255), Unique
- `phone`: VARCHAR(20), Unique
- `password_hash`: VARCHAR(255)
- `role`: ENUM ('BUYER', 'INDIVIDUAL_SELLER', 'BUSINESS_SELLER', 'ADMIN')
- `is_verified`: BOOLEAN, Default False
- `created_at`: TIMESTAMPTZ

### `users.SellerProfile`
- `id`: UUID (Primary Key)
- `user`: 1-to-1 ForeignKey to `User`
- `business_name`: VARCHAR(255), Nullable
- `trade_license_number`: VARCHAR(100), Nullable
- `rating`: DECIMAL(3, 2), Default 5.00
- `is_premium`: BOOLEAN, Default False
- `monthly_gmv_allowance`: DECIMAL(12, 2), Default 0.00
- `used_gmv`: DECIMAL(12, 2), Default 0.00
- `billing_cycle_end`: TIMESTAMPTZ, Nullable

### `products.Product`
- `id`: UUID (Primary Key)
- `seller`: ForeignKey to `User`
- `title`: VARCHAR(255)
- `category`: VARCHAR(100)
- `condition`: VARCHAR(50) (Used, Refurbished, Like New)
- `description`: TEXT
- `image`: ImageField / URL
- `ai_metadata`: JSONB
- `created_at`: TIMESTAMPTZ

### `auctions.Auction`
- `id`: UUID (Primary Key)
- `product`: 1-to-1 ForeignKey to `Product`
- `starting_bid`: DECIMAL(12, 2)
- `current_bid`: DECIMAL(12, 2)
- `bid_increment`: DECIMAL(12, 2)
- `reserve_price`: DECIMAL(12, 2), Nullable
- `start_time`: TIMESTAMPTZ
- `end_time`: TIMESTAMPTZ
- `status`: ENUM ('DRAFT', 'SCHEDULED', 'LIVE', 'ENDED', 'WINNER_VALIDATION', 'READY_TO_SHIP', 'SETTLEMENT', 'COMPLETED', 'CANCELLED', 'NO_WINNER')
- `winner`: ForeignKey to `User`, Nullable
- `created_at`: TIMESTAMPTZ

### `auctions.Bid`
- `id`: UUID (Primary Key)
- `auction`: ForeignKey to `Auction`
- `bidder`: ForeignKey to `User`
- `amount`: DECIMAL(12, 2)
- `ip_address`: INET
- `user_agent`: TEXT
- `created_at`: TIMESTAMPTZ

### `billing.Transaction`
- `id`: UUID (Primary Key)
- `auction`: ForeignKey to `Auction`
- `buyer`: ForeignKey to `User`
- `seller`: ForeignKey to `User`
- `final_amount`: DECIMAL(12, 2)
- `platform_fee`: DECIMAL(12, 2)
- `covered_by_subscription`: BOOLEAN
- `is_unlocked`: BOOLEAN, Default False
- `payment_status`: VARCHAR(50)
- `created_at`: TIMESTAMPTZ

---

## 4. Key Workflows & State Transitions

### 4.1 Auction State Machine


[ DRAFT ] ──────────► [ SCHEDULED ] ──────────► [ LIVE ] │ │ ▼ ▼ [ CANCELLED ] [ ENDED ] │ ▼ [ WINNER_VALIDATION ] │ ┌────────────────┴────────────────┐ ▼ ▼ [ READY_TO_SHIP ] [ NO_WINNER ] │ ▼ [ SETTLEMENT ] │ ▼ [ COMPLETED ]
### 4.2 Live Bidding Concurrency Safeguards
1. Bid arrives via WebSocket at `/ws/auctions/<id>/`.
2. Backend opens an atomic transaction with `select_for_update()` on the `Auction` record.
3. Validates that the auction is `LIVE`, bidder is not the seller, and `amount >= current_bid + bid_increment`.
4. Saves new `Bid`, updates `Auction.current_bid` and `Auction.winner`.
5. Dynamic Anti-Sniping: If remaining time < 30 seconds, dynamically add 60 seconds to `end_time`.
6. Redis pub/sub broadcasts `NEW_HIGHEST_BID` to the auction room group and fires a targeted `OUTBID` alert to the previous highest bidder's private channel.

### 4.3 Multimodal AI Listing Pipeline
1. Seller uploads product image and enters a title[cite: 1].
2. Frontend dispatches request to `/api/products/generate-description/`.
3. Celery worker receives task, initializes `google-generativeai` (`gemini-1.5-flash`), reads image bytes, and prompts the multimodal model[cite: 1].
4. Worker returns structured description (Overview, Condition, Key Specs)[cite: 1].
5. Seller inspects and edits the text in a `<textarea>` prior to scheduling the auction[cite: 1].

### 4.4 Monetization & Contact Protection
- When an auction hits `READY_TO_SHIP`, buyer shipping address and phone remain hidden[cite: 1].
- Seller clicks "Unlock Contact Details"[cite: 1]:
  - **Premium Seller:** Deducts final amount from `monthly_gmv_allowance`[cite: 1]. Platform fee is ৳0[cite: 1].
  - **Standard Seller:** Deducts 5% platform fee from seller balance[cite: 1].
- Transaction transitions to `is_unlocked = True`, revealing full buyer fulfillment data[cite: 1].

---

## 5. Master Implementation Roadmap

### Phase 1: Foundations, Containerization & Models
- Multi-container setup with `docker-compose.yml` (Daphne/Django, Postgres, Redis, Celery Worker, Celery Beat).
- Implementation of models: `User`, `SellerProfile`, `Product`, `Auction`, `Bid`, `Transaction`.
- JWT/Session authentication endpoints and custom Django Admin views.

### Phase 2: AI Listing Assistant & Catalog
- Asynchronous Celery task for multimodal Gemini description generation[cite: 1].
- Product CRUD endpoints with image upload pipelines.
- Polling mechanism for frontend auto-filling description box.

### Phase 3: Real-Time Bidding Engine
- Channels consumer (`AuctionBidConsumer`) with Redis channel layers[cite: 1].
- Atomic row-locking bid validation and dynamic anti-sniping timer extensions.
- Celery Beat periodic scheduler to cycle auction states (`SCHEDULED` -> `LIVE` -> `ENDED`).
- Live bidding frontend room with live synchronized clock and bid history.

### Phase 4: Post-Auction Monetization & Dashboards
- Seller buyer-contact unlock controller (GMV allowance vs. 5% platform fee)[cite: 1].
- Seller Dashboard (sales analytics, active listings, GMV quota progress bar)[cite: 1].
- Buyer Dashboard (active bids, won items, delivery address submission)[cite: 1].

### Phase 5: Governance, Site Chatbot & Anti-Fraud
- Anti-shill bidding heuristic monitor (IP/device pattern matching)[cite: 1].
- Embedded 24/7 AI Site Assistant using Gemini grounded in platform rules[cite: 1].
- Admin Command Center for emergency auction suspensions and dispute handling[cite: 1].



