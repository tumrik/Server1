import os
import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET = os.getenv("POSTBACK_SECRET", "secret123")

db = None


# ---------- DB ----------
@app.on_event("startup")
async def startup():
    global db
    db = await asyncpg.create_pool(DATABASE_URL)


# ---------- OFFER REDIRECT ----------
@app.get("/offer")
async def offer(subid: int, offer_id: int):
    # 👉 сюда вставишь свою CPA ссылку
    offer_link = f"https://your-cpa-network.com?subid={subid}&offer_id={offer_id}"

    return RedirectResponse(url=offer_link)


# ---------- POSTBACK ----------
@app.get("/postback")
async def postback(request: Request):
    data = dict(request.query_params)

    if data.get("key") != SECRET:
        return {"error": "unauthorized"}

    subid = data.get("subid")
    txid = data.get("txid")
    offer_id = data.get("offer_id")
    status = data.get("status")

    if not subid or not txid or status != "approved":
        return {"status": "ignored"}

    user_id = int(subid)
    offer_id = int(offer_id)

    async with db.acquire() as conn:

        # анти-дубликат
        exists = await conn.fetchrow(
            "SELECT * FROM conversions WHERE txid=$1", txid
        )

        if exists:
            return {"status": "duplicate"}

        offer = await conn.fetchrow(
            "SELECT * FROM offers WHERE id=$1", offer_id
        )

        if not offer:
            return {"error": "offer not found"}

        reward = offer["reward"]

        # записываем конверсию
        await conn.execute("""
            INSERT INTO conversions(user_id, offer_id, txid, reward)
            VALUES($1, $2, $3, $4)
        """, user_id, offer_id, txid, reward)

        # начисляем баллы
        await conn.execute("""
            UPDATE users
            SET points = points + $1,
                clicks = clicks + 1
            WHERE user_id=$2
        """, reward, user_id)

    return {"status": "ok"}
