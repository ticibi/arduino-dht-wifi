import asyncio
import serial
import threading
import time
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

# Global serial settings and object.
current_com_port = "COM3"
current_baud_rate = 9600
ser = None
serial_lock = threading.Lock()

# Global variable for the main event loop.
app_loop = None

def init_serial():
    global ser
    with serial_lock:
        if ser is not None:
            try:
                ser.close()
            except Exception as e:
                print("Error closing serial:", e)
        try:
            ser = serial.Serial(current_com_port, current_baud_rate, timeout=1)
            print(f"Serial opened on {current_com_port} at {current_baud_rate}")
        except Exception as e:
            print("Error opening serial:", e)
            ser = None

# Initialize serial connection.
init_serial()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_loop
    app_loop = asyncio.get_running_loop()
    print("Startup: app_loop is set.")
    yield
    print("Shutdown: cleaning up if necessary.")

app = FastAPI(lifespan=lifespan)

# Manager to keep track of connected WebSocket clients.
class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print("WebSocket client connected.")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print("WebSocket client disconnected.")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print("Error sending message:", e)

manager = ConnectionManager()

# Background thread that reads serial data.
def serial_reader():
    global ser, app_loop
    while True:
        with serial_lock:
            if ser and ser.in_waiting:
                try:
                    line = ser.readline().decode("utf-8").strip()
                except Exception as e:
                    print("Error reading serial:", e)
                    line = ""
                if line:
                    if app_loop is not None:
                        try:
                            fut = asyncio.run_coroutine_threadsafe(manager.broadcast(line), app_loop)
                            fut.result(timeout=1)
                        except Exception as e:
                            print("Error broadcasting:", e)
                        print("Broadcasted:", line)
        time.sleep(0.1)

threading.Thread(target=serial_reader, daemon=True).start()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect incoming messages; just keep the connection alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/update_settings")
async def update_settings(request: Request):
    global current_com_port, current_baud_rate
    data = await request.json()
    current_com_port = data.get("com_port", "COM3")
    try:
        current_baud_rate = int(data.get("baud_rate", 9600))
    except ValueError:
        current_baud_rate = 9600
    init_serial()
    return {"status": "ok", "com_port": current_com_port, "baud_rate": current_baud_rate}

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return html_content

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
