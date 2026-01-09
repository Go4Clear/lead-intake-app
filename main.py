from fastapi import FastAPI, Header, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import EmailStr
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import io
import csv
import os

app = FastAPI()

# --------------------
# Config
# --------------------
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

# --------------------
# Database
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String, nullable=False, default="web")

    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    message = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)

# --------------------
# UI (Demo Website)
# --------------------
PAGE_STYLE = """
<style>
  body { font-family: Arial, sans-serif; background: #0b1220; color: #e8eefc; }
  .wrap { max-width: 720px; margin: 48px auto; padding: 0 18px; }
  .card { background: #121a2b; border: 1px solid #24304a; border-radius: 14px; padding: 18px; }
  h1,h2 { margin: 0 0 10px 0; }
  p { color: #b7c4e6; line-height: 1.5; }
  label { display:block; margin: 12px 0 6px; color: #cdd8f5; }
  input, textarea { width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #2a3754; background: #0e1627; color: #e8eefc; }
  button { margin-top: 14px; padding: 10px 14px; border: 0; border-radius: 12px; background: #3b82f6; color: white; cursor: pointer; font-weight: 700; }
  button:hover { opacity: 0.92; }
  .row { display:flex; gap: 10px; flex-wrap: wrap; }
  .pill { display:inline-block; padding: 4px 10px; border-radius: 999px; background: #0e1627; border: 1px solid #2a3754; color:#b7c4e6; font-size: 12px; }
  table { width:100%; border-collapse: collapse; margin-top: 12px; }
  th, td { padding: 10px; border-bottom: 1px solid #24304a; vertical-align: top; }
  th { text-align:left; color:#cdd8f5; }
  a { color: #93c5fd; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .muted { color:#8fa2cc; font-size: 12px; }
  .danger { color:#fca5a5; }
</style>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    # A simple demo landing/contact page
    return f"""
    <html>
      <head>
        <title>Lead Intake Demo</title>
        <p style="margin-top:10px;">
  <strong>What this system does:</strong>
</p>
<ul>
  <li>Captures website leads securely</li>
  <li>Blocks spam automatically</li>
  <li>Stores submissions in a private dashboard</li>
  <li>Prevents missed inquiries and lost revenue</li>
</ul>

        {PAGE_STYLE}
      </head>
      <body>
      <div style="
        background:#f59e0b;
        color:#111827;
        padding:10px 14px;
        font-weight:700;
        text-align:center;
">
  DEMO MODE — Lead Intake System (FastAPI + Database + Spam Protection)
</div>

 <div class="wrap">
          <div class="card">
            <div class="row" style="justify-content: space-between; align-items:center;">
              <h1 style="margin:0;">Lead Intake Demo</h1>
              <span class="pill">FastAPI + DB + Spam Filter</span>
            </div>
            <p style="margin-top:10px;">
              This is a simple website demo. Submitting this form creates a lead in the database.
              Admins can view leads at <code>/admin</code>.
            </p>

            <h2 style="margin-top:18px;">Contact Us</h2>
            <form method="post" action="/submit-form">
              <label>Name</label>
              <input name="name" placeholder="Jane Doe" required />

              <label>Email</label>
              <input name="email" type="email" placeholder="jane@example.com" required />

              <label>Message</label>
              <textarea name="message" rows="5" placeholder="How can we help?" required></textarea>

              <!-- Honeypot: bots fill this, humans won't see it -->
              <input name="website" style="display:none" />

              <button type="submit">Send</button>
            </form>
            
            <p class="muted" style="margin-top:16px;">
              This is a demo. In production, this system can be customized, branded,
  and connected to email, CRM, or automation tools.
</p>

<p class="muted" style="margin-top:14px;">
              Tip: View API docs at <a href="/docs">/docs</a> • Health check at <a href="/health">/health</a>
            </p>
          </div>
        </div>
      </body>
    </html>
    """


@app.get("/thanks", response_class=HTMLResponse)
def thanks():
    return f"""
    <html>
      <head>
        <title>Thanks</title>
        {PAGE_STYLE}
      </head>
      <body>
        <div class="wrap">
          <div class="card">
            <h1>Thanks!</h1>
            <p>Your message was received. We’ll follow up soon.</p>
            <p><a href="/">Back to home</a></p>
          </div>
        </div>
      </body>
    </html>
    """


@app.get("/admin", response_class=HTMLResponse)
def admin_page(key: str = Query(default="")):
    # Simple demo admin page using querystring key, e.g. /admin?key=cuphead
    if key != ADMIN_KEY:
        return HTMLResponse(
            content=f"""
            <html><head><title>Admin</title>{PAGE_STYLE}</head>
            <body><div class="wrap"><div class="card">
              <h1 class="danger">Unauthorized</h1>
              <p>Provide the admin key like: <code>/admin?key=YOUR_KEY</code></p>
            </div></div></body></html>
            """,
            status_code=401
        )

    db = SessionLocal()
    try:
        leads = db.query(Lead).order_by(Lead.id.desc()).limit(50).all()
        rows = "".join(
            f"<tr><td>{l.id}</td><td>{l.name}<br><span class='muted'>{l.email}</span></td><td>{l.message}</td></tr>"
            for l in leads
        ) or "<tr><td colspan='3' class='muted'>No leads yet.</td></tr>"

        return f"""
        <html>
          <head>
            <title>Admin - Leads</title>
            {PAGE_STYLE}
          </head>
          <body>
            <div class="wrap">
              <div class="card">
                <div class="row" style="justify-content: space-between; align-items:center;">
                  <h1 style="margin:0;">Admin: Latest Leads</h1>
                  <span class="pill">Top 50</span>
                </div>

                <p class="muted">This is a demo admin view. For production, use real auth.</p>

                <table>
                  <thead>
                    <tr><th>ID</th><th>Name / Email</th><th>Message</th></tr>
                  </thead>
                  <tbody>
                    {rows}
                  </tbody>
                </table>

                <p class="muted" style="margin-top:14px;">
                  API endpoint: <code>/leads</code> (requires header <code>x-admin-key</code>)
                </p>
              </div>
            </div>
          </body>
        </html>
        """
    finally:
        db.close()

# --------------------
# API
# --------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/submit")
def submit_lead_api(
    name: str,
    email: EmailStr,
    message: str,
    website: str | None = None
):
    # Honeypot
    if website:
        raise HTTPException(status_code=400, detail="Invalid submission")

    # Validation
    if len(name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name too short")
    if len(message.strip()) < 10:
        raise HTTPException(status_code=400, detail="Message too short")

    db = SessionLocal()
    try:
        row = Lead(name=name.strip(), email=str(email).strip(), message=message.strip(), source="web")
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"saved": True, "id": row.id}
    finally:
        db.close()


@app.post("/submit-form")
def submit_lead_form(
    name: str = Form(...),
    email: EmailStr = Form(...),
    message: str = Form(...),
    website: str = Form("")
):
    # Reuse same logic
    submit_lead_api(name=name, email=email, message=message, website=website)
    return RedirectResponse(url="/thanks", status_code=303)


@app.get("/export.csv")
def export_csv(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db = SessionLocal()
    try:
        leads = db.query(Lead).order_by(Lead.id.desc()).all()

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "created_at", "source", "name", "email", "message"])
        for l in leads:
            writer.writerow([l.id, l.created_at, l.source, l.name, l.email, l.message])

        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads.csv"},
        )
    finally:
        db.close()
