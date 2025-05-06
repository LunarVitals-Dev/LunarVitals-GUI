import asyncio
import re
import json
import logging
from PySide6.QtCore import QThread, Signal
from bleak import BleakClient
import demjson3

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

    # async def connect_and_listen(self):
    #     try:
    #         async with BleakClient(self.mac_address) as client:
    #             self.client = client
    #             logging.info(f"Connected to Nordic BLE Device {self.mac_address}")
                
    #             services = await client.get_services()
    #             # for svc in services:
    #             #     for ch in svc.characteristics:
    #             #         print(f"Char {ch.uuid!r}: props={ch.properties}")

    #             # Read‑loop
    #             while not self.stop_requested:
    #                 try:
    #                     raw = await client.read_gatt_char(self.rx_uuid)
    #                     logging.debug(f"Raw chunk: {raw!r}")

    #                     # Try common decodings
    #                     for codec in ('utf-8','latin-1','ascii'):
    #                         try:
    #                             decoded = raw.decode(codec)
    #                             break
    #                         except UnicodeDecodeError:
    #                             decoded = None

    #                     if not decoded:
    #                         logging.warning("Discarding undecodable BLE chunk")
    #                         await asyncio.sleep(0.1)
    #                         continue

    #                     #print(f"Got text fragment: {decoded!r}")
    #                     self.received_data += decoded

    #                     # Try to pull out any full JSON payloads
    #                     self.process_received_data()

    #                 except Exception as e:
    #                     logging.error(f"Error during read: {e}")

    #                 await asyncio.sleep(1)

    #     except Exception as e:
    #         logging.error(f"BLE connection error: {e}")

    #     finally:
    #         self.client = None
    #         logging.info("Disconnected BLE client")

    def process_received_data(self):
        """
        Extract complete JSON arrays (assumed to be wrapped in square brackets)
        from the accumulated data and then emit them via the data_received signal.
        Processed text is removed from the buffer up to the end of the last complete match.
        """

        # This pattern is non-greedy so it should capture each JSON array separately.
        json_pattern = r'\[.*?\]'
        
        # Use finditer to get match objects, including their start and end positions.
        matches = list(re.finditer(json_pattern, self.received_data))
        
        if matches:
            # The end index of the last match tells us how much of the buffer was processed.
            last_index = matches[-1].end()
            # Extract all found JSON array strings.
            json_objects = [m.group() for m in matches]
            # Remove the processed portion from the buffer.
            self.received_data = self.received_data[last_index:]
        
            # Process each JSON array found.
            for json_str in json_objects:
                data_list = None
                try:
                    data_list = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logging.warning(f"JSON Decode Error: {e}, attempting repair...")
                    try:
                        data_list = demjson3.decode(json_str, strict=False)
                        logging.info("Successfully recovered malformed JSON.")
                    except Exception as repair_err:
                        logging.error(f"JSON Repair Failed: {repair_err}, data: {json_str}")
                        continue  # skip to next payload

                # At this point, data_list should be parsed or repaired
                if not data_list:
                    continue

                if isinstance(data_list, list):
                    for sensor_data in data_list:
                        
                            self.data_received.emit(sensor_data)
                       
                else:
                    if self._validate_packet(data_list):
                        self.data_received.emit(data_list)
            # for json_str in json_objects:
            #     try:
            #         # Parse the JSON array, which should return a list of sensor objects.
            #         data_list = json.loads(json_str)
                    
            #         # If the parsed object is a list, emit each sensor's data individually.
            #         if isinstance(data_list, list):
            #             for sensor_data in data_list:
            #                 self.data_received.emit(sensor_data)
            #         else:
            #             self.data_received.emit(data_list)
            #     except json.JSONDecodeError as e:
            #         logging.error(f"JSON Decode Error: {e}, data: {json_str}")
            #     except Exception as e:
            #         logging.error(f"Error processing JSON: {e}")
    # def _validate_packet(self, packet):
    # # Acceptable top-level sensor keys
    # valid_keys = {
    #     "Accel", "Gyro", "Pressure",
    #     "AmbientTemp", "ObjectTemp",
    #     "RespiratoryRate", "PulseSensor",
    #     "SPO2_Sensor"
    # }

    # return isinstance(packet, dict) and any(k in packet for k in valid_keys)

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