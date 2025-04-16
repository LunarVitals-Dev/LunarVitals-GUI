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
        self.received_data = ""
        self.client = None
        self.stop_requested = False

    async def connect_and_listen(self):
        try:
            async with BleakClient(self.mac_address) as client:
                self.client = client
                logging.info(f"Connected to Nordic BLE Device: {self.mac_address}")
                
                # Optionally, read the services and log the characteristic properties.
                services = await client.get_services()
                char = services.get_characteristic(self.rx_uuid)
                if char:
                    logging.debug(f"Characteristic Properties: {char.properties}")
                else:
                    logging.warning(f"Characteristic {self.rx_uuid} not found!")

                # Loop: continuously read the GATT characteristic.
                while not self.stop_requested:
                    try:
                        response = await client.read_gatt_char(self.rx_uuid)
                        logging.debug(f"Raw Data received: {response}")
                        decoded_message = None

                        # Try decoding in UTF-8, fallback to Latin-1, ASCII, and finally hex.
                        try:
                            decoded_message = response.decode('utf-8')
                        except UnicodeDecodeError:
                            logging.info("UTF-8 decoding failed. Trying Latin-1.")
                            try:
                                decoded_message = response.decode('latin-1')
                            except UnicodeDecodeError:
                                logging.info("Latin-1 decoding failed. Trying ASCII.")
                                try:
                                    decoded_message = response.decode('ascii')
                                except UnicodeDecodeError:
                                    logging.info("ASCII decoding failed. Using hex representation.")
                                    decoded_message = response.hex()

                        logging.debug(f"Decoded Data: {decoded_message}")

                        # Append decoded message to the buffer and process it.
                        self.received_data += decoded_message
                        self.process_received_data()
                        
                    except Exception as e:
                        logging.error(f"Error during read: {e}")
                    
                    await asyncio.sleep(0.2)

        except Exception as e:
            logging.error(f"BLE connection error: {e}")
        finally:
            self.client = None

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
                try:
                    # Parse the JSON array, which should return a list of sensor objects.
                    data_list = json.loads(json_str)
                    
                    # If the parsed object is a list, emit each sensor's data individually.
                    if isinstance(data_list, list):
                        for sensor_data in data_list:
                            self.data_received.emit(sensor_data)
                    else:
                        self.data_received.emit(data_list)
                except json.JSONDecodeError as e:
                    logging.error(f"JSON Decode Error: {e}. Problematic JSON string: {json_str}")
                except Exception as e:
                    logging.error(f"Error processing JSON: {e}")

    def run(self):
        # Run the asyncio event loop in this thread.
        asyncio.run(self.connect_and_listen())

    def stop(self):
        # Signal the loop to exit.
        self.stop_requested = True
        self.quit()
        self.wait()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    mac_address = "C0:0F:DD:31:AC:91"  
    rx_uuid = "00002A3D-0000-1000-8000-00805F9B34FB"

    worker = NordicBLEWorker(mac_address, rx_uuid)
    
    try:
        asyncio.run(worker.connect_and_listen())
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Stopping BLE worker.")
        worker.stop()