from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QToolBar,
    QHBoxLayout, QPushButton, QComboBox, QStackedWidget, QGridLayout, QFrame,
    QFormLayout, QLineEdit, QMessageBox, QStackedWidget
)

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap, QFontDatabase, QFont, QIntValidator
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
import logging
import re     

class IntroPage(QWidget):
    profile_submitted = Signal(str, str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("introPage") 

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Form container with styling applied
        form_widget = QWidget()
        form_widget.setObjectName("introForm")  
        form_layout = QFormLayout(form_widget)
        form_layout.setContentsMargins(50, 30, 50, 30)

        # Title
        title_label = QLabel("Astronaut Profile Setup")
        title_label.setObjectName("introTitle")  
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Name input field
        self.name_input = QLineEdit()
        self.name_input.setObjectName("introForm") 
        self.name_input.setPlaceholderText("Enter astronaut's name")
        form_layout.addRow(QLabel("Name:"), self.name_input)

        # Gender selection
        self.gender_combo = QComboBox()
        self.gender_combo.setObjectName("introForm") 
        self.gender_combo.addItems(["Male", "Female", "Other"])
        form_layout.addRow(QLabel("Gender:"), self.gender_combo)

        # Age input
        self.age_input = QLineEdit()
        self.age_input.setObjectName("introForm") 
        self.age_input.setPlaceholderText("Enter astronaut's age")
        self.age_input.setValidator(QIntValidator(self)) 
        self.age_input.setMaxLength(2) 
        form_layout.addRow(QLabel("Age:"), self.age_input)

        layout.addWidget(form_widget)

        # Submit button
        self.submit_button = QPushButton("Start Monitoring")
        self.submit_button.setObjectName("submitButton")  
        self.submit_button.clicked.connect(self.submit_profile)

        # Center the button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.submit_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()

    def submit_profile(self):
        name = self.name_input.text().strip()
        gender = self.gender_combo.currentText()
        age_text = self.age_input.text().strip()

        # Validate name and age
        if not name or not age_text:
            QMessageBox.warning(self, "Input Error", "Please enter the astronaut's name and age.")
            return

        age = int(age_text)

        self.profile_submitted.emit(name, gender, age)

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

                def callback(sender, data):
                    try:
                        message = data.decode('utf-8')
                        self.received_data += message
                        self.process_received_data()

                    except Exception as e:
                        logging.error(f"Error in BLE callback: {e}")

                await client.start_notify(self.rx_uuid, callback)

                while self.running:
                    await asyncio.sleep(0.1) # Sleep to prevent blocking the event loop
                    if self._stop_event.is_set():
                        break

                await client.stop_notify(self.rx_uuid)
        except Exception as e:
            logging.error(f"BLE connection error: {e}")
        finally:
            self._client = None

    def process_received_data(self):
        #Use regex to split by complete JSON arrays
        json_pattern = r'\[.*?\]'
        json_objects = re.findall(json_pattern, self.received_data)

        #Clear processed data
        self.received_data = self.received_data[len("".join(json_objects)):]

        for json_str in json_objects:
            try:
                #Load JSON string to object, stripping square brackets
                data = json.loads(json_str[1:-1])
                self.data_received.emit(data)
            except json.JSONDecodeError as e:
                logging.error(f"JSON Decode Error: {e}.  Problematic JSON String: {json_str}")
            except Exception as e:
                logging.error(f"Error processing JSON: {e}")

    def run(self):
        asyncio.run(self.connect_and_listen())

    def stop(self):
        self.running = False
        if self._client:
            self._stop_event.set()
        self.quit()


class AstronautMonitor(QMainWindow):
    ACTIVITIES = ["No Activity", "Running", "Walking", "Hiking", "Cranking", "Lifting"]
    NORDIC_DEVICE_MAC = "F7:98:E4:81:FC:48"
    UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

    def __init__(self, name, gender, age):
        super().__init__()
        self.setWindowTitle("Physiological Monitoring System")
        self.resize(1024, 768)

        self.load_custom_font()
        
        self.astronaut_name = name
        self.astronaut_gender = gender
        self.astronaut_age = age

        try:
            self.client = MongoClient(os.getenv("MONGODB_URI"))
            self.db = self.client["LunarVitalsDB"]
            self.collection = self.db["sensor_data"]
        except Exception as e:
            logging.error(f"Error connecting to MongoDB: {e}")
            sys.exit(1)

        self.chart_style = {
            'background': 'white',
            'foreground': '#062a61',
            'title_size': '20pt',
            'title_color': '#062a61',
            'axis_color': '#062a61',
            'grid_color': 'e0e0e0'
        }

        self.init_data_buffers()

        self.worker = NordicBLEWorker(self.NORDIC_DEVICE_MAC, self.UART_RX_UUID)
        self.worker.data_received.connect(self.handle_ble_data)
        self.worker.start()

        self.initUI()

        self.mongo_buffer = []

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.flush_mongo_buffer)
        self.update_timer.timeout.connect(self.update_home_page)
        self.update_timer.timeout.connect(self.update_current_chart)
        self.update_timer.start(100)

        self.current_chart_type = None

        print(f"Astronaut Profile - Name: {self.astronaut_name}, Gender: {self.astronaut_gender}, Age: {self.astronaut_age}")
        
    def load_custom_font(self):
        self.custom_font_id = QFontDatabase.addApplicationFont("assets/MegatransdemoRegular-8M9B0.otf")
        if self.custom_font_id != -1:
            self.custom_font_family = QFontDatabase.applicationFontFamilies(self.custom_font_id)[0]
            self.custom_font = QFont(self.custom_font_family)
        else:
            logging.error("Failed to load custom font")
            self.custom_font = None

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
        self.SPO2 = deque(maxlen=self.maxlen)
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
                logging.error(f"Error inserting into MongoDB: {e}")

    def handle_ble_data(self, data):
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
                    elif sensor_name == "MAX_SP02 Sensor" and "SPO2" in sensor_data:
                        self.pressure.append(sensor_data["SPO2"])

        except Exception as e:
            logging.error(f"Error processing BLE data: {e}")

    def initUI(self):
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)
        self.home_page = QWidget()
        self.data_page = QWidget()  
        self.init_home_page()
        self.init_data_page() 
        self.central_stack.addWidget(self.home_page)
        self.central_stack.addWidget(self.data_page)  
        self.create_navbar()
        
    def init_home_page(self):
        layout = QGridLayout()
        
        # Header title
        header_label = QLabel(f"{self.astronaut_name}'s Dashboard")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label, 0, 0, 1, 3)  # Title spans 3 columns at the top

        self.data_labels = {}

        # Sensor display configuration
        self.sensor_config = {
            "PulseSensor": {
                "display_name": "Heart Rate Monitor",
                "measurements": {"pulse_BPM": "Heart Rate (BPM)"},
                "grid_position": (1, 0)  # Left column
            },
            "RespiratoryRate": {
                "display_name": "Breathing Rate Monitor",
                "measurements": {"BRPM": "Breathing Rate (breaths/min)"},
                "grid_position": (2, 0)
            },
            "MPU_Accelerometer": {
                "display_name": "Step Counter",
                "measurements": {"steps": "Total Steps"},
                "grid_position": (3, 0)
            },
            "MLX_ObjectTemperature": {
                "display_name": "Body Temperature",
                "measurements": {"Celsius": "Temperature (°C)"},
                "grid_position": (1, 2)  # Right column
            },
            "BMP_Pressure": {
                "display_name": "Atmospheric Pressure",
                "measurements": {"hPa": "Pressure (hPa)"},
                "grid_position": (2, 2)
            },
            "MAX_SPO2 Sensor": {
                "display_name": "Blood Oxygen Monitor",
                "measurements": {"SPO2": "Blood Oxygen (%)"},
                "grid_position": (3, 2)
            }
        }

        # Create sensor boxes
        for sensor_name, config in self.sensor_config.items():
            sensor_box = QFrame()
            sensor_box.setObjectName("sensorBox")
            sensor_box.setProperty("class", "sensor-box")

            box_layout = QVBoxLayout()
            title = QLabel(f"<b>{config['display_name']}</b>")
            if self.custom_font:
                title.setFont(self.custom_font)
            title.setProperty("class", "sensor-title")
            box_layout.addWidget(title)

            self.data_labels[sensor_name] = {}
            for key, display_name in config['measurements'].items():
                value_label = QLabel(f"{display_name}: N/A")
                if self.custom_font:
                    value_label.setFont(self.custom_font)
                value_label.setProperty("class", "sensor-value")
                self.data_labels[sensor_name][key] = value_label
                box_layout.addWidget(value_label)

            sensor_box.setLayout(box_layout)
            row, col = config['grid_position']
            layout.addWidget(sensor_box, row, col)

        # Add astronaut image
        center_image = QLabel()
        center_image.setObjectName("centerImage")
        center_image.setFixedSize(300, 500)  
        center_image.setScaledContents(True)
        pixmap = QPixmap('assets/spaceman.png')
        center_image.setPixmap(pixmap)

        # Place image in center column spanning rows 1 to 3
        layout.addWidget(center_image, 1, 1, 3, 1, Qt.AlignCenter)

        # Set column and row stretch for even spacing
        layout.setColumnStretch(0, 1)  # Left
        layout.setColumnStretch(1, 1)  # Center
        layout.setColumnStretch(2, 1)  # Right
        layout.setRowStretch(1, 1)
        layout.setRowStretch(2, 1)
        layout.setRowStretch(3, 1)

        self.home_page.setLayout(layout)


    def update_home_page(self):
        if hasattr(self, 'latest_data'):
            for sensor_name, sensor_data in self.latest_data.items():
                if isinstance(sensor_data, dict) and sensor_name in self.data_labels:
                    for key, value in sensor_data.items():
                        if key in self.data_labels[sensor_name]:
                            display_name = next(
                                (config['measurements'][key] 
                                for config in self.sensor_config.values() 
                                if key in config['measurements']),
                                key
                            )
                            self.data_labels[sensor_name][key].setText(
                                f"{display_name}: {value:.2f}"
                            )


    def init_data_page(self):
        layout = QVBoxLayout()
        activity_layout = QHBoxLayout()

        # Create individual buttons for each activity
        self.activity_buttons = {}
        for activity in self.ACTIVITIES:
            button = QPushButton(activity)
            button.setCheckable(True)  # Make the button toggleable
            button.clicked.connect(lambda checked, act=activity: self.set_current_activity(act))
            self.activity_buttons[activity] = button
            activity_layout.addWidget(button)

        # Create a widget to hold the activity layout
        activity_widget = QWidget()
        activity_widget.setLayout(activity_layout)

        # Create a horizontal layout to center the activity widget
        centered_layout = QHBoxLayout()
        centered_layout.addStretch()
        centered_layout.addWidget(activity_widget)
        centered_layout.addStretch()

        layout.addLayout(centered_layout)

        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_widget.setLayout(buttons_layout)
        self.pulse_button = QPushButton("Pulse")
        self.resp_button = QPushButton("Respiratory")
        self.accel_button = QPushButton("Accelerometer")
        self.gyro_button = QPushButton("Gyroscope")
        self.temp_button = QPushButton("Temperature")
        buttons_layout.addWidget(self.pulse_button)
        buttons_layout.addWidget(self.resp_button)
        buttons_layout.addWidget(self.accel_button)
        buttons_layout.addWidget(self.gyro_button)
        buttons_layout.addWidget(self.temp_button)

        self.pulse_button.clicked.connect(lambda: self.update_chart('pulse'))
        self.resp_button.clicked.connect(lambda: self.update_chart('resp'))
        self.accel_button.clicked.connect(lambda: self.update_chart('accel'))
        self.gyro_button.clicked.connect(lambda: self.update_chart('gyro'))
        self.temp_button.clicked.connect(lambda: self.update_chart('temp'))
        layout.addWidget(buttons_widget)

        self.chart_widget = pg.PlotWidget()
        self.setup_chart(self.chart_widget, "Sensor Data")
        layout.addWidget(self.chart_widget)
        self.data_page.setLayout(layout)

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

    def update_current_chart(self):
        if not self.current_chart_type:
            return

        if self.timestamps:
            first_timestamp = self.timestamps[0]
            relative_timestamps = [t - first_timestamp for t in self.timestamps]
            relative_timestamps = np.array(relative_timestamps)

        if self.current_chart_type == 'pulse':
            if self.pulse and self.timestamps:
                pulse_np = np.array(self.pulse)
                self.pulse_plot.setData(relative_timestamps, pulse_np)

        elif self.current_chart_type == 'resp':
            if self.resp and self.timestamps:
                resp_np = np.array(self.resp)
                self.resp_plot.setData(relative_timestamps[:len(resp_np)], resp_np)

        elif self.current_chart_type == 'accel':
            if self.accel_x and self.timestamps:
                accel_x_np = np.array(self.accel_x)
                accel_y_np = np.array(self.accel_y)
                accel_z_np = np.array(self.accel_z)
                self.accel_x_plot.setData(relative_timestamps[:len(accel_x_np)], accel_x_np)
                self.accel_y_plot.setData(relative_timestamps[:len(accel_y_np)], accel_y_np)
                self.accel_z_plot.setData(relative_timestamps[:len(accel_z_np)], accel_z_np)

        elif self.current_chart_type == 'gyro':
            if self.gyro_x and self.timestamps:
                gyro_x_np = np.array(self.gyro_x)
                gyro_y_np = np.array(self.gyro_y)
                gyro_z_np = np.array(self.gyro_z)
                self.gyro_x_plot.setData(relative_timestamps[:len(gyro_x_np)], gyro_x_np)
                self.gyro_y_plot.setData(relative_timestamps[:len(gyro_y_np)], gyro_y_np)
                self.gyro_z_plot.setData(relative_timestamps[:len(gyro_z_np)], gyro_z_np)

        elif self.current_chart_type == 'temp':
            if self.obj_temp and self.timestamps:
                obj_temp_np = np.array(self.obj_temp)
                amb_temp_np = np.array(self.amb_temp)
                self.obj_temp_plot.setData(relative_timestamps[:len(obj_temp_np)], obj_temp_np)
                self.amb_temp_plot.setData(relative_timestamps[:len(amb_temp_np)], amb_temp_np)

    def create_navbar(self):
        navbar_widget = QWidget()
        navbar_layout = QHBoxLayout(navbar_widget)
        navbar_layout.setSpacing(30)
        navbar_layout.setContentsMargins(0, 0, 0, 0) #important

        # Left Buttons
        left_buttons = QWidget()
        left_layout = QHBoxLayout(left_buttons)

        home_button = QPushButton("Home")
        home_button.setObjectName("navButton")
        home_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.home_page))
        left_layout.addWidget(home_button)


        # Logo
        self.logo_label = QLabel()
        pixmap = QPixmap("assets/lunarlogo.png")
        pixmap = pixmap.scaled(250, 80, Qt.KeepAspectRatio)
        self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignCenter)

        # Right Buttons
        right_buttons = QWidget()
        right_layout = QHBoxLayout(right_buttons)

        data_button = QPushButton("Data")
        data_button.setObjectName("navButton")
        data_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.data_page))
        right_layout.addWidget(data_button)

        # Add widgets to navbar layout with appropriate stretch factors
        navbar_layout.addWidget(left_buttons)
        navbar_layout.addStretch()  # Center the logo with stretch
        navbar_layout.addWidget(self.logo_label)
        navbar_layout.addStretch()  # Center the logo with stretch
        navbar_layout.addWidget(right_buttons)

        navbar = QToolBar()
        navbar.setMovable(False)
        navbar.addWidget(navbar_widget)
        self.addToolBar(navbar)

    def closeEvent(self, event):
        self.worker.stop()
        self.update_timer.stop()
        event.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.intro_page = IntroPage()
        self.stack.addWidget(self.intro_page)

        self.intro_page.profile_submitted.connect(self.start_monitoring)

        self.setWindowTitle("Astronaut Health Monitor")
        self.setGeometry(100, 100, 1024, 768)

    def start_monitoring(self, name, gender, age):
        self.monitoring_page = AstronautMonitor(name, gender, age)
        self.stack.addWidget(self.monitoring_page)
        self.stack.setCurrentWidget(self.monitoring_page)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file:
        app.setStyleSheet(file.read())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())