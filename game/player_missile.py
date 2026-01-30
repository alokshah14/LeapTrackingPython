"""Player missile class that shoots upward from the bottom."""

import pygame
import math
from .constants import (
    PLAYER_MISSILE_WIDTH, PLAYER_MISSILE_HEIGHT, PLAYER_MISSILE_SPEED,
    GAME_AREA_TOP, GAME_AREA_BOTTOM, LANE_WIDTH, FINGER_NAMES
)
from ui.colors import MISSILE_PLAYER, FINGER_COLORS


class PlayerMissile:
    """Player missile that shoots upward to intercept enemy missiles."""

    def __init__(self, lane: int, target_missile=None):
        """
        Initialize a player missile in the specified lane.

        Args:
            lane: The lane index (0-9) for the missile
            target_missile: The enemy missile being targeted (for hit detection)
        """
        self.lane = lane
        self.finger_name = FINGER_NAMES[lane]
        self.width = PLAYER_MISSILE_WIDTH
        self.height = PLAYER_MISSILE_HEIGHT

        # Position missile in center of lane at bottom
        self.x = lane * LANE_WIDTH + (LANE_WIDTH - self.width) // 2
        self.y = GAME_AREA_BOTTOM - self.height

        # Speed (upward, so negative)
        self.speed = PLAYER_MISSILE_SPEED

        # Target tracking
        self.target_missile = target_missile
        self.has_target = target_missile is not None

        # State
        self.active = True
        self.hit_target = False

        # Visual properties
        self.color = FINGER_COLORS.get(self.finger_name, MISSILE_PLAYER)
        self.trail = []  # Trail positions for visual effect
        self.phase = 0

    def update(self, dt: float = 1.0):
        """
        Update missile position and check for collisions.

        Args:
            dt: Delta time multiplier
        """
        if not self.active:
            return

        # Store trail position
        self.trail.append((self.x + self.width // 2, self.y + self.height))
        if len(self.trail) > 10:
            self.trail.pop(0)

        # Move upward
        self.y -= self.speed * dt
        self.phase += 0.2

        # Check if reached top
        if self.y < GAME_AREA_TOP - self.height:
            self.active = False
            return

        # Check collision with target
        if self.has_target and self.target_missile and self.target_missile.active:
            if self.check_collision(self.target_missile):
                self.hit_target = True
                self.target_missile.destroy()
                self.active = False

    def check_collision(self, enemy_missile) -> bool:
        """Check if this missile collides with an enemy missile."""
        my_rect = self.get_rect()
        enemy_rect = enemy_missile.get_rect()
        return my_rect.colliderect(enemy_rect)

    def get_rect(self) -> pygame.Rect:
        """Get the missile's bounding rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def get_center(self) -> tuple:
        """Get the missile's center position."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def draw(self, surface: pygame.Surface):
        """
        Draw the missile on the given surface.

        Args:
            surface: Pygame surface to draw on
        """
        if not self.active and not self.hit_target:
            return

        # Draw trail
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(255 * (i / len(self.trail)) * 0.5)
            radius = 3 + i // 3
            trail_color = tuple(min(255, c + 50) for c in self.color)
            pygame.draw.circle(surface, trail_color, (int(tx), int(ty)), radius)

        if not self.active:
            return

        # Main missile body (sleeker design pointing up)
        points = [
            (self.x + self.width // 2, self.y),  # Nose (top)
            (self.x + self.width, self.y + self.height * 0.3),  # Right wing
            (self.x + self.width * 0.7, self.y + self.height),  # Right bottom
            (self.x + self.width * 0.3, self.y + self.height),  # Left bottom
            (self.x, self.y + self.height * 0.3),  # Left wing
        ]

        # Glow effect
        glow_intensity = abs(math.sin(self.phase)) * 0.3 + 0.7
        color = tuple(int(c * glow_intensity) for c in self.color)

        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, (200, 255, 200), points, 2)

        # Thruster flame (at bottom, pointing down)
        flame_height = 8 + int(abs(math.sin(self.phase * 2)) * 6)
        flame_points = [
            (self.x + self.width * 0.35, self.y + self.height),
            (self.x + self.width // 2, self.y + self.height + flame_height),
            (self.x + self.width * 0.65, self.y + self.height),
        ]
        flame_color = (100, 200, 255) if int(self.phase * 3) % 2 == 0 else (150, 255, 255)
        pygame.draw.polygon(surface, flame_color, flame_points)
