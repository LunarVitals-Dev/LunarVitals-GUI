import asyncio
import json
from PySide6.QtWidgets import QApplication, QMainWindow, QComboBox, QVBoxLayout, QWidget
from PySide6.QtCore import QThread, Signal
from bleak import BleakClient
import pymongo
from datetime import datetime

# MongoDB setup
MONGO_URI = "mongodb+srv://LunarVitals:lunarvitals1010@peakfitness.i5blp.mongodb.net/"
DATABASE_NAME = "LunarVitalsDB"
client = pymongo.MongoClient(MONGO_URI)
db = client[DATABASE_NAME]

# MongoDB function to insert data
def send_to_mongo(sensor_data, collection_name):
    try:
        # Convert string to JSON if it isn't already a dictionary
        if isinstance(sensor_data, str):
            sensor_data = json.loads(sensor_data)
        
        # Add timestamp or any other metadata you need (optional)
        sensor_data['timestamp'] = datetime.utcnow()
        
        # Get the collection
        collection = db[collection_name]
        
        # Insert data into MongoDB
        result = collection.insert_one(sensor_data)
        print(f"Data inserted with ID: {result.inserted_id}")
    except Exception as e:
        print(f"Error inserting data into MongoDB: {e}")

# Activity list
ACTIVITIES = ["Running", "Walking", "Cycling", "Jumping", "Lifting"]

NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48"  # Replace with your device MAC address
UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Replace with your RX UUID

class NordicBLEWorker(QThread):
    data_received = Signal(dict)  # Signal to send received data to the GUI

    def __init__(self, mac_address, rx_uuid):
        super().__init__()
        self.mac_address = mac_address
        self.rx_uuid = rx_uuid
        self.running = True
        self.received_data = ""  # To accumulate incoming data

    async def connect_and_listen(self):
        async with BleakClient(self.mac_address) as client:
            print(f"Connected to Nordic BLE Device: {self.mac_address}")

            # Callback for handling received notifications
            def callback(sender, data):
                try:
                    message = data.decode('utf-8')
                    self.received_data += message

                    # Process the complete JSON object(s)
                    while True:
                        json_start = self.received_data.find('[')
                        json_end = self.received_data.find(']', json_start)

                        if json_start == -1 or json_end == -1:
                            break

                        # Extract the complete JSON object
                        json_data = self.received_data[json_start + 1:json_end]  # Remove markers
                        self.received_data = self.received_data[json_end + 1:]  # Remove processed data

                        # Emit the parsed JSON data
                        self.data_received.emit(json.loads(json_data))

                except Exception as e:
                    print(f"Error processing data: {e}")

            await client.start_notify(self.rx_uuid, callback)

            while self.running:
                await asyncio.sleep(1)

            await client.stop_notify(self.rx_uuid)

    def run(self):
        asyncio.run(self.connect_and_listen())

    def stop(self):
        self.running = False
        self.quit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nordic BLE Data Receiver")

        # Dropdown for selecting activity
        self.activity_combobox = QComboBox()
        self.activity_combobox.addItems(ACTIVITIES)
        self.activity_combobox.setCurrentIndex(0)  # Set default activity (e.g., "Running")

        # Layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.activity_combobox)
        
        # Create a central widget and set layout
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Start the Nordic BLE worker
        self.worker = NordicBLEWorker(NORDIC_DEVICE_MAC, UART_RX_UUID)
        self.worker.data_received.connect(self.handle_data)
        self.worker.start()

    def handle_data(self, data):
        # Get the selected activity from the dropdown
        selected_activity = self.activity_combobox.currentText()

        # Add activity ID to the data
        data['activity_id'] = selected_activity

        # Print data received for debugging
        print(f"Data received: {data}")

        # Insert the received data into the MongoDB collection (e.g., "sensor_data")
        send_to_mongo(data, "sensor_data")

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


# import asyncio
# import json
# from PySide6.QtWidgets import QApplication, QMainWindow
# from PySide6.QtCore import QThread, Signal
# from bleak import BleakClient
# import pymongo
# from datetime import datetime

# # MongoDB setup
# MONGO_URI = "mongodb+srv://LunarVitals:lunarvitals1010@peakfitness.i5blp.mongodb.net/"
# DATABASE_NAME = "LunarVitalsDB"
# client = pymongo.MongoClient(MONGO_URI)
# db = client[DATABASE_NAME]

# # MongoDB function to insert data
# def send_to_mongo(sensor_data, collection_name):
#     try:
#         # Convert string to JSON if it isn't already a dictionary
#         if isinstance(sensor_data, str):
#             sensor_data = json.loads(sensor_data)
        
#         # Add timestamp or any other metadata you need (optional)
#         sensor_data['timestamp'] = datetime.utcnow()
        
#         # Get the collection
#         collection = db[collection_name]
        
#         # Insert data into MongoDB
#         result = collection.insert_one(sensor_data)
#         print(f"Data inserted with ID: {result.inserted_id}")
#     except Exception as e:
#         print(f"Error inserting data into MongoDB: {e}")


# NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48"  # Replace with your device MAC address
# UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Replace with your RX UUID

# class NordicBLEWorker(QThread):
#     data_received = Signal(dict)  # Signal to send received data to the GUI

#     def __init__(self, mac_address, rx_uuid):
#         super().__init__()
#         self.mac_address = mac_address
#         self.rx_uuid = rx_uuid
#         self.running = True
#         self.received_data = ""  # To accumulate incoming data

#     async def connect_and_listen(self):
#         async with BleakClient(self.mac_address) as client:
#             print(f"Connected to Nordic BLE Device: {self.mac_address}")

#             # Callback for handling received notifications
#             def callback(sender, data):
#                 try:
#                     message = data.decode('utf-8')
#                     # Accumulate data
#                     self.received_data += message

#                     # Process the complete JSON object(s)
#                     while True:
#                         # Find the start and end of a JSON object
#                         json_start = self.received_data.find('[')
#                         json_end = self.received_data.find(']', json_start)

#                         if json_start == -1 or json_end == -1:
#                             break

#                         # Extract the complete JSON object
#                         json_data = self.received_data[json_start + 1:json_end]  # Remove markers
#                         self.received_data = self.received_data[json_end + 1:]  # Remove processed data

#                         # Emit the parsed JSON data
#                         self.data_received.emit(json.loads(json_data))

#                 except Exception as e:
#                     print(f"Error processing data: {e}")

#             await client.start_notify(self.rx_uuid, callback)

#             # Keep the connection open
#             while self.running:
#                 await asyncio.sleep(1)

#             await client.stop_notify(self.rx_uuid)

#     def run(self):
#         asyncio.run(self.connect_and_listen())

#     def stop(self):
#         self.running = False
#         self.quit()


# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("Nordic BLE Data Receiver")

#         # Start the Nordic BLE worker
#         self.worker = NordicBLEWorker(NORDIC_DEVICE_MAC, UART_RX_UUID)
#         self.worker.data_received.connect(self.handle_data)
#         self.worker.start()

#     def handle_data(self, data):
#         # Print data received for debugging
#         print(f"Data received: {data}")

#         # Insert the received data into the MongoDB collection (e.g., "sensor_data")
#         send_to_mongo(data, "sensor_data")

#     def closeEvent(self, event):
#         # Stop the worker thread when closing the app
#         self.worker.stop()
#         self.worker.wait()
#         super().closeEvent(event)


# if __name__ == "__main__":
#     app = QApplication([])
#     window = MainWindow()
#     window.show()
#     app.exec()


# # import asyncio
# # import json
# # from PySide6.QtWidgets import QApplication, QMainWindow
# # from PySide6.QtCore import QThread, Signal
# # from bleak import BleakClient

# # NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48"  # Replace with your device MAC address
# # UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Replace with your RX UUID

# # class NordicBLEWorker(QThread):
# #     data_received = Signal(dict)  # Signal to send received data to the GUI

# #     def __init__(self, mac_address, rx_uuid):
# #         super().__init__()
# #         self.mac_address = mac_address
# #         self.rx_uuid = rx_uuid
# #         self.running = True
# #         self.received_data = ""  # To accumulate incoming data

# #     async def connect_and_listen(self):
# #         async with BleakClient(self.mac_address) as client:
# #             print(f"Connected to Nordic BLE Device: {self.mac_address}")

# #             # Callback for handling received notifications
# #             def callback(sender, data):
# #                 try:
# #                     message = data.decode('utf-8')
# #                     #print(f"Received data chunk: {message}")

# #                     # Accumulate data
# #                     self.received_data += message

# #                     # Process the complete JSON object(s)
# #                     while True:
# #                         # Find the start and end of a JSON object
# #                         json_start = self.received_data.find('[')
# #                         json_end = self.received_data.find(']', json_start)

# #                         if json_start == -1 or json_end == -1:
# #                             # No complete JSON object yet
# #                             #print("Data is incomplete, waiting for more...")
# #                             break

# #                         # Extract the complete JSON object
# #                         json_data = self.received_data[json_start + 1:json_end]  # Remove markers
# #                         self.received_data = self.received_data[json_end + 1:]  # Remove processed data

# #                         print(f"Complete JSON object: {json_data}")
# #                         self.data_received.emit(json.loads(json_data))  # Emit the parsed JSON data

# #                 except Exception as e:
# #                     print(f"Error processing data: {e}")

# #             await client.start_notify(self.rx_uuid, callback)

# #             # Keep the connection open
# #             while self.running:
# #                 await asyncio.sleep(1)

# #             await client.stop_notify(self.rx_uuid)

# #     def run(self):
# #         asyncio.run(self.connect_and_listen())

# #     def stop(self):
# #         self.running = False
# #         self.quit()


# # class MainWindow(QMainWindow):
# #     def __init__(self):
# #         super().__init__()
# #         self.setWindowTitle("Nordic BLE Data Receiver")

# #         # Start the Nordic BLE worker
# #         self.worker = NordicBLEWorker(NORDIC_DEVICE_MAC, UART_RX_UUID)
# #         self.worker.data_received.connect(self.handle_data)
# #         self.worker.start()

# #     def handle_data(self, data):
# #         return
# #         #print(f"Data received: {data}")

# #     def closeEvent(self, event):
# #         # Stop the worker thread when closing the app
# #         self.worker.stop()
# #         self.worker.wait()
# #         super().closeEvent(event)


# # if __name__ == "__main__":
# #     app = QApplication([])
# #     window = MainWindow()
# #     window.show()
# #     app.exec()
