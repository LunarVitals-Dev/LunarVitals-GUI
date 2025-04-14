import asyncio
import re
import json
import logging
from PySide6.QtCore import QThread, Signal
from bleak import BleakClient

class NordicBLEWorker(QThread):
    data_received = Signal(dict)
     
    def __init__(self, mac_address, rx_uuid):
        super().__init__()
        self.mac_address = mac_address
        self.rx_uuid = rx_uuid
        self.running = True
        self.received_data = ""
        self._client = None
        self._stop_event = asyncio.Event()

    async def connect_and_listen(self):
        try:
            async with BleakClient(self.mac_address) as client:
                self._client = client
                logging.info(f"Connected to Nordic BLE Device: {self.mac_address}")

                # Callback to be called when data is received from the BLE device.
                def callback(sender, data):
                    try:
                        message = data.decode('utf-8')
                        self.received_data += message
                        self.process_received_data()
                    except Exception as e:
                        logging.error(f"Error in BLE callback: {e}")

                await client.start_notify(self.rx_uuid, callback)

                # Listen for data until stopped.
                while self.running:
                    await asyncio.sleep(0.1)
                    if self._stop_event.is_set():
                        break

                await client.stop_notify(self.rx_uuid)
        except Exception as e:
            logging.error(f"BLE connection error: {e}")
        finally:
            self._client = None

    def process_received_data(self):
        # Use regex to extract complete JSON arrays.
        json_pattern = r'\[.*?\]'
        json_objects = re.findall(json_pattern, self.received_data)
        # Remove processed data.
        self.received_data = self.received_data[len("".join(json_objects)):]
        for json_str in json_objects:
            try:
                # Strip the square brackets and parse the JSON.
                data = json.loads(json_str[1:-1])
                self.data_received.emit(data)
            except json.JSONDecodeError as e:
                logging.error(f"JSON Decode Error: {e}. Problematic JSON String: {json_str}")
            except Exception as e:
                logging.error(f"Error processing JSON: {e}")

    def run(self):
        # Run the asyncio event loop in this thread.
        asyncio.run(self.connect_and_listen())

    def stop(self):
        self.running = False
        if self._client:
            self._stop_event.set()
        self.quit()

    def reset_connection(self):
        """Reset the Bluetooth connection."""
        if self._client:
            try:
                asyncio.run(self._client.disconnect())
                logging.info("Disconnected from BLE device.")
            except Exception as e:
                logging.error(f"Error disconnecting from BLE device: {e}")
        self._stop_event.clear()
        asyncio.run(self.connect_and_listen())
