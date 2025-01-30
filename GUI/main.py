from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QWidget, QHeaderView, QLabel, QToolBar, QHBoxLayout, QSpacerItem, QSizePolicy, 
    QStackedWidget, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
from datetime import datetime
from collections import deque
import os
import pyqtgraph as pg
import sys
import random

class AstronautMonitor(QMainWindow):
    def __init__(self):
        load_dotenv()
        super().__init__()

        self.setWindowTitle("Physiological Monitoring System")
        self.resize(1024, 768)
        
        # Initialize data buffers with max length of 200
        self.init_data_buffers()
        self.last_timestamp = None

        # MongoDB setup
        try:
            self.client = MongoClient(os.getenv("MONGODB_URI"))
            self.db = self.client["LunarVitalsDB"]
            self.collection = self.db["sensor_data"]
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            sys.exit(1)

        # Set common chart style
        self.chart_style = {
            'background': 'white',
            'foreground': '#062a61',
            'title_size': '20pt',
            'title_color': '#062a61',
            'axis_color': '#062a61',
            'grid_color': '#e0e0e0'
        }
        
        self.initUI()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_data)
        self.timer.start(100)
        
    def initUI(self):
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)
        
        # Create pages
        self.home_page = QWidget()
        self.about_page = QWidget()
        
        self.init_home_page()
        self.init_about_page()

        self.central_stack.addWidget(self.home_page)
        self.central_stack.addWidget(self.about_page)

        # Create navigation bar
        self.create_navbar()

        # Load initial data
        self.load_data()

    def init_data_buffers(self):
        self.accel_x = deque(maxlen=200)
        self.accel_y = deque(maxlen=200)
        self.accel_z = deque(maxlen=200)
        self.gyro_x = deque(maxlen=200)
        self.gyro_y = deque(maxlen=200)
        self.gyro_z = deque(maxlen=200)
        self.obj_temp = deque(maxlen=200)
        self.amb_temp = deque(maxlen=200)
        self.resp = deque(maxlen=200)

    def init_home_page(self):    
        layout = QVBoxLayout()
        
        # Header
        header_label = QLabel("Physiological Monitoring Dashboard")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        # Buttons container
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_widget.setLayout(buttons_layout)
        
        # Create buttons
        self.accel_button = QPushButton("Accelerometer")
        self.gyro_button = QPushButton("Gyroscope")
        self.temp_button = QPushButton("Temperature")
        self.resp_button = QPushButton("Respiratory")
        
        # Add buttons to layout
        buttons_layout.addWidget(self.accel_button)
        buttons_layout.addWidget(self.gyro_button)
        buttons_layout.addWidget(self.temp_button)
        buttons_layout.addWidget(self.resp_button)
        
        # Connect button signals
        self.accel_button.clicked.connect(lambda: self.update_chart('accel'))
        self.gyro_button.clicked.connect(lambda: self.update_chart('gyro'))
        self.temp_button.clicked.connect(lambda: self.update_chart('temp'))
        self.resp_button.clicked.connect(lambda: self.update_chart('resp'))
        
        layout.addWidget(buttons_widget)
        
        # Create chart widget
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
        """Update the chart based on the selected sensor type"""
        self.chart_widget.clear()
        x_range = list(range(200))  # Create a fixed range for x-axis
        
        if sensor_type == 'accel':
            self.chart_widget.setTitle("Accelerometer Data")
            self.chart_widget.plot(x_range[:len(self.accel_x)], list(self.accel_x), pen='r', name='X')
            self.chart_widget.plot(x_range[:len(self.accel_y)], list(self.accel_y), pen='g', name='Y')
            self.chart_widget.plot(x_range[:len(self.accel_z)], list(self.accel_z), pen='b', name='Z')
        
        elif sensor_type == 'gyro':
            self.chart_widget.setTitle("Gyroscope Data")
            self.chart_widget.plot(x_range[:len(self.gyro_x)], list(self.gyro_x), pen='r', name='X')
            self.chart_widget.plot(x_range[:len(self.gyro_y)], list(self.gyro_y), pen='g', name='Y')
            self.chart_widget.plot(x_range[:len(self.gyro_z)], list(self.gyro_z), pen='b', name='Z')
        
        elif sensor_type == 'temp':
            self.chart_widget.setTitle("Temperature Data")
            self.chart_widget.plot(x_range[:len(self.obj_temp)], list(self.obj_temp), pen='r', name='Object')
            self.chart_widget.plot(x_range[:len(self.amb_temp)], list(self.amb_temp), pen='g', name='Ambient')
        
        elif sensor_type == 'resp':
            self.chart_widget.setTitle("Respiratory Rate")
            self.chart_widget.plot(x_range[:len(self.resp)], list(self.resp), pen='r', name='Respiratory Rate')

    # [Rest of the class implementation remains the same...]
    def init_about_page(self):
        layout = QVBoxLayout()
        
        header_label = QLabel("About The Project")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        about_text = QLabel(
            "Lunar Vitals Monitoring System\n"
            "This application provides real-time monitoring of astronaut "
            "physiological data during lunar missions. It features:\n"
            "Real-time sensor data visualization\n"
            "Activity recognition using machine learning\n"
            "Comprehensive health monitoring capabilities"
        )
        about_text.setObjectName("aboutText")
        about_text.setAlignment(Qt.AlignCenter)
        about_text.setWordWrap(True)
        layout.addWidget(about_text)
        
        self.about_page.setLayout(layout)

    def create_navbar(self):
        navbar_widget = QWidget()
        navbar_layout = QHBoxLayout(navbar_widget)
        navbar_layout.setSpacing(30)

        # Left side buttons
        left_buttons = QWidget()
        left_layout = QHBoxLayout(left_buttons)
        home_button = QPushButton("Home")
        home_button.setObjectName("navButton")
        home_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.home_page))
        left_layout.addWidget(home_button)
        navbar_layout.addWidget(left_buttons)

        navbar_layout.addStretch()

        # Centered logo
        self.logo_label = QLabel()
        pixmap = QPixmap("lunarlogo.png")
        pixmap = pixmap.scaled(200, 60, Qt.KeepAspectRatio)
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

    def load_data(self):
        try:
            query = {}
            if self.last_timestamp:
                query = {"timestamp": {"$gt": self.last_timestamp}}

            # Fetch new data sorted by timestamp
            cursor = self.collection.find(query).sort("timestamp", 1)
            new_data = list(cursor)

            if new_data:
                for i in range(0, len(new_data), 3):
                    if i + 3 <= len(new_data):
                        cycle = new_data[i:i+3]
                        
                        # Update the last timestamp to the latest in the cycle
                        self.last_timestamp = cycle[-1]["timestamp"]

                        # Extract data for each sensor in the cycle
                        temp_entry = cycle[0]
                        resp_entry = cycle[1]
                        accel_entry = cycle[2]

                        # Accelerometer data (entry 1)
                        accel_data = accel_entry.get('Accelerometer', {})
                        self.accel_x.append(accel_data.get('X_g', 0))
                        self.accel_y.append(accel_data.get('Y_g', 0))
                        self.accel_z.append(accel_data.get('Z_g', 0))

                        # Gyroscope data (entry 1)
                        gyro_data = accel_entry.get('Gyroscope', {})
                        self.gyro_x.append(gyro_data.get('X_deg_per_s', 0))
                        self.gyro_y.append(gyro_data.get('Y_deg_per_s', 0))
                        self.gyro_z.append(gyro_data.get('Z_deg_per_s', 0))

                        # Temperature data (entry 2)
                        self.obj_temp.append(temp_entry.get('ObjectTemperature', {}).get('Celsius', 0))
                        self.amb_temp.append(temp_entry.get('AmbientTemperature', {}).get('Celsius', 0))

                        # Respiratory Rate data (entry 3)
                        self.resp.append(resp_entry.get('RespiratoryRate', {}).get('Value_mV', 0))

        except Exception as e:
            print(f"Error loading data: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file:
        style_sheet = file.read()
        app.setStyleSheet(style_sheet)
    
    window = AstronautMonitor()
    window.show()
    sys.exit(app.exec_())