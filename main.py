from fastapi import FastAPI, Request
from pydantic import BaseModel
import time
import sqlite3

app = FastAPI()

conn = sqlite3.connect("server.db", check_same_thread=False)
cursor = conn.cursor()

# таблицы (БЕЗ лишних отступов)
cursor.execute(
"""CREATE TABLE IF NOT EXISTS clicks (
click_id TEXT PRIMARY KEY,
user_id INTEGER,
ip TEXT,
created INTEGER,
visited INTEGER DEFAULT 0,
used INTEGER DEFAULT 0
)"""
)

cursor.execute(
"""CREATE TABLE IF NOT EXISTS logs (
ip TEXT,
user_id INTEGER,
time INTEGER
)"""
)

conn.commit()

SECRET = "Ap41daLd"

class Click(BaseModel):
    click_id: str
    user_id: int

# 🔑 создание задания
@app.post("/create_click")
def create_click(data: Click, request: Request):
    ip = request.client.host
    now = int(time.time())

    cursor.execute(
        "INSERT INTO clicks (click_id, user_id, ip, created) VALUES (?, ?, ?, ?)",
        (data.click_id, data.user_id, ip, now)
    )
    conn.commit()

    return {"status": "ok"}

# 🌐 подтверждение посещения сайта
@app.post("/visit")
async def visit(request: Request):
    body = await request.json()

    if body.get("secret") != SECRET:
        return {"status": "forbidden"}

    click_id = body.get("click_id")

    cursor.execute("UPDATE clicks SET visited=1 WHERE click_id=?", (click_id,))
    conn.commit()

    return {"status": "visited"}

# 🔒 лимиты
def check_limits(ip, user_id):
    now = int(time.time())

    cursor.execute(
        "SELECT COUNT(*) FROM logs WHERE ip=? AND time > ?",
        (ip, now - 3600)
    )
    if cursor.fetchone()[0] > 10:
        return False

    cursor.execute(
        "SELECT COUNT(*) FROM logs WHERE user_id=? AND time > ?",
        (user_id, now - 86400)
    )
    if cursor.fetchone()[0] > 30:
        return False

    return True

# 🔍 проверка задания
@app.get("/check/{click_id}")
def check(click_id: str, request: Request):
    ip = request.client.host

    cursor.execute("SELECT * FROM clicks WHERE click_id=?", (click_id,))
    row = cursor.fetchone()

    if not row:
        return {"valid": False}

    _, user_id, saved_ip, created, visited, used = row

    if used or not visited:
        return {"valid": False}

    if time.time() - created < 10:
        return {"valid": False}

    if not check_limits(ip, user_id):
        return {"valid": False}

    return {"valid": True}

# ✅ использование
@app.post("/use/{click_id}")
def use(click_id: str, request: Request):
    ip = request.client.host

    cursor.execute("SELECT user_id FROM clicks WHERE click_id=?", (click_id,))
    row = cursor.fetchone()

    if row:
        user_id = row[0]

        cursor.execute(
            "INSERT INTO logs (ip, user_id, time) VALUES (?, ?, ?)",
            (ip, user_id, int(time.time()))
        )

    cursor.execute("UPDATE clicks SET used=1 WHERE click_id=?", (click_id,))
    conn.commit()

    return {"status": "used"}