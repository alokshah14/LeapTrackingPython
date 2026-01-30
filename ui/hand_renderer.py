"""Hand visualization renderer for displaying Leap Motion hand tracking."""

import pygame
import math
from typing import Dict, List, Optional, Set
from game.constants import (
    WINDOW_WIDTH, GAME_AREA_BOTTOM, HAND_DISPLAY_HEIGHT,
    FINGER_NAMES, FINGER_DISPLAY_NAMES, PALM_RADIUS,
    FINGER_TIP_RADIUS, FINGER_JOINT_RADIUS, HAND_SCALE
)
from .colors import (
    HAND_COLOR, HAND_OUTLINE, FINGER_NORMAL, FINGER_HIGHLIGHT,
    FINGER_PRESSED, FINGER_COLORS, WHITE, BLACK, GRAY
)


class HandRenderer:
    """Renders hand visualization at bottom of game screen."""

    def __init__(self, surface: pygame.Surface):
        """
        Initialize the hand renderer.

        Args:
            surface: Main pygame surface to draw on
        """
        self.surface = surface
        self.hand_area_top = GAME_AREA_BOTTOM + 20
        self.hand_area_height = HAND_DISPLAY_HEIGHT

        # Center positions for each hand
        self.left_hand_center = (WINDOW_WIDTH // 4, self.hand_area_top + self.hand_area_height // 2)
        self.right_hand_center = (3 * WINDOW_WIDTH // 4, self.hand_area_top + self.hand_area_height // 2)

        # Finger layout offsets (relative to palm center)
        # Arranged as they would appear looking at your hands palm-down
        self.finger_offsets = {
            'pinky': (-80, -40),
            'ring': (-40, -60),
            'middle': (0, -70),
            'index': (40, -60),
            'thumb': (70, 0),
        }

        # Fingers that should be highlighted (target fingers)
        self.highlighted_fingers: Set[str] = set()

        # Pulse animation for highlights
        self.pulse_phase = 0

    def set_highlighted_fingers(self, fingers: List[str]):
        """
        Set which fingers should be highlighted.

        Args:
            fingers: List of finger names to highlight (e.g., ['left_index', 'right_thumb'])
        """
        self.highlighted_fingers = set(fingers)

    def clear_highlights(self):
        """Clear all finger highlights."""
        self.highlighted_fingers.clear()

    def update(self, dt: float = 1.0):
        """Update animations."""
        self.pulse_phase += 0.1 * dt

    def draw(self, hand_data: Dict, finger_states: Dict[str, bool]):
        """
        Draw the hand visualization.

        Args:
            hand_data: Dictionary with hand tracking data from HandTracker.get_display_data()
            finger_states: Dictionary mapping finger names to pressed state
        """
        # Draw background area
        pygame.draw.rect(
            self.surface,
            (20, 20, 40),
            (0, self.hand_area_top - 10, WINDOW_WIDTH, self.hand_area_height + 20)
        )
        pygame.draw.line(
            self.surface,
            (60, 60, 100),
            (0, self.hand_area_top - 10),
            (WINDOW_WIDTH, self.hand_area_top - 10),
            2
        )

        # Draw label
        font = pygame.font.Font(None, 28)
        label = font.render("Hand Tracking", True, (150, 150, 200))
        self.surface.blit(label, (WINDOW_WIDTH // 2 - label.get_width() // 2, self.hand_area_top - 5))

        # Draw each hand
        self._draw_hand('left', hand_data.get('left'), finger_states, self.left_hand_center)
        self._draw_hand('right', hand_data.get('right'), finger_states, self.right_hand_center, mirror=True)

        # Draw finger labels
        self._draw_finger_labels()

    def _draw_hand(self, hand_type: str, hand_data: Optional[Dict],
                   finger_states: Dict[str, bool], center: tuple, mirror: bool = False):
        """Draw a single hand."""
        cx, cy = center

        # Draw hand outline even if not tracked
        if hand_data is None:
            self._draw_missing_hand(center, hand_type)
            return

        # Draw palm
        pygame.draw.circle(self.surface, HAND_COLOR, center, PALM_RADIUS)
        pygame.draw.circle(self.surface, HAND_OUTLINE, center, PALM_RADIUS, 2)

        # Draw fingers
        for finger_name, offset in self.finger_offsets.items():
            full_name = f"{hand_type}_{finger_name}"
            ox, oy = offset

            # Mirror for right hand
            if mirror:
                ox = -ox

            finger_pos = (cx + int(ox * HAND_SCALE), cy + int(oy * HAND_SCALE))

            # Get finger state
            is_pressed = finger_states.get(full_name, False)
            is_highlighted = full_name in self.highlighted_fingers

            # Draw finger
            self._draw_finger(finger_pos, center, full_name, is_pressed, is_highlighted)

    def _draw_finger(self, tip_pos: tuple, palm_pos: tuple, finger_name: str,
                     is_pressed: bool, is_highlighted: bool):
        """Draw a single finger with connection to palm."""
        # Calculate intermediate joint position
        jx = palm_pos[0] + (tip_pos[0] - palm_pos[0]) * 0.5
        jy = palm_pos[1] + (tip_pos[1] - palm_pos[1]) * 0.5

        # Draw finger bone connections
        pygame.draw.line(self.surface, HAND_COLOR, palm_pos, (jx, jy), 8)
        pygame.draw.line(self.surface, HAND_COLOR, (jx, jy), tip_pos, 6)

        # Draw joint
        pygame.draw.circle(self.surface, HAND_OUTLINE, (int(jx), int(jy)), FINGER_JOINT_RADIUS)

        # Determine tip color
        if is_pressed:
            tip_color = FINGER_PRESSED
            radius = FINGER_TIP_RADIUS + 4
        elif is_highlighted:
            # Pulsing highlight effect
            pulse = abs(math.sin(self.pulse_phase * 2)) * 0.5 + 0.5
            tip_color = tuple(int(c * pulse + FINGER_HIGHLIGHT[i] * (1 - pulse))
                            for i, c in enumerate(FINGER_COLORS.get(finger_name, FINGER_HIGHLIGHT)))
            radius = FINGER_TIP_RADIUS + int(pulse * 6)
        else:
            tip_color = FINGER_COLORS.get(finger_name, FINGER_NORMAL)
            radius = FINGER_TIP_RADIUS

        # Draw fingertip
        pygame.draw.circle(self.surface, tip_color, tip_pos, radius)
        pygame.draw.circle(self.surface, WHITE, tip_pos, radius, 2)

        # Draw highlight ring for target fingers
        if is_highlighted and not is_pressed:
            ring_radius = radius + 8 + int(abs(math.sin(self.pulse_phase * 3)) * 5)
            pygame.draw.circle(self.surface, FINGER_HIGHLIGHT, tip_pos, ring_radius, 3)

    def _draw_missing_hand(self, center: tuple, hand_type: str):
        """Draw indicator for missing hand."""
        # Draw ghost outline
        pygame.draw.circle(self.surface, GRAY, center, PALM_RADIUS, 2)

        # Draw X
        font = pygame.font.Font(None, 48)
        text = font.render("?", True, GRAY)
        text_rect = text.get_rect(center=center)
        self.surface.blit(text, text_rect)

        # Label
        label_font = pygame.font.Font(None, 24)
        label = label_font.render(f"{hand_type.upper()} HAND NOT DETECTED", True, GRAY)
        label_rect = label.get_rect(center=(center[0], center[1] + PALM_RADIUS + 20))
        self.surface.blit(label, label_rect)

    def _draw_finger_labels(self):
        """Draw labels for each finger lane."""
        font = pygame.font.Font(None, 20)
        y = self.hand_area_top + self.hand_area_height - 15

        for i, (name, display) in enumerate(zip(FINGER_NAMES, FINGER_DISPLAY_NAMES)):
            x = i * (WINDOW_WIDTH // 10) + (WINDOW_WIDTH // 20)
            color = FINGER_COLORS.get(name, WHITE)

            # Draw colored marker
            pygame.draw.rect(self.surface, color, (x - 15, y - 2, 30, 4))

            # Draw label
            label = font.render(display, True, color)
            label_rect = label.get_rect(center=(x, y + 12))
            self.surface.blit(label, label_rect)


class CalibrationHandRenderer(HandRenderer):
    """Extended hand renderer for calibration mode with additional feedback."""

    def __init__(self, surface: pygame.Surface):
        super().__init__(surface)
        self.current_calibration_finger = None
        self.calibration_phase = 'idle'
        self.progress = 0.0

    def set_calibration_state(self, finger_name: str, phase: str, progress: float):
        """
        Set the current calibration state.

        Args:
            finger_name: Name of finger being calibrated
            phase: 'rest' or 'press'
            progress: 0.0 to 1.0 progress of current phase
        """
        self.current_calibration_finger = finger_name
        self.calibration_phase = phase
        self.progress = progress

        # Set highlight for current finger
        if finger_name:
            self.highlighted_fingers = {finger_name}
        else:
            self.highlighted_fingers.clear()

    def draw_calibration_overlay(self, instructions: str, status: Dict):
        """Draw calibration-specific UI overlay."""
        # Progress bar
        bar_width = 400
        bar_height = 20
        bar_x = (WINDOW_WIDTH - bar_width) // 2
        bar_y = GAME_AREA_BOTTOM + 50

        # Background
        pygame.draw.rect(self.surface, (40, 40, 60), (bar_x, bar_y, bar_width, bar_height))

        # Progress fill
        fill_width = int(bar_width * status['progress'])
        pygame.draw.rect(self.surface, (100, 200, 100), (bar_x, bar_y, fill_width, bar_height))

        # Border
        pygame.draw.rect(self.surface, WHITE, (bar_x, bar_y, bar_width, bar_height), 2)

        # Progress text
        font = pygame.font.Font(None, 24)
        progress_text = f"Finger {status['finger_index'] + 1} of {status['total_fingers']}"
        text = font.render(progress_text, True, WHITE)
        self.surface.blit(text, (bar_x + bar_width // 2 - text.get_width() // 2, bar_y + bar_height + 5))

        # Instructions
        inst_font = pygame.font.Font(None, 36)
        inst_text = inst_font.render(instructions, True, (255, 255, 100))
        self.surface.blit(inst_text, (WINDOW_WIDTH // 2 - inst_text.get_width() // 2, bar_y - 40))

        # Phase indicator
        phase_text = f"Phase: {status['phase'].upper()} ({status['samples_collected']}/{status['samples_needed']} samples)"
        phase_render = font.render(phase_text, True, (150, 150, 200))
        self.surface.blit(phase_render, (WINDOW_WIDTH // 2 - phase_render.get_width() // 2, bar_y + bar_height + 25))
