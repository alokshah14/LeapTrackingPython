"""Calibration system for finger press detection."""

import json
import os
import time
from typing import Dict, Optional
from game.constants import (
    CALIBRATION_FILE, FINGER_NAMES, FINGER_DISPLAY_NAMES,
    FINGER_PRESS_THRESHOLD
)


class CalibrationManager:
    """Manages calibration data for finger press detection."""

    def __init__(self, calibration_file: str = CALIBRATION_FILE):
        """Initialize the calibration manager."""
        self.calibration_file = calibration_file
        self.calibration_data = {}
        self.is_calibrated = False

        # Default thresholds
        self.thresholds = {name: FINGER_PRESS_THRESHOLD for name in FINGER_NAMES}

        # Calibration process state
        self.calibrating = False
        self.current_finger_index = 0
        self.calibration_phase = 'idle'  # 'waiting_hands', 'rest', 'press', 'transitioning', 'complete'
        self.samples = {'rest': [], 'press': []}
        self.sample_count = 30  # More samples for accuracy
        self.sample_delay = 0.05  # 50ms between samples

        # Timing
        self.last_sample_time = 0
        self.phase_start_time = 0
        self.transition_duration = 1.0  # 1 second transition between phases

        # Load existing calibration if available
        self._load_calibration()

    def _load_calibration(self) -> bool:
        """Load calibration data from file."""
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
        """Get the press threshold for a specific finger."""
        return self.thresholds.get(finger_name, FINGER_PRESS_THRESHOLD)

    def start_calibration(self):
        """Start the calibration process."""
        self.calibrating = True
        self.current_finger_index = 0
        self.calibration_phase = 'waiting_hands'
        self.samples = {'rest': [], 'press': []}
        self.calibration_data = {}
        self.phase_start_time = time.time()
        print("Starting calibration process...")

    def get_current_finger(self) -> Optional[str]:
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
        """Get current calibration status."""
        phase = self.calibration_phase
        samples_count = len(self.samples.get('rest' if phase == 'rest' else 'press', []))

        return {
            'calibrating': self.calibrating,
            'current_finger': self.get_current_finger(),
            'current_finger_display': self.get_current_finger_display(),
            'finger_index': self.current_finger_index,
            'total_fingers': len(FINGER_NAMES),
            'phase': phase,
            'samples_collected': samples_count,
            'samples_needed': self.sample_count,
            'progress': self.current_finger_index / len(FINGER_NAMES),
            'waiting_for_space': phase == 'transitioning',
        }

    def update_calibration(self, hand_data: Dict, relative_y: float) -> bool:
        """
        Update calibration with current hand data.

        Args:
            hand_data: Current hand tracking data
            relative_y: Relative Y position of current finger

        Returns:
            True if calibration is still in progress
        """
        if not self.calibrating:
            return False

        current_time = time.time()

        # Check if waiting for hands
        if self.calibration_phase == 'waiting_hands':
            finger = self.get_current_finger()
            if finger:
                hand_type = 'left' if 'left' in finger else 'right'
                if hand_data.get(hand_type) is not None:
                    self.calibration_phase = 'rest'
                    self.phase_start_time = current_time
                    print(f"Hand detected, starting calibration for {finger}")
            return True

        # Transitioning phase - wait for user to press space
        if self.calibration_phase == 'transitioning':
            return True

        # Collect samples with delay
        if current_time - self.last_sample_time >= self.sample_delay:
            self.last_sample_time = current_time

            phase = self.calibration_phase
            if phase in ['rest', 'press']:
                self.samples[phase].append(relative_y)

                # Check if we have enough samples
                if len(self.samples[phase]) >= self.sample_count:
                    self._advance_to_next_phase()

        return True

    def confirm_phase_transition(self):
        """User pressed SPACE to confirm phase transition."""
        if self.calibration_phase == 'transitioning':
            self.samples['press'] = []  # Clear press samples
            self.calibration_phase = 'press'
            self.phase_start_time = time.time()
            print("Starting press phase...")

    def _advance_to_next_phase(self):
        """Advance to next calibration phase."""
        if self.calibration_phase == 'rest':
            # Go to transitioning state - wait for user to confirm
            self.calibration_phase = 'transitioning'
            self.phase_start_time = time.time()
            print("Rest samples collected. Press SPACE when ready to press finger.")

        elif self.calibration_phase == 'press':
            # Calculate threshold for this finger
            finger_name = self.get_current_finger()
            self._calculate_threshold(finger_name)

            # Move to next finger
            self.current_finger_index += 1
            self.samples = {'rest': [], 'press': []}

            if self.current_finger_index >= len(FINGER_NAMES):
                self._complete_calibration()
            else:
                self.calibration_phase = 'waiting_hands'
                self.phase_start_time = time.time()
                print(f"Moving to next finger: {self.get_current_finger()}")

    def _calculate_threshold(self, finger_name: str):
        """Calculate and store threshold for a finger."""
        rest_samples = self.samples['rest']
        press_samples = self.samples['press']

        if not rest_samples or not press_samples:
            self.thresholds[finger_name] = FINGER_PRESS_THRESHOLD
            return

        rest_avg = sum(rest_samples) / len(rest_samples)
        press_avg = sum(press_samples) / len(press_samples)

        # Threshold is midpoint between rest and press
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

        if not finger_full:
            return ""

        hand = "LEFT" if "left" in finger_full else "RIGHT"
        finger_name = finger_full.split('_')[1].upper()

        if self.calibration_phase == 'waiting_hands':
            return f"Place your {hand} hand above the sensor"
        elif self.calibration_phase == 'rest':
            return f"Keep {hand} {finger_name} finger RELAXED - collecting samples..."
        elif self.calibration_phase == 'transitioning':
            return f"Press SPACE, then PRESS {hand} {finger_name} finger DOWN"
        elif self.calibration_phase == 'press':
            return f"Hold {hand} {finger_name} finger PRESSED DOWN - collecting samples..."

        return ""
