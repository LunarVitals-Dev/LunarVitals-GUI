from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QWidget, QHeaderView, QLabel, QToolBar, QHBoxLayout, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from pymongo import MongoClient
import pyqtgraph as pg
import sys
import random


class AstronautMonitor(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Physiological Monitoring System")
        self.resize(1024, 768)

        # MongoDB setup
        try:
            self.client = MongoClient("mongodb+srv://LunarVitals:lunarvitals1010@peakfitness.i5blp.mongodb.net/")
            self.db = self.client["vitals"]
            self.collection = self.db["sensors"]
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
        self.table.setHorizontalHeaderLabels(["Total Steps", "Total Distance", "Active Minutes", "Calories"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setWordWrap(True)
        self.main_layout.addWidget(self.table)
        
        # Start the timer to simulate real-time data updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.simulate_data)
        self.timer.start(1000)  

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
        
    
    def simulate_data(self):
        """Simulate new data and insert into MongoDB."""
        new_total_steps = random.randint(0, 20000)
        new_total_distance = random.uniform(0, 50)
        new_active_minutes = random.randint(0, 180)
        new_calories = random.randint(0, 3000)

        # Insert new simulated data into MongoDB
        self.collection.insert_one({
            "TotalSteps": new_total_steps,
            "TotalDistance": new_total_distance,
            "VeryActiveMinutes": new_active_minutes,
            "Calories": new_calories,
        })

        # Reload the data and update the table and chart
        self.load_data()

    def update_table(self, total_steps, total_distance, active_minutes, calories):
        """Update the table with new simulated data."""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        self.table.setItem(row_position, 0, QTableWidgetItem(str(total_steps)))
        self.table.setItem(row_position, 1, QTableWidgetItem(f"{total_distance:.2f}"))
        self.table.setItem(row_position, 2, QTableWidgetItem(str(active_minutes)))
        self.table.setItem(row_position, 3, QTableWidgetItem(str(calories)))

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
            self.table.setRowCount(0) 
            total_steps = []
            total_distance = []
            active_minutes = []
            calories = []

            for doc in self.collection.find():
                row_position = self.table.rowCount()
                self.table.insertRow(row_position)

                # Format data
                total_steps_value = f"{doc.get('TotalSteps', 0)}"
                total_distance_value = f"{doc.get('TotalDistance', 0):.2f}"
                active_minutes_value = f"{doc.get('VeryActiveMinutes', 0)}"
                calories_value = f"{doc.get('Calories', 0)}"

                self.table.setItem(row_position, 0, QTableWidgetItem(total_steps_value))
                self.table.setItem(row_position, 1, QTableWidgetItem(total_distance_value))
                self.table.setItem(row_position, 2, QTableWidgetItem(active_minutes_value))
                self.table.setItem(row_position, 3, QTableWidgetItem(calories_value))

                # Collect data for chart
                total_steps.append(doc.get("TotalSteps", 0))
                total_distance.append(doc.get("TotalDistance", 0))
                active_minutes.append(doc.get("VeryActiveMinutes", 0))
                calories.append(doc.get("Calories", 0))

            # Plot data on chart
            self.plot_data(total_steps, total_distance, active_minutes, calories)
        except Exception as e:
            print(f"Error loading data: {e}")

    def plot_data(self, total_steps, total_distance, active_minutes, calories):
        """Plot data on the chart widget."""
        self.chart_widget.clear()  # Clear existing plots
        x = range(len(total_steps))

        # Plot each data series
        self.chart_widget.plot(x, total_steps, pen='r', name="Total Steps")
        self.chart_widget.plot(x, total_distance, pen='g', name="Total Distance")
        self.chart_widget.plot(x, active_minutes, pen='b', name="Active Minutes")
        self.chart_widget.plot(x, calories, pen='y', name="Calories")

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
