"""Enemy missile class that descends from the sky."""

import pygame
import random
import math
import time
from .constants import (
    MISSILE_WIDTH, MISSILE_HEIGHT, MISSILE_BASE_SPEED,
    GAME_AREA_TOP, GAME_AREA_BOTTOM, LANE_WIDTH, FINGER_NAMES
)
from ui.colors import MISSILE_ENEMY, FINGER_COLORS


class Missile:
    """Enemy missile that falls from the top of the screen."""

    def __init__(self, lane: int, speed_multiplier: float = 1.0):
        """
        Initialize a missile in the specified lane.

        Args:
            lane: The lane index (0-9) for the missile
            speed_multiplier: Difficulty-based speed adjustment
        """
        self.lane = lane
        self.finger_name = FINGER_NAMES[lane]
        self.width = MISSILE_WIDTH
        self.height = MISSILE_HEIGHT

        # Position missile in center of lane
        self.x = lane * LANE_WIDTH + (LANE_WIDTH - self.width) // 2
        self.y = GAME_AREA_TOP - self.height  # Start above screen

        # Speed settings
        self.base_speed = MISSILE_BASE_SPEED
        self.speed = self.base_speed * speed_multiplier

        # State
        self.active = True
        self.hit = False
        self.reached_bottom = False
        self.spawn_time_ms = time.time() * 1000  # Timestamp for reaction time calculation

        # Visual properties
        self.color = FINGER_COLORS.get(self.finger_name, MISSILE_ENEMY)
        self.pulse_phase = random.uniform(0, 2 * math.pi)

        # Warning indicator
        self.warning_shown = False

    def update(self, dt: float = 1.0):
        """
        Update missile position.

        Args:
            dt: Delta time multiplier
        """
        if not self.active:
            return

        self.y += self.speed * dt
        self.pulse_phase += 0.1

        # Check if reached bottom
        if self.y >= GAME_AREA_BOTTOM:
            self.reached_bottom = True
            self.active = False

    def get_rect(self) -> pygame.Rect:
        """Get the missile's bounding rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def get_center(self) -> tuple:
        """Get the missile's center position."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def destroy(self):
        """Mark the missile as destroyed (hit by player)."""
        self.hit = True
        self.active = False

    def draw(self, surface: pygame.Surface):
        """
        Draw the missile on the given surface.

        Args:
            surface: Pygame surface to draw on
        """
        if not self.active:
            return

        # Pulsing effect
        pulse = abs(math.sin(self.pulse_phase)) * 0.3 + 0.7

        # Main missile body
        rect = self.get_rect()

        # Draw missile body (pointed shape)
        points = [
            (self.x + self.width // 2, self.y),  # Nose
            (self.x + self.width, self.y + self.height * 0.7),  # Right
            (self.x + self.width * 0.7, self.y + self.height),  # Right fin
            (self.x + self.width * 0.3, self.y + self.height),  # Left fin
            (self.x, self.y + self.height * 0.7),  # Left
        ]

        # Draw with color
        color = tuple(int(c * pulse) for c in self.color)
        pygame.draw.polygon(surface, color, points)

        # Draw outline
        pygame.draw.polygon(surface, (255, 255, 255), points, 2)

        # Draw flame/thruster at bottom
        flame_colors = [(255, 100, 0), (255, 200, 0), (255, 255, 100)]
        flame_height = 10 + int(abs(math.sin(self.pulse_phase * 3)) * 10)
        flame_points = [
            (self.x + self.width * 0.35, self.y + self.height),
            (self.x + self.width // 2, self.y + self.height + flame_height),
            (self.x + self.width * 0.65, self.y + self.height),
        ]
        pygame.draw.polygon(surface, flame_colors[int(self.pulse_phase) % 3], flame_points)

        # Draw lane indicator text
        font = pygame.font.Font(None, 24)
        from .constants import FINGER_DISPLAY_NAMES
        text = font.render(FINGER_DISPLAY_NAMES[self.lane], True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.x + self.width // 2, self.y + self.height // 2))
        surface.blit(text, text_rect)

    def draw_warning(self, surface: pygame.Surface):
        """Draw warning indicator at top of lane."""
        if self.y < GAME_AREA_TOP + 50 and self.active:
            warning_y = GAME_AREA_TOP + 10
            center_x = self.x + self.width // 2

            # Flashing warning triangle
            if int(self.pulse_phase * 5) % 2 == 0:
                points = [
                    (center_x, warning_y),
                    (center_x - 15, warning_y + 25),
                    (center_x + 15, warning_y + 25),
                ]
                pygame.draw.polygon(surface, (255, 255, 0), points)
                pygame.draw.polygon(surface, (255, 0, 0), points, 2)
