from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QWidget, QHeaderView, QLabel, QToolBar, QHBoxLayout, QSpacerItem, QSizePolicy, QStackedWidget
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
            self.collection = self.db["SensorData"]
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
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Value (mV)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setWordWrap(True)
        layout.addWidget(self.table)

        # Chart area (PyQtGraph)
        self.chart_widget1 = pg.PlotWidget()
        self.chart_widget1.setTitle("Respiratory Rate", size='16pt')
        self.chart_widget1.setLabel('left', 'Value', size='10pt')
        self.chart_widget1.setLabel('bottom', 'Time (Records)', size='10pt')
        self.chart_widget1.getAxis('left').setStyle(tickFont=QFont("Arial", 10))
        self.chart_widget1.getAxis('bottom').setStyle(tickFont=QFont("Arial", 10))
        layout.addWidget(self.chart_widget1, stretch=1)
        
        # Chart area (PyQtGraph)
        self.chart_widget2 = pg.PlotWidget()
        self.chart_widget2.setTitle("Motion Detection", size='16pt')
        self.chart_widget2.setLabel('left', 'Value', size='10pt')
        self.chart_widget2.setLabel('bottom', 'Time (Records)', size='10pt')
        self.chart_widget2.getAxis('left').setStyle(tickFont=QFont("Arial", 10))
        self.chart_widget2.getAxis('bottom').setStyle(tickFont=QFont("Arial", 10))
        layout.addWidget(self.chart_widget2, stretch=1)
        
        # Chart area (PyQtGraph)
        self.chart_widget3 = pg.PlotWidget()
        self.chart_widget3.setTitle("Temperature", size='16pt')
        self.chart_widget3.setLabel('left', 'Value', size='10pt')
        self.chart_widget3.setLabel('bottom', 'Time (Records)', size='10pt')
        self.chart_widget3.getAxis('left').setStyle(tickFont=QFont("Arial", 10))
        self.chart_widget3.getAxis('bottom').setStyle(tickFont=QFont("Arial", 10))
        layout.addWidget(self.chart_widget3, stretch=1)

    def init_ml_page(self):
        layout = QVBoxLayout()

        # Header
        header_label = QLabel("Machine Learning Dashboard")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # Test Button
        test_button = QPushButton("Click Me")
        layout.addWidget(test_button)

        # Dummy Chart
        dummy_chart = pg.PlotWidget()
        dummy_chart.setTitle("Dummy Graph", size="16pt")
        dummy_chart.plot([1, 2, 3, 4], [10, 20, 30, 40])  # Simple line plot
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
        

    def update_table(self, timestamp, respiratory):
        """Update the table with new simulated data."""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        self.table.setItem(row_position, 0, QTableWidgetItem(timestamp))
        self.table.setItem(row_position, 1, QTableWidgetItem(str(respiratory)))

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
        """Load data from MongoDB and display it in the table and chart."""
        try:
            self.table.setRowCount(0)  # Clear existing table rows
            timestamp = []
            respiratory = []

            # Fetch and process non-zero records
            for doc in self.collection.find():
                respiratory_value = doc.get('value', 0)
                
                # Skip records with zero value
                if respiratory_value == 0:
                    continue

                # Format data
                timestamp_value = 0
                if isinstance(doc.get('timestamp'), datetime):
                    timestamp_value = int(doc.get('timestamp').timestamp() * 1000)  # Convert to milliseconds
                elif isinstance(doc.get('timestamp'), int):
                    timestamp_value = doc.get('timestamp')  # Use the integer directly

                # Update table
                row_position = self.table.rowCount()
                self.table.insertRow(row_position)
                self.table.setItem(row_position, 0, QTableWidgetItem(str(timestamp_value)))
                self.table.setItem(row_position, 1, QTableWidgetItem(str(respiratory_value)))

                # Collect data for chart
                timestamp.append(timestamp_value)
                respiratory.append(respiratory_value)

            # Plot data on chart
            self.plot_data(timestamp, respiratory)
        except Exception as e:
            print(f"Error loading data: {e}")


    def plot_data(self, timestamp, respiratory):
        """Plot data on the chart widget."""
        self.chart_widget1.clear()
        self.chart_widget2.clear()
        self.chart_widget3.clear()
        x = range(len(respiratory))

        self.chart_widget1.plot(x, respiratory, pen='r', name="Respiratory")
        self.chart_widget2.plot(x, respiratory, pen='g', name="Motion")
        self.chart_widget3.plot(x, respiratory, pen='b', name="Temperature")

        # Add legend if not already present
        if not hasattr(self, "legend_added"):
            self.chart_widget1.addLegend(offset=(0, 0))
            self.chart_widget2.addLegend(offset=(0, 0))
            self.chart_widget3.addLegend(offset=(0, 0))
            self.legend_added = True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file:
        style_sheet = file.read()
        app.setStyleSheet(style_sheet)

    window = AstronautMonitor()
    window.show()
    sys.exit(app.exec_())
