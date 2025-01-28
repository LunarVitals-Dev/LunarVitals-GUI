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
            
        # Main stacked widget to hold pages
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        # Set common chart style
        self.chart_style = {
            'background': 'white',
            'foreground': '#062a61',
            'title_size': '20pt',
            'title_color': '#062a61',
            'axis_color': '#062a61',
            'grid_color': '#e0e0e0'
        }

        # Create pages
        self.home_page = QWidget()
        self.ml_page = QWidget()
        self.about_page = QWidget()
        
        self.init_home_page()
        self.init_ml_page()
        self.init_about_page()

        self.central_stack.addWidget(self.home_page)
        self.central_stack.addWidget(self.ml_page)
        self.central_stack.addWidget(self.about_page)

        # Create navigation bar
        self.create_navbar()

        # Load initial data
        self.load_data()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_data)
        self.timer.start(100)

    def init_data_buffers(self):
        self.accel_x = deque(maxlen=200)
        self.accel_y = deque(maxlen=200)
        self.accel_z = deque(maxlen=200)
        self.gyro_x = deque(maxlen=200)
        self.gyro_y = deque(maxlen=200)
        self.gyro_z = deque(maxlen=200)
        self.obj_temp = deque(maxlen=200)
        self.amb_temp = deque(maxlen=200)
        self.pressure = deque(maxlen=200)
        self.resp = deque(maxlen=200)

    def setup_chart(self, chart_widget, title):
        chart_widget.setBackground('white')
        chart_widget.setTitle(title, size=self.chart_style['title_size'], color=self.chart_style['title_color'])
        chart_widget.showGrid(x=True, y=True, alpha=0.3)
        chart_widget.getAxis('bottom').setPen(self.chart_style['axis_color'])
        chart_widget.getAxis('left').setPen(self.chart_style['axis_color'])
        return chart_widget

    def init_home_page(self):    
        layout = QVBoxLayout()
        header_label = QLabel("Physiological Monitoring Dashboard")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        # Create chart layout with 2x3 grid
        charts_layout = QVBoxLayout()
        charts_layout.setSpacing(20)
        
        self.chart_widget1 = self.setup_chart(pg.PlotWidget(), "Accelerometer (g)")
        self.chart_widget2 = self.setup_chart(pg.PlotWidget(), "Gyroscope (°/s)")
        self.chart_widget3 = self.setup_chart(pg.PlotWidget(), "Temperature (°C)")
        self.chart_widget4 = self.setup_chart(pg.PlotWidget(), "Pressure (hPa)")
        self.chart_widget5 = self.setup_chart(pg.PlotWidget(), "Respiratory Rate (mV)")

        charts_layout.addWidget(self.chart_widget1)
        charts_layout.addWidget(self.chart_widget2)
        charts_layout.addWidget(self.chart_widget3)
        charts_layout.addWidget(self.chart_widget4)
        charts_layout.addWidget(self.chart_widget5)

        layout.addLayout(charts_layout)
        self.home_page.setLayout(layout)

    def init_ml_page(self):
        layout = QVBoxLayout()
        
        header_label = QLabel("Activity Recognition Dashboard")
        header_label.setObjectName("pageHeader")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # Activity selection
        activity_layout = QHBoxLayout()
        activity_label = QLabel("Select Activity:")
        activity_label.setObjectName("subHeader")
        activity_combobox = QComboBox()
        activity_combobox.addItems(["Running", "Walking", "Cycling", "Jumping", "Lifting"])
        activity_layout.addWidget(activity_label)
        activity_layout.addWidget(activity_combobox)
        activity_layout.addStretch()
        layout.addLayout(activity_layout)

        # ML visualization chart
        ml_chart = self.setup_chart(pg.PlotWidget(), "Activity Recognition")
        layout.addWidget(ml_chart)

        self.ml_page.setLayout(layout)

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
        ml_button = QPushButton("ML")
        ml_button.setObjectName("navButton")
        ml_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.ml_page))
        left_layout.addWidget(ml_button)
        navbar_layout.addWidget(left_buttons)

        # Add flexible space before logo
        navbar_layout.addStretch()

        # Centered logo
        self.logo_label = QLabel()
        pixmap = QPixmap("lunarlogo.png")
        pixmap = pixmap.scaled(200, 60, Qt.KeepAspectRatio)
        self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignCenter)
        navbar_layout.addWidget(self.logo_label)

        # Add flexible space after logo
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
            # Query to fetch data newer than the last timestamp
            query = {}
            if self.last_timestamp:
                query = {"timestamp": {"$gt": self.last_timestamp}}

            # Fetch new data sorted by timestamp
            cursor = self.collection.find(query).sort("timestamp", 1)
            new_data = list(cursor)

            if new_data:
                # Group the data into cycles of 4 entries
                for i in range(0, len(new_data), 4):
                    if i + 4 <= len(new_data):
                        cycle = new_data[i:i+4]
                        
                        # Update the last timestamp to the latest in the cycle
                        self.last_timestamp = cycle[-1]["timestamp"]

                        # Extract data for each sensor in the cycle
                        accel_entry = cycle[0]
                        temp_entry = cycle[1]
                        pressure_entry = cycle[2]
                        resp_entry = cycle[3]

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

                        # Object and Ambient Temperature data (entry 2)
                        self.obj_temp.append(temp_entry.get('ObjectTemperature', {}).get('Celsius', 0))
                        self.amb_temp.append(temp_entry.get('AmbientTemperature', {}).get('Celsius', 0))

                        # Pressure data (entry 3)
                        self.pressure.append(pressure_entry.get('Pressure', {}).get('hPa', 0))

                        # Respiratory Rate data (entry 4)
                        self.resp.append(resp_entry.get('RespiratoryRate', {}).get('Value_mV', 0))


                # Update the charts with the new data
                self.update_charts()


        except Exception as e:
            print(f"Error loading data: {e}")


    def update_charts(self):
        """Update all charts with the current data"""
        # Get the full range of points
        x_range = list(range(max(0, len(self.accel_x)-200), len(self.accel_x)))
        
        # Update accelerometer chart
        self.chart_widget1.clear()
        self.chart_widget1.plot(x_range, list(self.accel_x), pen='r', name='X')
        self.chart_widget1.plot(x_range, list(self.accel_y), pen='g', name='Y')
        self.chart_widget1.plot(x_range, list(self.accel_z), pen='b', name='Z')

        # Update gyroscope chart
        self.chart_widget2.clear()
        self.chart_widget2.plot(x_range, list(self.gyro_x), pen='r', name='X')
        self.chart_widget2.plot(x_range, list(self.gyro_y), pen='g', name='Y')
        self.chart_widget2.plot(x_range, list(self.gyro_z), pen='b', name='Z')

        # Update temperature chart
        self.chart_widget3.clear()
        self.chart_widget3.plot(x_range, list(self.obj_temp), pen='r', name='Object')
        self.chart_widget3.plot(x_range, list(self.amb_temp), pen='g', name='Ambient')

        # Update pressure chart
        self.chart_widget4.clear()
        self.chart_widget4.plot(x_range, list(self.pressure), pen='r')

        # Update respiratory rate chart
        self.chart_widget5.clear()
        self.chart_widget5.plot(x_range, list(self.resp), pen='r')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file:
        style_sheet = file.read()
        app.setStyleSheet(style_sheet)
    
    window = AstronautMonitor()
    window.show()
    sys.exit(app.exec_())