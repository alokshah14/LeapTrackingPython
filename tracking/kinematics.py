"""Kinematics processor for calculating biomechanical metrics from finger movements."""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from game.constants import FINGER_NAMES, FINGER_PRESS_ANGLE_THRESHOLD


@dataclass
class TrialMetrics:
    """Biomechanical metrics for a single trial (finger press event)."""
    # Timing
    reaction_time_ms: float  # Time from missile spawn to press

    # Correctness
    target_finger: str
    pressed_finger: str
    is_wrong_finger: bool

    # Motion metrics
    target_path_length: float  # Path length of target finger
    non_target_path_lengths: Dict[str, float]  # Path lengths of other fingers
    motion_leakage_ratio: float  # MLR = sum(non-target) / target

    # Clean trial criteria
    coupled_keypress: bool  # Did another finger cross 30-degree threshold?
    is_clean_trial: bool  # Correct finger, no coupling, MLR <= 0.10


class KinematicsProcessor:
    """Processes frame data to calculate biomechanical metrics."""

    # Window configuration (milliseconds)
    WINDOW_BEFORE_MS = 200  # 200ms before press
    WINDOW_AFTER_MS = 400   # 400ms after press
    MLR_THRESHOLD = 0.10    # Maximum MLR for a "clean" trial

    def __init__(self, hand_tracker):
        """
        Initialize the kinematics processor.

        Args:
            hand_tracker: HandTracker instance for accessing frame buffer
        """
        self.hand_tracker = hand_tracker

    def calculate_trial_metrics(
        self,
        press_timestamp_ms: float,
        target_finger: str,
        pressed_finger: str,
        missile_spawn_time_ms: float
    ) -> TrialMetrics:
        """
        Calculate all biomechanical metrics for a trial.

        Args:
            press_timestamp_ms: Timestamp when the finger press was detected
            target_finger: The finger assigned to the missile
            pressed_finger: The finger the player actually pressed
            missile_spawn_time_ms: Timestamp when the missile was spawned

        Returns:
            TrialMetrics object containing all calculated metrics
        """
        # Get frames in the analysis window
        frames = self.hand_tracker.get_frames_in_window(
            press_timestamp_ms,
            self.WINDOW_BEFORE_MS,
            self.WINDOW_AFTER_MS
        )

        # Calculate reaction time
        reaction_time_ms = press_timestamp_ms - missile_spawn_time_ms

        # Calculate path lengths for all fingers
        path_lengths = self._calculate_all_path_lengths(frames)

        # Get target and non-target path lengths
        target_path_length = path_lengths.get(target_finger, 0.0)
        non_target_path_lengths = {
            name: length for name, length in path_lengths.items()
            if name != target_finger
        }

        # Calculate Motion Leakage Ratio
        if target_path_length > 0.001:  # Avoid division by zero
            total_non_target = sum(non_target_path_lengths.values())
            motion_leakage_ratio = total_non_target / target_path_length
        else:
            motion_leakage_ratio = float('inf') if sum(non_target_path_lengths.values()) > 0 else 0.0

        # Check for coupled keypress (any other finger crossed threshold)
        coupled_keypress = self._check_coupled_keypress(frames, pressed_finger)

        # Determine if this is a clean trial
        is_wrong_finger = (target_finger != pressed_finger)
        is_clean_trial = (
            not is_wrong_finger and
            not coupled_keypress and
            motion_leakage_ratio <= self.MLR_THRESHOLD
        )

        return TrialMetrics(
            reaction_time_ms=reaction_time_ms,
            target_finger=target_finger,
            pressed_finger=pressed_finger,
            is_wrong_finger=is_wrong_finger,
            target_path_length=target_path_length,
            non_target_path_lengths=non_target_path_lengths,
            motion_leakage_ratio=motion_leakage_ratio,
            coupled_keypress=coupled_keypress,
            is_clean_trial=is_clean_trial
        )

    def _calculate_all_path_lengths(self, frames: List) -> Dict[str, float]:
        """
        Calculate path length for each finger across all frames.

        Path length = sum of Euclidean distances between consecutive tip positions.

        Args:
            frames: List of FrameSnapshot objects

        Returns:
            Dictionary mapping finger names to their path lengths
        """
        path_lengths = {name: 0.0 for name in FINGER_NAMES}

        if len(frames) < 2:
            return path_lengths

        # Sort frames by timestamp
        sorted_frames = sorted(frames, key=lambda f: f.timestamp_ms)

        for i in range(1, len(sorted_frames)):
            prev_frame = sorted_frames[i - 1]
            curr_frame = sorted_frames[i]

            for finger_name in FINGER_NAMES:
                prev_finger = prev_frame.get_finger(finger_name)
                curr_finger = curr_frame.get_finger(finger_name)

                if prev_finger and curr_finger:
                    distance = self._euclidean_distance(
                        prev_finger.tip_position,
                        curr_finger.tip_position
                    )
                    path_lengths[finger_name] += distance

        return path_lengths

    def _euclidean_distance(
        self,
        pos1: Tuple[float, float, float],
        pos2: Tuple[float, float, float]
    ) -> float:
        """Calculate Euclidean distance between two 3D positions."""
        return math.sqrt(
            (pos2[0] - pos1[0]) ** 2 +
            (pos2[1] - pos1[1]) ** 2 +
            (pos2[2] - pos1[2]) ** 2
        )

    def _check_coupled_keypress(self, frames: List, pressed_finger: str) -> bool:
        """
        Check if any finger other than the pressed finger crossed the 30-degree threshold.

        Args:
            frames: List of FrameSnapshot objects
            pressed_finger: The finger that was intentionally pressed

        Returns:
            True if another finger was detected as pressed during the window
        """
        for frame in frames:
            for finger_name in FINGER_NAMES:
                if finger_name == pressed_finger:
                    continue

                finger = frame.get_finger(finger_name)
                if finger and finger.is_pressed:
                    return True

        return False

    def calculate_motion_amplitude(
        self,
        frames: List,
        finger_name: str
    ) -> float:
        """
        Calculate motion amplitude (path length) for a specific finger.

        Args:
            frames: List of FrameSnapshot objects
            finger_name: Name of the finger to analyze

        Returns:
            Total path length in millimeters
        """
        if len(frames) < 2:
            return 0.0

        sorted_frames = sorted(frames, key=lambda f: f.timestamp_ms)
        total_distance = 0.0

        for i in range(1, len(sorted_frames)):
            prev_finger = sorted_frames[i - 1].get_finger(finger_name)
            curr_finger = sorted_frames[i].get_finger(finger_name)

            if prev_finger and curr_finger:
                total_distance += self._euclidean_distance(
                    prev_finger.tip_position,
                    curr_finger.tip_position
                )

        return total_distance

    def get_mlr_rating(self, mlr: float) -> str:
        """
        Get a human-readable rating for an MLR value.

        Args:
            mlr: Motion Leakage Ratio value

        Returns:
            Rating string
        """
        if mlr <= 0.05:
            return "PERFECT"
        elif mlr <= 0.10:
            return "CLEAN"
        elif mlr <= 0.25:
            return "GOOD"
        elif mlr <= 0.50:
            return "FAIR"
        else:
            return "NEEDS WORK"
