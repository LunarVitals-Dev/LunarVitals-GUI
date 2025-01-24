from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QWidget, QHeaderView, QLabel, QToolBar, QHBoxLayout, QSpacerItem, QSizePolicy, 
    QStackedWidget, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
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

        # Create navigation bar (toolbar) with logo in the center
        self.create_navbar()

        # Load initial data
        self.load_data()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_data)  # Connect the timeout signal to load_data
        self.timer.start(1000)  # Update every 1000 milliseconds
    
        
    def init_home_page(self):    
        layout = QVBoxLayout()
        header_label = QLabel("Consumable Monitoring Dashboard")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        self.home_page.setLayout(layout)

        # Table widget
        # self.table = QTableWidget()
        # self.table.setColumnCount(4)
        # self.table.setHorizontalHeaderLabels(["Timestamp", "Value (mV)"])
        # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # self.table.verticalHeader().setDefaultSectionSize(30)
        # self.table.setWordWrap(True)
        # layout.addWidget(self.table)

        self.chart_widget1 = pg.PlotWidget()
        self.chart_widget2 = pg.PlotWidget()
        self.chart_widget3 = pg.PlotWidget()
        self.chart_widget4 = pg.PlotWidget()
        self.chart_widget5 = pg.PlotWidget()

        # Add each chart widget to the layout
        layout.addWidget(self.chart_widget1)
        layout.addWidget(self.chart_widget2)
        layout.addWidget(self.chart_widget3)
        layout.addWidget(self.chart_widget4)
        layout.addWidget(self.chart_widget5)

    def init_ml_page(self):
        layout = QVBoxLayout()
        
        ACTIVITIES = ["Running", "Walking", "Cycling", "Jumping", "Lifting"]

        # Header
        header_label = QLabel("Machine Learning Dashboard")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        activity_combobox = QComboBox()
        activity_combobox.addItems(ACTIVITIES)
        activity_combobox.setCurrentIndex(0)
        layout.addWidget(activity_combobox)

        # Dummy Chart
        dummy_chart = pg.PlotWidget()
        dummy_chart.setTitle("Dummy Graph", size="16pt")
        dummy_chart.plot([1, 2, 3, 4], [10, 20, 30, 40]) 
        layout.addWidget(dummy_chart)

        # Test Label
        test_label = QLabel("This is a test label.")
        test_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(test_label)

        # Assign layout to the ML page
        self.ml_page.setLayout(layout)

        
        
    def init_about_page(self):
        layout = QVBoxLayout()
        header_label = QLabel("About Us")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        self.about_page.setLayout(layout)
        
        # Add a dummy description
        about_text = QLabel("This is a dummy 'About Us' page.\n\n"
                        "This application is for monitoring physiological data in astronauts.\n"
                        "Developed as part of the Capstone project.")
        about_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(about_text)
        

    # def update_table(self, timestamp, respiratory):
    #     """Update the table with new simulated data."""
    #     row_position = self.table.rowCount()
    #     self.table.insertRow(row_position)

    #     self.table.setItem(row_position, 0, QTableWidgetItem(timestamp))
    #     self.table.setItem(row_position, 1, QTableWidgetItem(str(respiratory)))

    def create_navbar(self):
        """Create a navigation bar (toolbar) with the logo centered and navigation buttons."""
        # Create a central widget for the navbar layout
        navbar_widget = QWidget()
        navbar_layout = QHBoxLayout(navbar_widget)
        navbar_layout.setSpacing(30) 

        # Home button
        home_button = QPushButton("Home")
        home_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.home_page))
        navbar_layout.addWidget(home_button)

        # ML button
        ml_button = QPushButton("ML")
        ml_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.ml_page))
        navbar_layout.addWidget(ml_button)
        
        navbar_layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # QLabel for the logo
        self.logo_label = QLabel(self)
        pixmap = QPixmap("lunarlogo.png")  # Specify the path to your logo file
        pixmap = pixmap.scaled(200, 60, Qt.KeepAspectRatio)
        self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignCenter)
        navbar_layout.addWidget(self.logo_label)

        navbar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        settings_button = QPushButton("About")
        settings_button.clicked.connect(lambda: self.central_stack.setCurrentWidget(self.about_page))
        navbar_layout.addWidget(settings_button)
        
        # Create a QToolBar and add the custom widget as the toolbar content
        navbar = QToolBar()
        navbar.setMovable(False)  # Make the toolbar unmovable
        navbar.addWidget(navbar_widget)  # Add the navbar widget with custom layout to the toolbar

        # Add the toolbar to the main window
        self.addToolBar(navbar)

    def load_data(self):
        try:
            #self.table.setRowCount(0) 
            accel_x, accel_y, accel_z = [], [], []
            gyro_x, gyro_y, gyro_z = [], [], []
            obj_temp, temperature = [], []
            pressure = []
            resp = []

            for doc in self.collection.find():
                # Process accelerometer data
                accel_data = doc.get('Accelerometer', {})
                accel_x.append(accel_data.get('X_g', 0))
                accel_y.append(accel_data.get('Y_g', 0))
                accel_z.append(accel_data.get('Z_g', 0))

                # Process gyroscope data
                gyro_data = doc.get('Gyroscope', {})
                gyro_x.append(gyro_data.get('X_deg_per_s', 0))
                gyro_y.append(gyro_data.get('Y_deg_per_s', 0))
                gyro_z.append(gyro_data.get('Z_deg_per_s', 0))

                # Process other sensors
                obj_temp.append(doc.get('ObjectTemperature', {}).get('Celsius', 0))
                temperature.append(doc.get('Temperature', {}).get('Celsius', 0))
                pressure.append(doc.get('Pressure', {}).get('hPa', 0))
                resp.append(doc.get('RespiratoryRate', {}).get('Value_mV', 0))

            # Plot each sensor's data
            self.plot_sensor_data(self.chart_widget1, accel_x, accel_y, accel_z, title="Accelerometer (g)")
            self.plot_sensor_data(self.chart_widget2, gyro_x, gyro_y, gyro_z, title="Gyroscope (°/s)")
            self.plot_double_sensor(self.chart_widget3, obj_temp, temperature, title="Ambient vs Object Temperature (°C)")
            self.plot_single_sensor(self.chart_widget4, pressure, title="Pressure (hPa)")
            self.plot_single_sensor(self.chart_widget5, resp, title="Respiratory Rate (mV)")

        except Exception as e:
            print(f"Error loading data: {e}")
            
    def plot_sensor_data(self, chart, x_data, y_data, z_data, title=""):
        chart.clear()
        chart.setTitle(title, size='16pt')
        chart.plot(x_data, pen='r')
        chart.plot(y_data, pen='g')
        chart.plot(z_data, pen='b')

    def plot_single_sensor(self, chart, data, title=""):
        chart.clear()
        chart.setTitle(title, size='16pt')
        chart.plot(data, pen='r')
        
    def plot_double_sensor(self, chart, data1, data2, title=""):
        chart.clear()
        chart.setTitle(title, size='16pt')
        chart.plot(data1, pen='r')
        chart.plot(data2, pen='g')
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file:
        style_sheet = file.read()
        app.setStyleSheet(style_sheet)

    window = AstronautMonitor()
    window.show()
    sys.exit(app.exec_())
