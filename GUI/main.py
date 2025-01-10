from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QWidget, QHeaderView, QLabel, QToolBar, QHBoxLayout, QSpacerItem, QSizePolicy
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

        # Main layout for the central widget
        self.main_layout = QVBoxLayout()
        
        # Header for the application
        self.header_label = QLabel("Consumable Monitoring Dashboard")
        self.header_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.header_label)

        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Value (mV)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setWordWrap(True)
        self.main_layout.addWidget(self.table)

        # Chart area (PyQtGraph)
        self.chart_widget = pg.PlotWidget()
        self.chart_widget.setTitle("Astronaut's Health Data", size='16pt')
        self.chart_widget.setLabel('left', 'Value', size='10pt')
        self.chart_widget.setLabel('bottom', 'Time (Records)', size='10pt')
        self.chart_widget.getAxis('left').setStyle(tickFont=QFont("Arial", 10))
        self.chart_widget.getAxis('bottom').setStyle(tickFont=QFont("Arial", 10))
        self.main_layout.addWidget(self.chart_widget, stretch=1)

        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.setFixedSize(140, 60)  
        self.refresh_button.clicked.connect(self.load_data)  
        self.main_layout.addWidget(self.refresh_button, alignment=Qt.AlignCenter)

        # Set layout
        container = QWidget()
        container.setLayout(self.main_layout)
        self.setCentralWidget(container)

        # Create navigation bar (toolbar) with logo in the center
        self.create_navbar()

        # Load initial data
        self.load_data()
        

    def update_table(self, timestamp, respiratory):
        """Update the table with new simulated data."""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        self.table.setItem(row_position, 0, QTableWidgetItem(timestamp))
        self.table.setItem(row_position, 1, QTableWidgetItem(str(respiratory)))

    def create_navbar(self):
        """Create a navigation bar (toolbar) with the logo centered."""
        navbar = QToolBar()
        navbar.setMovable(False)  # Make toolbar unmovable

        # Create a layout to hold the logo in the center
        navbar_layout = QHBoxLayout()

        # Add a spacer before the logo to push it towards the center
        spacer_left = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        navbar_layout.addItem(spacer_left)

        # QLabel for logo
        self.logo_label = QLabel(self)
        
        # Load the logo image using QPixmap
        pixmap = QPixmap("lunarlogo.png")  # Specify the path to your logo file
        pixmap = pixmap.scaled(200, 60, Qt.KeepAspectRatio)
        self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignCenter)  # Center the logo

        navbar_layout.addWidget(self.logo_label)

        # Add a spacer after the logo to complete the centering
        spacer_right = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        navbar_layout.addItem(spacer_right)

        # Create a QWidget to hold the layout, then add it to the toolbar
        navbar_widget = QWidget()
        navbar_widget.setLayout(navbar_layout)
        navbar.addWidget(navbar_widget)

        # Add the navbar to the main window
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

                print(f"Parsed: Timestamp={timestamp_value}, Value={respiratory_value}")  # Debugging

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
        self.chart_widget.clear()  # Clear existing plots
        x = range(len(respiratory))

        self.chart_widget.plot(x, respiratory, pen='g', name="Respiratory")

        # Add legend if not already present
        if not hasattr(self, "legend_added"):
            self.chart_widget.addLegend(offset=(0, 0))
            self.legend_added = True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file:
        style_sheet = file.read()
        app.setStyleSheet(style_sheet)

    window = AstronautMonitor()
    window.show()
    sys.exit(app.exec_())
