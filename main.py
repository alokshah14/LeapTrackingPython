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
    FINGER_NAMES, GAME_AREA_BOTTOM
)
from game.game_engine import GameEngine, GameState
from game.high_scores import HighScoreManager
from tracking.leap_controller import LeapController, SimulatedLeapController
from tracking.hand_tracker import HandTracker
from tracking.calibration import CalibrationManager
from tracking.session_logger import SessionLogger
from tracking.kinematics import KinematicsProcessor
from tracking.trial_summary import TrialSummaryExporter
from ui.game_ui import GameUI, MenuUI
from ui.hand_renderer_3d import OpenGLHandRenderer
from ui.hand_renderer import HandRenderer as OldHandRenderer, CalibrationHandRenderer
from ui.colors import BACKGROUND
from game.sound_manager import SoundManager
from OpenGL.GL import *
from OpenGL.GLU import *


class FingerInvaders:
    """Main game application class."""

    def __init__(self):
        """Initialize the game application."""
        # Set up display with OpenGL
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
        pygame.display.gl_set_attribute(pygame.GL_STENCIL_SIZE, 8)
        pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.DOUBLEBUF | pygame.OPENGL)
        self.screen = pygame.display.get_surface() # This is the OpenGL context surface

        # Create an off-screen surface for 2D Pygame rendering
        self.pygame_2d_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)

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

        # Initialize high score manager and load persisted high score
        self.high_score_manager = HighScoreManager()
        top_score = self.high_score_manager.get_top_score("classic")
        if top_score:
            self.game_engine.high_score = top_score

        # Initialize session logger
        self.session_logger = SessionLogger()

        # Initialize trial summary exporter for clean biomechanics output
        self.trial_summary = TrialSummaryExporter()

        # Initialize kinematics processor for biomechanical analysis
        self.kinematics = KinematicsProcessor(self.hand_tracker)

        # Initialize sound manager
        self.sound_manager = SoundManager()

        # Initialize UI components (all drawing to the off-screen 2D surface)
        self.game_ui = GameUI(self.pygame_2d_surface)
        self.menu_ui = MenuUI(self.pygame_2d_surface)
        self.hand_renderer = OpenGLHandRenderer(self.screen) # 3D renderer still uses main screen
        self.calibration_renderer = CalibrationHandRenderer(self.pygame_2d_surface)
        self.old_hand_renderer = OldHandRenderer(self.pygame_2d_surface) # Keep for angle bars etc.

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

        # High score celebration state
        self.new_high_score_rank = None
        self.new_high_score_value = 0
        self.celebration_animation = 0

        # Hand position warning state
        self.hands_not_ready_message_time = 0

        # Waiting for hands state
        self.waiting_countdown = None  # Countdown before game starts (seconds)

        # Running state
        self.running = True

        # Initialize OpenGL for 2D overlay
        self._init_2d_opengl()

    def _init_2d_opengl(self):
        """Initializes OpenGL settings for drawing the 2D Pygame overlay."""
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.0, 0.0, 0.0, 0.0) # Clear to black, but will be overwritten by 2D surface

    def _get_texture(self, surface):
        """Converts a pygame surface into an OpenGL texture."""
        # Don't flip - we'll handle orientation in texture coordinates
        texture_data = pygame.image.tostring(surface, "RGBA", False)
        width, height = surface.get_size()

        texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        return texture_id, width, height

    def _draw_2d_overlay_with_opengl(self):
        """Renders the 2D Pygame surface as an OpenGL texture overlay."""
        # Disable depth test and lighting for 2D overlay
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)

        # Enable texturing and blending
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Use scissor test to only draw in the game area (exclude hand area at bottom)
        # OpenGL coords: y=0 at bottom. Hand area is at bottom (y=0 to y=200)
        # Game area is from y=200 to y=900
        glEnable(GL_SCISSOR_TEST)
        hand_area_height = WINDOW_HEIGHT - GAME_AREA_BOTTOM  # 200 pixels
        glScissor(0, hand_area_height, WINDOW_WIDTH, GAME_AREA_BOTTOM)

        # Reset viewport to full screen
        glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

        # Orthographic projection for 2D rendering
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        # Generate texture from Pygame surface
        texture_id, tex_width, tex_height = self._get_texture(self.pygame_2d_surface)

        # Draw full textured quad (scissor will clip to game area)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        # Flip texture vertically (Pygame Y=0 top, OpenGL Y=0 bottom)
        glTexCoord2f(0, 1); glVertex2f(0, 0)
        glTexCoord2f(1, 1); glVertex2f(WINDOW_WIDTH, 0)
        glTexCoord2f(1, 0); glVertex2f(WINDOW_WIDTH, WINDOW_HEIGHT)
        glTexCoord2f(0, 0); glVertex2f(0, WINDOW_HEIGHT)
        glEnd()

        glDeleteTextures(1, [texture_id])

        glDisable(GL_SCISSOR_TEST)

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        glDisable(GL_TEXTURE_2D)

    def run(self):
        """Main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 16.67  # Normalize to 60fps

            # Handle events
            self._handle_events()

            # Update
            self._update(dt)

            # Render
            # --- START 2D Pygame Rendering ---
            # Clear the off-screen 2D surface with transparent black
            self.pygame_2d_surface.fill((0, 0, 0, 0))

            self._render()  # Draw to self.pygame_2d_surface

            # --- OpenGL Combined Rendering ---
            # Clear the OpenGL buffers
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            # Draw 3D hands first (in the hand area viewport)
            self.hand_renderer.draw()

            # Then overlay the 2D Pygame surface on top (with transparency)
            self._draw_2d_overlay_with_opengl()

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
                enabled = self.old_hand_renderer.toggle_angle_bars()
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
            elif state == GameState.HIGH_SCORES:
                self.game_engine.state = GameState.MENU
            elif state == GameState.WAITING_FOR_HANDS:
                # Cancel waiting, go back to menu
                self.game_engine.state = GameState.MENU
            elif state == GameState.NEW_HIGH_SCORE:
                # Skip celebration, go to game over
                self.game_engine.state = GameState.GAME_OVER

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
            elif state == GameState.NEW_HIGH_SCORE:
                # Continue to game over screen
                self.game_engine.state = GameState.GAME_OVER

        # Menu navigation
        elif state == GameState.MENU:
            if event.key == pygame.K_UP:
                self.menu_ui.move_selection(-1, 4, self.calibration.has_calibration())
            elif event.key == pygame.K_DOWN:
                self.menu_ui.move_selection(1, 4, self.calibration.has_calibration())
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
            # Go to waiting for hands state
            self.game_engine.state = GameState.WAITING_FOR_HANDS
            self.waiting_countdown = None  # Will be set when hands are in position
        elif option == 1:
            # Calibrate
            self.game_engine.state = GameState.CALIBRATION_MENU
        elif option == 2:
            # High Scores
            self.game_engine.state = GameState.HIGH_SCORES
        elif option == 3:
            # Quit
            self.running = False

    def _save_high_score(self):
        """Save the current game score to high scores."""
        game_state = self.game_engine.get_game_state()
        stats = game_state['stats']

        # Calculate accuracy
        total_attempts = stats['missiles_hit'] + stats['wrong_fingers']
        accuracy = (stats['missiles_hit'] / total_attempts * 100) if total_attempts > 0 else 0

        # Get clean trial rate and avg reaction time from trial summary if available
        clean_trial_rate = 0
        avg_reaction_time = 0
        if self.trial_summary.trials:
            clean_count = sum(1 for t in self.trial_summary.trials if t.is_clean_trial)
            clean_trial_rate = (clean_count / len(self.trial_summary.trials)) * 100
            valid_rts = [t.reaction_time_ms for t in self.trial_summary.trials if t.reaction_time_ms > 0]
            avg_reaction_time = sum(valid_rts) / len(valid_rts) if valid_rts else 0

        # Add to high scores
        rank = self.high_score_manager.add_score(
            score=game_state['score'],
            game_mode="classic",
            duration_seconds=0,  # Could track this if needed
            accuracy=accuracy,
            clean_trial_rate=clean_trial_rate,
            avg_reaction_time_ms=avg_reaction_time
        )

        # Update game engine high score if this is a new record
        if rank == 1:
            self.game_engine.high_score = game_state['score']
        elif rank:
            # Update to the actual top score
            top = self.high_score_manager.get_top_score("classic")
            if top:
                self.game_engine.high_score = top

        # Trigger celebration screen if it's a high score
        if rank:
            self.new_high_score_rank = rank
            self.new_high_score_value = game_state['score']
            self.celebration_animation = 0
            self.game_engine.state = GameState.NEW_HIGH_SCORE
            self.sound_manager.play_celebration()

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
                        self.old_hand_renderer.show_clean_trial(trial_metrics.motion_leakage_ratio)

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

                # Check if game just ended - save high score
                if self.game_engine.state == GameState.GAME_OVER:
                    self._save_high_score()

            for pos in events['missile_destroyed']:
                self.game_ui.add_explosion(pos[0], pos[1])
                self.sound_manager.play_explosion()

            # Update hand highlighting
            self.old_hand_renderer.set_highlighted_fingers(self.game_engine.get_highlighted_fingers())

            # Update finger angle data for display
            finger_angles = self.hand_tracker.get_all_finger_angles()
            self.old_hand_renderer.set_finger_angles(
                finger_angles,
                self.calibration.calibration_data.get('baseline_angles', {})
            )

        elif state == GameState.CALIBRATING:
            self._update_calibration(dt)

        elif state == GameState.PAUSED:
            # Check if hands returned
            self.hand_tracker.update()
            if self.hand_tracker.are_hands_visible():
                if self.game_engine.pause_reason == "HANDS NOT DETECTED":
                    self.game_engine.resume_game()

        elif state == GameState.WAITING_FOR_HANDS:
            # Check if hands are in calibrated position
            hand_data = self.leap_controller.update()
            position_status = self.calibration.check_hand_positions(hand_data)

            if position_status['both_in_position']:
                # Hands are in position - start or continue countdown
                if self.waiting_countdown is None:
                    self.waiting_countdown = 3.0  # 3 second countdown
                else:
                    self.waiting_countdown -= dt * 0.0167  # Roughly 1 second per 60 frames
                    if self.waiting_countdown <= 0:
                        # Start the game!
                        self.game_engine.start_game()
                        self.session_logger.start_session(self.calibration.calibration_data)
                        self.trial_summary.start_session()
                        self.waiting_countdown = None
            else:
                # Hands not in position - reset countdown
                self.waiting_countdown = None

        elif state == GameState.NEW_HIGH_SCORE:
            # Update celebration animation
            self.celebration_animation += dt * 0.1

        # Update UI animations
        self.game_ui.update(dt)
        self.menu_ui.update(dt)
        self.hand_renderer.update(dt)
        self.old_hand_renderer.update(dt)

        # Decay hands not ready message timer
        if self.hands_not_ready_message_time > 0:
            self.hands_not_ready_message_time -= dt * 0.05

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

            # Show hand position overlay if calibration exists
            if self.calibration.has_calibration():
                hand_data = self.leap_controller.update()
                position_status = self.calibration.check_hand_positions(hand_data)
                calibrated_positions = self.calibration.get_calibrated_palm_positions()
                if calibrated_positions.get('left') or calibrated_positions.get('right'):
                    self.menu_ui.draw_hand_position_overlay(position_status, calibrated_positions)

            # Show warning if hands not in position when trying to start
            if self.hands_not_ready_message_time > 0:
                self._draw_hands_not_ready_warning()

        elif state == GameState.CALIBRATION_MENU:
            self.menu_ui.draw_calibration_menu(self.calibration.has_calibration())

        elif state == GameState.CALIBRATING:
            self._render_calibration()

        elif state == GameState.WAITING_FOR_HANDS:
            self._render_waiting_for_hands()

        elif state == GameState.PLAYING:
            self._render_game()

        elif state == GameState.PAUSED:
            self._render_game()
            self.game_ui.draw_pause_overlay(self.game_engine.pause_reason)

        elif state == GameState.GAME_OVER:
            self._render_game()
            game_state = self.game_engine.get_game_state()
            self.game_ui.draw_game_over(game_state['score'], game_state['high_score'])

        elif state == GameState.HIGH_SCORES:
            high_scores = self.high_score_manager.get_high_scores("classic")
            self.menu_ui.draw_high_scores(high_scores)

        elif state == GameState.NEW_HIGH_SCORE:
            self.menu_ui.draw_new_high_score(
                self.new_high_score_value,
                self.new_high_score_rank,
                self.celebration_animation
            )

    def _render_game(self):
        """Render the main game."""
        game_state = self.game_engine.get_game_state()

        # Background
        self.game_ui.draw_background()

        # Lanes
        self.game_ui.draw_lanes(game_state['target_fingers'])

        # Enemy missiles - draw to 2D surface
        for missile in game_state['enemy_missiles']:
            missile.draw(self.pygame_2d_surface)
            missile.draw_warning(self.pygame_2d_surface)

        # Player missiles - draw to 2D surface
        for missile in game_state['player_missiles']:
            missile.draw(self.pygame_2d_surface)

        # Explosions
        self.game_ui.draw_explosions()

        # HUD
        self.game_ui.draw_hud(
            game_state['score'],
            game_state['lives'],
            game_state['difficulty'],
            game_state['streak']
        )

        # Update 3D hand data (actual drawing happens in main loop after 2D overlay)
        hand_data = self.hand_tracker.get_display_data()
        finger_states = self.hand_tracker.get_all_finger_states()
        highlighted_fingers = set(self.game_engine.get_highlighted_fingers())
        self.hand_renderer.set_hand_data(hand_data, finger_states, highlighted_fingers)

        # Hand visualization (2D elements from old renderer)
        self.old_hand_renderer.set_highlighted_fingers(self.game_engine.get_highlighted_fingers())
        finger_angles = self.hand_tracker.get_all_finger_angles()
        self.old_hand_renderer.set_finger_angles(
            finger_angles,
            self.calibration.calibration_data.get('baseline_angles', {})
        )
        self.old_hand_renderer._draw_finger_labels()  # Draw only labels
        self.old_hand_renderer._draw_angle_bars(finger_states)  # Draw angle bars
        self.old_hand_renderer._draw_clean_trial_indicator()  # Draw clean trial indicator

    def _render_calibration(self):
        """Render calibration screen."""
        # Get calibration status
        status = self.calibration.get_calibration_status()
        instructions = self.calibration.get_instructions()

        # Draw hand visualization
        hand_data = self.hand_tracker.get_display_data()
        finger_states = self.hand_tracker.get_all_finger_states()
        self.calibration_renderer.draw(hand_data, finger_states)

        # Update 3D hand renderer so hands show in the bottom area
        highlighted = {self.calibration.get_current_finger()} if self.calibration.get_current_finger() else set()
        self.hand_renderer.set_hand_data(hand_data, finger_states, highlighted)

        # Draw calibration overlay
        self.calibration_renderer.draw_calibration_overlay(instructions, status)

        # Draw title
        font = pygame.font.Font(None, 56)
        title = font.render("CALIBRATION MODE", True, (255, 255, 255))
        self.pygame_2d_surface.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 30))

        # Draw instructions for simulation mode
        if isinstance(self.leap_controller, SimulatedLeapController):
            sim_font = pygame.font.Font(None, 24)
            sim_text = sim_font.render(
                "Simulation Mode: Use Q-W-E-R-T (left) and Y-U-I-O-P (right) keys",
                True, (150, 150, 200)
            )
            self.pygame_2d_surface.blit(sim_text, (WINDOW_WIDTH // 2 - sim_text.get_width() // 2, 80))

    def _render_waiting_for_hands(self):
        """Render the waiting for hands screen."""
        # Dark background
        self.pygame_2d_surface.fill((20, 20, 40))

        # Title
        font_title = pygame.font.Font(None, 64)
        title = font_title.render("POSITION YOUR HANDS", True, (255, 255, 255))
        self.pygame_2d_surface.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 80))

        # Instructions
        font_inst = pygame.font.Font(None, 32)
        inst1 = font_inst.render("Place your hands above the Leap Motion sensor", True, (200, 200, 200))
        inst2 = font_inst.render("in the same position as during calibration", True, (200, 200, 200))
        self.pygame_2d_surface.blit(inst1, (WINDOW_WIDTH // 2 - inst1.get_width() // 2, 160))
        self.pygame_2d_surface.blit(inst2, (WINDOW_WIDTH // 2 - inst2.get_width() // 2, 195))

        # Get current hand positions and draw status
        hand_data = self.leap_controller.update()
        position_status = self.calibration.check_hand_positions(hand_data)
        calibrated_positions = self.calibration.get_calibrated_palm_positions()

        # Draw hand position indicators
        self.menu_ui.draw_hand_position_overlay(position_status, calibrated_positions, large=True)

        # Show countdown if hands are in position
        if self.waiting_countdown is not None:
            font_countdown = pygame.font.Font(None, 120)
            countdown_num = max(1, int(self.waiting_countdown) + 1)
            countdown_text = font_countdown.render(str(countdown_num), True, (100, 255, 100))
            self.pygame_2d_surface.blit(countdown_text,
                (WINDOW_WIDTH // 2 - countdown_text.get_width() // 2, 350))

            ready_text = font_inst.render("GET READY!", True, (100, 255, 100))
            self.pygame_2d_surface.blit(ready_text,
                (WINDOW_WIDTH // 2 - ready_text.get_width() // 2, 480))
        else:
            # Show waiting status
            if position_status.get('left_in_position') and position_status.get('right_in_position'):
                status_text = "Both hands in position!"
                status_color = (100, 255, 100)
            elif position_status.get('left_in_position'):
                status_text = "Left hand OK - Position right hand"
                status_color = (255, 255, 100)
            elif position_status.get('right_in_position'):
                status_text = "Right hand OK - Position left hand"
                status_color = (255, 255, 100)
            else:
                status_text = "Position both hands..."
                status_color = (255, 150, 150)

            status_render = font_inst.render(status_text, True, status_color)
            self.pygame_2d_surface.blit(status_render,
                (WINDOW_WIDTH // 2 - status_render.get_width() // 2, 400))

        # ESC to cancel
        font_small = pygame.font.Font(None, 24)
        esc_text = font_small.render("Press ESC to cancel", True, (150, 150, 150))
        self.pygame_2d_surface.blit(esc_text, (WINDOW_WIDTH // 2 - esc_text.get_width() // 2, 550))

    def _draw_hands_not_ready_warning(self):
        """Draw warning message when hands are not in position."""
        # Semi-transparent overlay
        overlay = pygame.Surface((500, 100), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))

        # Warning text
        font_large = pygame.font.Font(None, 42)
        font_small = pygame.font.Font(None, 28)

        title = font_large.render("HANDS NOT IN POSITION", True, (255, 100, 100))
        subtitle = font_small.render("Place hands in calibrated position to start", True, (255, 255, 255))

        # Center on screen
        overlay_x = (WINDOW_WIDTH - 500) // 2
        overlay_y = WINDOW_HEIGHT // 2 - 50

        self.pygame_2d_surface.blit(overlay, (overlay_x, overlay_y))
        self.pygame_2d_surface.blit(title, (overlay_x + 250 - title.get_width() // 2, overlay_y + 20))
        self.pygame_2d_surface.blit(subtitle, (overlay_x + 250 - subtitle.get_width() // 2, overlay_y + 60))

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
