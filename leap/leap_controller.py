"""Leap Motion controller interface."""

import time
from typing import Optional, Dict, List, Tuple

try:
    import leap
    LEAP_AVAILABLE = True
except ImportError:
    LEAP_AVAILABLE = False
    print("Warning: Leap Motion SDK not found. Running in simulation mode.")


class LeapController:
    """Interface for Leap Motion hand tracking."""

    def __init__(self):
        """Initialize the Leap Motion controller."""
        self.connection = None
        self.connected = False
        self.last_frame = None
        self.hands_data = {'left': None, 'right': None}
        self.simulation_mode = not LEAP_AVAILABLE

        if LEAP_AVAILABLE:
            self._init_leap()

    def _init_leap(self):
        """Initialize the Leap Motion connection."""
        try:
            self.connection = leap.Connection()
            self.connection.connect()
            self.connected = True
            print("Leap Motion connected successfully.")
        except Exception as e:
            print(f"Failed to connect to Leap Motion: {e}")
            self.simulation_mode = True

    def update(self) -> Dict:
        """
        Update and return the current hand tracking data.

        Returns:
            Dictionary containing hand data for left and right hands
        """
        if self.simulation_mode:
            return self._get_simulation_data()

        try:
            frame = self.connection.get_latest_frame()
            if frame:
                self.last_frame = frame
                self.hands_data = self._process_frame(frame)
        except Exception as e:
            print(f"Error reading Leap frame: {e}")

        return self.hands_data

    def _process_frame(self, frame) -> Dict:
        """Process a Leap frame and extract hand data."""
        hands = {'left': None, 'right': None}

        for hand in frame.hands:
            hand_type = 'left' if hand.type == leap.HandType.Left else 'right'

            # Extract finger data
            fingers = {}
            finger_names = ['thumb', 'index', 'middle', 'ring', 'pinky']

            for i, digit in enumerate(hand.digits):
                finger_name = finger_names[i]
                tip = digit.distal.next_joint  # Fingertip position

                fingers[finger_name] = {
                    'tip_position': (tip.x, tip.y, tip.z),
                    'extended': digit.is_extended,
                }

            # Get palm data
            palm = hand.palm

            hands[hand_type] = {
                'visible': True,
                'palm_position': (palm.position.x, palm.position.y, palm.position.z),
                'palm_normal': (palm.normal.x, palm.normal.y, palm.normal.z),
                'fingers': fingers,
                'grab_strength': hand.grab_strength,
                'pinch_strength': hand.pinch_strength,
            }

        return hands

    def _get_simulation_data(self) -> Dict:
        """Return simulated hand data for testing without Leap Motion."""
        # Return None to indicate no hands (will be replaced by keyboard simulation)
        return {'left': None, 'right': None}

    def get_hands_visible(self) -> Tuple[bool, bool]:
        """
        Check if hands are currently visible.

        Returns:
            Tuple of (left_visible, right_visible)
        """
        left_visible = self.hands_data['left'] is not None
        right_visible = self.hands_data['right'] is not None
        return left_visible, right_visible

    def get_finger_positions(self) -> Dict:
        """
        Get positions of all fingertips.

        Returns:
            Dictionary mapping finger names to positions
        """
        positions = {}

        for hand_type in ['left', 'right']:
            hand = self.hands_data[hand_type]
            if hand:
                for finger_name, finger_data in hand['fingers'].items():
                    key = f"{hand_type}_{finger_name}"
                    positions[key] = finger_data['tip_position']

        return positions

    def is_connected(self) -> bool:
        """Check if Leap Motion is connected."""
        return self.connected and not self.simulation_mode

    def cleanup(self):
        """Clean up the Leap Motion connection."""
        if self.connection:
            try:
                self.connection.disconnect()
            except:
                pass


class SimulatedLeapController(LeapController):
    """Simulated Leap controller that uses keyboard input for testing."""

    def __init__(self):
        """Initialize simulated controller."""
        self.connected = False
        self.simulation_mode = True
        self.hands_data = {'left': None, 'right': None}

        # Simulated hand state
        self.simulated_hands_visible = True
        self.simulated_finger_states = {
            'left_pinky': 0.0,
            'left_ring': 0.0,
            'left_middle': 0.0,
            'left_index': 0.0,
            'left_thumb': 0.0,
            'right_thumb': 0.0,
            'right_index': 0.0,
            'right_middle': 0.0,
            'right_ring': 0.0,
            'right_pinky': 0.0,
        }

        # Base positions for simulation
        self.base_palm_y = 150.0
        self.base_finger_y = 200.0

    def set_hands_visible(self, visible: bool):
        """Set whether hands are visible in simulation."""
        self.simulated_hands_visible = visible

    def set_finger_pressed(self, finger_name: str, pressed: bool):
        """
        Simulate a finger press.

        Args:
            finger_name: Name of finger (e.g., 'left_index')
            pressed: Whether finger is pressed (True) or released (False)
        """
        if finger_name in self.simulated_finger_states:
            # Lower Y value means pressed (finger moved down)
            self.simulated_finger_states[finger_name] = -50.0 if pressed else 0.0

    def update(self) -> Dict:
        """Update and return simulated hand data."""
        if not self.simulated_hands_visible:
            self.hands_data = {'left': None, 'right': None}
            return self.hands_data

        # Generate simulated hand data
        for hand_type in ['left', 'right']:
            fingers = {}
            finger_names = ['thumb', 'index', 'middle', 'ring', 'pinky']

            for finger_name in finger_names:
                key = f"{hand_type}_{finger_name}"
                offset = self.simulated_finger_states.get(key, 0.0)

                # Calculate tip position
                tip_y = self.base_finger_y + offset

                fingers[finger_name] = {
                    'tip_position': (0.0, tip_y, 0.0),
                    'extended': offset >= 0,
                }

            self.hands_data[hand_type] = {
                'visible': True,
                'palm_position': (0.0, self.base_palm_y, 0.0),
                'palm_normal': (0.0, -1.0, 0.0),
                'fingers': fingers,
                'grab_strength': 0.0,
                'pinch_strength': 0.0,
            }

        return self.hands_data

    def cleanup(self):
        """No cleanup needed for simulation."""
        pass
