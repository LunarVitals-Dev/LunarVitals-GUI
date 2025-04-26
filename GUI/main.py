from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QToolBar,
    QHBoxLayout, QPushButton, QComboBox, QStackedWidget, QGridLayout, QFrame,
    QFormLayout, QLineEdit, QMessageBox
)

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QPixmap, QFont, QIntValidator
import time
from dotenv import load_dotenv
import pyqtgraph as pg
from pyqtgraph import mkPen
from collections import deque
from pymongo import MongoClient
import sys
import os
import numpy as np
import logging
import joblib
from bluetooth import NordicBLEWorker

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import tensorflow as tf

# Load the trained model and preprocessing objects
class MLManager(QObject):
    # Define a signal that emits three objects (model, scaler, encoder)
    artifacts_ready = Signal(object, object, object)

    def load_artifacts(self):
        try:
            # Load your trained model and preprocessing objects
            model = tf.keras.models.load_model("activity_model_mongodb.keras")
            scaler = joblib.load("feature_scaler_mongodb.joblib")
            encoder = joblib.load("activity_encoder_mongodb.joblib")
            # print("Loaded trained model and preprocessing objects.")
            # Emit the loaded artifacts
            self.artifacts_ready.emit(model, scaler, encoder)
        except Exception as e:
            print("Error loading trained artifacts:", e)

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
        self.name_input.setText("Peak") # need to comment out
        form_layout.addRow(QLabel("Name:"), self.name_input)

        # Gender selection
        self.gender_combo = QComboBox()
        self.gender_combo.setObjectName("introForm") 
        self.gender_combo.addItems(["Male", "Female", "Other"])
        self.gender_combo.setCurrentText("Male") # need to comment out
        form_layout.addRow(QLabel("Gender:"), self.gender_combo)

        # Age input
        self.age_input = QLineEdit()
        self.age_input.setObjectName("introForm") 
        self.age_input.setPlaceholderText("Enter astronaut's age")
        self.age_input.setValidator(QIntValidator(self)) 
        self.age_input.setMaxLength(2) 
        self.age_input.setText("21") # need to comment out
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

class AstronautMonitor(QMainWindow):
    NORDIC_DEVICE_MAC = "DF:9E:5B:95:6A:D9" 
    # NORDIC_DEVICE_MAC = "C0:0F:DD:31:AC:91" #Main prototype
    GATT_UUID = "00002A3D-0000-1000-8000-00805F9B34FB"


    def __init__(self, name, gender, age):
        super().__init__()
        
        self.astronaut_name = name
        self.astronaut_gender = gender
        self.astronaut_age = age
        
        self.model = None
        self.scaler = None
        self.encoder = None
        
        self.current_activity = "No Activity"
        
        load_dotenv()
        
        MONGODB_URI = os.getenv("MONGODB_URI")
        # print(f"MONGODB_URI: {MONGODB_URI}")

        try:
            self.client = MongoClient(MONGODB_URI)
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
        
        self.setup_ble_worker()
        
        # Create and use an instance of MLManager to load the artifacts.
        self.ml_manager = MLManager()
        self.ml_manager.artifacts_ready.connect(self.on_artifacts_ready)
        self.ml_manager.load_artifacts()

        self.initUI()

        self.mongo_buffer = []
        
        self.last_prediction = 0.0

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.flush_mongo_buffer)
        self.update_timer.timeout.connect(self.update_home_page)
        self.update_timer.timeout.connect(self.update_current_chart)
        self.update_timer.start(1000)

        self.current_chart_type = None

        # print(f"Astronaut Profile - Name: {self.astronaut_name}, Gender: {self.astronaut_gender}, Age: {self.astronaut_age}")
    
    def on_artifacts_ready(self, model, scaler, encoder):
        # This slot is called when the MLManager has loaded your artifacts.
        self.model = model
        self.scaler = scaler
        self.encoder = encoder
        # print("ML artifacts are ready for use in predictions.")
         
    def setup_ble_worker(self):
        # Instantiate the BLE worker with your device's MAC address and the RX characteristic UUID.
        self.ble_worker = NordicBLEWorker(self.NORDIC_DEVICE_MAC, self.GATT_UUID)
        # Connect the data_received signal from BLE worker to your BLE data handler.
        self.ble_worker.data_received.connect(self.handle_ble_data)
        self.ble_worker.start()

    def init_data_buffers(self):
        self.maxlen = 100
        self.pulse = deque(maxlen=self.maxlen)
        self.resp = deque(maxlen=self.maxlen)
        self.accel_x = deque(maxlen=self.maxlen)
        self.accel_y = deque(maxlen=self.maxlen)
        self.accel_z = deque(maxlen=self.maxlen)
        self.step_rate = deque(maxlen=self.maxlen)
        self.gyro_x = deque(maxlen=self.maxlen)
        self.gyro_y = deque(maxlen=self.maxlen)
        self.gyro_z = deque(maxlen=self.maxlen)
        self.rotate_rate = deque(maxlen=self.maxlen)
        self.obj_temp = deque(maxlen=self.maxlen)
        self.amb_temp = deque(maxlen=self.maxlen)
        self.pressure = deque(maxlen=self.maxlen)
        self.timestamps = deque(maxlen=self.maxlen)

    def send_to_mongo(self, sensor_data):
        # add the astronaut info
        sensor_data['astronaut_name']   = self.astronaut_name
        sensor_data['astronaut_gender'] = self.astronaut_gender
        sensor_data['astronaut_age']    = self.astronaut_age
        sensor_data['timestamp'] = time.time()
        sensor_data['activity_id'] = self.current_activity
        self.mongo_buffer.append(sensor_data)
        #print(f"Data added to buffer: {sensor_data}")
        
    def flush_mongo_buffer(self):
        if self.mongo_buffer:
            try:
                self.collection.insert_many(self.mongo_buffer)
                self.mongo_buffer = []
            except Exception as e:
                logging.error(f"Error inserting into MongoDB: {e}")
                
    def update_blood_oxygen(self, SPO2: float):
        if SPO2 > 95:
            status = "Normal"
        elif SPO2 > 90:
            status = "Concerning"
        elif SPO2 > 85:
            status = "Low"
        elif SPO2 == 0:
            status = "Not Detected"
        else:
            status = "Critical"

        self.blood_oxygen_label.setText(f"Blood Oxygen: {status}")
                
    def update_prediction_display(self, prediction):
        """Update the UI with the predicted activity."""
        # Console log
        print(f"Predicted Activity: {prediction}")
        # Update the on‐screen label
        self.activity_label.setText(f"Current Activity: {prediction}")
        
    def on_new_sensor_data(self):
        now = time.time()

        if self.pulse and self.resp and self.obj_temp and self.step_rate and self.rotate_rate and (now - self.last_prediction) >= 10:
            self.last_prediction = now

            # compute the 10‑s averages
            avg_bpm  = np.mean(self.pulse)
            avg_brpm = np.mean(self.resp)
            body_temp = np.mean(self.obj_temp)
            step_rate = np.mean(self.step_rate)
            rotate_rate = np.mean(self.rotate_rate)

            # scale, predict, decode
            X_new    = np.array([[avg_bpm, avg_brpm, body_temp, step_rate, rotate_rate]])
            X_scaled = self.scaler.transform(X_new)
            probs    = self.model.predict(X_scaled)
            idx      = np.argmax(probs, axis=1)[0]
            label    = self.encoder.categories_[0][idx]

            # update the UI
            self.update_prediction_display(label)

    def handle_ble_data(self, data):
        try:
            # merge list → dict as you already do…
            if isinstance(data, list):
                merged_data = {}
                for sensor_obj in data:
                    merged_data.update(sensor_obj)
                data = merged_data

            # write to Mongo, etc.
            self.send_to_mongo(data)

            # initialize once
            if not hasattr(self, 'latest_data'):
                self.latest_data = {}

            # update just the keys you got this time
            self.latest_data.update(data)
            
            # print(data)

            # Process each sensor's data.
            for sensor_name, sensor_data in data.items():
                if isinstance(sensor_data, dict):
                    if sensor_name == "PulseSensor" and "Value_mV" in sensor_data:
                        value = sensor_data["Value_mV"]
                        self.pulse.append(value)
                        self.timestamps.append(time.time())
                    elif sensor_name == "RespiratoryRate" and "avg_mV" in sensor_data:
                        value = sensor_data["avg_mV"]
                        self.resp.append(value)
                    elif sensor_name == "Accel":
                        x = sensor_data.get("X_g", 0)
                        y = sensor_data.get("Y_g", 0)
                        z = sensor_data.get("Z_g", 0)
                        step = sensor_data.get("step_rate", 0)
                        self.accel_x.append(x)
                        self.accel_y.append(y)
                        self.accel_z.append(z)
                        self.step_rate.append(step)
                    elif sensor_name == "Gyro":
                        x = sensor_data.get("X_deg", 0)
                        y = sensor_data.get("Y_deg", 0)
                        z = sensor_data.get("Z_deg", 0)
                        rotate = sensor_data.get("rotation_rate", 0)
                        self.gyro_x.append(x)
                        self.gyro_y.append(y)
                        self.gyro_z.append(z)
                        self.rotate_rate.append(rotate)
                    elif sensor_name == "ObjectTemp" and "Celsius" in sensor_data:
                        value = sensor_data["Celsius"]
                        self.obj_temp.append(value)
                    elif sensor_name == "AmbientTemp" and "Celsius" in sensor_data:
                        value = sensor_data["Celsius"]
                        self.amb_temp.append(value)
                    elif sensor_name == "Pressure" and "hPa" in sensor_data:
                        value = sensor_data["hPa"]
                        self.pressure.append(value)
                    elif sensor_name == "SPO2_Sensor" and "SPO2" in sensor_data:
                        value = sensor_data["SPO2"]
                        self.update_blood_oxygen(value)

                self.on_new_sensor_data()

        except Exception as e:
            logging.error(f"Error processing BLE data: {e}")

    def initUI(self):
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)
        
        self.home_page = QWidget()
        self.data_page = QWidget()  
        self.about_page = QWidget()
        
        self.init_home_page()
        self.init_data_page() 
        self.init_about_page()
        
        self.central_stack.addWidget(self.home_page)
        self.central_stack.addWidget(self.data_page)
        self.central_stack.addWidget(self.about_page)  
        self.create_navbar()
        
    def switch_to_chart(self, chart_type):
        # Switch to the data page (assuming self.central_stack is your QStackedWidget)
        self.central_stack.setCurrentWidget(self.data_page)
        # Update the chart in the data page with the selected sensor type
        self.update_chart(chart_type)
        
    def create_sensor_box(self, sensor_name, config):
        # Create a container for the sensor box.
        sensor_box = QFrame()
        sensor_box.setObjectName("sensorBox")
        sensor_box.setProperty("class", "sensor-box")

        box_layout = QVBoxLayout()
        
        title_button = QPushButton(config['display_name'])
        title_button.setProperty("class", "sensor-title-button")
        
        # Get the chart type (if any) for routing.
        chart_type = self.sensor_to_chart_type.get(sensor_name)
        if chart_type:
            # Use a helper to capture chart_type for this sensor.
            def make_callback(chart_type_value):
                return lambda checked: self.switch_to_chart(chart_type_value)
            title_button.clicked.connect(make_callback(chart_type))
        box_layout.addWidget(title_button)
        
        # Create measurement label(s). For Blood Oxygen, it will be the only widget.
        self.data_labels[sensor_name] = {}
        for key, display_name in config['measurements'].items():
            value_label = QLabel(f"{display_name}: N/A")
            value_label.setProperty("class", "sensor-value")
            self.data_labels[sensor_name][key] = value_label
            box_layout.addWidget(value_label)

        sensor_box.setLayout(box_layout)
        return sensor_box
        
    def init_home_page(self):
        layout = QGridLayout()
        
        # Header title
        header_label = QLabel(f"Astronaut {self.astronaut_name}'s Dashboard")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label, 0, 0, 1, 3)  # Title spans 3 columns at the top

        self.data_labels = {}

        # Sensor display configuration
        self.sensor_config = {
            "PulseSensor": {
                "display_name": "Heart Rate Monitor",
                "measurements": {"pulse_BPM": "Heart Rate (BPM)"},
                "grid_position": (1, 0)  
            },
            "RespiratoryRate": {
                "display_name": "Breathing Rate Monitor",
                "measurements": {"BRPM": "Breathing Rate (breaths/min)"},
                "grid_position": (2, 0)
            },
            "ObjectTemp": {
                "display_name": "Body Temperature",
                "measurements": {"Celsius": "Temperature (°C)"},
                "grid_position": (3, 0)  
            },
            "Accel": {
                "display_name": "Rate Of Steps",
                "measurements": {"step_rate": "Step Rate (steps/min)"},
                "grid_position": (1, 2)
            },
            "Gyro": {
                "display_name": "Rate of Arm Swings",
                "measurements": {"rotation_rate": "Rotation Rate (steps/min)"},
                "grid_position": (2, 2)
            },
            "Pressure": {
                "display_name": "Atmospheric Pressure",
                "measurements": {"hPa": "Pressure (hPa)"},
                "grid_position": (3, 2)
            },
        }
        
        # Maps sensor_name to chart type string for update_chart
        self.sensor_to_chart_type = {
            "PulseSensor": "pulse",
            "RespiratoryRate": "resp",
            "Accel": "accel",
            "Gyro": "gyro",
            "ObjectTemp": "temp",
            "Pressure": "pressure", 
        }

        # Create sensor boxes using the helper function
        for sensor_name, config in self.sensor_config.items():
            sensor_box = self.create_sensor_box(sensor_name, config)
            row, col = config['grid_position']
            layout.addWidget(sensor_box, row, col)

        # Create astronaut image
        center_image = QLabel()
        center_image.setObjectName("centerImage")
        center_image.setFixedSize(300, 510)
        center_image.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap('assets/spaceman.png')
        scaled = pixmap.scaled(
            225, 370,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        center_image.setPixmap(scaled)
        
        layout.addWidget(center_image, 1, 1, 3, 1, Qt.AlignCenter)

        self.activity_label = QLabel("Current Activity: N/A")
        self.activity_label.setObjectName("activityLabel")
        self.activity_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.activity_label, 1, 1)
        
        self.blood_oxygen_label = QLabel("Blood Oxygen: N/A")
        self.blood_oxygen_label.setObjectName("bloodOxygenLabel")
        self.blood_oxygen_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.blood_oxygen_label, 3, 1)

        self.home_page.setLayout(layout)


    def update_home_page(self):
        # print(">>> latest_data keys:", list(self.latest_data.keys()))
        if not hasattr(self, 'latest_data'):
            return

        for sensor_name, sensor_data in self.latest_data.items():
            # skip anything that isn’t a dict or we don’t have labels for
            if sensor_name not in self.data_labels or not isinstance(sensor_data, dict):
                continue

            # only loop over the keys that actually exist in self.data_labels
            for key, label in self.data_labels[sensor_name].items():
                if key in sensor_data:
                    disp = self.sensor_config[sensor_name]['measurements'][key]
                    label.setText(f"{disp}: {sensor_data[key]}") 

    def set_current_activity(self, activity):
        # Uncheck all buttons
        for button in self.activity_buttons.values():
            button.setChecked(False)

        # Check the selected button
        self.activity_buttons[activity].setChecked(True)

        # Set the current activity
        self.current_activity = activity
        #print(f"Current activity set to: {self.current_activity}")


    def init_data_page(self):
        layout = QVBoxLayout()
        activity_layout = QHBoxLayout()
        
        ACTIVITIES = ["No Activity", "Running", "Walking", "Hiking", "Cranking", "Lifting"]

        # Create individual buttons for each activity
        self.activity_buttons = {}
        for activity in ACTIVITIES:
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
        self.pres_button = QPushButton("Pressure")
        buttons_layout.addWidget(self.pulse_button)
        buttons_layout.addWidget(self.resp_button)
        buttons_layout.addWidget(self.accel_button)
        buttons_layout.addWidget(self.gyro_button)
        buttons_layout.addWidget(self.temp_button)
        buttons_layout.addWidget(self.pres_button)

        self.pulse_button.clicked.connect(lambda: self.update_chart('pulse'))
        self.resp_button.clicked.connect(lambda: self.update_chart('resp'))
        self.accel_button.clicked.connect(lambda: self.update_chart('accel'))
        self.gyro_button.clicked.connect(lambda: self.update_chart('gyro'))
        self.temp_button.clicked.connect(lambda: self.update_chart('temp'))
        self.pres_button.clicked.connect(lambda: self.update_chart('pressure'))
        layout.addWidget(buttons_widget)

        self.chart_widget = pg.PlotWidget()
        self.setup_chart(self.chart_widget, "Sensor Data")
        layout.addWidget(self.chart_widget)
        self.data_page.setLayout(layout)
        
    # about page that explains the project and our mission
    def init_about_page(self):
        layout = QVBoxLayout()
        about_label = QLabel("About the Project")
        about_label.setObjectName("aboutTitle")
        about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(about_label)

        about_text = QLabel("Lunar extravehicular activities (EVAs) are long missions that require astronauts to perform various tasks under extreme conditions with limited consumables. To combat the safety risk of over-depleting critical resources, we created a wearable biomonitoring system that measures, analyzes, and predicts physiological signals: including heart rate, respiration rate, body temperature, and step count. These signals are collected by a suite of sensors, which collects the data, filters it, and transmits it via Bluetooth to a database, where it is displayed here. Our solution aims to improve mission safety and efficiency and serve as a foundation for support in human space exploration.")
        about_text.setObjectName("aboutText")
        about_text.setWordWrap(True)  # Enable word wrapping
        layout.addWidget(about_text)

        self.about_page = QWidget()
        self.about_page.setLayout(layout)
        self.about_page.setObjectName("aboutPage")

    def setup_chart(self, chart_widget, title):
        # white background, black text
        plot_item = chart_widget.getPlotItem()
        chart_widget.setBackground('w')
        plot_item.setTitle(title, **{
            'size': self.chart_style['title_size'],
            'color': self.chart_style['title_color']
        })
        plot_item.showGrid(x=True, y=True, alpha=0.3)

        # axis styling
        for axis in (plot_item.getAxis('bottom'), plot_item.getAxis('left')):
            axis.setPen(self.chart_style['axis_color'])
            axis.setTextPen(self.chart_style['axis_color'])
            axis.setStyle(tickFont=QFont('Arial', 12))

        # add a legend in the top‐right corner
        self.legend = plot_item.addLegend(offset=(10,10))
        return chart_widget

    def update_chart(self, sensor_type):
        self.current_chart_type = sensor_type
        self.chart_widget.setObjectName("chartWidget")
        self.chart_widget.clear()

        # Determine title, axis labels, legend names, pens & symbols
        if sensor_type == 'pulse':
            title, left, units = "Heart Rate", "Value", "mV"
            names  = ['Heart Rate']
            pens   = [mkPen(color=(255,  0,   0), width=2)]  # red
            symbols= [None]
        elif sensor_type == 'resp':
            title, left, units = "Breathing Rate", "Value", "mV"
            names  = ['Breathing Rate']
            pens   = [mkPen(color=(255,  0,   0), width=2)]  # red
            symbols= [None]
        elif sensor_type == 'accel':
            title, left, units = "Accelerometer Data", "Acceleration", "g"
            names  = ['X-axis','Y-axis','Z-axis']
            pens   = [
                mkPen(color=(255,   0,   0), width=2),  # red
                mkPen(color=(  0, 255,   0), width=2),  # green
                mkPen(color=(  0,   0, 255), width=2)   # blue
            ]
            symbols= [None, None, None]
        elif sensor_type == 'gyro':
            title, left, units = "Gyroscope Data", "Angular Velocity", "deg/s"
            names  = ['X-Gyro','Y-Gyro','Z-Gyro']
            pens   = [
                mkPen(color=(255,   0,   0), width=2),  # red
                mkPen(color=(  0, 255,   0), width=2),  # green
                mkPen(color=(  0,   0, 255), width=2)   # blue
            ]
            symbols= [None, None, None]
        elif sensor_type == 'temp':
            title, left, units = "Temperature Data", "Temperature", "°C"
            names  = ['Object Temp','Ambient Temp']
            pens   = [
                mkPen(color=(255,   0,   0), width=2),  # red
                mkPen(color=(  0, 255,   0), width=2),  # green
            ]
            symbols= [None, None]
        elif sensor_type == 'pressure':
            title, left, units = "Pressure Data", "Pressure", "hPa"
            names  = ['Pressure']
            pens   = [
                mkPen(color=(255,   0,   0), width=2),  # red
            ]
            symbols= [None]
        else:
            return  # unknown type

        # (re)apply styling + legend
        self.setup_chart(self.chart_widget, title)
        plot_item = self.chart_widget.getPlotItem()
        plot_item.setLabel('bottom', 'Time', units='s')
        plot_item.setLabel('left',   left,   units=units)

        # create each curve, registering it in the legend
        plots = []
        for name, pen, symbol in zip(names, pens, symbols):
            if symbol:
                p = self.chart_widget.plot(pen=pen, name=name,
                                        symbol=symbol, symbolSize=5)
            else:
                p = self.chart_widget.plot(pen=pen, name=name)
            plots.append(p)

        # assign back to instance vars so update_current_chart can find them
        if sensor_type == 'pulse':
            self.pulse_plot = plots[0]
        elif sensor_type == 'resp':
            self.resp_plot = plots[0]
        elif sensor_type == 'accel':
            self.accel_x_plot, self.accel_y_plot, self.accel_z_plot = plots
        elif sensor_type == 'gyro':
            self.gyro_x_plot, self.gyro_y_plot, self.gyro_z_plot = plots
        elif sensor_type == 'temp':
            self.obj_temp_plot, self.amb_temp_plot = plots
        elif sensor_type == 'pressure':
            self.pressure_plot = plots[0]

        # finally draw the data
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
                
        elif self.current_chart_type == 'pressure':
            if self.pressure and self.timestamps:
                pressure_np = np.array(self.pressure)
                self.pressure_plot.setData(relative_timestamps[:len(pressure_np)], pressure_np)
                
    def refresh_monitoring_page(self):
        """Refresh the monitoring page by resetting the Bluetooth connection."""
        logging.info("Resetting Bluetooth connection...")
        if self.ble_worker and self.ble_worker.isRunning():
            # Stop the running worker gracefully.
            self.ble_worker.stop()
            self.ble_worker.wait()  # Ensure the thread fully terminates.
        # Create a new worker instance.
        self.ble_worker = NordicBLEWorker(self.NORDIC_DEVICE_MAC, self.GATT_UUID)
        self.ble_worker.data_received.connect(self.handle_ble_data)
        self.ble_worker.start()

        # Optionally, clear the chart and reset buffers
        self.init_data_buffers()
        self.current_chart_type = None
        self.chart_widget.clear()

        logging.info("Monitoring page refreshed.")

    def create_navbar(self):
        navbar_widget = QWidget()
        navbar_layout = QHBoxLayout(navbar_widget)
        navbar_layout.setSpacing(40)
        navbar_layout.setContentsMargins(0, 0, 0, 0) 
        
        self.logo_label = QLabel()
        pixmap = QPixmap("assets/lunarlogo.png")
        pixmap = pixmap.scaled(250, 90, Qt.KeepAspectRatio)
        self.logo_label.setPixmap(pixmap)

        right_buttons = QWidget()
        right_layout = QHBoxLayout(right_buttons)

        home_button = QPushButton("Home")
        home_button.setObjectName("navButton")
        home_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.home_page))
        right_layout.addWidget(home_button)
        
        data_button = QPushButton("Sensors")
        data_button.setObjectName("navButton")
        data_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.data_page))
        right_layout.addWidget(data_button)

        about_button = QPushButton("About")
        about_button.setObjectName("navButton")
        about_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.about_page))
        right_layout.addWidget(about_button)
   
        connect_button = QPushButton("Connect")
        connect_button.setObjectName("navButton")
        connect_button.clicked.connect(self.refresh_monitoring_page)  
        right_layout.addWidget(connect_button)
    
        navbar_layout.addWidget(self.logo_label)
        navbar_layout.addStretch() 
        navbar_layout.addWidget(right_buttons)

        navbar = QToolBar()
        navbar.setMovable(False)
        navbar.addWidget(navbar_widget)
        self.addToolBar(navbar)

    def closeEvent(self, event):
        self.ble_worker.stop()
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
        
        self.resize(1280, 800)

    def start_monitoring(self, name, gender, age):
        self.monitoring_page = AstronautMonitor(name, gender, age)
        self.stack.addWidget(self.monitoring_page)
        self.stack.setCurrentWidget(self.monitoring_page)
        
        self.resize(1280, 800)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file:
        app.setStyleSheet(file.read())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())