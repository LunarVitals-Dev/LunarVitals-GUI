from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QWidget, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from pymongo import MongoClient
import pyqtgraph as pg
import sys

class AstronautMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Physiological Monitoring System")
        self.resize(1024, 768)

        # MongoDB setup
        self.client = MongoClient("mongodb://localhost:27017/")
        self.db = self.client["vitals"]
        self.collection = self.db["monitoring"]

        # Main layout
        self.main_layout = QVBoxLayout()

        # Header for the application
        self.header_label = QPushButton("Health Monitoring Dashboard")
        self.header_label.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px;")
        self.main_layout.addWidget(self.header_label)

       # Set up the table widget
        self.table = QTableWidget()
        self.table.setColumnCount(4)  # Adjust based on your data fields
        self.table.setHorizontalHeaderLabels(["TotalSteps", "TotalDistance", "VeryActiveMinutes", "Calories"])

        # Set the style for the table
        self.table.setStyleSheet("font-size: 30px; padding: 8px; border: 1px solid black; background: #1a1b41;")
        
        # Set explicit column widths to ensure no truncation
        self.table.setColumnWidth(0, 180)  # Width for "TotalSteps"
        self.table.setColumnWidth(1, 180)  # Width for "TotalDistance"
        self.table.setColumnWidth(2, 180)  # Width for "VeryActiveMinutes"
        self.table.setColumnWidth(3, 180)  # Width for "Calories"

        # Stretch columns to fit content and ensure headers are not cut off
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # Stretch columns
        self.table.horizontalHeader().setMinimumSectionSize(150)  # Set a minimum size for columns to prevent cutting off text

        # Adjust the row height to accommodate larger text
        self.table.verticalHeader().setDefaultSectionSize(30)  # Adjust this value to fit your content

        # Enable text wrapping in cells to avoid truncation
        self.table.setWordWrap(True)

        # Add the table to the layout
        self.main_layout.addWidget(self.table)
        

        # Button to refresh data
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.setStyleSheet("font-size: 14px; padding: 8px;")
        self.refresh_button.clicked.connect(self.load_data)
        self.main_layout.addWidget(self.refresh_button)

        # Chart area (PyQtGraph)
        self.chart_widget = pg.PlotWidget()
        self.chart_widget.setTitle("Astronaut's Health Data", size='15pt')
        self.chart_widget.setLabel('left', 'Value')
        self.chart_widget.setLabel('bottom', 'Time (Records)')
        font = QFont("Arial", 10)  # You can adjust the font size as needed
        self.chart_widget.getAxis('left').setStyle(tickFont=font)
        self.chart_widget.getAxis('bottom').setStyle(tickFont=font)
        self.chart_widget.setBackground('#f0f0f0')  # Light background for the chart
        self.main_layout.addWidget(self.chart_widget)

        # Set layout
        container = QWidget()
        container.setLayout(self.main_layout)
        self.setCentralWidget(container)

        # Load initial data
        self.load_data()

    def load_data(self):
        """Load data from MongoDB and display it in the table and chart."""
        self.table.setRowCount(0)  # Clear existing rows
        total_steps = []
        total_distance = []
        active_minutes = []
        calories = []

        for doc in self.collection.find():
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)

            # Format data to 4 decimal places
            total_steps_value = f"{doc.get('TotalSteps'):.4f}"
            total_distance_value = f"{doc.get('TotalDistance'):.4f}"
            active_minutes_value = f"{doc.get('VeryActiveMinutes'):.4f}"
            calories_value = f"{doc.get('Calories'):.4f}"

            self.table.setItem(row_position, 0, QTableWidgetItem(total_steps_value))
            self.table.setItem(row_position, 1, QTableWidgetItem(total_distance_value))
            self.table.setItem(row_position, 2, QTableWidgetItem(active_minutes_value))
            self.table.setItem(row_position, 3, QTableWidgetItem(calories_value))

            # Collect data for chart
            total_steps.append(doc.get("TotalSteps"))
            total_distance.append(doc.get("TotalDistance"))
            active_minutes.append(doc.get("VeryActiveMinutes"))
            calories.append(doc.get("Calories"))

        # Plot data on chart
        self.plot_data(total_steps, total_distance, active_minutes, calories)

    def plot_data(self, total_steps, total_distance, active_minutes, calories):
        """Plot data on the chart widget."""
        self.chart_widget.clear()  # Clear previous plot
        x = range(len(total_steps))

        # Plot each of the data series
        self.chart_widget.plot(x, total_steps, pen='r', name="Total Steps")
        self.chart_widget.plot(x, total_distance, pen='g', name="Total Distance")
        self.chart_widget.plot(x, active_minutes, pen='b', name="Very Active Minutes")
        self.chart_widget.plot(x, calories, pen='y', name="Calories")

        # Add legend
        self.chart_widget.addLegend()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open('stylesheet.qss', 'r') as file: 
        style_sheet = file.read() 
        app.setStyleSheet(style_sheet)
    
    window = AstronautMonitor()
    window.show()
    sys.exit(app.exec_())
