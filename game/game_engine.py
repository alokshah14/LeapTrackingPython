"""Main game engine managing game state and logic."""

import pygame
import random
import time
from typing import List, Dict, Optional
from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS, GAME_TITLE,
    GAME_AREA_TOP, GAME_AREA_BOTTOM, NUM_LANES, LANE_WIDTH,
    FINGER_NAMES, STARTING_LIVES, STARTING_SCORE, STARTING_DIFFICULTY,
    DIFFICULTY_LEVELS, POINTS_CORRECT_HIT, POINTS_WRONG_FINGER, POINTS_MISSILE_MISSED,
    CORRECT_HITS_TO_INCREASE, WRONG_HITS_TO_DECREASE, HAND_MISSING_PAUSE_DELAY
)
from .missile import Missile
from .player_missile import PlayerMissile


class GameState:
    """Enumeration of game states."""
    MENU = 'menu'
    CALIBRATION_MENU = 'calibration_menu'
    CALIBRATING = 'calibrating'
    PLAYING = 'playing'
    PAUSED = 'paused'
    GAME_OVER = 'game_over'


class GameEngine:
    """Core game engine managing game logic and state."""

    def __init__(self, hand_tracker, calibration_manager):
        """
        Initialize the game engine.

        Args:
            hand_tracker: HandTracker instance for finger input
            calibration_manager: CalibrationManager instance
        """
        self.hand_tracker = hand_tracker
        self.calibration = calibration_manager

        # Game state
        self.state = GameState.MENU
        self.previous_state = None

        # Game variables
        self.score = STARTING_SCORE
        self.lives = STARTING_LIVES
        self.difficulty = STARTING_DIFFICULTY
        self.high_score = 0

        # Difficulty tracking
        self.correct_streak = 0
        self.wrong_streak = 0
        self.difficulty_index = 0
        self.difficulty_order = ['Easy', 'Medium', 'Hard', 'Expert']

        # Missiles
        self.enemy_missiles: List[Missile] = []
        self.player_missiles: List[PlayerMissile] = []

        # Spawn timing
        self.last_spawn_time = 0
        self.spawn_interval = DIFFICULTY_LEVELS[self.difficulty]['spawn_interval']

        # Target fingers (fingers with active missiles)
        self.target_fingers: List[str] = []

        # Pause reason
        self.pause_reason = "PAUSED"

        # Statistics
        self.stats = {
            'total_missiles': 0,
            'missiles_hit': 0,
            'missiles_missed': 0,
            'wrong_fingers': 0,
        }

    def reset_game(self):
        """Reset game to starting state."""
        self.score = STARTING_SCORE
        self.lives = STARTING_LIVES
        self.difficulty = STARTING_DIFFICULTY
        self.difficulty_index = 0
        self.correct_streak = 0
        self.wrong_streak = 0

        self.enemy_missiles.clear()
        self.player_missiles.clear()
        self.target_fingers.clear()

        self.last_spawn_time = pygame.time.get_ticks()
        self.spawn_interval = DIFFICULTY_LEVELS[self.difficulty]['spawn_interval']

        self.stats = {
            'total_missiles': 0,
            'missiles_hit': 0,
            'missiles_missed': 0,
            'wrong_fingers': 0,
        }

    def start_game(self):
        """Start a new game."""
        self.reset_game()
        self.state = GameState.PLAYING

    def pause_game(self, reason: str = "PAUSED"):
        """Pause the game."""
        if self.state == GameState.PLAYING:
            self.previous_state = self.state
            self.state = GameState.PAUSED
            self.pause_reason = reason

    def resume_game(self):
        """Resume from pause."""
        if self.state == GameState.PAUSED:
            self.state = GameState.PLAYING
            self.last_spawn_time = pygame.time.get_ticks()

    def update(self, dt: float = 1.0) -> Dict:
        """
        Update game state.

        Args:
            dt: Delta time multiplier

        Returns:
            Dictionary with update events for UI feedback
        """
        events = {
            'score_change': 0,
            'life_lost': False,
            'missile_destroyed': [],
            'wrong_finger': False,
            'difficulty_changed': False,
        }

        if self.state != GameState.PLAYING:
            return events

        current_time = pygame.time.get_ticks()

        # Check for hand visibility (auto-pause)
        if self.hand_tracker.should_pause_game(HAND_MISSING_PAUSE_DELAY):
            self.pause_game("HANDS NOT DETECTED")
            return events

        # Get finger presses
        pressed_fingers = self.hand_tracker.update()

        # Handle finger presses
        for finger in pressed_fingers:
            self._handle_finger_press(finger, events)

        # Update missiles
        self._update_missiles(dt, events)

        # Spawn new missiles
        if current_time - self.last_spawn_time >= self.spawn_interval:
            self._spawn_missile()
            self.last_spawn_time = current_time

        # Update target fingers list
        self.target_fingers = [m.finger_name for m in self.enemy_missiles if m.active]

        # Check game over
        if self.lives <= 0:
            self.state = GameState.GAME_OVER
            if self.score > self.high_score:
                self.high_score = self.score

        return events

    def _handle_finger_press(self, finger_name: str, events: Dict):
        """Handle a finger press event."""
        # Find if there's a missile in this finger's lane
        lane = FINGER_NAMES.index(finger_name)
        target_missile = None

        for missile in self.enemy_missiles:
            if missile.lane == lane and missile.active:
                target_missile = missile
                break

        # Create player missile
        player_missile = PlayerMissile(lane, target_missile)
        self.player_missiles.append(player_missile)

        if target_missile:
            # Correct finger - will hit target
            self.score += POINTS_CORRECT_HIT
            self.correct_streak += 1
            self.wrong_streak = 0
            events['score_change'] = POINTS_CORRECT_HIT
            self.stats['missiles_hit'] += 1

            # Check for difficulty increase
            if self.correct_streak >= CORRECT_HITS_TO_INCREASE:
                self._increase_difficulty()
                self.correct_streak = 0
                events['difficulty_changed'] = True
        else:
            # Wrong finger - miss
            self.score += POINTS_WRONG_FINGER
            self.score = max(0, self.score)  # Don't go negative
            self.wrong_streak += 1
            self.correct_streak = 0
            events['score_change'] = POINTS_WRONG_FINGER
            events['wrong_finger'] = True
            self.stats['wrong_fingers'] += 1

            # Check for difficulty decrease
            if self.wrong_streak >= WRONG_HITS_TO_DECREASE:
                self._decrease_difficulty()
                self.wrong_streak = 0
                events['difficulty_changed'] = True

    def _update_missiles(self, dt: float, events: Dict):
        """Update all missiles."""
        # Update enemy missiles
        for missile in self.enemy_missiles[:]:
            missile.update(dt)

            if missile.reached_bottom:
                # Player missed this missile
                self.lives -= 1
                self.score += POINTS_MISSILE_MISSED
                self.score = max(0, self.score)
                events['life_lost'] = True
                self.stats['missiles_missed'] += 1
                self.enemy_missiles.remove(missile)

            elif missile.hit:
                # Missile was destroyed
                events['missile_destroyed'].append(missile.get_center())
                self.enemy_missiles.remove(missile)

        # Update player missiles
        for missile in self.player_missiles[:]:
            missile.update(dt)

            if not missile.active:
                self.player_missiles.remove(missile)

    def _spawn_missile(self):
        """Spawn a new enemy missile."""
        settings = DIFFICULTY_LEVELS[self.difficulty]

        # Check max missiles
        if len(self.enemy_missiles) >= settings['max_missiles']:
            return

        # Choose a random lane that doesn't have a missile near the top
        available_lanes = []
        for i in range(NUM_LANES):
            lane_clear = True
            for missile in self.enemy_missiles:
                if missile.lane == i and missile.y < GAME_AREA_TOP + 200:
                    lane_clear = False
                    break
            if lane_clear:
                available_lanes.append(i)

        if not available_lanes:
            return

        lane = random.choice(available_lanes)
        missile = Missile(lane, settings['speed_multiplier'])
        self.enemy_missiles.append(missile)
        self.stats['total_missiles'] += 1

    def _increase_difficulty(self):
        """Increase difficulty level."""
        if self.difficulty_index < len(self.difficulty_order) - 1:
            self.difficulty_index += 1
            self.difficulty = self.difficulty_order[self.difficulty_index]
            self.spawn_interval = DIFFICULTY_LEVELS[self.difficulty]['spawn_interval']
            print(f"Difficulty increased to {self.difficulty}")

    def _decrease_difficulty(self):
        """Decrease difficulty level."""
        if self.difficulty_index > 0:
            self.difficulty_index -= 1
            self.difficulty = self.difficulty_order[self.difficulty_index]
            self.spawn_interval = DIFFICULTY_LEVELS[self.difficulty]['spawn_interval']
            print(f"Difficulty decreased to {self.difficulty}")

    def get_game_state(self) -> Dict:
        """Get current game state for rendering."""
        return {
            'score': self.score,
            'lives': self.lives,
            'difficulty': self.difficulty,
            'streak': self.correct_streak,
            'target_fingers': self.target_fingers,
            'enemy_missiles': self.enemy_missiles,
            'player_missiles': self.player_missiles,
            'high_score': self.high_score,
            'stats': self.stats,
        }

    def get_highlighted_fingers(self) -> List[str]:
        """Get list of fingers that should be highlighted (have incoming missiles)."""
        return self.target_fingers.copy()
