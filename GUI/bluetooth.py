import asyncio
import csv
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
        
        self.csv_headers = [
            "X_g","Y_g","Z_g","s_rate",
            "X_deg","Y_deg","Z_deg","r_rate",
            "ACelsius", "OCelsius",
            "hPa",
            "avg_mV", "BRPM",
            "Value_mV", "pulse_BPM", 
            "SPO2"
        ]
        
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
                            
                            # print(f">>> DECODED: {decoded!r}")

                        except Exception as e:
                            logging.error(f"Error during read: {e}")
                            break  # Drop to reconnect attempt

                        await asyncio.sleep(1)

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
        # split on newlines; keep the last partial line in the buffer
        lines = self.received_data.split('\n')
        complete, self.received_data = lines[:-1], lines[-1]
        for line in complete:
            if not line.strip():
                continue
            # use csv.reader in case you want to handle quoted fields later
            for row in csv.reader([line]):
                # convert to floats
                try:
                    vals = [float(x) for x in row]
                except ValueError:
                    logging.warning(f"Bad CSV row: {row}")
                    continue
                # map to dict if you like:
                if len(vals) == len(self.csv_headers):
                    packet = dict(zip(self.csv_headers, vals))
                    self.data_received.emit(packet)
                else:
                    # fallback: emit raw list
                    self.data_received.emit(vals)

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