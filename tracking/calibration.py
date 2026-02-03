"""Calibration system for finger press detection using angle-based thresholds."""

import json
import os
import time
from typing import Dict, Optional
from game.constants import (
    CALIBRATION_FILE, FINGER_NAMES, FINGER_DISPLAY_NAMES,
    FINGER_PRESS_THRESHOLD, FINGER_PRESS_ANGLE_THRESHOLD
)


class CalibrationManager:
    """Manages calibration data for finger press detection using angle-based thresholds."""

    def __init__(self, calibration_file: str = CALIBRATION_FILE):
        """Initialize the calibration manager."""
        self.calibration_file = calibration_file
        self.calibration_data = {}
        self.is_calibrated = False

        # Default thresholds (Y-position based, for backward compatibility)
        self.thresholds = {name: FINGER_PRESS_THRESHOLD for name in FINGER_NAMES}

        # Angle-based thresholds
        self.angle_thresholds = {name: FINGER_PRESS_ANGLE_THRESHOLD for name in FINGER_NAMES}
        self.baseline_angles = {name: None for name in FINGER_NAMES}

        # Calibration process state
        self.calibrating = False
        self.current_finger_index = 0
        self.calibration_phase = 'idle'  # 'waiting_hands', 'capturing_baseline', 'calibrating_finger', 'complete'

        # Baseline capture state
        self.baseline_samples = {name: [] for name in FINGER_NAMES}
        self.baseline_sample_count = 30  # Samples needed for baseline
        self.baseline_captured = False

        # Current finger angle tracking
        self.current_finger_angle = 0.0
        self.current_finger_angle_from_baseline = 0.0

        # Timing
        self.last_sample_time = 0
        self.sample_delay = 0.03  # 30ms between samples
        self.phase_start_time = 0

        # Auto-advance hold time (must hold at threshold for this long)
        self.hold_time_required = 0.5  # 500ms
        self.threshold_reached_time = None

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
            self.angle_thresholds = data.get('angle_thresholds', self.angle_thresholds)
            self.baseline_angles = data.get('baseline_angles', self.baseline_angles)
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
            'angle_thresholds': self.angle_thresholds,
            'baseline_angles': self.baseline_angles,
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
        """Get the press threshold for a specific finger (Y-position based)."""
        return self.thresholds.get(finger_name, FINGER_PRESS_THRESHOLD)

    def get_angle_threshold(self, finger_name: str) -> float:
        """Get the angle threshold for a specific finger."""
        return self.angle_thresholds.get(finger_name, FINGER_PRESS_ANGLE_THRESHOLD)

    def get_baseline_angle(self, finger_name: str) -> Optional[float]:
        """Get the baseline angle for a specific finger."""
        return self.baseline_angles.get(finger_name)

    def start_calibration(self):
        """Start the calibration process."""
        self.calibrating = True
        self.current_finger_index = 0
        self.calibration_phase = 'waiting_hands'
        self.baseline_samples = {name: [] for name in FINGER_NAMES}
        self.baseline_captured = False
        self.calibration_data = {}
        self.phase_start_time = time.time()
        self.threshold_reached_time = None
        self.current_finger_angle = 0.0
        self.current_finger_angle_from_baseline = 0.0
        print("Starting angle-based calibration process...")

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
        return {
            'calibrating': self.calibrating,
            'current_finger': self.get_current_finger(),
            'current_finger_display': self.get_current_finger_display(),
            'finger_index': self.current_finger_index,
            'total_fingers': len(FINGER_NAMES),
            'phase': self.calibration_phase,
            'baseline_captured': self.baseline_captured,
            'current_angle': self.current_finger_angle,
            'angle_from_baseline': self.current_finger_angle_from_baseline,
            'threshold_angle': FINGER_PRESS_ANGLE_THRESHOLD,
            'progress': self.current_finger_index / len(FINGER_NAMES),
            'threshold_reached': self.threshold_reached_time is not None,
            'hold_progress': self._get_hold_progress(),
        }

    def _get_hold_progress(self) -> float:
        """Get progress of holding at threshold (0.0 to 1.0)."""
        if self.threshold_reached_time is None:
            return 0.0
        elapsed = time.time() - self.threshold_reached_time
        return min(1.0, elapsed / self.hold_time_required)

    def update_calibration(self, hand_data: Dict, finger_angles: Dict) -> bool:
        """
        Update calibration with current hand data and finger angles.

        Args:
            hand_data: Current hand tracking data
            finger_angles: Dictionary of finger angles from hand tracker

        Returns:
            True if calibration is still in progress
        """
        if not self.calibrating:
            return False

        current_time = time.time()

        # Phase: Waiting for hands
        if self.calibration_phase == 'waiting_hands':
            # Check if both hands are visible
            left_visible = hand_data.get('left') is not None
            right_visible = hand_data.get('right') is not None

            if left_visible and right_visible:
                self.calibration_phase = 'capturing_baseline'
                self.phase_start_time = current_time
                print("Both hands detected. Capturing baseline - keep all fingers RELAXED...")
            return True

        # Phase: Capturing baseline for all fingers
        if self.calibration_phase == 'capturing_baseline':
            return self._update_baseline_capture(hand_data, finger_angles, current_time)

        # Phase: Calibrating individual fingers
        if self.calibration_phase == 'calibrating_finger':
            return self._update_finger_calibration(hand_data, finger_angles, current_time)

        return True

    def _update_baseline_capture(self, hand_data: Dict, finger_angles: Dict, current_time: float) -> bool:
        """Capture baseline angles for all fingers."""
        # Collect samples for all fingers
        if current_time - self.last_sample_time >= self.sample_delay:
            self.last_sample_time = current_time

            for finger_name in FINGER_NAMES:
                angle = finger_angles.get(finger_name, 0.0)
                self.baseline_samples[finger_name].append(angle)

            # Check if we have enough samples for all fingers
            min_samples = min(len(samples) for samples in self.baseline_samples.values())

            if min_samples >= self.baseline_sample_count:
                # Calculate baseline averages
                for finger_name in FINGER_NAMES:
                    samples = self.baseline_samples[finger_name]
                    avg = sum(samples) / len(samples)
                    self.baseline_angles[finger_name] = avg
                    print(f"Baseline for {finger_name}: {avg:.1f} degrees")

                self.baseline_captured = True
                self.calibration_phase = 'calibrating_finger'
                self.phase_start_time = current_time
                print(f"Baseline captured. Now calibrating {self.get_current_finger()}...")
                print(f"Press finger down past {FINGER_PRESS_ANGLE_THRESHOLD} degrees to calibrate.")

        return True

    def _update_finger_calibration(self, hand_data: Dict, finger_angles: Dict, current_time: float) -> bool:
        """Calibrate individual fingers by detecting when they reach the threshold angle."""
        current_finger = self.get_current_finger()
        if not current_finger:
            self._complete_calibration()
            return False

        # Check if the correct hand is visible
        hand_type = 'left' if 'left' in current_finger else 'right'
        if hand_data.get(hand_type) is None:
            self.threshold_reached_time = None
            return True

        # Get current angle and angle from baseline
        current_angle = finger_angles.get(current_finger, 0.0)
        baseline = self.baseline_angles.get(current_finger, 0.0)
        angle_from_baseline = current_angle - baseline

        self.current_finger_angle = current_angle
        self.current_finger_angle_from_baseline = angle_from_baseline

        # Check if finger has reached threshold
        if angle_from_baseline >= FINGER_PRESS_ANGLE_THRESHOLD:
            if self.threshold_reached_time is None:
                self.threshold_reached_time = current_time
                print(f"{current_finger} reached threshold ({angle_from_baseline:.1f} degrees)")

            # Check if held long enough
            if current_time - self.threshold_reached_time >= self.hold_time_required:
                self._calibrate_current_finger(current_angle, baseline, angle_from_baseline)
                self._advance_to_next_finger()
        else:
            # Reset hold timer if finger moved back
            if self.threshold_reached_time is not None:
                self.threshold_reached_time = None

        return True

    def _calibrate_current_finger(self, current_angle: float, baseline: float, angle_from_baseline: float):
        """Record calibration for the current finger."""
        finger_name = self.get_current_finger()

        # Store calibration data
        self.angle_thresholds[finger_name] = FINGER_PRESS_ANGLE_THRESHOLD
        self.calibration_data[finger_name] = {
            'baseline_angle': baseline,
            'calibrated_angle': current_angle,
            'angle_threshold': FINGER_PRESS_ANGLE_THRESHOLD,
            'recorded_press_angle': angle_from_baseline,
        }

        # Also update Y-position threshold for backward compatibility
        # (This will be less accurate but provides a fallback)
        self.thresholds[finger_name] = FINGER_PRESS_THRESHOLD

        print(f"Calibrated {finger_name}: baseline={baseline:.1f}, press_angle={angle_from_baseline:.1f}")

    def _advance_to_next_finger(self):
        """Advance to next finger in calibration sequence."""
        self.current_finger_index += 1
        self.threshold_reached_time = None
        self.current_finger_angle = 0.0
        self.current_finger_angle_from_baseline = 0.0

        if self.current_finger_index >= len(FINGER_NAMES):
            self._complete_calibration()
        else:
            self.phase_start_time = time.time()
            next_finger = self.get_current_finger()
            print(f"Moving to next finger: {next_finger}")

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
        self.baseline_samples = {name: [] for name in FINGER_NAMES}
        self.threshold_reached_time = None
        print("Calibration cancelled.")

    def reset_calibration(self):
        """Reset all calibration data."""
        self.calibration_data = {}
        self.thresholds = {name: FINGER_PRESS_THRESHOLD for name in FINGER_NAMES}
        self.angle_thresholds = {name: FINGER_PRESS_ANGLE_THRESHOLD for name in FINGER_NAMES}
        self.baseline_angles = {name: None for name in FINGER_NAMES}
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

        if self.calibration_phase == 'waiting_hands':
            return "Place BOTH hands above the sensor"

        if self.calibration_phase == 'capturing_baseline':
            return "Keep ALL fingers RELAXED - capturing baseline..."

        if self.calibration_phase == 'calibrating_finger':
            finger = self.get_current_finger_display()
            finger_full = self.get_current_finger()

            if not finger_full:
                return ""

            hand = "LEFT" if "left" in finger_full else "RIGHT"
            finger_name = finger_full.split('_')[1].upper()

            if self.threshold_reached_time is not None:
                hold_progress = self._get_hold_progress()
                return f"HOLD {hand} {finger_name} - {int(hold_progress * 100)}%"
            else:
                return f"Press {hand} {finger_name} down past {FINGER_PRESS_ANGLE_THRESHOLD} degrees"

        return ""

    # Legacy method for compatibility
    def confirm_phase_transition(self):
        """Legacy method - no longer needed with auto-advance."""
        pass
