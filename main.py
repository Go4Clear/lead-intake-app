import os
from datetime import datetime

import stripe
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse,
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker


# --------------------
# Config (ENV VARS)
# --------------------
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# Price (change whenever you want)
PRICE_CENTS = int(os.getenv("PRICE_CENTS", "2500"))  

if not STRIPE_SECRET_KEY:
    # Local dev is fine, but you MUST set this for Stripe to work
    print("WARNING: STRIPE_SECRET_KEY is not set")

stripe.api_key = STRIPE_SECRET_KEY


# --------------------
# App
# --------------------
app = FastAPI()


# --------------------
# Database setup
# --------------------
engine = create_engine(
    "sqlite:///./leads.db",
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    message = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String, nullable=False, default="web")

    paid = Column(Boolean, nullable=False, default=False)
    stripe_session_id = Column(String, nullable=True, unique=True)
    paid_at = Column(DateTime, nullable=True)


Base.metadata.create_all(bind=engine)


# --------------------
# Helpers
# --------------------
def require_paid_session(session_id: str) -> stripe.checkout.Session:
    """
    Verifies this Stripe Checkout session is PAID.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured (missing STRIPE_SECRET_KEY)")
    if not session_id or len(session_id.strip()) < 10:
        raise HTTPException(status_code=400, detail="Missing or invalid session_id")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Stripe session")

    if session.payment_status != "paid":
        raise HTTPException(status_code=402, detail="Payment not completed")

    return session


# --------------------
# Routes
# --------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/debug/base-url")
def debug_base_url(key: str):
    if key != os.getenv("ADMIN_KEY"):
        raise HTTPException(status_code=401, detail="nope")
  
    return {
        "APP_BASE_URL_env": os.getenv("APP_BASE_URL"),
        "BASE_URL_VAR_USED": BASE_URL
    }

@app.get("/stripe-test")
def stripe_test():
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Missing STRIPE_SECRET_KEY env var")

    try:
        bal = stripe.Balance.retrieve()
        return {
            "ok": True,
            "livemode": bal.get("livemode"),
            "available": bal.get("available", []),
            "pending": bal.get("pending", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
def home():
    dollars = PRICE_CENTS / 100
    return f"""
    <html>
      <head>
        <title>Lead Intake (Paid)</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          body {{ font-family: Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }}
          .box {{ border: 1px solid #ddd; padding: 18px; border-radius: 10px; }}
          button {{ padding: 12px 16px; font-size: 16px; cursor: pointer; }}
          .small {{ color:#666; font-size: 14px; }}
        </style>
      </head>
      <body>
        <h1>✅ Paid Lead Intake</h1>
        <div class="box">
          <p><b>Pay ${dollars:.2f}</b> to submit a serious request.</p>
          <form action="/create-checkout-session" method="post">
            <button type="submit">Pay & Continue</button>
          </form>
          <p class="small">After payment, you’ll be redirected to the intake form.</p>
        </div>
        <hr/>
        <p class="small">
          Built with FastAPI + Stripe Checkout.
        </p>
      </body>
    </html>
    """


@app.post("/create-checkout-session")
def create_checkout_session():
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured (missing STRIPE_SECRET_KEY)")

    success_url = f"{BASE_URL}/intake?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{BASE_URL}/"

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Lead Intake Submission"},
                "unit_amount": PRICE_CENTS
            },
            "quantity": 1
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"product": "paid_lead_intake"}
    )

    return RedirectResponse(url=session.url, status_code=303)


@app.get("/intake", response_class=HTMLResponse)
def intake(session_id: str):
    # Must be paid to view form
    require_paid_session(session_id)

    return f"""
    <html>
      <head>
        <title>Paid Intake Form</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          body {{ font-family: Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }}
          input, textarea {{ width: 100%; padding: 10px; margin: 8px 0; }}
          button {{ padding: 12px 16px; font-size: 16px; cursor: pointer; }}
          .small {{ color:#666; font-size: 14px; }}
        </style>
      </head>
      <body>
        <h1>Paid Intake Form</h1>
        <p class="small">Payment verified ✅</p>

        <form action="/submit_paid" method="post">
          <input type="hidden" name="session_id" value="{session_id}" />

          <label>Name</label>
          <input name="name" required minlength="2" />

          <label>Email</label>
          <input name="email" type="email" required />

          <label>Message</label>
          <textarea name="message" required minlength="10" rows="6"></textarea>

          <button type="submit">Submit Request</button>
        </form>

        <p class="small">If you refresh this page later, it will still work as long as the session is paid and unused.</p>
      </body>
    </html>
    """


@app.post("/submit_paid", response_class=HTMLResponse)
def submit_paid(
    session_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
):
    # Confirm payment
    require_paid_session(session_id)

    # Cheap validation
    if len(name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name too short")
    if len(message.strip()) < 10:
        raise HTTPException(status_code=400, detail="Message too short")

    db = SessionLocal()
    try:
        # Prevent re-using same paid session_id multiple times
        exists = db.query(Lead).filter(Lead.stripe_session_id == session_id).first()
        if exists:
            raise HTTPException(status_code=409, detail="This payment session was already used.")

        row = Lead(
            name=name.strip(),
            email=email.strip(),
            message=message.strip(),
            source="web_paid",
            paid=True,
            stripe_session_id=session_id,
            paid_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        return f"""
        <html>
          <head><meta name="viewport" content="width=device-width, initial-scale=1" /></head>
          <body style="font-family: Arial; max-width:720px; margin:40px auto; padding:0 16px;">
            <h1>✅ Submitted</h1>
            <p>Your request is in. Lead ID: <b>{row.id}</b></p>
            <p><a href="/">Back to home</a></p>
          </body>
        </html>
        """
    finally:
        db.close()
