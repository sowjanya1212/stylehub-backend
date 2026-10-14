# StyleHub – Fashion Mini Store · Backend

FastAPI + SQLAlchemy 2 (ORM only) + SQLite + JWT + bcrypt + Stripe (test mode).

## Project layout

```
app/
  main.py            # app factory, CORS, router wiring, Stripe error handler
  config.py          # env-based settings (pydantic-settings)
  database.py        # engine, session, Base
  models.py          # User, Product, CartItem, Order, OrderItem
  schemas.py         # request/response validation (Pydantic v2)
  security.py        # bcrypt hashing + JWT create/decode
  deps.py            # get_current_user (protected routes)
  seed.py            # demo products
  routers/           # auth, products, cart, orders, webhooks
  services/payments.py   # Stripe + order status transitions
tests/               # pytest suite (Stripe is mocked)
```

## 1. Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # Windows: copy .env.example .env
```

Edit `.env`:

* `SECRET_KEY` – generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`
* `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` – from Stripe Dashboard → Developers → API keys (**test mode**)
* `STRIPE_WEBHOOK_SECRET` – see step 3

## 2. Run

```bash
uvicorn app.main:app --reload
```

* Swagger UI: http://localhost:8000/docs  (call `/auth/login` with email + password, then click **Authorize** and paste the `access_token`)
* Tables are created and 12 demo products are seeded automatically on first start.

## 3. Stripe webhook (local)

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

Copy the printed `whsec_...` into `STRIPE_WEBHOOK_SECRET` and restart the server.
Test card: `4242 4242 4242 4242`, any future expiry, any CVC.
Declined card: `4000 0000 0000 9995`.

## 4. Tests

```bash
pytest -q
```

## API summary

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | – | Create account (email, full_name, password) |
| POST | `/auth/login` | – | Login with only `email` + `password` → `{access_token, token_type, expires_in}` |
| GET | `/auth/me` | ✔ | Current user |
| GET | `/products` | – | List; `q`, `category`, `sort`, `page`, `page_size` |
| GET | `/products/categories` | – | Category names |
| GET | `/products/{id}` | – | Single product |
| GET | `/cart` | ✔ | Cart with line totals and total |
| POST | `/cart/items` | ✔ | `{product_id, quantity}` – add (merges quantity) |
| PUT | `/cart/items/{product_id}` | ✔ | `{quantity}` – set quantity |
| DELETE | `/cart/items/{product_id}` | ✔ | Remove item |
| DELETE | `/cart` | ✔ | Clear cart |
| POST | `/orders/checkout` | ✔ | Cart → pending order + PaymentIntent → `client_secret` |
| POST | `/orders/{id}/confirm` | ✔ | Verify payment with Stripe, update status |
| GET | `/orders` | ✔ | Order history |
| GET | `/orders/{id}` | ✔ | Single order |
| POST | `/webhooks/stripe` | Stripe signature | `payment_intent.succeeded / payment_failed / canceled` |

Send the token as `Authorization: Bearer <access_token>`.

## Checkout flow (for the frontend, Day 6–7)

1. `POST /orders/checkout` → get `client_secret`, `publishable_key`, `order.id`.
2. `loadStripe(publishable_key)` → `<Elements options={{clientSecret}}>` → `<PaymentElement/>`.
3. `stripe.confirmPayment({ elements, redirect: "if_required" })`.
4. On success call `POST /orders/{id}/confirm` and show the result (the webhook also updates the order).

Order statuses: `pending → paid | failed | cancelled`.
On `paid`: stock is decremented and the user's cart is cleared.

## Security notes

* Passwords hashed with bcrypt (12 rounds); never returned by the API.
* JWT (HS256) with `exp`/`sub` required; secrets only from environment variables.
* All DB access via SQLAlchemy ORM (no raw SQL); inputs validated by Pydantic.
* Prices come from the DB, never from the client; Stripe amount is checked against the order total before marking it paid.
* Webhook signatures are verified; payment state is read from Stripe, not trusted from the browser.
* Money stored as integer cents.

## Production hardening (next steps)

Alembic migrations instead of `create_all`, PostgreSQL instead of SQLite, rate limiting on `/auth/*`, HTTPS-only CORS origins, a job to expire stale `pending` orders.
