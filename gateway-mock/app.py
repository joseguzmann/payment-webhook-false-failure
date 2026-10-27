"""A fake payment gateway that behaves like the real one did in production.

Its "documentation" says a transaction ends as success, failure or pending. In practice it
sends numeric codes, and for some payments it sends two callbacks: "in review" (0/36) while
its anti-fraud check runs, and the approval (1/3) about a minute later.
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8001")
CHAT_URL = os.getenv("CHAT_URL", "http://localhost:8000")
# The real gap was ~49 s. Shorter by default so the demo is quick to watch.
DELAY = float(os.getenv("CALLBACK_DELAY_SECONDS", "5"))

# Each scenario is a list of (seconds to wait, status, status_detail).
SCENARIOS = {
    "in_review_then_approved": [(0, "0", "36"), (DELAY, "1", "3")],
    "approved": [(0, "1", "3")],
    "expired": [(0, "5", "14")],
    "declined": [(0, "failure", "9")],
}
DESCRIPTIONS = {
    "in_review_then_approved": f"Anti-fraud review first (0/36), approval {DELAY:g} s later (1/3). What we saw in production.",
    "approved": "Approved at once (1/3).",
    "expired": "The customer never paid and the link expired (5/14).",
    "declined": "The card was declined (failure).",
}

app = FastAPI(title="PayLink gateway (mock)")
# The demo chat page reads the callback log from another port.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])
links: dict[str, dict] = {}
# Every callback sent, with the webhook's answer, so the demo can show what happened behind the chat.
sent: list[dict] = []


class LinkIn(BaseModel):
    reference: str
    amount_cents: int
    callback_url: str


@app.post("/links")
def create_link(body: LinkIn):
    link_id = uuid.uuid4().hex[:10]
    links[link_id] = body.model_dump()
    return {"id": link_id, "url": f"{PUBLIC_URL}/pay/{link_id}"}


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PayLink checkout</title>
<style>
  body {{ margin: 0; font-family: system-ui, sans-serif; background: #f4f5f7; color: #1d2330; }}
  .card {{ max-width: 420px; margin: 48px auto; background: #fff; border-radius: 12px; padding: 24px;
          box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
  .brand {{ font-weight: 700; color: #4b3df5; }}
  .amount {{ font-size: 32px; font-weight: 700; margin: 8px 0 20px; }}
  .note {{ font-size: 13px; color: #667; margin-bottom: 12px; }}
  label {{ display: block; border: 1px solid #dde; border-radius: 8px; padding: 10px 12px; margin: 8px 0; cursor: pointer; }}
  label:has(input:checked) {{ border-color: #4b3df5; background: #f3f1ff; }}
  label b {{ display: block; }}
  label span {{ font-size: 13px; color: #556; }}
  input {{ float: right; }}
  button {{ width: 100%; margin-top: 12px; padding: 12px; border: 0; border-radius: 8px; background: #4b3df5;
           color: #fff; font-size: 16px; cursor: pointer; }}
</style></head><body><div class="card">{body}</div></body></html>"""


@app.get("/pay/{link_id}", response_class=HTMLResponse)
def pay_page(link_id: str):
    link = links.get(link_id)
    if link is None:
        return HTMLResponse(PAGE.format(body="<p>Unknown link.</p>"), status_code=404)
    options = "".join(
        f'<label><input type="radio" name="scenario" value="{name}"{" checked" if i == 0 else ""}>'
        f'<b>{name.replace("_", " ").capitalize()}</b><span>{DESCRIPTIONS[name]}</span></label>'
        for i, name in enumerate(SCENARIOS)
    )
    return PAGE.format(body=(
        f'<div class="brand">PayLink</div><div class="amount">${link["amount_cents"] / 100:.2f}</div>'
        f'<div class="note">Mock gateway. Choose how it will answer the payment:</div>'
        f'<form method="post" action="/pay/{link_id}">{options}<button>Pay</button></form>'))


@app.post("/pay/{link_id}", response_class=HTMLResponse)
async def pay(link_id: str, request: Request, tasks: BackgroundTasks):
    scenario = (await request.form())["scenario"]
    tasks.add_task(send_callbacks, links[link_id], SCENARIOS[scenario])
    return PAGE.format(body='<div class="brand">PayLink</div><p>Payment submitted.</p>'
                            f'<p><a href="{CHAT_URL}">Back to the chat</a> to see what the customer receives.</p>')


@app.get("/callbacks")
def callbacks():
    return sent


@app.post("/callbacks/reset")
def reset_callbacks():
    sent.clear()
    return {"ok": True}


async def send_callbacks(link: dict, steps: list[tuple[float, str, str]]) -> None:
    # Listed up front with their arrival time, so the demo can show a callback that is still coming.
    start = datetime.now(timezone.utc).timestamp()
    entries, offset = [], 0.0
    for wait, status, detail in steps:
        offset += wait
        entries.append({"due": datetime.fromtimestamp(start + offset, timezone.utc).isoformat(), "at": None,
                        "reference": link["reference"], "status": status, "status_detail": detail,
                        "http": None, "result": None})
    sent.extend(entries)
    async with httpx.AsyncClient(timeout=10) as client:
        for (wait, status, detail), entry in zip(steps, entries):
            await asyncio.sleep(wait)
            payload = {"transaction": {"id": uuid.uuid4().hex[:12], "status": status,
                                       "status_detail": detail, "dev_reference": link["reference"]}}
            response = await client.post(link["callback_url"], json=payload)
            entry.update(at=datetime.now(timezone.utc).isoformat(), http=response.status_code,
                         result=response.json().get("result") if response.content else None)
