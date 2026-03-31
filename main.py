from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import aiosqlite, asyncio
from datetime import datetime
import os, json

app = FastAPI()
DB = "/home/ubuntu/projects/jarvis-dashboard/tasks.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium',
            category TEXT DEFAULT 'General',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            due_date TEXT DEFAULT ''
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            sender TEXT DEFAULT 'shrey',
            created_at TEXT DEFAULT (datetime('now')),
            read INTEGER DEFAULT 0
        )""")
        await db.commit()

@app.on_event("startup")
async def startup():
    await init_db()

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ''
    status: Optional[str] = 'todo'
    priority: Optional[str] = 'medium'
    category: Optional[str] = 'General'
    due_date: Optional[str] = ''

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[str] = None

class MessageCreate(BaseModel):
    text: str
    sender: Optional[str] = 'shrey'

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("/home/ubuntu/projects/jarvis-dashboard/index.html") as f:
        return f.read()

@app.get("/api/tasks")
async def get_tasks(status: Optional[str] = None, priority: Optional[str] = None):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM tasks"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, created_at DESC"
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "INSERT INTO tasks (title, description, status, priority, category, due_date) VALUES (?,?,?,?,?,?)",
            (task.title, task.description, task.status, task.priority, task.category, task.due_date)
        )
        await db.commit()
        task_id = cursor.lastrowid
    async with aiosqlite.connect(DB) as db2:
        db2.row_factory = aiosqlite.Row
        async with db2.execute("SELECT * FROM tasks WHERE id=?", (task_id,)) as c2:
            row = await c2.fetchone()
            return dict(row)

@app.put("/api/tasks/{task_id}")
async def update_task(task_id: int, task: TaskUpdate):
    updates = {k: v for k, v in task.dict().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No updates provided")
    updates['updated_at'] = datetime.now().isoformat()
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [task_id]
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE tasks SET {sets} WHERE id=?", vals)
        await db.commit()
    return {"ok": True}

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        await db.commit()
    return {"ok": True}

@app.get("/api/messages")
async def get_messages():
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM messages ORDER BY created_at ASC LIMIT 50") as c:
            rows = await c.fetchall()
            return [dict(r) for r in rows]

@app.post("/api/messages")
async def send_message(msg: MessageCreate):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("INSERT INTO messages (text, sender) VALUES (?,?)", (msg.text, msg.sender))
        await db.commit()
        msg_id = cursor.lastrowid
    return {"ok": True, "id": msg_id}

@app.put("/api/messages/{msg_id}/read")
async def mark_read(msg_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE messages SET read=1 WHERE id=?", (msg_id,))
        await db.commit()
    return {"ok": True}

@app.get("/api/stats")
async def get_stats():
    async with aiosqlite.connect(DB) as db:
        stats = {}
        for status in ['todo', 'in_progress', 'done', 'blocked']:
            async with db.execute("SELECT COUNT(*) FROM tasks WHERE status=?", (status,)) as c:
                stats[status] = (await c.fetchone())[0]
        for priority in ['urgent', 'high', 'medium', 'low']:
            async with db.execute("SELECT COUNT(*) FROM tasks WHERE priority=?", (priority,)) as c:
                stats[f'priority_{priority}'] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM messages WHERE read=0 AND sender='shrey'") as c:
            stats['unread_messages'] = (await c.fetchone())[0]
        return stats
