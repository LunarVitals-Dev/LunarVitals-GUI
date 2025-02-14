from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QToolBar,
    QHBoxLayout, QPushButton, QComboBox, QStackedWidget, QGridLayout
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap
from bleak import BleakClient
from pymongo import MongoClient
import time
from dotenv import load_dotenv
import pyqtgraph as pg
from collections import deque
import asyncio
import json
import sys
import os
import numpy as np


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
                print(f"Connected to Nordic BLE Device: {self.mac_address}")

                def callback(sender, data):
                    try:
                        message = data.decode('utf-8')
                        self.received_data += message

                        json_start = self.received_data.find('[')
                        json_end = self.received_data.find(']', json_start)

                        if json_start != -1 and json_end != -1:
                            json_data = self.received_data[json_start + 1:json_end]
                            self.received_data = self.received_data[json_end + 1:]
                            self.data_received.emit(json.loads(json_data))

                    except Exception as e:
                        print(f"Error processing data: {e}")

                await client.start_notify(self.rx_uuid, callback)

                while self.running:
                    await asyncio.sleep(0.1) # Sleep to prevent blocking the event loop
                    if self._stop_event.is_set():
                        break

                await client.stop_notify(self.rx_uuid)
        except Exception as e:
            print(f"BLE connection error: {e}")
        finally:
            self._client = None

    def run(self):
        asyncio.run(self.connect_and_listen())

    def stop(self):
        self.running = False
        if self._client:
            self._stop_event.set()
        self.quit()


class AstronautMonitor(QMainWindow):
    ACTIVITIES = ["Running", "Walking", "Hiking", "Jumping", "Lifting"]
    NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48"
    UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Physiological Monitoring System")
        self.resize(1024, 768)

        # MongoDB setup
        try:
            self.client = MongoClient(os.getenv("MONGODB_URI"))
            self.db = self.client["LunarVitalsDB"]
            self.collection = self.db["sensor_data"]
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            sys.exit(1)

        self.chart_style = {
            'background': 'white',
            'foreground': '#062a61',
            'title_size': '20pt',
            'title_color': '#062a61',
            'axis_color': '#062a61',
            'grid_color': '#e0e0e0'
        }

        self.init_data_buffers()

        self.worker = NordicBLEWorker(self.NORDIC_DEVICE_MAC, self.UART_RX_UUID)
        self.worker.data_received.connect(self.handle_ble_data)
        self.worker.start()

        self.initUI()
        
        self.mongo_buffer = []

        # Timer for updating charts
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.flush_mongo_buffer)
        self.update_timer.timeout.connect(self.update_current_chart)
        self.update_timer.timeout.connect(self.update_data_page)
        self.update_timer.start(100)

        self.current_chart_type = None
        self.data_counter = 0
        self.downsample_rate = 2

    def init_data_buffers(self):
        self.maxlen = 100
        self.pulse = deque(maxlen=self.maxlen)
        self.resp = deque(maxlen=self.maxlen)
        self.accel_x = deque(maxlen=self.maxlen)
        self.accel_y = deque(maxlen=self.maxlen)
        self.accel_z = deque(maxlen=self.maxlen)
        self.gyro_x = deque(maxlen=self.maxlen)
        self.gyro_y = deque(maxlen=self.maxlen)
        self.gyro_z = deque(maxlen=self.maxlen)
        self.obj_temp = deque(maxlen=self.maxlen)
        self.amb_temp = deque(maxlen=self.maxlen)
        self.pressure = deque(maxlen=self.maxlen)
        self.timestamps = deque(maxlen=self.maxlen)

    def send_to_mongo(self, sensor_data):
        sensor_data['timestamp'] = time.time()
        sensor_data['activity_id'] = self.activity_combo.currentText()
        self.mongo_buffer.append(sensor_data)
        
    def flush_mongo_buffer(self):
        if self.mongo_buffer:
            try:
                self.collection.insert_many(self.mongo_buffer)
                self.mongo_buffer = []
            except Exception as e:
                print(f"Error inserting into MongoDB: {e}")

    def handle_ble_data(self, data):
        self.data_counter += 1
        current_time = time.time()

        try:
            self.send_to_mongo(data)

            self.latest_data = data

            for sensor_name, sensor_data in data.items():
                if isinstance(sensor_data, dict):
                    if sensor_name == "PulseSensor" and "Value_mV" in sensor_data:
                        self.pulse.append(sensor_data["Value_mV"])
                        self.timestamps.append(current_time)
                    elif sensor_name == "RespiratoryRate" and "avg_mV" in sensor_data:
                        self.resp.append(sensor_data["avg_mV"])
                    elif sensor_name == "MPU_Accelerometer":
                        self.accel_x.append(sensor_data.get("X_g", 0))
                        self.accel_y.append(sensor_data.get("Y_g", 0))
                        self.accel_z.append(sensor_data.get("Z_g", 0))
                    elif sensor_name == "MPU_Gyroscope":
                        self.gyro_x.append(sensor_data.get("X_deg_per_s", 0))
                        self.gyro_y.append(sensor_data.get("Y_deg_per_s", 0))
                        self.gyro_z.append(sensor_data.get("Z_deg_per_s", 0))
                    elif sensor_name == "MLX_ObjectTemperature" and "Celsius" in sensor_data:
                        self.obj_temp.append(sensor_data["Celsius"])
                    elif sensor_name == "MLX_AmbientTemperature" and "Celsius" in sensor_data:
                        self.amb_temp.append(sensor_data["Celsius"])
                    elif sensor_name == "BMP_Pressure" and "hPa" in sensor_data:
                        self.pressure.append(sensor_data["hPa"])

        except Exception as e:
            print(f"Error processing BLE data: {e}")

    def initUI(self):
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)
        self.home_page = QWidget()
        self.about_page = QWidget()
        self.data_page = QWidget()  
        self.init_home_page()
        self.init_about_page()
        self.init_data_page()   
        self.central_stack.addWidget(self.home_page)
        self.central_stack.addWidget(self.about_page)
        self.central_stack.addWidget(self.data_page)  
        self.create_navbar()


    def init_home_page(self):
        layout = QVBoxLayout()
        header_label = QLabel("Physiological Monitoring Dashboard")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        activity_layout = QHBoxLayout()
        activity_label = QLabel("Current Activity:")
        self.activity_combo = QComboBox()
        self.activity_combo.addItems(self.ACTIVITIES)
        activity_layout.addWidget(activity_label)
        activity_layout.addWidget(self.activity_combo)
        activity_layout.addStretch()
        activity_widget = QWidget()
        activity_widget.setLayout(activity_layout)
        layout.addWidget(activity_widget)

        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_widget.setLayout(buttons_layout)
        self.pulse_button = QPushButton("Pulse")
        self.resp_button = QPushButton("Respiratory")
        self.accel_button = QPushButton("Accelerometer")
        self.gyro_button = QPushButton("Gyroscope")
        self.temp_button = QPushButton("Temperature")
        self.pressure_button = QPushButton("Pressure")
        buttons_layout.addWidget(self.pulse_button)
        buttons_layout.addWidget(self.resp_button)
        buttons_layout.addWidget(self.accel_button)
        buttons_layout.addWidget(self.gyro_button)
        buttons_layout.addWidget(self.temp_button)
        buttons_layout.addWidget(self.pressure_button)

        self.pulse_button.clicked.connect(lambda: self.update_chart('pulse'))
        self.resp_button.clicked.connect(lambda: self.update_chart('resp'))
        self.accel_button.clicked.connect(lambda: self.update_chart('accel'))
        self.gyro_button.clicked.connect(lambda: self.update_chart('gyro'))
        self.temp_button.clicked.connect(lambda: self.update_chart('temp'))
        self.pressure_button.clicked.connect(lambda: self.update_chart('pressure'))
        layout.addWidget(buttons_widget)

        self.chart_widget = pg.PlotWidget()
        self.setup_chart(self.chart_widget, "Sensor Data")
        layout.addWidget(self.chart_widget)
        self.home_page.setLayout(layout)

    def setup_chart(self, chart_widget, title):
        chart_widget.setBackground('white')
        chart_widget.setTitle(title, size=self.chart_style['title_size'], color=self.chart_style['title_color'])
        chart_widget.showGrid(x=True, y=True, alpha=0.3)
        chart_widget.getAxis('bottom').setPen(self.chart_style['axis_color'])
        chart_widget.getAxis('left').setPen(self.chart_style['axis_color'])
        return chart_widget

    def update_chart(self, sensor_type):
        self.current_chart_type = sensor_type
        self.chart_widget.clear()

        if sensor_type == 'pulse':
            self.chart_widget.setTitle("Pulse Rate")
            self.chart_widget.setLabel('bottom', "Time", units='s')
            self.chart_widget.setLabel('left', "Value", units='mV')
            self.pulse_plot = self.chart_widget.plot(pen='r')
            self.update_current_chart()

        elif sensor_type == 'resp':
            self.chart_widget.setTitle("Respiratory Rate")
            self.chart_widget.setLabel('bottom', "Time", units='s')
            self.chart_widget.setLabel('left', "Value", units='mV')
            self.resp_plot = self.chart_widget.plot(pen='r')
            self.update_current_chart()

        elif sensor_type == 'accel':
            self.chart_widget.setTitle("Accelerometer Data")
            self.chart_widget.setLabel('bottom', "Time", units='s')
            self.chart_widget.setLabel('left', "Acceleration", units='g')
            self.accel_x_plot = self.chart_widget.plot(pen='r')
            self.accel_y_plot = self.chart_widget.plot(pen='g')
            self.accel_z_plot = self.chart_widget.plot(pen='b')
            self.update_current_chart()

        elif sensor_type == 'gyro':
            self.chart_widget.setTitle("Gyroscope Data")
            self.chart_widget.setLabel('bottom', "Time", units='s')
            self.chart_widget.setLabel('left', "Angular Velocity", units='deg/s')
            self.gyro_x_plot = self.chart_widget.plot(pen='r')
            self.gyro_y_plot = self.chart_widget.plot(pen='g')
            self.gyro_z_plot = self.chart_widget.plot(pen='b')
            self.update_current_chart()

        elif sensor_type == 'temp':
            self.chart_widget.setTitle("Temperature Data")
            self.chart_widget.setLabel('bottom', "Time", units='s')
            self.chart_widget.setLabel('left', "Temperature", units='°C')
            self.obj_temp_plot = self.chart_widget.plot(pen='r')
            self.amb_temp_plot = self.chart_widget.plot(pen='g')
            self.update_current_chart()

        elif sensor_type == 'pressure':
            self.chart_widget.setTitle("Pressure Data")
            self.chart_widget.setLabel('bottom', "Time", units='s')
            self.chart_widget.setLabel('left', "Pressure", units='hPa')
            self.pressure_plot = self.chart_widget.plot(pen='r')
            self.update_current_chart()

    def update_current_chart(self):
        if not self.current_chart_type:
            return
        if self.data_counter % self.downsample_rate != 0:
            return

        if self.timestamps:
            first_timestamp = self.timestamps[0]
            relative_timestamps = [t - first_timestamp for t in self.timestamps]
            relative_timestamps = np.array(relative_timestamps)

        if self.current_chart_type == 'pulse':
            if self.pulse and self.timestamps:
                pulse_np = np.array(self.pulse)
                self.pulse_plot.setData(relative_timestamps, pulse_np)
                self.pulse_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)

        elif self.current_chart_type == 'resp':
            if self.resp and self.timestamps:
                resp_np = np.array(self.resp)
                self.resp_plot.setData(relative_timestamps[:len(resp_np)], resp_np)
                self.resp_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)

        elif self.current_chart_type == 'accel':
            if self.accel_x and self.timestamps:
                accel_x_np = np.array(self.accel_x)
                accel_y_np = np.array(self.accel_y)
                accel_z_np = np.array(self.accel_z)
                self.accel_x_plot.setData(relative_timestamps[:len(accel_x_np)], accel_x_np)
                self.accel_y_plot.setData(relative_timestamps[:len(accel_y_np)], accel_y_np)
                self.accel_z_plot.setData(relative_timestamps[:len(accel_z_np)], accel_z_np)
                self.accel_x_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)
                self.accel_y_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)
                self.accel_z_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)

        elif self.current_chart_type == 'gyro':
            if self.gyro_x and self.timestamps:
                gyro_x_np = np.array(self.gyro_x)
                gyro_y_np = np.array(self.gyro_y)
                gyro_z_np = np.array(self.gyro_z)
                self.gyro_x_plot.setData(relative_timestamps[:len(gyro_x_np)], gyro_x_np)
                self.gyro_y_plot.setData(relative_timestamps[:len(gyro_y_np)], gyro_y_np)
                self.gyro_z_plot.setData(relative_timestamps[:len(gyro_z_np)], gyro_z_np)
                self.gyro_x_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)
                self.gyro_y_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)
                self.gyro_z_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)

        elif self.current_chart_type == 'temp':
            if self.obj_temp and self.timestamps:
                obj_temp_np = np.array(self.obj_temp)
                amb_temp_np = np.array(self.amb_temp)
                self.obj_temp_plot.setData(relative_timestamps[:len(obj_temp_np)], obj_temp_np)
                self.amb_temp_plot.setData(relative_timestamps[:len(amb_temp_np)], amb_temp_np)
                self.obj_temp_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)
                self.amb_temp_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)

        elif self.current_chart_type == 'pressure':
            if self.pressure and self.timestamps:
                pressure_np = np.array(self.pressure)
                self.pressure_plot.setData(relative_timestamps[:len(pressure_np)], pressure_np)
                self.pressure_plot.setDownsampling(method='subsample', auto=True, ds=self.downsample_rate)

    def init_about_page(self):
        layout = QVBoxLayout()
        header_label = QLabel("About The Project")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        about_text = QLabel(
            "Lunar Vitals Monitoring System\n"
            "This application provides real-time monitoring of astronaut physiological data during lunar missions."
        )
        about_text.setAlignment(Qt.AlignCenter)
        about_text.setWordWrap(True)
        layout.addWidget(about_text)
        self.about_page.setLayout(layout)

    def init_data_page(self):
        layout = QGridLayout()
        self.data_labels = {}

        row = 0
        for sensor_name in ["PulseSensor", "RespiratoryRate", "MPU_Accelerometer",
                            "MPU_Gyroscope", "MLX_ObjectTemperature",
                            "MLX_AmbientTemperature", "BMP_Pressure"]:
            self.data_labels[sensor_name] = {}
            layout.addWidget(QLabel(f"<b>{sensor_name}:</b>"), row, 0, alignment=Qt.AlignLeft)
            row += 1

            if sensor_name == "PulseSensor":
                self.data_labels[sensor_name]["Value_mV"] = QLabel("Value_mV: N/A")
                layout.addWidget(self.data_labels[sensor_name]["Value_mV"], row, 0, alignment=Qt.AlignLeft)
                row += 1
            elif sensor_name == "RespiratoryRate":
                self.data_labels[sensor_name]["avg_mV"] = QLabel("avg_mV: N/A")
                layout.addWidget(self.data_labels[sensor_name]["avg_mV"], row, 0, alignment=Qt.AlignLeft)
                row += 1
            elif sensor_name == "MPU_Accelerometer":
                for axis in ["X_g", "Y_g", "Z_g"]:
                    self.data_labels[sensor_name][axis] = QLabel(f"{axis}: N/A")
                    layout.addWidget(self.data_labels[sensor_name][axis], row, 0, alignment=Qt.AlignLeft)
                    row += 1
            elif sensor_name == "MPU_Gyroscope":
                for axis in ["X_deg_per_s", "Y_deg_per_s", "Z_deg_per_s"]:
                    self.data_labels[sensor_name][axis] = QLabel(f"{axis}: N/A")
                    layout.addWidget(self.data_labels[sensor_name][axis], row, 0, alignment=Qt.AlignLeft)
                    row += 1
            elif sensor_name in ["MLX_ObjectTemperature", "MLX_AmbientTemperature"]:
                self.data_labels[sensor_name]["Celsius"] = QLabel("Celsius: N/A")
                layout.addWidget(self.data_labels[sensor_name]["Celsius"], row, 0, alignment=Qt.AlignLeft)
                row += 1
            elif sensor_name == "BMP_Pressure":
                self.data_labels[sensor_name]["hPa"] = QLabel("hPa: N/A")
                layout.addWidget(self.data_labels[sensor_name]["hPa"], row, 0, alignment=Qt.AlignLeft)
                row += 1

        layout.setRowStretch(row, 1)
        self.data_page.setLayout(layout)


    def update_data_page(self):
        if hasattr(self, 'latest_data'):
            for sensor_name, sensor_data in self.latest_data.items():
                if isinstance(sensor_data, dict) and sensor_name in self.data_labels:
                    for key, value in sensor_data.items():
                        if key in self.data_labels[sensor_name]:
                            self.data_labels[sensor_name][key].setText(f"{key}: {value:.2f}")

    def create_navbar(self):
        navbar_widget = QWidget()
        navbar_layout = QHBoxLayout(navbar_widget)
        navbar_layout.setSpacing(30)

        left_buttons = QWidget()
        left_layout = QHBoxLayout(left_buttons)
        home_button = QPushButton("Home")
        home_button.setObjectName("navButton")
        home_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.home_page))
        left_layout.addWidget(home_button)
        navbar_layout.addWidget(left_buttons)

        navbar_layout.addStretch()

        # Data Page Button  <-  Moved BEFORE logo
        data_button = QPushButton("Data")
        data_button.setObjectName("navButton")
        data_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.data_page))
        left_layout.addWidget(data_button) #add to left layout


        self.logo_label = QLabel()
        pixmap = QPixmap("lunarlogo.png")
        pixmap = pixmap.scaled(250, 80, Qt.KeepAspectRatio)
        self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignCenter)
        navbar_layout.addWidget(self.logo_label)

        navbar_layout.addStretch()

        right_buttons = QWidget()
        right_layout = QHBoxLayout(right_buttons)
        about_button = QPushButton("About")
        about_button.setObjectName("navButton")
        about_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.about_page))
        right_layout.addWidget(about_button)
        navbar_layout.addWidget(right_buttons)

        navbar = QToolBar()
        navbar.setMovable(False)
        navbar.addWidget(navbar_widget)
        self.addToolBar(navbar)

    def closeEvent(self, event):
        self.worker.stop()
        self.update_timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file:
        style_sheet = file.read()
        app.setStyleSheet(style_sheet)
    window = AstronautMonitor()
    window.show()
    sys.exit(app.exec())
