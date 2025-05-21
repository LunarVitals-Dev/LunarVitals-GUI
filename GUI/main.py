from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QToolBar,
    QHBoxLayout, QPushButton, QComboBox, QStackedWidget, QGridLayout, QFrame,
    QFormLayout, QLineEdit, QSizePolicy
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
import datetime
from bluetooth import NordicBLEWorker
from PySide6.QtWidgets import QLabel, QComboBox, QTextEdit, QFrame
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from data_collection_page import (
    init_data_collection_page,
    update_data_collection_page,
    create_data_labels,
    set_current_activity,
    set_current_activity_label,
    set_current_astronaut,
    ActivityTracker,
    ACTIVITY_LABELS
)

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
    # NORDIC_DEVICE_MAC = "DD:81:76:1A:A4:6A"
    NORDIC_DEVICE_MAC = "C0:0F:DD:31:AC:91" #Main prototype
    GATT_UUID = "00002A3D-0000-1000-8000-00805F9B34FB"


    def __init__(self, name, gender, age, weight):
        super().__init__()
        
        self.data_labels = {}
        self.astronaut_name = name
        self.astronaut_gender = gender
        self.astronaut_age = age
        self.astronaut_weight = weight
        self.model_status_label = False
        self.data_collection_page = QWidget()
        self.upload_start_time = None
        self.upload_label_counts = {} 
        # Bind external functions to self
        self.set_current_astronaut = set_current_astronaut.__get__(self)
        self.init_data_collection_page = init_data_collection_page.__get__(self)
        self.update_data_collection_page = update_data_collection_page.__get__(self)
        self.create_data_labels = create_data_labels.__get__(self)
        self.set_current_activity = set_current_activity.__get__(self)
        self.set_current_activity_label = set_current_activity_label.__get__(self)
        
        self.current_activity = "Idle"
       
        self.predicted_activity = ""
        
        self.activities = ACTIVITY_LABELS
        
        self.activity_tracker = ActivityTracker(self.activities)

        self.init_data_collection_page()
        self.model = None
        self.scaler = None
        self.encoder = None

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
        
        self.initUI()
        self.setup_ble_worker()
        
        # Create and use an instance of MLManager to load the artifacts.
        self.ml_manager = MLManager()
        self.ml_manager.artifacts_ready.connect(self.on_artifacts_ready)
        self.ml_manager.load_artifacts()

        self.mongo_upload_enabled = False
        self.mongo_buffer = []
        
        self.last_prediction = 0.0

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.flush_mongo_buffer)
        self.update_timer.timeout.connect(self.update_home_page)
        self.update_timer.timeout.connect(self.update_current_chart)
        self.update_timer.timeout.connect(self.update_data_collection_page)
        self.update_timer.timeout.connect(self.update_mission_length)
        self.update_timer.start(1000)
        
        self.prediction_timer = QTimer(self)
        self.prediction_timer.timeout.connect(self.on_new_sensor_data)
        self.prediction_timer.timeout.connect(self.updateActivityChart)
        self.prediction_timer.start(5000) 

        self.current_chart_type = None
    
    def on_artifacts_ready(self, model, scaler, encoder):
        # This slot is called when the MLManager has loaded your artifacts.
        self.model = model
        self.scaler = scaler
        self.encoder = encoder
        self.model_status_label = True
        print("ML artifacts are ready for use in predictions.")
         
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
        self.maxlen = 50
        self.pulse = deque(maxlen=self.maxlen)
        self.resp = deque(maxlen=self.maxlen)
        self.accel_x = deque(maxlen=self.maxlen)
        self.accel_y = deque(maxlen=self.maxlen)
        self.accel_z = deque(maxlen=self.maxlen)
        self.step_rate = deque(maxlen=5)
        self.gyro_x = deque(maxlen=self.maxlen)
        self.gyro_y = deque(maxlen=self.maxlen)
        self.gyro_z = deque(maxlen=self.maxlen)
        self.rotate_rate = deque(maxlen=5)
        self.obj_temp = deque(maxlen=self.maxlen)
        self.amb_temp = deque(maxlen=self.maxlen)
        self.pressure = deque(maxlen=self.maxlen)
        self.timestamps = deque(maxlen=self.maxlen)
        self.spo2_buffer = deque(maxlen=5)
        self.brpm = deque(maxlen=5)
        self.pulse_BPM = deque(maxlen=5)
        
    def flush_mongo_buffer(self):
        if not self.mongo_upload_enabled:
            self.mongo_buffer = []  
            return
        if self.mongo_buffer:
            try:
                self.collection.insert_many(self.mongo_buffer)
                #self.mongo_output_area.append(f"Inserted {len(self.mongo_buffer)} records successfully.\n")
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
            status = "Detecting"
        else:
            status = "Critical"

        self.blood_oxygen_label.setText(f"SPO2: {status}")
        # Set the dynamic property
        self.blood_oxygen_label.setProperty("status", status)
        self.blood_oxygen_label.setObjectName("bloodOxygenLabel")

        # Re-apply style so Qt notices the property change
        self.blood_oxygen_label.style().unpolish(self.blood_oxygen_label)
        self.blood_oxygen_label.style().polish(self.blood_oxygen_label)
        self.blood_oxygen_label.update()

                
    def update_prediction_display(self, prediction, confidence=None):
        print(f"Prediction: {prediction}")
        self.activity_label.setText(f"Current Activity: \n {prediction}")
        self.activity_label_data_collection.setText(f"Current Activity: {prediction}")
        if confidence is not None:
            self.confidence_label.setText(f"Confidence: {confidence:.2%}")
            self.confidence_label_data_collection.setText(f"Confidence: {confidence:.2%}")
        
    def on_new_sensor_data(self):
        if len(self.pulse_BPM) == 0:      
            return "No Data", 0

        avg_bpm    = np.mean(self.pulse_BPM)   if self.pulse_BPM    else 0
        avg_brpm   = np.mean(self.brpm)        if self.brpm         else 0
        body_temp  = np.mean(self.obj_temp)    if self.obj_temp     else 0.0
        step_rate  = np.mean(self.step_rate)   if self.step_rate    else 0
        rotate_rate= np.mean(self.rotate_rate) if self.rotate_rate  else 0

        # scale, predict, decode
        X_new    = np.array([[avg_bpm, avg_brpm, body_temp, step_rate, rotate_rate]])
        X_scaled = self.scaler.transform(X_new)
        probs    = self.model.predict(X_scaled)
        idx      = np.argmax(probs, axis=1)[0]
        label    = self.encoder.categories_[0][idx]
        confidence = float(probs[0, idx])
        
        self.predicted_activity = label

        # update the UI
        self.update_prediction_display(label, confidence) 
        
    VALID_RANGES = {
        "s_rate":    (0, 205),
        "r_rate":    (0, 210),
        "OCelsius":  (10.0, 45.0),
        "Value_mV":  (0, 3300),
        "pulse_BPM": (0, 180),
        "avg_mV":    (0, 3300),
        "BRPM":      (0, 45)
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

            self.mongo_output_area.append(f"{doc}\n")
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
        
    def update_mission_length(self):
        elapsed = datetime.datetime.now() - self.mission_start
        total_seconds = int(elapsed.total_seconds())
        hrs, rem = divmod(total_seconds, 3600)
        mins, secs = divmod(rem, 60)
        self.mission_length_label.setText(
            f"Mission Length: \n {hrs:02d}:{mins:02d}:{secs:02d}"
        )
        
    def updateActivityChart(self):
        leader = self.activity_tracker.update(self.predicted_activity)

        now = time.time()
        durations = []
        for act in self.activities:
            dur = self.activity_tracker._durations.get(act, 0.0)
            if act == self.activity_tracker._current and self.activity_tracker._t_start:
                dur += now - self.activity_tracker._t_start
            durations.append(dur)

        total = sum(durations)
        fractions = [(d / total if total else 0.0) for d in durations]
        
        self.activityAxes.set_autoscale_on(False)
        
        self.activityAxes.set_xlim(-0.5, len(self.activities) - 0.5)
        self.activityAxes.set_ylim(0, 1)
        
        x = np.arange(len(self.activities))
        self.activityAxes.bar(x, fractions, width=0.6)
        self.activityAxes.set_xticks(x)
        self.activityAxes.set_xticklabels(
            self.activities, rotation=45, ha="right", color="white", fontweight="bold"
        )
        self.activityAxes.set_ylim(0, 1)
        self.activityAxes.set_ylabel("Fraction of Time", color="white")
        self.activityAxes.set_title("Overall Activity", color="white", fontsize=16, fontweight="bold")
        for spine in self.activityAxes.spines.values():
            spine.set_color("white")
        self.activityAxes.tick_params(colors="white")
        self.activityCanvas.draw()

        
    def switch_to_chart(self, chart_type):
        # Switch to the data page (assuming self.central_stack is your QStackedWidget)
        self.central_stack.setCurrentWidget(self.data_page)
        # Update the chart in the data page with the selected sensor type
        self.update_chart(chart_type)
        
    def create_sensor_box(self, sensor_name, config):
        # Create a container for the sensor box.
        sensor_box = QFrame()
        sensor_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        sensor_box.setMinimumWidth(0)
        sensor_box.setMinimumHeight(0) 
        sensor_box.setObjectName("sensorBox")
        sensor_box.setProperty("class", "sensor-box")

        box_layout = QVBoxLayout()
        
        title_button = QPushButton(config['display_name'])
        title_button.setProperty("class", "sensor-title-button")
        
        chart_type = self.sensor_to_chart_type.get(sensor_name)
        if chart_type:
            # Use a helper to capture chart_type for this sensor.
            def make_callback(chart_type_value):
                return lambda checked: self.switch_to_chart(chart_type_value)
            title_button.clicked.connect(make_callback(chart_type))
        box_layout.addWidget(title_button)
        
        self.data_labels[sensor_name] = {}
        for key, display_name in config['measurements'].items():
            if (key != "SPO2"):
                value_label = QLabel(f"N/A {display_name}")
            else:
                value_label = QLabel(f"{display_name}: N/A")
                
            value_label.setProperty("class", "sensor-value")
            self.data_labels[sensor_name][key] = value_label
            box_layout.addWidget(value_label)
            
        icon_label = QLabel()
        icon_path  = f"assets/icons/{sensor_name}.png" 
        pix         = QPixmap(icon_path)
        pix         = pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(pix)
        icon_label.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(icon_label)

        sensor_box.setLayout(box_layout)
        return sensor_box
        
    def init_home_page(self):
        self.sensor_to_chart_type = {
            "PulseSensor": "pulse",
            "RespRate":    "resp",
            "Accel":       "accel",
            "Gyro":        "gyro",
            "ObjectTemp":  "temp",
            "Pressure":    "pressure",
        }
        layout = QGridLayout()

        header_label = QLabel(f"Astronaut {self.astronaut_name}'s Live Vitals")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label, 0, 2)

        self.sensor_config = {
            "PulseSensor": {
                "display_name": "Heart Rate and SPO2",
                "measurements": {"pulse_BPM": "BPM", "SPO2": "SPO2"},
                "grid_position": (0, 0, 2, 1),
            },
            "RespRate": {
                "display_name": "Breathing Rate",
                "measurements": {"BRPM": "breaths/min"},
                "grid_position": (2, 0, 2, 1),
            },
            "ObjectTemp": {
                "display_name": "Body Temperature",
                "measurements": {"OCelsius": "°C"},
                "grid_position": (4, 0, 2, 1),
            },
            "Accel": {
                "display_name": "Rate Of Steps",
                "measurements": {"s_rate": "steps/min"},
                "grid_position": (0, 4, 2, 1),
            },
            "Gyro": {
                "display_name": "Rate of Arm Swings",
                "measurements": {"r_rate": "swings/min"},
                "grid_position": (2, 4, 2, 1),
            },
            "Pressure": {
                "display_name": "Barometric Pressure",
                "measurements": {"hPa": "hPa"},
                "grid_position": (4, 4, 2, 1),
            },
        }
        
        for name, cfg in self.sensor_config.items():
            box = self.create_sensor_box(name, cfg)
            r, c, rs, cs = cfg["grid_position"]
            layout.addWidget(box, r, c, rs, cs)

        self.activity_label = QLabel("Current Activity: \n N/A")
        self.confidence_label = QLabel("Confidence: N/A")
        self.activity_label.setObjectName("activityLabel")
        self.confidence_label.setObjectName("confidenceLabel")
        self.activity_label.setAlignment(Qt.AlignCenter)
        self.confidence_label.setAlignment(Qt.AlignCenter)
        
        container = QWidget()
        inner_layout = QVBoxLayout(container)
        inner_layout.setContentsMargins(5, 5, 5, 5)
        inner_layout.setSpacing(10)                  

        inner_layout.addWidget(self.activity_label)
        inner_layout.addWidget(self.confidence_label)
        inner_layout.setAlignment(Qt.AlignCenter)

        layout.addWidget(container, 1, 1, 2, 1)

        fig = Figure(figsize=(3, 2.5), facecolor="none", constrained_layout=True)
        fig.patch.set_alpha(0)
        self.activityCanvas = FigureCanvas(fig)
        self.activityCanvas.setStyleSheet("background: transparent")
        self.activityAxes   = fig.add_subplot(111)
        self.activityAxes.patch.set_alpha(0)
        self.activityAxes.set_title("Overall Activity", color="white", fontsize = 16, fontweight = "bold")
        
        self.activityAxes.set_facecolor("none")
        
        self.activityAxes.set_autoscale_on(False)

        self.activityAxes.set_xlim(-0.5, len(self.activities)-0.5)
        self.activityAxes.set_ylim(0, 1)

        self.activityAxes.set_xticks(np.arange(len(self.activities)))
        self.activityAxes.set_xticklabels(
            self.activities, rotation=45, ha="right", color="white", fontweight = "bold"
        )

        self.activityAxes.set_ylabel("Fraction of Time", color="white")
   
        for spine in self.activityAxes.spines.values():
            spine.set_color("white")
        self.activityAxes.tick_params(colors="white")

        self.activityCanvas.draw()
        layout.addWidget(self.activityCanvas, 3, 1, 2, 1)
        
        self.oxygen_consumed_label = QLabel("Oxygen Consumed: \n N/A")
        self.oxygen_consumed_label.setObjectName("oxygenConsumedLabel")
        self.oxygen_consumed_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.oxygen_consumed_label, 1, 3, 2, 1)

        self.mission_length_label = QLabel("Mission Length: \n 00:00:00")
        self.mission_length_label.setObjectName("missionLengthLabel")
        self.mission_length_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.mission_length_label, 3, 3, 2, 1)

        self.mission_start = datetime.datetime.now()

        center_image = QLabel()
        center_image.setObjectName("centerImage")
        center_image.setAlignment(Qt.AlignCenter)
        pix = QPixmap("assets/spaceman.png")
        scaled = pix.scaled(380, 570, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        center_image.setPixmap(scaled)
        layout.addWidget(center_image, 1, 2, 4, 1)
        
        layout.setContentsMargins(5,5,5,5)

        for row in range(6):
            layout.setRowStretch(row, 1)

        for col in (1, 2, 3):                
            layout.setColumnStretch(col, 1)
            
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(4, 0)

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
                if (field != "SPO2"):
                    label.setText(f"{s} {disp}")
                else:
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


    def init_data_page(self):
        layout = QVBoxLayout()
 
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
        self.mongo_upload_enabled = not self.mongo_upload_enabled
        if self.mongo_upload_enabled:
            self.upload_status.setText("Upload Status: <font color='green'>ON</font>")
            self.upload_toggle_button_data_collection.setText("Stop Upload")
            self.upload_start_time = time.time()
            self.upload_label_counts.clear()
        else: 
            self.upload_status.setText("Upload Status: <font color='red'>OFF</font>")
            self.upload_toggle_button_data_collection.setText("Start Upload")
            self.upload_start_time = None

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

    def closeEvent(self, event):
        self.ble_worker.stop()
        self.update_timer.stop()
        event.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
       # Keeps counts of each activity label

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