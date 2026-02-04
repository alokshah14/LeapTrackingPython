#!/usr/bin/env python3
"""
Finger Invaders - A Leap Motion finger individuation game.

A Space Invaders-style game where players use finger presses detected by
Leap Motion to shoot down incoming missiles. Each missile is assigned to
a specific finger, and players must press the correct finger to destroy it.
"""

import pygame
import sys
from typing import Optional

# Initialize pygame
pygame.init()

# Import game modules
from game.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS, GAME_TITLE,
    FINGER_NAMES
)
from game.game_engine import GameEngine, GameState
from tracking.leap_controller import LeapController, SimulatedLeapController
from tracking.hand_tracker import HandTracker
from tracking.calibration import CalibrationManager
from tracking.session_logger import SessionLogger
from tracking.kinematics import KinematicsProcessor
from tracking.trial_summary import TrialSummaryExporter
from ui.game_ui import GameUI, MenuUI
from ui.hand_renderer import HandRenderer, CalibrationHandRenderer
from ui.colors import BACKGROUND
from game.sound_manager import SoundManager


class FingerInvaders:
    """Main game application class."""

    def __init__(self):
        """Initialize the game application."""
        # Set up display
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(GAME_TITLE)
        self.clock = pygame.time.Clock()

        # Initialize Leap Motion
        self.leap_controller = LeapController()
        if self.leap_controller.simulation_mode:
            print("Running in simulation mode - use keyboard for input")
            self.leap_controller = SimulatedLeapController()

        # Initialize calibration and hand tracking
        self.calibration = CalibrationManager()
        self.hand_tracker = HandTracker(self.leap_controller, self.calibration)

        # Initialize game engine
        self.game_engine = GameEngine(self.hand_tracker, self.calibration)

        # Initialize session logger
        self.session_logger = SessionLogger()

        # Initialize trial summary exporter for clean biomechanics output
        self.trial_summary = TrialSummaryExporter()

        # Initialize kinematics processor for biomechanical analysis
        self.kinematics = KinematicsProcessor(self.hand_tracker)

        # Initialize sound manager
        self.sound_manager = SoundManager()

        # Initialize UI components
        self.game_ui = GameUI(self.screen)
        self.menu_ui = MenuUI(self.screen)
        self.hand_renderer = HandRenderer(self.screen)
        self.calibration_renderer = CalibrationHandRenderer(self.screen)

        # Keyboard simulation mapping (for testing without Leap Motion)
        self.key_finger_map = {
            pygame.K_q: 'left_pinky',
            pygame.K_w: 'left_ring',
            pygame.K_e: 'left_middle',
            pygame.K_r: 'left_index',
            pygame.K_t: 'left_thumb',
            pygame.K_y: 'right_thumb',
            pygame.K_u: 'right_index',
            pygame.K_i: 'right_middle',
            pygame.K_o: 'right_ring',
            pygame.K_p: 'right_pinky',
        }

        # Running state
        self.running = True

    def run(self):
        """Main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 16.67  # Normalize to 60fps

            # Handle events
            self._handle_events()

            # Update
            self._update(dt)

            # Render
            self._render()

            pygame.display.flip()

        self._cleanup()

    def _handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

            elif event.type == pygame.KEYUP:
                self._handle_keyup(event)

    def _handle_keydown(self, event):
        """Handle key press events."""
        state = self.game_engine.state

        # Global keys
        if event.key == pygame.K_m:
            # Toggle sound
            enabled = self.sound_manager.toggle_sound()
            print(f"Sound {'enabled' if enabled else 'disabled'}")

        elif event.key == pygame.K_b:
            # Toggle angle bars during gameplay
            if state == GameState.PLAYING:
                enabled = self.hand_renderer.toggle_angle_bars()
                print(f"Angle bars {'enabled' if enabled else 'disabled'}")

        elif event.key == pygame.K_ESCAPE:
            if state == GameState.PLAYING:
                self.game_engine.pause_game()
            elif state == GameState.PAUSED:
                # End session when leaving game
                game_state = self.game_engine.get_game_state()
                self.session_logger.end_session(game_state['score'], game_state['lives'])
                self.trial_summary.end_session(game_state['score'])
                self.game_engine.state = GameState.MENU
            elif state == GameState.GAME_OVER:
                self.game_engine.state = GameState.MENU
            elif state == GameState.CALIBRATING:
                self.calibration.cancel_calibration()
                self.game_engine.state = GameState.MENU
            elif state == GameState.CALIBRATION_MENU:
                self.game_engine.state = GameState.MENU

        elif event.key == pygame.K_SPACE:
            if state == GameState.PAUSED:
                self.game_engine.resume_game()
            elif state == GameState.GAME_OVER:
                # End previous session and start new one
                game_state = self.game_engine.get_game_state()
                self.session_logger.end_session(game_state['score'], game_state['lives'])
                self.trial_summary.end_session(game_state['score'])
                self.game_engine.start_game()
                self.session_logger.start_session(self.calibration.calibration_data)
                self.trial_summary.start_session()
            elif state == GameState.CALIBRATION_MENU:
                self.calibration.start_calibration()
                self.game_engine.state = GameState.CALIBRATING
            elif state == GameState.CALIBRATING:
                # Confirm phase transition in calibration
                self.calibration.confirm_phase_transition()

        # Menu navigation
        elif state == GameState.MENU:
            if event.key == pygame.K_UP:
                self.menu_ui.move_selection(-1, 3, self.calibration.has_calibration())
            elif event.key == pygame.K_DOWN:
                self.menu_ui.move_selection(1, 3, self.calibration.has_calibration())
            elif event.key == pygame.K_RETURN:
                self._handle_menu_selection()

        # Keyboard simulation for finger presses (in simulation mode)
        elif state == GameState.PLAYING or state == GameState.CALIBRATING:
            if isinstance(self.leap_controller, SimulatedLeapController):
                if event.key in self.key_finger_map:
                    finger = self.key_finger_map[event.key]
                    self.leap_controller.set_finger_pressed(finger, True)

    def _handle_keyup(self, event):
        """Handle key release events."""
        # Keyboard simulation for finger releases
        if isinstance(self.leap_controller, SimulatedLeapController):
            if event.key in self.key_finger_map:
                finger = self.key_finger_map[event.key]
                self.leap_controller.set_finger_pressed(finger, False)

    def _handle_menu_selection(self):
        """Handle menu option selection."""
        option = self.menu_ui.get_selected_option()

        if option == 0 and self.calibration.has_calibration():
            # Start Game
            self.game_engine.start_game()
            # Start session logging with calibration data
            self.session_logger.start_session(self.calibration.calibration_data)
            self.trial_summary.start_session()
        elif option == 1:
            # Calibrate
            self.game_engine.state = GameState.CALIBRATION_MENU
        elif option == 2:
            # Quit
            self.running = False

    def _update(self, dt: float):
        """Update game state."""
        state = self.game_engine.state

        if state == GameState.PLAYING:
            events = self.game_engine.update(dt)

            # Get current hand data for logging
            hand_data = self.leap_controller.update()
            game_state = self.game_engine.get_game_state()

            # Log finger press events with biomechanical metrics and play sounds
            for press_event in events.get('finger_presses', []):
                # Calculate biomechanical trial metrics
                trial_metrics = None
                if press_event['target']:  # Only calculate if there was a target
                    trial_metrics = self.kinematics.calculate_trial_metrics(
                        press_timestamp_ms=press_event['press_time_ms'],
                        target_finger=press_event['target'],
                        pressed_finger=press_event['finger'],
                        missile_spawn_time_ms=press_event['missile_spawn_time_ms']
                    )

                    # Show clean trial indicator if applicable
                    if trial_metrics.is_clean_trial:
                        self.hand_renderer.show_clean_trial(trial_metrics.motion_leakage_ratio)

                    # Record trial for clean summary export
                    self.trial_summary.record_trial(
                        target_finger=press_event['target'],
                        pressed_finger=press_event['finger'],
                        trial_metrics=trial_metrics
                    )

                self.session_logger.log_finger_press(
                    finger_pressed=press_event['finger'],
                    target_finger=press_event['target'],
                    is_correct=press_event['correct'],
                    left_hand_data=hand_data.get('left'),
                    right_hand_data=hand_data.get('right'),
                    score=game_state['score'],
                    lives=game_state['lives'],
                    difficulty=game_state['difficulty'],
                    trial_metrics=trial_metrics
                )

                # Play fire sound for every finger press
                self.sound_manager.play_fire()

                # Play hit or miss sound based on correctness
                if press_event['correct']:
                    self.sound_manager.play_hit()
                else:
                    self.sound_manager.play_miss()

            # Log missed missiles
            for missed in events.get('missiles_missed', []):
                self.session_logger.log_missile_missed(
                    target_finger=missed,
                    left_hand_data=hand_data.get('left'),
                    right_hand_data=hand_data.get('right'),
                    score=game_state['score'],
                    lives=game_state['lives'],
                    difficulty=game_state['difficulty']
                )

            # Handle events for UI feedback
            if events['score_change'] > 0:
                self.game_ui.trigger_score_pulse(True)
            elif events['score_change'] < 0:
                self.game_ui.trigger_score_pulse(False)

            if events['life_lost']:
                self.game_ui.trigger_lives_flash()
                self.sound_manager.play_life_lost()

            for pos in events['missile_destroyed']:
                self.game_ui.add_explosion(pos[0], pos[1])
                self.sound_manager.play_explosion()

            # Update hand highlighting
            self.hand_renderer.set_highlighted_fingers(self.game_engine.get_highlighted_fingers())

            # Update finger angle data for display
            finger_angles = self.hand_tracker.get_all_finger_angles()
            self.hand_renderer.set_finger_angles(
                finger_angles,
                self.calibration.baseline_angles
            )

        elif state == GameState.CALIBRATING:
            self._update_calibration(dt)

        elif state == GameState.PAUSED:
            # Check if hands returned
            self.hand_tracker.update()
            if self.hand_tracker.are_hands_visible():
                if self.game_engine.pause_reason == "HANDS NOT DETECTED":
                    self.game_engine.resume_game()

        # Update UI animations
        self.game_ui.update(dt)
        self.menu_ui.update(dt)
        self.hand_renderer.update(dt)

    def _update_calibration(self, dt: float):
        """Update calibration process."""
        if not self.calibration.calibrating:
            self.game_engine.state = GameState.MENU
            return

        # Update hand tracking to get current finger positions and angles
        self.hand_tracker.update()

        current_finger = self.calibration.get_current_finger()

        # Get hand data and all finger angles
        hand_data = self.leap_controller.update()
        finger_angles = self.hand_tracker.get_all_finger_angles()

        # Update calibration with current data
        still_calibrating = self.calibration.update_calibration(hand_data, finger_angles)

        if not still_calibrating:
            self.game_engine.state = GameState.MENU

        # Update calibration renderer
        status = self.calibration.get_calibration_status()
        self.calibration_renderer.set_calibration_state(
            current_finger,
            status['phase'],
            status['progress']
        )

        # Update angle data for display
        self.calibration_renderer.set_angle_data(
            status.get('current_angle', 0.0),
            status.get('angle_from_baseline', 0.0),
            status.get('threshold_angle', 30.0),
            finger_angles
        )

    def _render(self):
        """Render the current game state."""
        state = self.game_engine.state

        if state == GameState.MENU:
            self.menu_ui.draw_main_menu(self.calibration.has_calibration())

        elif state == GameState.CALIBRATION_MENU:
            self.menu_ui.draw_calibration_menu(self.calibration.has_calibration())

        elif state == GameState.CALIBRATING:
            self._render_calibration()

        elif state == GameState.PLAYING:
            self._render_game()

        elif state == GameState.PAUSED:
            self._render_game()
            self.game_ui.draw_pause_overlay(self.game_engine.pause_reason)

        elif state == GameState.GAME_OVER:
            self._render_game()
            game_state = self.game_engine.get_game_state()
            self.game_ui.draw_game_over(game_state['score'], game_state['high_score'])

    def _render_game(self):
        """Render the main game."""
        game_state = self.game_engine.get_game_state()

        # Background
        self.game_ui.draw_background()

        # Lanes
        self.game_ui.draw_lanes(game_state['target_fingers'])

        # Enemy missiles
        for missile in game_state['enemy_missiles']:
            missile.draw(self.screen)
            missile.draw_warning(self.screen)

        # Player missiles
        for missile in game_state['player_missiles']:
            missile.draw(self.screen)

        # Explosions
        self.game_ui.draw_explosions()

        # HUD
        self.game_ui.draw_hud(
            game_state['score'],
            game_state['lives'],
            game_state['difficulty'],
            game_state['streak']
        )

        # Hand visualization
        hand_data = self.hand_tracker.get_display_data()
        finger_states = self.hand_tracker.get_all_finger_states()
        self.hand_renderer.draw(hand_data, finger_states)

    def _render_calibration(self):
        """Render calibration screen."""
        self.screen.fill(BACKGROUND)

        # Get calibration status
        status = self.calibration.get_calibration_status()
        instructions = self.calibration.get_instructions()

        # Draw hand visualization
        hand_data = self.hand_tracker.get_display_data()
        finger_states = self.hand_tracker.get_all_finger_states()
        self.calibration_renderer.draw(hand_data, finger_states)

        # Draw calibration overlay
        self.calibration_renderer.draw_calibration_overlay(instructions, status)

        # Draw title
        font = pygame.font.Font(None, 56)
        title = font.render("CALIBRATION MODE", True, (255, 255, 255))
        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 30))

        # Draw instructions for simulation mode
        if isinstance(self.leap_controller, SimulatedLeapController):
            sim_font = pygame.font.Font(None, 24)
            sim_text = sim_font.render(
                "Simulation Mode: Use Q-W-E-R-T (left) and Y-U-I-O-P (right) keys",
                True, (150, 150, 200)
            )
            self.screen.blit(sim_text, (WINDOW_WIDTH // 2 - sim_text.get_width() // 2, 80))

    def _cleanup(self):
        """Clean up resources."""
        # End any active session
        if self.session_logger.session_data:
            game_state = self.game_engine.get_game_state()
            self.session_logger.end_session(game_state['score'], game_state['lives'])
            self.trial_summary.end_session(game_state['score'])

        self.leap_controller.cleanup()
        pygame.quit()


def main():
    """Entry point for the game."""
    print("=" * 50)
    print("  FINGER INVADERS - Leap Motion Edition")
    print("=" * 50)
    print()
    print("Controls:")
    print("  - Arrow keys: Navigate menus")
    print("  - Enter: Select menu option")
    print("  - Space: Start/Resume/Restart")
    print("  - Escape: Pause/Menu/Quit")
    print("  - M: Toggle sound on/off")
    print("  - B: Toggle angle bars display")
    print()
    print("Simulation Mode Keys (when Leap Motion not available):")
    print("  Left hand:  Q(pinky) W(ring) E(middle) R(index) T(thumb)")
    print("  Right hand: Y(thumb) U(index) I(middle) O(ring) P(pinky)")
    print()

    game = FingerInvaders()
    game.run()


if __name__ == "__main__":
    main()
