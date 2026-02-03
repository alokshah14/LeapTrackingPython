"""Hand tracking and finger press detection."""

import time
import math
from typing import Dict, List, Optional, Tuple
from game.constants import (
    FINGER_NAMES, PRESS_DEBOUNCE_TIME, FINGER_PRESS_THRESHOLD,
    FINGER_PRESS_ANGLE_THRESHOLD
)


class HandTracker:
    """Tracks hands and detects finger presses using Leap Motion data."""

    def __init__(self, leap_controller, calibration_manager):
        """
        Initialize the hand tracker.

        Args:
            leap_controller: LeapController instance
            calibration_manager: CalibrationManager instance
        """
        self.leap = leap_controller
        self.calibration = calibration_manager

        # Current state
        self.hands_visible = {'left': False, 'right': False}
        self.finger_states = {name: False for name in FINGER_NAMES}
        self.finger_positions = {name: (0, 0, 0) for name in FINGER_NAMES}
        self.finger_relative_y = {name: 0.0 for name in FINGER_NAMES}
        self.finger_angles = {name: 0.0 for name in FINGER_NAMES}  # Flexion angles in degrees

        # Baseline angles for calibration (recorded when fingers are relaxed)
        self.baseline_angles = {name: None for name in FINGER_NAMES}

        # Press detection
        self.last_press_time = {name: 0 for name in FINGER_NAMES}
        self.press_events = []  # Queue of recent press events

        # Tracking state
        self.hands_missing_since = None

    def update(self) -> List[str]:
        """
        Update hand tracking and return list of new finger press events.

        Returns:
            List of finger names that were just pressed
        """
        current_time = time.time() * 1000  # Convert to ms

        # Get latest hand data from Leap
        hands_data = self.leap.update()

        # Update hand visibility
        self._update_hand_visibility(hands_data)

        # Update finger positions and detect presses
        new_presses = []

        for hand_type in ['left', 'right']:
            hand = hands_data.get(hand_type)
            if not hand:
                continue

            palm_y = hand['palm_position'][1]

            for finger_name, finger_data in hand['fingers'].items():
                full_name = f"{hand_type}_{finger_name}"
                tip_pos = finger_data['tip_position']

                # Store position
                self.finger_positions[full_name] = tip_pos

                # Calculate relative Y (tip relative to palm)
                relative_y = tip_pos[1] - palm_y
                self.finger_relative_y[full_name] = relative_y

                # Calculate finger flexion angle from bone directions
                if 'proximal_direction' in finger_data and 'intermediate_direction' in finger_data:
                    angle = self._calculate_flexion_angle(
                        finger_data['proximal_direction'],
                        finger_data['intermediate_direction']
                    )
                    self.finger_angles[full_name] = angle

                # Check for press using calibration threshold
                threshold = self.calibration.get_threshold(full_name)
                was_pressed = self.finger_states[full_name]
                is_pressed = relative_y < threshold

                # Detect new press with debounce
                if is_pressed and not was_pressed:
                    time_since_last = current_time - self.last_press_time[full_name]
                    if time_since_last >= PRESS_DEBOUNCE_TIME:
                        new_presses.append(full_name)
                        self.last_press_time[full_name] = current_time

                self.finger_states[full_name] = is_pressed

        self.press_events = new_presses
        return new_presses

    def _update_hand_visibility(self, hands_data: Dict):
        """Update hand visibility tracking."""
        current_time = time.time() * 1000

        left_visible = hands_data.get('left') is not None
        right_visible = hands_data.get('right') is not None

        self.hands_visible['left'] = left_visible
        self.hands_visible['right'] = right_visible

        # Track when hands went missing
        if not left_visible and not right_visible:
            if self.hands_missing_since is None:
                self.hands_missing_since = current_time
        else:
            self.hands_missing_since = None

    def are_hands_visible(self) -> bool:
        """Check if at least one hand is visible."""
        return self.hands_visible['left'] or self.hands_visible['right']

    def should_pause_game(self, delay_ms: float = 500) -> bool:
        """
        Check if game should pause due to missing hands.

        Args:
            delay_ms: How long hands must be missing before pausing

        Returns:
            True if game should pause
        """
        if self.hands_missing_since is None:
            return False

        current_time = time.time() * 1000
        return (current_time - self.hands_missing_since) >= delay_ms

    def get_finger_state(self, finger_name: str) -> bool:
        """Get current pressed state of a finger."""
        return self.finger_states.get(finger_name, False)

    def get_finger_position(self, finger_name: str) -> Tuple[float, float, float]:
        """Get current position of a fingertip."""
        return self.finger_positions.get(finger_name, (0, 0, 0))

    def get_finger_relative_y(self, finger_name: str) -> float:
        """Get finger tip Y position relative to palm."""
        return self.finger_relative_y.get(finger_name, 0.0)

    def get_all_finger_states(self) -> Dict[str, bool]:
        """Get pressed states for all fingers."""
        return self.finger_states.copy()

    def get_display_data(self) -> Dict:
        """
        Get data formatted for hand visualization display.

        Returns:
            Dictionary with hand display information
        """
        display_data = {
            'left': None,
            'right': None
        }

        hands_data = self.leap.hands_data

        for hand_type in ['left', 'right']:
            hand = hands_data.get(hand_type)
            if not hand:
                continue

            fingers = {}
            for finger_name, finger_data in hand['fingers'].items():
                full_name = f"{hand_type}_{finger_name}"
                fingers[finger_name] = {
                    'position': finger_data['tip_position'],
                    'pressed': self.finger_states.get(full_name, False),
                    'relative_y': self.finger_relative_y.get(full_name, 0.0),
                    'threshold': self.calibration.get_threshold(full_name),
                }

            display_data[hand_type] = {
                'palm_position': hand['palm_position'],
                'fingers': fingers,
                'visible': True,
            }

        return display_data

    def reset(self):
        """Reset tracking state."""
        self.finger_states = {name: False for name in FINGER_NAMES}
        self.press_events = []
        self.hands_missing_since = None

    def _calculate_flexion_angle(self, dir1: Tuple[float, float, float],
                                  dir2: Tuple[float, float, float]) -> float:
        """
        Calculate the angle between two bone direction vectors.

        Args:
            dir1: First direction vector (proximal bone)
            dir2: Second direction vector (intermediate bone)

        Returns:
            Angle in degrees between the two vectors
        """
        # Normalize vectors
        def normalize(v):
            mag = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
            if mag < 0.0001:
                return (0, 0, 0)
            return (v[0]/mag, v[1]/mag, v[2]/mag)

        n1 = normalize(dir1)
        n2 = normalize(dir2)

        # Calculate dot product
        dot = n1[0]*n2[0] + n1[1]*n2[1] + n1[2]*n2[2]

        # Clamp to prevent floating point errors with acos
        dot = max(-1.0, min(1.0, dot))

        # Calculate angle in degrees
        angle_rad = math.acos(dot)
        angle_deg = math.degrees(angle_rad)

        return angle_deg

    def get_finger_angle(self, finger_name: str) -> float:
        """Get current flexion angle of a finger in degrees."""
        return self.finger_angles.get(finger_name, 0.0)

    def get_finger_angle_from_baseline(self, finger_name: str) -> float:
        """
        Get the flexion angle relative to the baseline (rest position).

        Args:
            finger_name: Full finger name (e.g., 'left_index')

        Returns:
            Angle difference from baseline in degrees, or raw angle if no baseline
        """
        current_angle = self.finger_angles.get(finger_name, 0.0)
        baseline = self.baseline_angles.get(finger_name)

        if baseline is not None:
            return current_angle - baseline
        return current_angle

    def set_baseline_angle(self, finger_name: str):
        """Record the current angle as the baseline for a finger."""
        self.baseline_angles[finger_name] = self.finger_angles.get(finger_name, 0.0)

    def clear_baseline_angles(self):
        """Clear all baseline angles."""
        self.baseline_angles = {name: None for name in FINGER_NAMES}

    def get_all_finger_angles(self) -> Dict[str, float]:
        """Get flexion angles for all fingers."""
        return self.finger_angles.copy()
