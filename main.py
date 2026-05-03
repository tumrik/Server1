from fastapi import FastAPI, Request
from pydantic import BaseModel
import time
import sqlite3

app = FastAPI()

def get_db():
    conn = sqlite3.connect("server.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clicks (
        click_id TEXT PRIMARY KEY,
        user_id INTEGER,
        ip TEXT,
        created INTEGER,
        visited INTEGER DEFAULT 0,
        used INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        ip TEXT,
        user_id INTEGER,
        time INTEGER
    )
    """)

    conn.commit()
    conn.close()


SECRET = "Ap41daLd"

class Click(BaseModel):
    click_id: str
    user_id: int


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/create_click")
def create_click(data: Click, request: Request):
    conn = get_db()
    cursor = conn.cursor()

    ip = request.client.host
    now = int(time.time())

    cursor.execute(
        "INSERT INTO clicks (click_id, user_id, ip, created) VALUES (?, ?, ?, ?)",
        (data.click_id, data.user_id, ip, now)
    )

    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/visit")
async def visit(request: Request):
    body = await request.json()

    if body.get("secret") != SECRET:
        return {"status": "forbidden"}

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE clicks SET visited=1 WHERE click_id=?",
        (body.get("click_id"),)
    )

    conn.commit()
    conn.close()

    return {"status": "visited"}


def check_limits(ip, user_id):
    conn = get_db()
    cursor = conn.cursor()
    now = int(time.time())

    cursor.execute(
        "SELECT COUNT(*) FROM logs WHERE ip=? AND time > ?",
        (ip, now - 3600)
    )
    if cursor.fetchone()[0] > 10:
        conn.close()
        return False

    cursor.execute(
        "SELECT COUNT(*) FROM logs WHERE user_id=? AND time > ?",
        (user_id, now - 86400)
    )
    if cursor.fetchone()[0] > 30:
        conn.close()
        return False

    conn.close()
    return True


@app.get("/check/{click_id}")
def check(click_id: str, request: Request):
    conn = get_db()
    cursor = conn.cursor()

    ip = request.client.host

    cursor.execute("SELECT * FROM clicks WHERE click_id=?", (click_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"valid": False}

    user_id = row["user_id"]
    created = row["created"]
    visited = row["visited"]
    used = row["used"]

    if used or not visited:
        conn.close()
        return {"valid": False}

    if time.time() - created < 10:
        conn.close()
        return {"valid": False}

    if not check_limits(ip, user_id):
        conn.close()
        return {"valid": False}

    conn.close()
    return {"valid": True}


@app.post("/use/{click_id}")
def use(click_id: str, request: Request):
    conn = get_db()
    cursor = conn.cursor()

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
    conn.close()

    return {"status": "used"}