# StyleHub Backend (FastAPI)

## 1. Setup
```bash
cd stylehub-backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
```
Edit `.env`: set `SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
and your Stripe **test** keys (`sk_test_...`, `pk_test_...`).

## 2. Seed products & run
```bash
python -m app.seed
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs - interactive API docs. Call `POST /auth/login` with your email and password, copy the `access_token`,
click **Authorize**, paste the token, and click Authorize.

## 3. Stripe webhook (local)
Install the Stripe CLI, then:
```bash
stripe login
stripe listen --forward-to localhost:8000/orders/webhook
```
Copy the printed `whsec_...` into `STRIPE_WEBHOOK_SECRET` in `.env` and restart the server.
Test card: `4242 4242 4242 4242`, any future expiry, any CVC. Declined card: `4000 0000 0000 0002`.

## 4. Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | /auth/register | no | JSON: full_name, email, password |
| POST | /auth/login | no | JSON: email, password -> JWT |
| GET | /auth/me | yes | current user |
| GET | /products | no | list (?category=&search=&skip=&limit=) |
| GET | /products/{id} | no | single product |
| GET | /cart | yes | cart + totals |
| POST | /cart/items | yes | {product_id, quantity} |
| PATCH | /cart/items/{product_id} | yes | {quantity} |
| DELETE | /cart/items/{product_id} | yes | remove one product |
| DELETE | /cart | yes | clear cart |
| POST | /orders/checkout | yes | creates order + Stripe PaymentIntent -> client_secret |
| POST | /orders/{id}/confirm | yes | verify payment with Stripe (webhook fallback) |
| POST | /orders/webhook | Stripe | updates order status |
| GET | /orders, /orders/{id} | yes | order history |

Prices are in **cents** (1999 = $19.99). Send the JWT as `Authorization: Bearer <token>`.
