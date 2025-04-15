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
                
                # Query GATT services and the target characteristic.
                services = await client.get_services()
                char = services.get_characteristic(self.rx_uuid)
                if char:
                    logging.debug(f"Characteristic Properties: {char.properties}")
                else:
                    logging.warning(f"Characteristic {self.rx_uuid} not found!")

                # Define the callback for received BLE notifications.
                def callback(sender, data):
                    try:
                        # Try UTF-8 first.
                        try:
                            decoded_message = data.decode('utf-8')
                        except UnicodeDecodeError:
                            logging.info("UTF-8 decoding failed. Trying Latin-1.")
                            try:
                                decoded_message = data.decode('latin-1')
                            except UnicodeDecodeError:
                                logging.info("Latin-1 decoding failed. Trying ASCII.")
                                try:
                                    decoded_message = data.decode('ascii')
                                except UnicodeDecodeError:
                                    logging.info("ASCII decoding failed. Using hex representation.")
                                    decoded_message = data.hex()

                        # Optionally, print or log the decoded message.
                        logging.debug(f"Notification received from {sender}: {decoded_message}")

                        # Append decoded text to the running data buffer.
                        self.received_data += decoded_message
                        self.process_received_data()
                    except Exception as e:
                        logging.error(f"Error in BLE callback: {e}")

                # Start notifications on the selected GATT characteristic.
                await client.start_notify(self.rx_uuid, callback)

                # Continue processing notifications until a stop event is set.
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
        """
        Use regex to extract complete JSON arrays from the accumulated data.
        Each JSON array should appear within square brackets (e.g. [ ... ]).
        After processing, the extracted data is removed from the buffer.
        """
        json_pattern = r'\[.*?\]'
        json_objects = re.findall(json_pattern, self.received_data)
        if json_objects:
            # Remove the processed portion from the beginning of the received_data.
            processed_length = sum(len(obj) for obj in json_objects)
            self.received_data = self.received_data[processed_length:]
        for json_str in json_objects:
            try:
                # Remove the square brackets and parse the JSON.
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
