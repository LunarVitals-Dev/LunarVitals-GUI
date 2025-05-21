# data_collection_page.py

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QGridLayout, QWidget
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize
import time
import ast
from typing import Optional
from collections import Counter

ACTIVITY_LABELS = ["Idle", "Walking", "Lifting", "Crouching", "Skipping"]

class ActivityTracker:
    """Keeps track of how long each activity runs, and reports the current leader."""
    def __init__(self, activities: list[str]) -> None:
        self.activities = activities
        self.reset()

    def reset(self) -> None:
        self._durations: Counter[str] = Counter()
        self._current: Optional[str] = None
        self._t_start: Optional[float] = None

    def update(self, activity: str) -> str:
        now = time.time()

        # first-ever call
        if self._current is None:
            self._current, self._t_start = activity, now
            return activity

        # activity changed → close out the old segment
        if activity != self._current and self._t_start is not None:
            self._durations[self._current] += now - self._t_start
            self._current, self._t_start = activity, now

        # find leader including the still-open segment
        leader = self._current
        leader_time = self._durations[leader] + (now - (self._t_start or now))
        for act, dur in self._durations.items():
            if dur > leader_time:
                leader, leader_time = act, dur

        return leader

def init_data_collection_page(self):
    self.data_collection_page.setObjectName("dataCollectionPage")

    # top‐level layout
    main_layout = QHBoxLayout()

    # ─── Left: ML Predictions and Status ────────────────────────
    left_frame = QFrame()
    left_frame.setObjectName("dataCollectionLeft")
    left_frame.setFrameShape(QFrame.StyledPanel)
    left_frame.setLayout(QVBoxLayout())
    lf = left_frame.layout()
    lf.addWidget(QLabel("<b>ML Prediction Status</b>"))
    self.activity_label_data_collection = QLabel("Current Activity: N/A")
    lf.addWidget(self.activity_label_data_collection)
    self.confidence_label_data_collection = QLabel("Confidence: N/A")
    lf.addWidget(self.confidence_label_data_collection)
    lf.addSpacing(10)
    lf.addWidget(QLabel("<b>Upload Stats</b>"))
    self.upload_duration_label = QLabel("Duration: 0s")
    lf.addWidget(self.upload_duration_label)
    self.activity_distribution_label = QLabel("Activity Breakdown: N/A")
    lf.addWidget(self.activity_distribution_label)
    lf.addStretch()


    # ---------------- Right: Data Labeling & Uploading ---------------- #
    right_frame = QFrame()
    right_frame.setObjectName("dataCollectionRight")
    right_frame.setFrameShape(QFrame.StyledPanel)
    right_frame.setLayout(QVBoxLayout())
    rf = right_frame.layout()
    rf.addWidget(QLabel("<b>Labeling & Upload Controls</b>"))

    # Astronaut Selection
    rf.addWidget(QLabel("<b>Select Astronaut</b>"))
    astronauts = [
        ("Peak", "Male", 22, 140),
        ("Victor", "Male", 22, 140),
        ("Zeiler", "Male", 21, 130),
        ("Lucas", "Male", 21, 150),
        ("Allan", "Male", 21, 130)
    ]

    self.astronaut_buttons = {}
    astro_layout = QHBoxLayout()

    for name, gender, age, weight in astronauts:
        btn = QPushButton(name)
        btn.setCheckable(True)
        btn.clicked.connect(lambda checked, n=name, g=gender, a=age, w=weight: self.set_current_astronaut(n, g, a, w))
        btn.setStyleSheet("padding: 6px; font-size: 14px; font-weight: bold;")
        self.astronaut_buttons[name] = btn
        astro_layout.addWidget(btn)

    rf.addLayout(astro_layout)

    rf.addWidget(QLabel("Select Activity Label:"))

    self.label_buttons = {}
    activity_labels = ACTIVITY_LABELS
    button_layout = QGridLayout()

    for i, label in enumerate(activity_labels):
        button = QPushButton()
        button.setCheckable(True)
        # button.setIcon(QIcon(f"assets/{label.lower()}.png"))  # Make sure you have icons named idle.png, walking.png, etc.
        # button.setIconSize(QSize(64, 64))
        button.setText(label)
        button.setStyleSheet("padding: 10px; font-weight: bold; font-size: 14px;")
        button.clicked.connect(lambda checked, l=label: self.set_current_activity_label(l))
        self.label_buttons[label] = button
        button_layout.addWidget(button, i // 2, i % 2)

    rf.addLayout(button_layout)

    self.upload_status = QLabel("Upload Status: <font color='red'>OFF</font>")
    rf.addWidget(self.upload_status)

    self.upload_toggle_button_data_collection = QPushButton("Start Upload")
    self.upload_toggle_button_data_collection.setCheckable(True)
    self.upload_toggle_button_data_collection.clicked.connect(self.toggle_upload_to_mongo)
    rf.addWidget(self.upload_toggle_button_data_collection)

    rf.addWidget(QLabel("Currently Collected Data:"))
    self.mongo_output_area = QTextEdit()
    self.mongo_output_area.setReadOnly(True)
    self.mongo_output_area.setFixedHeight(150)
    rf.addWidget(self.mongo_output_area)

    self.mongo_data_labels = {}
    create_data_labels(self, rf)

    main_layout.addWidget(left_frame, 1)

    divider = QFrame()
    divider.setFrameShape(QFrame.Shape.VLine)
    divider.setFrameShadow(QFrame.Shadow.Sunken)
    main_layout.addWidget(divider)

    main_layout.addWidget(right_frame, 2)

    self.data_collection_page.setLayout(main_layout)
    #self.update_data_collection_page()

def set_current_astronaut(self, name, gender, age, weight):
    self.astronaut_name = name
    self.astronaut_gender = gender
    self.astronaut_age = age
    self.astronaut_weight = weight
    # print(f"Astronaut set to: {name}, {gender}, {age} y/o, {weight} lb")

    # Highlight selected button
    for n, btn in self.astronaut_buttons.items():
        if n == name:
            btn.setChecked(True)
        else:
            btn.setChecked(False)

def set_current_activity_label(self, label):
    # Uncheck all buttons except the one clicked
    for key, btn in self.label_buttons.items():
        btn.setChecked(key == label)

    self.set_current_activity(label)

def update_data_collection_page(self):
    if not hasattr(self, 'latest_data'):
        return
    try:
        latest_text = self.mongo_output_area.toPlainText().strip()

        # Get the last non-empty line
        last_line = next(reversed([line for line in latest_text.splitlines() if line.strip()]), None)
        if not last_line:
            return

        # Parse it into a dictionary
        data = ast.literal_eval(last_line)

        # Save latest data
        self.latest_data = data

        # Create new labels dynamically on first run
        if not self.mongo_data_labels:
            for key, value in data.items():
                field_layout = QHBoxLayout()
                key_label = QLabel(f"{key}:")
                key_label.setFixedWidth(100)

                val_label = QLabel(str(value))
                val_label.setStyleSheet("font-weight: bold")

                field_layout.addWidget(key_label)
                field_layout.addWidget(val_label)

                self.data_labels_layout.addLayout(field_layout)
                self.mongo_data_labels[key] = val_label

        else:
            # Update existing labels
            for key, val in data.items():
                if key in self.mongo_data_labels:
                    val_str = f"{val:.1f}" if isinstance(val, float) and not val.is_integer() else str(int(val)) if isinstance(val, float) else str(val)
                    self.mongo_data_labels[key].setText(val_str)


        # Update count
        self.upload_label_counts[self.current_activity] = self.upload_label_counts.get(self.current_activity, 0) + 1

        # Duration
        elapsed = int(time.time() - self.upload_start_time)
        self.upload_duration_label.setText(f"Duration: {elapsed}s")

        # Percentages
        total = sum(self.upload_label_counts.values())
        breakdown = ", ".join([
            f"{label}: {int(100 * count / total)}%" for label, count in self.upload_label_counts.items()
        ])
        self.activity_distribution_label.setText(f"Activity Breakdown: {breakdown}")
    except Exception as e:
        print(f"Error updating data collection page: {e}")


def create_data_labels(self, layout):
    self.mongo_data_labels = {}  # Empty dict to be populated after first data update
    self.data_labels_layout = layout  # Save for later dynamic population


def set_current_activity(self, activity):
    self.current_activity = activity
    print(f"Current activity set to: {self.current_activity}")