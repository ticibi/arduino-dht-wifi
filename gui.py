import asyncio
import threading
import queue
import re
import flet as ft
from flet import Dropdown, Row, Text, Column, ElevatedButton
import serial_asyncio

# Global variables for serial connection and update queue.
serial_transport = None
serial_protocol = None
update_queue = queue.Queue()

# Create a dedicated asyncio event loop for serial tasks.
serial_loop = asyncio.new_event_loop()

def start_serial_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Start the serial event loop in a daemon thread.
threading.Thread(target=start_serial_loop, args=(serial_loop,), daemon=True).start()

# This protocol handles asynchronous serial reading.
class SerialReader(asyncio.Protocol):
    def __init__(self, on_data_callback):
        self.on_data_callback = on_data_callback
        self.buffer = b""

    def connection_made(self, transport):
        self.transport = transport
        print("Serial connection opened.")

    def data_received(self, data):
        self.buffer += data
        # Process complete lines terminated by newline.
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                text = line.decode().strip()
            except UnicodeDecodeError:
                text = "<decode error>"
            self.on_data_callback(text)

    def connection_lost(self, exc):
        print("Serial connection lost.")
        if exc:
            print("Exception:", exc)

# Instead of directly updating the UI from the serial thread,
# we simply put each new line in a thread-safe queue.
def update_display(new_line: str):
    update_queue.put(new_line)

# The main Flet app.
async def main(page: ft.Page):
    page.title = "Serial Data Viewer"
    page.vertical_alignment = "start"
    page.padding = 20

    # Set the window size: 500 pixels wide and 250 pixels high.
    page.window_width = 800
    page.window_height = 350

    # --- Connection controls ---
    com_ports = [
        ft.dropdown.Option("COM1"),
        ft.dropdown.Option("COM2"),
        ft.dropdown.Option("COM3"),
        ft.dropdown.Option("COM4"),
        ft.dropdown.Option("COM5")
    ]
    com_dropdown = Dropdown(label="COM Port", options=com_ports, value="COM3")
    
    baud_options = [
        ft.dropdown.Option("9600"),
        ft.dropdown.Option("19200"),
        ft.dropdown.Option("38400"),
        ft.dropdown.Option("57600"),
        ft.dropdown.Option("115200"),
    ]
    baud_dropdown = Dropdown(label="Baud Rate", options=baud_options, value="9600")
    
    connect_button = ElevatedButton(text="Connect", on_click=lambda e: reconnect_serial())
    status_text = Text(value="Not connected.", size=14)

    connection_controls = Row(
        controls=[com_dropdown, baud_dropdown, connect_button],
        spacing=10
    )
    
    # --- Sensor value displays ---
    humidity_label = Text("Humidity:", size=16)
    humidity_value = Text("N/A", size=16)
    temp_label = Text("Temperature (°C):", size=16)
    temp_value = Text("N/A", size=16)
    humidity_delta_label = Text("Humidity Δ:", size=16)
    humidity_delta_value = Text("N/A", size=16)
    temp_delta_label = Text("Temperature Δ:", size=16)
    temp_delta_value = Text("N/A", size=16)
    
    sensor_values = Column(
        controls=[
            Row(controls=[humidity_label, humidity_value], spacing=10),
            Row(controls=[temp_label, temp_value], spacing=10),
            Row(controls=[humidity_delta_label, humidity_delta_value], spacing=10),
            Row(controls=[temp_delta_label, temp_delta_value], spacing=10)
        ],
        spacing=10
    )
    
    # Add all controls to the page.
    page.add(connection_controls, status_text, sensor_values)
    
    # Variables to store previous values for computing delta.
    last_humidity = None
    last_temp = None

    # Poll the update queue to process new serial data.
    async def poll_queue():
        nonlocal last_humidity, last_temp
        while True:
            try:
                # Get a new line from the queue (non-blocking).
                line = update_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue
            
            # Parse the incoming line.
            # Expected format (from Arduino): 
            # "Humidity: 50 %    Temperature: 24 *C / 75.2 *F"
            match = re.search(r"Humidity:\s*([\d\.]+).*Temperature:\s*([\d\.]+)", line)
            if match:
                try:
                    humidity = float(match.group(1))
                    temp = float(match.group(2))
                except ValueError:
                    continue
                
                # Compute the deltas.
                delta_h = humidity - last_humidity if last_humidity is not None else 0.0
                delta_t = temp - last_temp if last_temp is not None else 0.0
                last_humidity = humidity
                last_temp = temp
                
                # Update the UI values.
                humidity_value.value = f"{humidity:.2f} %"
                temp_value.value = f"{temp:.2f} °C"
                humidity_delta_value.value = f"{delta_h:+.2f} %"
                temp_delta_value.value = f"{delta_t:+.2f} °C"
                page.update()
            else:
                print("Received unrecognized data:", line)
    
    # Asynchronous function to (re)start the serial connection.
    async def start_serial():
        nonlocal status_text
        global serial_transport, serial_protocol

        port = com_dropdown.value
        try:
            baud = int(baud_dropdown.value)
        except ValueError:
            status_text.value = "Invalid baud rate!"
            page.update()
            return
        
        status_text.value = f"Connecting to {port} at {baud} baud..."
        page.update()
        
        # If already connected, close the previous connection.
        if serial_transport is not None:
            serial_transport.close()
        
        def protocol_factory():
            return SerialReader(on_data_callback=update_display)
        
        try:
            transport, protocol = await serial_asyncio.create_serial_connection(
                asyncio.get_running_loop(), protocol_factory, port, baudrate=baud
            )
            serial_transport = transport
            serial_protocol = protocol
            status_text.value = "Connected successfully!"
        except Exception as e:
            status_text.value = f"Error connecting: {e}"
        page.update()
    
    # Helper function to schedule the serial connection coroutine.
    def reconnect_serial():
        asyncio.run_coroutine_threadsafe(start_serial(), serial_loop)
    
    def on_dropdown_change(e):
        reconnect_serial()
    
    com_dropdown.on_change = on_dropdown_change
    baud_dropdown.on_change = on_dropdown_change
    
    # Auto connect on app start.
    reconnect_serial()
    
    # Start polling for serial data.
    asyncio.create_task(poll_queue())

ft.app(target=main)
