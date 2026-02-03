"""Game UI components including HUD, menus, and overlays."""

import pygame
import math
from typing import Dict, List, Optional
from game.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, GAME_AREA_TOP, GAME_AREA_BOTTOM,
    STARTING_LIVES, FINGER_NAMES, FINGER_DISPLAY_NAMES, LANE_WIDTH,
    DIFFICULTY_LEVELS
)
from .colors import (
    WHITE, BLACK, RED, GREEN, YELLOW, GRAY, DARK_GRAY,
    HUD_TEXT, HUD_VALUE, LIVES_COLOR, SCORE_COLOR, DIFFICULTY_COLOR,
    DIFFICULTY_COLORS, LANE_COLOR, LANE_BORDER, BACKGROUND,
    CALIBRATION_BG, CALIBRATION_TEXT, FINGER_COLORS, EXPLOSION_COLORS
)


class GameUI:
    """Manages all game UI elements."""

    def __init__(self, surface: pygame.Surface):
        """
        Initialize the game UI.

        Args:
            surface: Main pygame surface to draw on
        """
        self.surface = surface
        self.fonts = {
            'small': pygame.font.Font(None, 24),
            'medium': pygame.font.Font(None, 36),
            'large': pygame.font.Font(None, 48),
            'title': pygame.font.Font(None, 72),
        }

        # Animation state
        self.score_pulse = 0
        self.lives_flash = 0
        self.explosions = []

    def update(self, dt: float = 1.0):
        """Update UI animations."""
        # Decay score pulse
        if self.score_pulse > 0:
            self.score_pulse -= 0.1 * dt

        # Decay lives flash
        if self.lives_flash > 0:
            self.lives_flash -= 0.1 * dt

        # Update explosions
        self.explosions = [e for e in self.explosions if e['lifetime'] > 0]
        for explosion in self.explosions:
            explosion['lifetime'] -= dt * 16  # roughly 60fps

    def draw_background(self):
        """Draw the game background."""
        self.surface.fill(BACKGROUND)

        # Draw stars
        for i in range(50):
            x = (i * 97) % WINDOW_WIDTH
            y = (i * 53) % GAME_AREA_BOTTOM
            size = (i % 3) + 1
            brightness = 100 + (i * 7) % 155
            pygame.draw.circle(self.surface, (brightness, brightness, brightness), (x, y), size)

    def draw_lanes(self, target_fingers: List[str] = None):
        """
        Draw the lane dividers and target indicators.

        Args:
            target_fingers: List of fingers with active missiles
        """
        target_fingers = target_fingers or []

        for i in range(10):
            x = i * LANE_WIDTH
            finger_name = FINGER_NAMES[i]

            # Lane background (subtle highlight for active lanes)
            if finger_name in target_fingers:
                # Highlight active lanes
                pygame.draw.rect(
                    self.surface,
                    (40, 40, 80),
                    (x, GAME_AREA_TOP, LANE_WIDTH, GAME_AREA_BOTTOM - GAME_AREA_TOP)
                )
            else:
                pygame.draw.rect(
                    self.surface,
                    LANE_COLOR,
                    (x, GAME_AREA_TOP, LANE_WIDTH, GAME_AREA_BOTTOM - GAME_AREA_TOP)
                )

            # Lane divider
            pygame.draw.line(
                self.surface,
                LANE_BORDER,
                (x, GAME_AREA_TOP),
                (x, GAME_AREA_BOTTOM),
                1
            )

            # Lane label at bottom
            label = self.fonts['small'].render(FINGER_DISPLAY_NAMES[i], True, FINGER_COLORS[finger_name])
            label_rect = label.get_rect(center=(x + LANE_WIDTH // 2, GAME_AREA_BOTTOM - 15))
            self.surface.blit(label, label_rect)

        # Draw bottom line (target zone)
        pygame.draw.line(
            self.surface,
            (100, 100, 150),
            (0, GAME_AREA_BOTTOM),
            (WINDOW_WIDTH, GAME_AREA_BOTTOM),
            3
        )

    def draw_hud(self, score: int, lives: int, difficulty: str, streak: int = 0):
        """
        Draw the heads-up display.

        Args:
            score: Current score
            lives: Remaining lives
            difficulty: Current difficulty level
            streak: Current correct answer streak
        """
        # Background bar
        pygame.draw.rect(self.surface, (30, 30, 50), (0, 0, WINDOW_WIDTH, GAME_AREA_TOP))
        pygame.draw.line(self.surface, (60, 60, 100), (0, GAME_AREA_TOP), (WINDOW_WIDTH, GAME_AREA_TOP), 2)

        # Score
        score_color = SCORE_COLOR
        if self.score_pulse > 0:
            pulse = abs(math.sin(self.score_pulse * 5))
            score_color = tuple(int(c + (255 - c) * pulse) for c in SCORE_COLOR)

        score_label = self.fonts['small'].render("SCORE", True, HUD_TEXT)
        score_value = self.fonts['large'].render(str(score), True, score_color)
        self.surface.blit(score_label, (20, 15))
        self.surface.blit(score_value, (20, 35))

        # Lives
        lives_label = self.fonts['small'].render("LIVES", True, HUD_TEXT)
        self.surface.blit(lives_label, (200, 15))

        for i in range(STARTING_LIVES):
            x = 200 + i * 35
            y = 45

            if i < lives:
                color = LIVES_COLOR
                if self.lives_flash > 0 and i == lives:
                    color = WHITE
                pygame.draw.polygon(self.surface, color, [
                    (x + 12, y), (x + 24, y + 10), (x + 12, y + 24), (x, y + 10)
                ])
            else:
                pygame.draw.polygon(self.surface, DARK_GRAY, [
                    (x + 12, y), (x + 24, y + 10), (x + 12, y + 24), (x, y + 10)
                ], 2)

        # Difficulty
        diff_color = DIFFICULTY_COLORS.get(difficulty, WHITE)
        diff_label = self.fonts['small'].render("DIFFICULTY", True, HUD_TEXT)
        diff_value = self.fonts['medium'].render(difficulty.upper(), True, diff_color)
        self.surface.blit(diff_label, (WINDOW_WIDTH - 200, 15))
        self.surface.blit(diff_value, (WINDOW_WIDTH - 200, 35))

        # Streak (if any)
        if streak > 0:
            streak_text = f"Streak: {streak}"
            streak_render = self.fonts['medium'].render(streak_text, True, YELLOW)
            self.surface.blit(streak_render, (WINDOW_WIDTH // 2 - streak_render.get_width() // 2, 40))

    def trigger_score_pulse(self, positive: bool = True):
        """Trigger a score animation."""
        self.score_pulse = 1.0 if positive else 0.5

    def trigger_lives_flash(self):
        """Trigger a lives lost flash."""
        self.lives_flash = 1.0

    def add_explosion(self, x: int, y: int, color: tuple = None):
        """Add an explosion effect at the given position."""
        self.explosions.append({
            'x': x,
            'y': y,
            'color': color or EXPLOSION_COLORS[0],
            'lifetime': 30,
            'particles': [
                {'dx': (i % 5 - 2) * 3, 'dy': (i // 5 - 2) * 3, 'size': 5 + i % 3}
                for i in range(20)
            ]
        })

    def draw_explosions(self):
        """Draw active explosions."""
        for explosion in self.explosions:
            progress = explosion['lifetime'] / 30
            for particle in explosion['particles']:
                px = explosion['x'] + particle['dx'] * (1 - progress) * 10
                py = explosion['y'] + particle['dy'] * (1 - progress) * 10
                size = int(particle['size'] * progress)
                if size > 0:
                    color_index = int((1 - progress) * (len(EXPLOSION_COLORS) - 1))
                    color = EXPLOSION_COLORS[color_index]
                    pygame.draw.circle(self.surface, color, (int(px), int(py)), size)

    def draw_pause_overlay(self, reason: str = "PAUSED"):
        """
        Draw the pause overlay.

        Args:
            reason: Text to display (e.g., "PAUSED", "HANDS NOT DETECTED")
        """
        # Semi-transparent overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.surface.blit(overlay, (0, 0))

        # Pause text
        pause_text = self.fonts['title'].render(reason, True, WHITE)
        pause_rect = pause_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 50))
        self.surface.blit(pause_text, pause_rect)

        # Instructions
        inst_text = self.fonts['medium'].render("Press SPACE to continue or ESC for menu", True, GRAY)
        inst_rect = inst_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 30))
        self.surface.blit(inst_text, inst_rect)

    def draw_game_over(self, score: int, high_score: int = 0):
        """Draw the game over screen."""
        # Overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.surface.blit(overlay, (0, 0))

        # Game Over text
        go_text = self.fonts['title'].render("GAME OVER", True, RED)
        go_rect = go_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80))
        self.surface.blit(go_text, go_rect)

        # Score
        score_text = self.fonts['large'].render(f"Final Score: {score}", True, WHITE)
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.surface.blit(score_text, score_rect)

        # High score
        if score >= high_score and high_score > 0:
            hs_text = self.fonts['medium'].render("NEW HIGH SCORE!", True, YELLOW)
        else:
            hs_text = self.fonts['medium'].render(f"High Score: {high_score}", True, GRAY)
        hs_rect = hs_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 50))
        self.surface.blit(hs_text, hs_rect)

        # Instructions
        inst_text = self.fonts['medium'].render("Press SPACE to play again or ESC to quit", True, GRAY)
        inst_rect = inst_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 120))
        self.surface.blit(inst_text, inst_rect)


class MenuUI:
    """Main menu and calibration menu UI."""

    def __init__(self, surface: pygame.Surface):
        """Initialize menu UI."""
        self.surface = surface
        self.fonts = {
            'small': pygame.font.Font(None, 28),
            'medium': pygame.font.Font(None, 42),
            'large': pygame.font.Font(None, 56),
            'title': pygame.font.Font(None, 80),
        }
        self.selected_option = 0
        self.animation_phase = 0

    def update(self, dt: float = 1.0):
        """Update animations."""
        self.animation_phase += 0.05 * dt

    def draw_main_menu(self, has_calibration: bool = False):
        """
        Draw the main menu.

        Args:
            has_calibration: Whether calibration data exists
        """
        self.surface.fill(BACKGROUND)

        # Draw decorative elements
        for i in range(100):
            x = (i * 97 + int(self.animation_phase * 10)) % WINDOW_WIDTH
            y = (i * 53) % WINDOW_HEIGHT
            size = (i % 3) + 1
            brightness = 50 + (i * 7) % 100
            pygame.draw.circle(self.surface, (brightness, brightness, brightness + 50), (x, y), size)

        # Title
        title = self.fonts['title'].render("FINGER INVADERS", True, WHITE)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 120))
        self.surface.blit(title, title_rect)

        subtitle = self.fonts['medium'].render("Leap Motion Edition", True, (150, 150, 200))
        sub_rect = subtitle.get_rect(center=(WINDOW_WIDTH // 2, 180))
        self.surface.blit(subtitle, sub_rect)

        # Menu options
        options = [
            ("Start Game", "Begin playing with current calibration" if has_calibration else "Calibration required first"),
            ("Calibrate", "Set up finger detection thresholds"),
            ("Quit", "Exit the game"),
        ]

        start_y = 300
        for i, (label, description) in enumerate(options):
            y = start_y + i * 80

            # Check if option is available
            available = True
            if i == 0 and not has_calibration:
                available = False

            # Selection indicator
            if i == self.selected_option:
                pulse = abs(math.sin(self.animation_phase * 3)) * 0.3 + 0.7
                color = tuple(int(c * pulse) for c in (255, 255, 100))

                # Draw selection box
                box_width = 400
                pygame.draw.rect(
                    self.surface,
                    (50, 50, 80),
                    (WINDOW_WIDTH // 2 - box_width // 2, y - 15, box_width, 60),
                    border_radius=10
                )
                pygame.draw.rect(
                    self.surface,
                    color,
                    (WINDOW_WIDTH // 2 - box_width // 2, y - 15, box_width, 60),
                    2,
                    border_radius=10
                )
            else:
                color = WHITE if available else DARK_GRAY

            # Label
            label_text = self.fonts['large'].render(label, True, color if available else DARK_GRAY)
            label_rect = label_text.get_rect(center=(WINDOW_WIDTH // 2, y + 5))
            self.surface.blit(label_text, label_rect)

            # Description
            desc_text = self.fonts['small'].render(description, True, GRAY if available else DARK_GRAY)
            desc_rect = desc_text.get_rect(center=(WINDOW_WIDTH // 2, y + 35))
            self.surface.blit(desc_text, desc_rect)

        # Instructions
        inst = self.fonts['small'].render("Use UP/DOWN arrows to select, ENTER to confirm", True, (100, 100, 150))
        inst_rect = inst.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 50))
        self.surface.blit(inst, inst_rect)

    def draw_calibration_menu(self, has_calibration: bool = False):
        """Draw the calibration start menu."""
        self.surface.fill(CALIBRATION_BG)

        # Title
        title = self.fonts['title'].render("CALIBRATION", True, WHITE)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 100))
        self.surface.blit(title, title_rect)

        # Instructions
        instructions = [
            "Calibration will help the game detect your finger presses accurately.",
            "",
            "New Angle-Based Calibration:",
            "1. Place BOTH hands comfortably above the Leap Motion sensor",
            "2. Keep ALL fingers RELAXED while baseline is captured",
            "3. When prompted, press each finger down past 30 degrees",
            "4. Hold briefly - it will auto-advance to the next finger",
            "",
            "No need to press any keys between fingers!",
            "",
            "Press SPACE to begin calibration",
            "Press ESC to return to menu",
        ]

        if has_calibration:
            instructions.append("")
            instructions.append("(You have existing calibration data that will be replaced)")

        y = 180
        for line in instructions:
            if line:
                color = CALIBRATION_TEXT if not line.startswith("(") else YELLOW
                if "30 degrees" in line or "auto-advance" in line:
                    color = (100, 255, 100)  # Highlight key info
                text = self.fonts['small'].render(line, True, color)
                self.surface.blit(text, (100, y))
            y += 28

    def move_selection(self, direction: int, max_options: int, has_calibration: bool):
        """Move menu selection."""
        self.selected_option = (self.selected_option + direction) % max_options

        # Skip unavailable options
        if self.selected_option == 0 and not has_calibration:
            self.selected_option = (self.selected_option + direction) % max_options

    def get_selected_option(self) -> int:
        """Get currently selected option index."""
        return self.selected_option
