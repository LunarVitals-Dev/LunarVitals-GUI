import asyncio
import re
import json
import logging
from PySide6.QtCore import QThread, Signal
from bleak import BleakClient

class NordicBLEWorker(QThread):
    data_received = Signal(dict)

    def __init__(self, mac_address: str, rx_uuid: str):
        super().__init__()
        self.mac_address = mac_address
        self.rx_uuid = rx_uuid
        self.connected = False  # Track connection status
        self.retry_interval = 0  # Seconds between reconnection attempts

        # buffer for partial text
        self.received_data = ""
        self.client = None
        self.stop_requested = False
        
    async def connect_and_listen(self):
        while not self.stop_requested:
            try:
                async with BleakClient(self.mac_address) as client:
                    self.client = client
                    self.connected = True
                    logging.info(f"Connected to Nordic BLE Device {self.mac_address}")

                    services = await client.get_services()

                    while not self.stop_requested:
                        try:
                            raw = await client.read_gatt_char(self.rx_uuid)
                            logging.debug(f"Raw chunk: {raw!r}")

                            decoded = None
                            for codec in ('utf-8', 'latin-1', 'ascii'):
                                try:
                                    decoded = raw.decode(codec)
                                    break
                                except UnicodeDecodeError:
                                    continue

                            if not decoded:
                                logging.warning("Discarding undecodable BLE chunk")
                                await asyncio.sleep(0.1)
                                continue

                            self.received_data += decoded
                            self.process_received_data()

                        except Exception as e:
                            logging.error(f"Error during read: {e}")
                            break  # Drop to reconnect attempt

                        await asyncio.sleep(0.1)

            except Exception as e:
                logging.error(f"BLE connection error: {e}")

            finally:
                self.client = None
                self.connected = False
                logging.info("Disconnected BLE client")

            if not self.stop_requested:
                logging.info(f"Retrying connection in {self.retry_interval} seconds...")
                await asyncio.sleep(self.retry_interval)
 
    def process_received_data(self):
        """
        Extract complete JSON arrays (wrapped in square brackets)
        from the buffer, drop anything that won't parse, and emit each item.
        """
        json_pattern = r'\[.*?\]'
        matches = list(re.finditer(json_pattern, self.received_data))
        if not matches:
            return

        # Trim buffer up through the end of the last match
        last_index = matches[-1].end()
        chunks = [m.group() for m in matches]
        self.received_data = self.received_data[last_index:]

        for chunk in chunks:
            try:
                payload = json.loads(chunk)
            except json.JSONDecodeError as e:
                logging.warning(f"{e}: {chunk}")
                continue
            
            if isinstance(payload, list):
                for packet in payload:
                    self.data_received.emit(packet)
            else:
                continue

    def run(self):
        asyncio.run(self.connect_and_listen())

    def stop(self):
        self.stop_requested = True
        self.quit()
        self.wait()

    def is_connected(self) -> bool:
        return self.connected

# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG)

#     mac_address = "C0:0F:DD:31:AC:91"  
#     rx_uuid = "00002A3D-0000-1000-8000-00805F9B34FB"

#     worker = NordicBLEWorker(mac_address, rx_uuid)
    
#     try:
#         asyncio.run(worker.connect_and_listen())
#     except KeyboardInterrupt:
#         logging.info("Keyboard interrupt received. Stopping BLE worker.")
#         worker.stop()