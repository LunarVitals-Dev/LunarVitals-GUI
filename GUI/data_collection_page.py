from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QGridLayout, QWidget
)
import time
from typing import Optional, Dict, Tuple
from collections import Counter, defaultdict

ACTIVITY_LABELS: Tuple[str, ...] = (
    "Idle",
    "Walking",
    "Lifting",
    "Crouching",
    "Skipping",
) 

DEFAULT_METS: Dict[str, float] = {  
    "Idle":      1.0,
    "Walking":   3.8,
    "Lifting":   4.0,
    "Crouching": 3.5,
    "Skipping":  8.0,
}

class ActivityTracker:
    """Keeps track of how long each activity runs, and reports the current leader."""
    def __init__(self, mets: dict[str, float] | None = None) -> None:
        self.mets = mets or DEFAULT_METS
        self.activities = ACTIVITY_LABELS
        self.reset()
        
    def set_astronaut(self, *, age: int, gender: str, weight: float) -> None:
        """Update demographic data (call once when the user selects an astronaut)."""
        self.age = age
        self.gender = gender
        self.weight_kg = weight * 0.453592

    def reset(self) -> None:
        self._durations: Counter[str] = Counter()
        self._current: Optional[str] = None
        self._t_start: Optional[float] = None
        self._oxygen_per_activity = defaultdict(float)
        self._oxygen_total = 0.0

    def update(self, activity: str) -> None:
        """
        Call when activity updates.
        Activity - pass in current activity
        """
        now = time.time()

        # First-ever call
        if self._current is None:
            self._current   = activity
            self._last_time = now
            return

        # Seconds since the *previous* update
        dt = now - self._last_time
        self._last_time = now                 

        # Accumulate for the activity that was active during dt
        self._durations[self._current] += dt
        self._add_oxygen(dt, self._current)

        # If label changed, just switch—no extra accounting
        if activity != self._current:
            self._current = activity
    
    def total_oxy(self) -> float:
        """
        Return total liters of oxygen consumed
        """
        return self._oxygen_total
    
    def oxy_breakdown(self) -> dict[str, float]:
        """
        Return oxygen per activity
        """
        return dict(self._oxygen_per_activity)
    
    def _effective_met(self, activity: str) -> float:
        base = self.mets.get(activity, DEFAULT_METS[activity])

        # gender adjustment: 20 % lower for females
        gender_factor = 0.8 if self.gender.lower().startswith("f") else 1.0

        # age adjustment: −1 % per year above 30 
        age_factor = max(0.6, 1.0 - 0.01 * max(0, self.age - 30))

        return base * gender_factor * age_factor

    def _add_oxygen(self, dt: float, activity: str) -> None:
        met = self._effective_met(activity)
        # 3.5 mL/kg/min → L/min
        rate_lpm = met * 3.5 * self.weight_kg / 1000.0
        used = rate_lpm * dt / 60.0
        self._oxygen_per_activity[activity] += used
        self._oxygen_total += used

    def _add_elapsed(self, now: float) -> None:
        if self._current is None or self._t_start is None:
            return
        dt = now - self._t_start

        # Find total time of prev activity
        self._durations[self._current] += dt

        # Accumulate oxygen of new activity segment
        self._add_oxygen(dt, self._current)

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
    
    items = [f"{lbl}: N/A" for lbl in ACTIVITY_LABELS]

    init_conf = f"{', '.join(items[:3])}\n{', '.join(items[3:])}"

    self.confidence_label_data_collection = QLabel(init_conf)
    self.confidence_label_data_collection.setWordWrap(True)

    lf.addWidget(self.confidence_label_data_collection)
    lf.addSpacing(20)
    
    self.upload_status = QLabel("Upload Status: <font color='red'>OFF</font>")
    lf.addWidget(self.upload_status)
    self.upload_toggle_button_data_collection = QPushButton("Start Upload")
    self.upload_toggle_button_data_collection.setCheckable(True)
    self.upload_toggle_button_data_collection.clicked.connect(self.toggle_upload_to_mongo)
    lf.addWidget(self.upload_toggle_button_data_collection)
    self.upload_duration_label = QLabel("Duration: 0s")
    lf.addWidget(self.upload_duration_label)
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
        btn.setStyleSheet("padding: 6px; font-size: 16px; font-weight: bold;")
        self.astronaut_buttons[name] = btn
        astro_layout.addWidget(btn)

    rf.addLayout(astro_layout)

    rf.addWidget(QLabel("Select Activity Label:"))

    self.label_buttons = {}
    button_layout = QGridLayout()

    for i, label in enumerate(ACTIVITY_LABELS):
        button = QPushButton()
        button.setCheckable(True)
        button.setText(label)
        button.setStyleSheet("padding: 10px; font-weight: bold; font-size: 16px;")
        button.clicked.connect(lambda checked, l=label: self.set_current_activity_label(l))
        self.label_buttons[label] = button
        button_layout.addWidget(button, i // 2, i % 2)

    rf.addLayout(button_layout)

    rf.addWidget(QLabel("Currently Collected Data:"))
    self.mongo_output_area = QTextEdit()
    self.mongo_output_area.setReadOnly(True)
    self.mongo_output_area.setFixedHeight(300)
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
        # Update count
        self.upload_label_counts[self.current_activity] = self.upload_label_counts.get(self.current_activity, 0) + 1

        # Duration
        if self.upload_start_time is not None:
            elapsed = int(time.time() - self.upload_start_time)
        else:
            elapsed = 0
        self.upload_duration_label.setText(f"Duration: {elapsed}s")

    except Exception as e:
        print(f"Error updating data collection page: {e}")


def create_data_labels(self, layout):
    self.mongo_data_labels = {}  # Empty dict to be populated after first data update
    self.data_labels_layout = layout  # Save for later dynamic population


def set_current_activity(self, activity):
    self.current_activity = activity
    print(f"Current activity set to: {self.current_activity}")