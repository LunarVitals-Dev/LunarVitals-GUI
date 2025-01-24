from pymongo import MongoClient
from datetime import datetime
import sys
import asyncio
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import QThread, Signal
from bleak import BleakClient
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Replace with your Nordic device's MAC address and UUIDs
#NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48"
#NORDIC_DEVICE_MAC = "FB:F2:39:B0:84:16" #for vic
NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48" #for vic

UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

# MongoDB Setup
MONGO_URI = "mongodb+srv://LunarVitals:lunarvitals1010@peakfitness.i5blp.mongodb.net/"
DATABASE_NAME = "LunarVitalsDB"
COLLECTION_NAME = "SensorData"

class NordicBLEWorker(QThread):
    data_received = Signal(int)  # Signal to send the received data to the GUI

    def __init__(self, mac_address, rx_uuid):
        super().__init__()
        self.mac_address = mac_address
        self.rx_uuid = rx_uuid
        self.client = None
        self.running = True

    async def connect_and_listen(self):
        async with BleakClient(self.mac_address) as client:
            self.client = client
            print(f"Connected to Nordic BLE Device: {self.mac_address}")

            # Subscribe to notifications for the RX characteristic
            def callback(sender, data):
                try:
                    value = int(data.decode('utf-8').strip())  # Convert received data to an integer
                    print(f"Received data: {value}")  # Debugging print
                    self.data_received.emit(value)
                    self.save_to_database(value)  # Save data to MongoDB
                except ValueError:
                    print(f"Invalid data received: {data}")

            await client.start_notify(self.rx_uuid, callback)

            # Keep the connection open
            while self.running:
                await asyncio.sleep(1)

            await client.stop_notify(self.rx_uuid)

    def save_to_database(self, value):
        """Save the received data to the MongoDB database."""
        try:
            document = {
                "timestamp": datetime.utcnow(),
                "value": value
            }
            result = collection.insert_one(document)
            print(f"Saved to MongoDB: {document}")  # Debugging print
        except Exception as e:
            print(f"Error saving to MongoDB: {e}")

    def run(self):
        asyncio.run(self.connect_and_listen())

    def stop(self):
        self.running = False
        self.quit()


class LivePlot(QWidget):
    def __init__(self):
        super().__init__()
        self.data = []  # List to store incoming data

        # Set up Matplotlib figure and canvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Live Data Plot")
        self.ax.set_xlabel("Time (points)")
        self.ax.set_ylabel("Value")

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def update_plot(self, value):
        self.data.append(value)
        self.data = self.data[-100:]  # Keep only the last 100 points for visualization
        self.ax.clear()
        self.ax.plot(self.data, color="blue")
        self.ax.set_title("Live Data Plot")
        self.ax.set_xlabel("Time (points)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Data Plot with BLE and MongoDB")

        # Check MongoDB Connection
        try:
            global collection
            client = MongoClient(MONGO_URI)
            print("Connected to MongoDB Atlas")
            db = client[DATABASE_NAME]
            collection = db[COLLECTION_NAME]
            print(f"Database: {DATABASE_NAME}, Collection: {COLLECTION_NAME} selected")
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            sys.exit(1)  # Exit if the database connection fails

        # Create a LivePlot widget
        self.plot_widget = LivePlot()
        self.setCentralWidget(self.plot_widget)

        # Start the Nordic BLE worker
        self.worker = NordicBLEWorker(NORDIC_DEVICE_MAC, UART_RX_UUID)
        self.worker.data_received.connect(self.plot_widget.update_plot)
        self.worker.start()

    def closeEvent(self, event):
        # Stop the worker thread when closing the app
        self.worker.stop()
        self.worker.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
