import stripe


# ---------- Auth ----------
def test_register_login_me(client):
    r = client.post(
        "/auth/register",
        json={"email": "Jane@Example.com", "full_name": "Jane", "password": "Secret123"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "jane@example.com"
    assert "password" not in r.json() and "hashed_password" not in r.json()

    r = client.post("/auth/login", json={"email": "jane@example.com", "password": "Secret123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Jane"


def test_duplicate_email_rejected(client):
    body = {"email": "a@example.com", "full_name": "A", "password": "Secret123"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert client.post("/auth/register", json=body).status_code == 409


def test_weak_password_rejected(client):
    r = client.post(
        "/auth/register",
        json={"email": "a@example.com", "full_name": "A", "password": "onlyletters"},
    )
    assert r.status_code == 422


def test_wrong_password(client):
    client.post(
        "/auth/register",
        json={"email": "a@example.com", "full_name": "A", "password": "Secret123"},
    )
    r = client.post("/auth/login", json={"email": "a@example.com", "password": "Wrong1234"})
    assert r.status_code == 401


def test_protected_routes_require_token(client):
    assert client.get("/cart").status_code == 401
    assert client.get("/orders").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


# ---------- Products ----------
def test_products(client):
    r = client.get("/products", params={"page_size": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 12 and len(data["items"]) == 5

    pid = data["items"][0]["id"]
    assert client.get(f"/products/{pid}").json()["id"] == pid
    assert client.get("/products/99999").status_code == 404

    r = client.get("/products", params={"category": "Footwear"})
    assert all(p["category"] == "Footwear" for p in r.json()["items"])
    assert "Men" in client.get("/products/categories").json()


# ---------- Cart ----------
def test_cart_flow(client, auth_headers):
    h = auth_headers()
    p = client.get("/products/1").json()

    r = client.post("/cart/items", json={"product_id": 1, "quantity": 2}, headers=h)
    assert r.status_code == 201
    r = client.post("/cart/items", json={"product_id": 1, "quantity": 1}, headers=h)
    assert r.json()["items"][0]["quantity"] == 3
    assert r.json()["total_cents"] == 3 * p["price_cents"]

    r = client.put("/cart/items/1", json={"quantity": 1}, headers=h)
    assert r.json()["total_items"] == 1

    r = client.delete("/cart/items/1", headers=h)
    assert r.json()["items"] == [] and r.json()["total_cents"] == 0
    assert client.delete("/cart/items/1", headers=h).status_code == 404


def test_cart_stock_limit_and_unknown_product(client, auth_headers):
    h = auth_headers()
    r = client.post("/cart/items", json={"product_id": 12, "quantity": 99}, headers=h)
    assert r.status_code == 400
    assert client.post("/cart/items", json={"product_id": 9999}, headers=h).status_code == 404


def test_cart_is_user_specific(client, auth_headers):
    h1, h2 = auth_headers("one@example.com"), auth_headers("two@example.com")
    client.post("/cart/items", json={"product_id": 1}, headers=h1)
    assert client.get("/cart", headers=h1).json()["total_items"] == 1
    assert client.get("/cart", headers=h2).json()["total_items"] == 0


# ---------- Checkout / Stripe ----------
def _mock_stripe(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return {
            "id": "pi_test_1",
            "client_secret": "pi_test_1_secret_abc",
            "status": "requires_payment_method",
            "amount": kwargs["amount"],
        }

    def fake_retrieve(pid, **kwargs):
        return {"id": pid, "status": "succeeded", "amount": captured["amount"]}

    monkeypatch.setattr(stripe.PaymentIntent, "create", staticmethod(fake_create))
    monkeypatch.setattr(stripe.PaymentIntent, "retrieve", staticmethod(fake_retrieve))
    return captured


def test_checkout_and_confirm(client, auth_headers, monkeypatch):
    captured = _mock_stripe(monkeypatch)
    h = auth_headers()

    assert client.post("/orders/checkout", headers=h).status_code == 400  # empty cart

    client.post("/cart/items", json={"product_id": 1, "quantity": 2}, headers=h)
    stock_before = client.get("/products/1").json()["stock"]

    r = client.post("/orders/checkout", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["client_secret"] == "pi_test_1_secret_abc"
    assert body["order"]["status"] == "pending"
    assert captured["amount"] == body["order"]["total_cents"]
    order_id = body["order"]["id"]

    r = client.post(f"/orders/{order_id}/confirm", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "paid"

    assert client.get("/cart", headers=h).json()["items"] == []  # cart emptied
    assert client.get("/products/1").json()["stock"] == stock_before - 2
    assert [o["id"] for o in client.get("/orders", headers=h).json()] == [order_id]

    # idempotent
    assert client.post(f"/orders/{order_id}/confirm", headers=h).json()["status"] == "paid"
    assert client.get("/products/1").json()["stock"] == stock_before - 2


def test_cannot_read_other_users_order(client, auth_headers, monkeypatch):
    _mock_stripe(monkeypatch)
    h1, h2 = auth_headers("one@example.com"), auth_headers("two@example.com")
    client.post("/cart/items", json={"product_id": 1}, headers=h1)
    order_id = client.post("/orders/checkout", headers=h1).json()["order"]["id"]
    assert client.get(f"/orders/{order_id}", headers=h2).status_code == 404
    assert client.post(f"/orders/{order_id}/confirm", headers=h2).status_code == 404


def test_webhook_rejects_bad_signature(client):
    r = client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=bad"},
    )
    assert r.status_code == 400
