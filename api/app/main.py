import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from . import agent, webhook
from .db import get_session, init_db
from .models import OutboxMessage, Payment, Trace
from .paylink import PayLinkClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="PayLink webhook demo", lifespan=lifespan)


def get_gateway() -> PayLinkClient:
    return PayLinkClient()


class ChatIn(BaseModel):
    customer: str
    text: str


@app.get("/")
def chat_page():
    return FileResponse(Path(__file__).parent / "static" / "chat.html")


@app.post("/chat")
def chat(body: ChatIn, session: Session = Depends(get_session), gateway=Depends(get_gateway)):
    return agent.handle_turn(session, gateway, body.customer, body.text)


@app.post("/webhooks/paylink")
def paylink_webhook(payload: dict, session: Session = Depends(get_session)):
    return {"result": webhook.handle_callback(session, payload)}


@app.get("/outbox")
def outbox(customer: str, session: Session = Depends(get_session)):
    query = select(OutboxMessage).where(OutboxMessage.customer == customer).order_by(OutboxMessage.id)
    return session.exec(query).all()


@app.get("/payments")
def payments(customer: str, session: Session = Depends(get_session)):
    return session.exec(select(Payment).where(Payment.customer == customer).order_by(Payment.id)).all()


@app.post("/reset")
def reset(session: Session = Depends(get_session)):
    for table in (OutboxMessage, Payment, Trace):
        session.exec(delete(table))
    session.commit()
    return {"ok": True}

