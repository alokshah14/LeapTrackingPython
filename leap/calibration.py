"""Calibration system for finger press detection."""

import json
import os
import time
from typing import Dict, Optional, Callable
from game.constants import (
    CALIBRATION_FILE, FINGER_NAMES, FINGER_DISPLAY_NAMES,
    FINGER_PRESS_THRESHOLD
)


class CalibrationManager:
    """Manages calibration data for finger press detection."""

    def __init__(self, calibration_file: str = CALIBRATION_FILE):
        """
        Initialize the calibration manager.

        Args:
            calibration_file: Path to the calibration data file
        """
        self.calibration_file = calibration_file
        self.calibration_data = {}
        self.is_calibrated = False

        # Default thresholds
        self.thresholds = {name: FINGER_PRESS_THRESHOLD for name in FINGER_NAMES}

        # Calibration process state
        self.calibrating = False
        self.current_finger_index = 0
        self.calibration_phase = 'idle'  # 'idle', 'rest', 'press', 'complete'
        self.samples = {'rest': [], 'press': []}
        self.sample_count = 10

        # Load existing calibration if available
        self._load_calibration()

    def _load_calibration(self) -> bool:
        """
        Load calibration data from file.

        Returns:
            True if calibration was loaded successfully
        """
        if not os.path.exists(self.calibration_file):
            return False

        try:
            with open(self.calibration_file, 'r') as f:
                data = json.load(f)

            self.calibration_data = data
            self.thresholds = data.get('thresholds', self.thresholds)
            self.is_calibrated = True
            print("Loaded existing calibration data.")
            return True

        except (json.JSONDecodeError, IOError) as e:
            print(f"Failed to load calibration: {e}")
            return False

    def _save_calibration(self):
        """Save calibration data to file."""
        data = {
            'thresholds': self.thresholds,
            'calibration_data': self.calibration_data,
            'timestamp': time.time(),
        }

        try:
            with open(self.calibration_file, 'w') as f:
                json.dump(data, f, indent=2)
            print("Calibration data saved.")
        except IOError as e:
            print(f"Failed to save calibration: {e}")

    def has_calibration(self) -> bool:
        """Check if calibration data exists."""
        return self.is_calibrated

    def get_threshold(self, finger_name: str) -> float:
        """
        Get the press threshold for a specific finger.

        Args:
            finger_name: Full finger name (e.g., 'left_index')

        Returns:
            Threshold value (relative Y position)
        """
        return self.thresholds.get(finger_name, FINGER_PRESS_THRESHOLD)

    def start_calibration(self):
        """Start the calibration process."""
        self.calibrating = True
        self.current_finger_index = 0
        self.calibration_phase = 'rest'
        self.samples = {'rest': [], 'press': []}
        self.calibration_data = {}
        print("Starting calibration process...")

    def get_current_finger(self) -> str:
        """Get the finger currently being calibrated."""
        if self.current_finger_index < len(FINGER_NAMES):
            return FINGER_NAMES[self.current_finger_index]
        return None

    def get_current_finger_display(self) -> str:
        """Get display name of current finger."""
        if self.current_finger_index < len(FINGER_DISPLAY_NAMES):
            return FINGER_DISPLAY_NAMES[self.current_finger_index]
        return ""

    def get_calibration_status(self) -> Dict:
        """
        Get current calibration status.

        Returns:
            Dictionary with calibration progress information
        """
        return {
            'calibrating': self.calibrating,
            'current_finger': self.get_current_finger(),
            'current_finger_display': self.get_current_finger_display(),
            'finger_index': self.current_finger_index,
            'total_fingers': len(FINGER_NAMES),
            'phase': self.calibration_phase,
            'samples_collected': len(self.samples.get(self.calibration_phase, [])),
            'samples_needed': self.sample_count,
            'progress': self.current_finger_index / len(FINGER_NAMES),
        }

    def add_sample(self, relative_y: float):
        """
        Add a sample during calibration.

        Args:
            relative_y: The relative Y position of the fingertip
        """
        if not self.calibrating:
            return

        phase = self.calibration_phase
        if phase in ['rest', 'press']:
            self.samples[phase].append(relative_y)

    def has_enough_samples(self) -> bool:
        """Check if enough samples collected for current phase."""
        phase = self.calibration_phase
        if phase in ['rest', 'press']:
            return len(self.samples[phase]) >= self.sample_count
        return False

    def advance_phase(self) -> bool:
        """
        Advance to next calibration phase.

        Returns:
            True if calibration should continue, False if complete
        """
        if self.calibration_phase == 'rest':
            self.calibration_phase = 'press'
            return True

        elif self.calibration_phase == 'press':
            # Calculate threshold for this finger
            finger_name = self.get_current_finger()
            self._calculate_threshold(finger_name)

            # Move to next finger
            self.current_finger_index += 1
            self.samples = {'rest': [], 'press': []}

            if self.current_finger_index >= len(FINGER_NAMES):
                self._complete_calibration()
                return False

            self.calibration_phase = 'rest'
            return True

        return False

    def _calculate_threshold(self, finger_name: str):
        """Calculate and store threshold for a finger."""
        rest_samples = self.samples['rest']
        press_samples = self.samples['press']

        if not rest_samples or not press_samples:
            self.thresholds[finger_name] = FINGER_PRESS_THRESHOLD
            return

        # Average positions
        rest_avg = sum(rest_samples) / len(rest_samples)
        press_avg = sum(press_samples) / len(press_samples)

        # Threshold is midpoint between rest and press
        # (Press should be lower Y value - finger moved down)
        threshold = (rest_avg + press_avg) / 2

        self.thresholds[finger_name] = threshold
        self.calibration_data[finger_name] = {
            'rest_avg': rest_avg,
            'press_avg': press_avg,
            'threshold': threshold,
        }

        print(f"Calibrated {finger_name}: rest={rest_avg:.2f}, press={press_avg:.2f}, threshold={threshold:.2f}")

    def _complete_calibration(self):
        """Complete the calibration process."""
        self.calibrating = False
        self.calibration_phase = 'complete'
        self.is_calibrated = True
        self._save_calibration()
        print("Calibration complete!")

    def cancel_calibration(self):
        """Cancel the calibration process."""
        self.calibrating = False
        self.calibration_phase = 'idle'
        self.current_finger_index = 0
        self.samples = {'rest': [], 'press': []}
        print("Calibration cancelled.")

    def reset_calibration(self):
        """Reset all calibration data."""
        self.calibration_data = {}
        self.thresholds = {name: FINGER_PRESS_THRESHOLD for name in FINGER_NAMES}
        self.is_calibrated = False

        if os.path.exists(self.calibration_file):
            try:
                os.remove(self.calibration_file)
                print("Calibration file deleted.")
            except IOError:
                pass

    def get_instructions(self) -> str:
        """Get instruction text for current calibration phase."""
        if not self.calibrating:
            return ""

        finger = self.get_current_finger_display()
        finger_full = self.get_current_finger()

        # Determine which hand
        hand = "LEFT" if "left" in finger_full else "RIGHT"
        finger_name = finger_full.split('_')[1].upper()

        if self.calibration_phase == 'rest':
            return f"Keep {hand} hand {finger_name} finger RELAXED (extended)"
        elif self.calibration_phase == 'press':
            return f"PRESS {hand} hand {finger_name} finger DOWN"

        return ""
