from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QToolBar,
    QHBoxLayout, QPushButton, QComboBox, QStackedWidget, QGridLayout, QFrame,
    QFormLayout, QLineEdit
)
from PySide6.QtGui import QFontDatabase, QFont 
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QPixmap, QFont, QIntValidator
import time
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
from PySide6.QtWidgets import QLabel, QComboBox, QTextEdit, QFrame

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
            print("Loaded trained model and preprocessing objects.")
            # Emit the loaded artifacts
            self.artifacts_ready.emit(model, scaler, encoder)
        except Exception as e:
            print("Error loading trained artifacts:", e)

class IntroPage(QWidget):
    profile_submitted = Signal(str, str, int, int)

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
        
        # Weight input
        self.weight_input = QLineEdit()
        self.weight_input.setObjectName("introForm") 
        self.weight_input.setPlaceholderText("Enter astronaut's weight")
        self.weight_input.setValidator(QIntValidator(self)) 
        self.weight_input.setMaxLength(3) 
        self.weight_input.setText("140") # need to comment out
        form_layout.addRow(QLabel("Weight:"), self.weight_input)

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
        weight_text = self.weight_input.text().strip()

        age = int(age_text)
        weight = int(weight_text)

        self.profile_submitted.emit(name, gender, age, weight)


class AstronautMonitor(QMainWindow):
    #NORDIC_DEVICE_MAC = "DD:81:76:1A:A4:6A"
    NORDIC_DEVICE_MAC = "C0:0F:DD:31:AC:91" #Main prototype
    GATT_UUID = "00002A3D-0000-1000-8000-00805F9B34FB"


    def __init__(self, name, gender, age, weight):
        super().__init__()
        
        self.peak_lines = []
        self.astronaut_name = name
        self.astronaut_gender = gender
        self.astronaut_age = age
        self.astronaut_weight = weight
        
        self.model = None
        self.scaler = None
        self.encoder = None
        
        self.current_activity = "Idle"

        MONGODB_URI = "mongodb+srv://LunarVitals:lunarvitals1010@peakfitness.i5blp.mongodb.net/"

        try:
            self.client = MongoClient(MONGODB_URI)
            self.db = self.client["LunarVitalsDB"]
            self.collection = self.db["sensor_data"]
        except Exception as e:
            logging.error(f"Error connecting to MongoDB: {e}")
            sys.exit(1)

        self.chart_style = {
            'background': '#c8dae3',
            'title_size': '22px',
            'title_color': '#062a61',
            'axis_color': '#062a61',
        }

        self.init_data_buffers()
        
        self.setup_ble_worker()
        
        # Create and use an instance of MLManager to load the artifacts.
        self.ml_manager = MLManager()
        self.ml_manager.artifacts_ready.connect(self.on_artifacts_ready)
        self.ml_manager.load_artifacts()

        self.initUI()
        self.mongo_upload_enabled = False
        self.mongo_buffer = []
        
        self.last_prediction = 0.0

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.flush_mongo_buffer)
        self.update_timer.timeout.connect(self.update_home_page)
        self.update_timer.timeout.connect(self.update_current_chart)
        self.update_timer.timeout.connect(self.update_data_collection_page)
        # Update the page to reflect the new data
     
        self.update_timer.start(1000)
        
        self.prediction_timer = QTimer(self)
        self.prediction_timer.timeout.connect(self.on_new_sensor_data)
        self.prediction_timer.start(10000) 

        self.current_chart_type = None

        # print(f"Astronaut Profile - Name: {self.astronaut_name}, Gender: {self.astronaut_gender}, Age: {self.astronaut_age}")
    
    def on_artifacts_ready(self, model, scaler, encoder):
        # This slot is called when the MLManager has loaded your artifacts.
        self.model = model
        self.scaler = scaler
        self.encoder = encoder
        self.model_status_label.setText("Model Loaded: True")
        # print("ML artifacts are ready for use in predictions.")
         
    def setup_ble_worker(self):
        # Instantiate the BLE worker with your device's MAC address and the RX characteristic UUID.
        self.ble_worker = NordicBLEWorker(self.NORDIC_DEVICE_MAC, self.GATT_UUID)
        # Connect the data_received signal from BLE worker to your BLE data handler.
        self.ble_worker.data_received.connect(self.handle_ble_data)
        self.ble_worker.start()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(lambda: self.update_connection_status(self.ble_worker.is_connected()))
        self.status_timer.start(1000) 

    def init_data_buffers(self):
        self.maxlen = 100
        self.pulse = deque(maxlen=self.maxlen)
        self.resp = deque(maxlen=self.maxlen)
        self.accel_x = deque(maxlen=self.maxlen)
        self.accel_y = deque(maxlen=self.maxlen)
        self.accel_z = deque(maxlen=self.maxlen)
        self.step_rate = deque(maxlen=10)
        self.gyro_x = deque(maxlen=self.maxlen)
        self.gyro_y = deque(maxlen=self.maxlen)
        self.gyro_z = deque(maxlen=self.maxlen)
        self.rotate_rate = deque(maxlen=10)
        self.obj_temp = deque(maxlen=self.maxlen)
        self.amb_temp = deque(maxlen=self.maxlen)
        self.pressure = deque(maxlen=self.maxlen)
        self.timestamps = deque(maxlen=self.maxlen)
        self.spo2_buffer = deque(maxlen=5)
        self.brpm = deque(maxlen=10)
        self.pulse_BPM = deque(maxlen=10)
        
    def flush_mongo_buffer(self):
                         # Log the content of the buffer before insertion
        preview = "\n".join([str(record) for record in self.mongo_buffer])
        self.mongo_output_area.append(f"{preview}\n")
        if not self.mongo_upload_enabled:
         
            self.mongo_buffer = []  # Clear it anyway to avoid memory buildup
            return

        if self.mongo_buffer:
            try:


                self.collection.insert_many(self.mongo_buffer)
                self.mongo_output_area.append(f"Inserted {len(self.mongo_buffer)} records successfully.\n")
                self.mongo_buffer = []
            except Exception as e:
                logging.error(f"Error inserting into MongoDB: {e}")
                self.mongo_output_area.append(f"Upload Error: {str(e)}")

                
    def update_blood_oxygen(self, SPO2):
        self.spo2_buffer.append(SPO2)
        SPO2 = np.median(self.spo2_buffer)
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

        self.blood_oxygen_label.setText(f"SpO2: {status}")

    
    def toggle_data_upload(self):
        self.mongo_upload_enabled = not self.mongo_upload_enabled
        if self.mongo_upload_enabled:
            self.upload_status.setText("Upload Status: <font color='green'>ON</font>")
            self.upload_toggle_button.setText("Stop Upload")
        else:
            self.upload_status.setText("Upload Status: <font color='red'>OFF</font>")
            self.upload_toggle_button.setText("Start Upload")

                
    def update_prediction_display(self, prediction, confidence=None):
        self.activity_label.setText(f"Current Activity: {prediction}")
        if confidence is not None:
            self.confidence_label.setText(f"Confidence: {confidence:.2%}")
        
    def on_new_sensor_data(self):

        # compute the 10‑s averages
        avg_bpm  = np.mean(self.pulse_BPM)
        avg_brpm = np.mean(self.brpm)
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
        
    VALID_RANGES = {
        "s_rate":    (0, 205),
        "r_rate":    (0, 210),
        "OCelsius":  (10.0, 45.0),
        "Value_mV":  (0, 3300),
        "pulse_BPM": (0, 220),
        "avg_mV":    (0, 3300),
        "BRPM":      (0, 60)
    }

    def clamp(self, field: str, val: float) -> float:
        """
        Clamp val into the valid range for this field, if defined;
        otherwise return val unchanged.
        """
        if field in self.VALID_RANGES:
            lo, hi = self.VALID_RANGES[field]
            if val < lo:
                return lo
            if val > hi:
                return hi
        return val

    def handle_ble_data(self, data):
        try:
            now_ts = time.time()

            for field, val in data.items():
                if field in self.VALID_RANGES:
                    data[field] = self.clamp(field, val)

            self.latest_data = getattr(self, "latest_data", {})
            self.latest_data.update(data)

            # — Accelerometer
            x, y, z = data["X_g"], data["Y_g"], data["Z_g"]
            s_rate  = self.clamp("s_rate", data["s_rate"])
            self.accel_x.append(x)
            self.accel_y.append(y)
            self.accel_z.append(z)
            self.step_rate.append(s_rate)

            # — Gyroscope
            gx, gy, gz = data["X_deg"], data["Y_deg"], data["Z_deg"]
            r_rate     = self.clamp("r_rate", data["r_rate"])
            self.gyro_x.append(gx)
            self.gyro_y.append(gy)
            self.gyro_z.append(gz)
            self.rotate_rate.append(r_rate)

            # — Temperatures
            ac = data["ACelsius"]
            oc = self.clamp("OCelsius", data["OCelsius"])
            self.amb_temp.append(ac)
            self.obj_temp.append(oc)

            # — Pressure
            self.pressure.append(data["hPa"])

            # — Pulse
            mv  = self.clamp("Value_mV",  data["Value_mV"])
            bpm = self.clamp("pulse_BPM", data["pulse_BPM"])
            self.pulse.append(mv)
            self.pulse_BPM.append(bpm)

            # — Respiration
            avg = self.clamp("avg_mV", data["avg_mV"])
            br  = self.clamp("BRPM",   data["BRPM"])
            self.resp.append(avg)
            self.brpm.append(br)
            self.timestamps.append(now_ts)
            
            # — Blood Oxygen
            spo2 = data["SPO2"]
            self.update_blood_oxygen(spo2)
            
            doc = {
                "timestamp":        now_ts,
                "astronaut_name":   self.astronaut_name,
                "astronaut_gender": self.astronaut_gender,
                "astronaut_age":    self.astronaut_age,
                "astronaut_weight": self.astronaut_weight,
                "activity_id":      self.current_activity,
            }
            # merge in the flat CSV data
            doc.update(data)
            self.mongo_buffer.append(doc)
            
            self.flush_mongo_buffer()

        except Exception as e:
            logging.error(f"Error processing BLE data: {e}")
            
    def initUI(self):
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)
        
        self.home_page = QWidget()
        self.data_page = QWidget()  
        self.about_page = QWidget()
        self.data_collection_page = QWidget()
        
        self.init_home_page()
        self.init_data_page() 
        self.init_about_page()
        self.init_data_collection_page()
        
        self.central_stack.addWidget(self.home_page)
        self.central_stack.addWidget(self.data_page)
        self.central_stack.addWidget(self.about_page)  
        self.central_stack.addWidget(self.data_collection_page)  
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
            "RespRate": {
                "display_name": "Breathing Rate Monitor",
                "measurements": {"BRPM": "Breathing Rate (breaths/min)"},
                "grid_position": (2, 0)
            },
            "ObjectTemp": {
                "display_name": "Body Temperature",
                "measurements": {"OCelsius": "Temperature (°C)"},
                "grid_position": (3, 0)  
            },
            "Accel": {
                "display_name": "Rate Of Steps",
                "measurements": {"s_rate": "Step Rate (steps/min)"},
                "grid_position": (1, 2)
            },
            "Gyro": {
                "display_name": "Rate of Arm Swings",
                "measurements": {"r_rate": "Rotation Rate (swings/min)"},
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
            "RespRate": "resp",
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
        center_image.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap('assets/spaceman.png')
        scaled = pixmap.scaled(
            400, 600,
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
        if not hasattr(self, 'latest_data'):
            return

        for sensor_name, config in self.sensor_config.items():
            for field, disp in config['measurements'].items():
                if field not in self.latest_data:
                    continue

                raw = self.latest_data[field]

                if isinstance(raw, float):
                    if raw.is_integer():
                        s = str(int(raw))
                    else:
                        s = f"{raw:.1f}"  
                else:
                    s = str(raw)

                label = self.data_labels[sensor_name][field]
                label.setText(f"{disp}: {s}")

    def update_data_collection_page(self):
        if not hasattr(self, 'latest_data'):
            return

        # Assuming the data structure is similar to the homepage (same keys)
        for field, label in self.mongo_data_labels.items():
            if field not in self.latest_data:
                label.setText("N/A")
                continue

            raw = self.latest_data[field]

            if isinstance(raw, float):
                if raw.is_integer():
                    raw = int(raw)
                else:
                    raw = f"{raw:.1f}"

            label.setText(f"{raw}")

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
        # activity_layout = QHBoxLayout()
        
        # ACTIVITIES = ["Idle", "Walking", "Skipping", "Lifting", "Crouching"]

        # # Create individual buttons for each activity
        # self.activity_buttons = {}
        # for activity in ACTIVITIES:
        #     button = QPushButton(activity)
        #     button.setCheckable(True)  # Make the button toggleable
        #     button.clicked.connect(lambda checked, act=activity: self.set_current_activity(act))
        #     self.activity_buttons[activity] = button
        #     activity_layout.addWidget(button)

        # # Create a widget to hold the activity layout
        # activity_widget = QWidget()
        # activity_widget.setLayout(activity_layout)

        # Create a horizontal layout to center the activity widget
        centered_layout = QHBoxLayout()
        centered_layout.addStretch()
        # centered_layout.addWidget(activity_widget)
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
        image_label = QLabel()
        pixmap = QPixmap("assets/group.png")
        image_label.setPixmap(pixmap.scaledToWidth(900, Qt.SmoothTransformation))
        image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(image_label)
        about_text = QLabel("Lunar extravehicular activities (EVAs) are long missions that require astronauts to perform various tasks under extreme conditions with limited consumables. To combat the safety risk of over-depleting critical resources, we created a wearable biomonitoring system that measures, analyzes, and predicts physiological signals: including heart rate, respiration rate, body temperature, and step count. These signals are collected by a suite of sensors, which collects the data, filters it, and transmits it via Bluetooth to a database, where it is displayed here. Our solution aims to improve mission safety and efficiency and serve as a foundation for support in human space exploration.")
        about_text.setObjectName("aboutText")
        about_text.setWordWrap(True)  # Enable word wrapping
        layout.addWidget(about_text)

        self.about_page = QWidget()
        self.about_page.setLayout(layout)
        self.about_page.setObjectName("aboutPage")

    def create_data_labels(self, right_section):
        # Example fields to show on the page
        data_fields = [
            "ACelsius", "BRPM", "Value_mV", "SPO2", "pulse_BPM", "r_rate", "s_rate"
        ]

        # Add a label for each field to right_section and store them in mongo_data_labels
        for field in data_fields:
            label = QLabel(f"{field}: N/A")
            self.mongo_data_labels[field] = label
            right_section.addWidget(label)

    def init_data_collection_page(self):
        

        main_layout = QHBoxLayout()

        # ---------------- Left: ML Predictions and Status ---------------- #
        left_section = QVBoxLayout()

        # ML Prediction Title
        left_section.addWidget(QLabel("<b>ML Prediction Status</b>"))

        # Current Activity Prediction
        self.activity_label = QLabel("Current Activity: Loading...")
        left_section.addWidget(self.activity_label)

        # Confidence Label
        self.confidence_label = QLabel("Confidence: N/A")
        left_section.addWidget(self.confidence_label)

        # Model Status
        self.model_status_label = QLabel("Model Loaded: False")
        left_section.addWidget(self.model_status_label)

        # Spacer
        left_section.addStretch()

        # ---------------- Right: Data Labeling & Uploading ---------------- #
        right_section = QVBoxLayout()

        # Label Title
        right_section.addWidget(QLabel("<b>Labeling & Upload Controls</b>"))

        # Label selection dropdown
        self.label_combo = QComboBox()
        self.label_combo.addItems(["Idle", "Walking", "Skipping", "Lifting", "Crouching"])
        self.label_combo.currentTextChanged.connect(lambda label: self.set_current_activity(label))
        right_section.addWidget(QLabel("Select Label:"))
        right_section.addWidget(self.label_combo)

        # Uploading status indicator
        self.upload_status = QLabel("Upload Status: <font color='red'>OFF</font>")
        right_section.addWidget(self.upload_status)

        # Start/Stop Upload Button
        self.upload_toggle_button = QPushButton("Start Upload")
        self.upload_toggle_button.setCheckable(True)
        self.upload_toggle_button.clicked.connect(self.toggle_data_upload)
        right_section.addWidget(self.upload_toggle_button)

        # MongoDB Output Preview
        right_section.addWidget(QLabel("Currently Collected Data:"))
        self.mongo_output_area = QTextEdit()
        self.mongo_output_area.setReadOnly(True)
        self.mongo_output_area.setFixedHeight(150)
        right_section.addWidget(self.mongo_output_area)

              # Data fields labels (e.g., temperature, pulse, etc.)
        self.mongo_data_labels = {}  # A dictionary to hold all your data-related labels
        self.create_data_labels(right_section)
        # Spacer
        #right_section.addStretch()

        # Add left and right section to main layout
        main_layout.addLayout(left_section)

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(divider)

        main_layout.addLayout(right_section)

        # Set layout to the page
        self.data_collection_page.setLayout(main_layout)
        self.update_data_collection_page() 

    def setup_chart(self, chart_widget, title):
        plot_item = chart_widget.getPlotItem()
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
        chart_widget.setBackground(self.chart_style['background'])
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
        self.chart_widget.setBackground(self.chart_style['background'])
  
        plot_item = self.chart_widget.getPlotItem()
        plot_item.setLabel('bottom', 'Time', units='s')
        plot_item.setLabel('left',   left,   units=units)

        # create each curve, registering it in the legend
        plots = []
        for name, pen, symbol in zip(names, pens, symbols):
            if symbol:
                p = self.chart_widget.plot(pen=pen, name=name, symbol=symbol, symbolSize=5)
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
        
        try:
            if self.current_chart_type == 'pulse':
                if self.pulse_plot and self.pulse:
                    pulse_np = np.array(self.pulse)
                    n = min(len(relative_timestamps), len(pulse_np))
                    self.pulse_plot.setData(relative_timestamps[:n], pulse_np[:n])
                else:
                    logging.warning("pulse_plot not initialized or no pulse data.")
            
            elif self.current_chart_type == 'resp':
                if self.resp and self.timestamps:
                    resp_np = np.array(self.resp)
                    self.resp_plot.setData(relative_timestamps[:len(resp_np)], resp_np)

            elif self.current_chart_type == 'accel':
                if all([self.accel_x_plot, self.accel_y_plot, self.accel_z_plot]) and self.accel_x:
                    ax, ay, az = map(np.array, (self.accel_x, self.accel_y, self.accel_z))
                    n = min(len(relative_timestamps), len(ax))
                    self.accel_x_plot.setData(relative_timestamps[:n], ax[:n])
                    self.accel_y_plot.setData(relative_timestamps[:n], ay[:n])
                    self.accel_z_plot.setData(relative_timestamps[:n], az[:n])

            elif self.current_chart_type == 'gyro':
                if all([self.gyro_x_plot, self.gyro_y_plot, self.gyro_z_plot]) and self.gyro_x:
                    gx, gy, gz = map(np.array, (self.gyro_x, self.gyro_y, self.gyro_z))
                    n = min(len(relative_timestamps), len(gx))
                    self.gyro_x_plot.setData(relative_timestamps[:n], gx[:n])
                    self.gyro_y_plot.setData(relative_timestamps[:n], gy[:n])
                    self.gyro_z_plot.setData(relative_timestamps[:n], gz[:n])

            elif self.current_chart_type == 'temp':
                if self.obj_temp_plot and self.amb_temp_plot and self.obj_temp:
                    obj_np = np.array(self.obj_temp)
                    amb_np = np.array(self.amb_temp)
                    n = min(len(relative_timestamps), len(obj_np))
                    self.obj_temp_plot.setData(relative_timestamps[:n], obj_np[:n])
                    self.amb_temp_plot.setData(relative_timestamps[:n], amb_np[:n])

            elif self.current_chart_type == 'pressure':
                if self.pressure_plot and self.pressure:
                    pressure_np = np.array(self.pressure)
                    n = min(len(relative_timestamps), len(pressure_np))
                    self.pressure_plot.setData(relative_timestamps[:n], pressure_np[:n])

        except Exception as e:
            logging.error(f"Error updating {self.current_chart_type} chart: {e}")

    def update_connection_status(self, connected: bool):
        if connected:
            self.status_label.setText("Status: Connected")
        else:
            self.status_label.setText("Status: Disconnected")
            
        # flip the dynamic property — Qt will re-style based on QSS rules
        self.status_label.setProperty("connected", connected)

        # force a re-polish so the style sheet is re-applied immediately
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def toggle_upload_to_mongo(self):
        if self.upload_toggle.isChecked():
            self.upload_toggle.setText("MongoDB: ON")
            self.mongo_upload_enabled = True
        else:
            self.upload_toggle.setText("MongoDB: OFF")
            self.mongo_upload_enabled = False

    def create_navbar(self):
        navbar_widget = QWidget()
        navbar_layout = QHBoxLayout(navbar_widget)
        navbar_layout.setSpacing(40)
        navbar_layout.setContentsMargins(0, 0, 0, 0) 
        
        self.logo_label = QLabel()
        pixmap = QPixmap("assets/lunarlogoLong.png")
        pixmap = pixmap.scaled(300, 100, Qt.KeepAspectRatio)
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

        
        data_collection_button = QPushButton("Data Collection")
        data_collection_button.setObjectName("navButton")
        data_collection_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.data_collection_page))
        right_layout.addWidget(data_collection_button)

        about_button = QPushButton("About")
        about_button.setObjectName("navButton")
        about_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.about_page))
        right_layout.addWidget(about_button)
    
        navbar_layout.addWidget(self.logo_label)
        navbar_layout.addStretch() 
        navbar_layout.addWidget(right_buttons)

        navbar = QToolBar()
        navbar.setMovable(False)
        navbar.addWidget(navbar_widget)
        self.addToolBar(navbar)

        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setObjectName("statusLabel")
        navbar_layout.addWidget(self.status_label)

        self.upload_toggle = QPushButton("MongoDB: OFF")
        self.upload_toggle.setCheckable(True)
        self.upload_toggle.setChecked(False)
        self.upload_toggle.setObjectName("navButton")
        self.upload_toggle.clicked.connect(self.toggle_upload_to_mongo)
        right_layout.addWidget(self.upload_toggle)


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
 

    def start_monitoring(self, name, gender, age, weight):
        self.monitoring_page = AstronautMonitor(name, gender, age, weight)
        self.stack.addWidget(self.monitoring_page)
        self.stack.setCurrentWidget(self.monitoring_page)
        

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.showNormal()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font_path = r"assets/Nasalization.otf"
    font_id = QFontDatabase.addApplicationFont(font_path)

    if font_id != -1:
        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        app.setFont(QFont(font_family))
    else:
      print("Failed to load font.")
    with open('stylesheet.qss', 'r') as file:
        app.setStyleSheet(file.read())
    
    window = MainWindow()
    window.showFullScreen()

    sys.exit(app.exec())