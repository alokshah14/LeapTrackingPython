"""Color definitions for the game UI."""

# Basic colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)

# Game-specific colors
BACKGROUND = (10, 10, 30)
MISSILE_ENEMY = (255, 50, 50)
MISSILE_PLAYER = (50, 255, 50)
HAND_COLOR = (100, 150, 200)
HAND_OUTLINE = (150, 200, 255)
FINGER_NORMAL = (100, 150, 200)
FINGER_HIGHLIGHT = (255, 255, 0)
FINGER_PRESSED = (0, 255, 0)
LANE_COLOR = (40, 40, 60)
LANE_BORDER = (60, 60, 80)
HUD_TEXT = (200, 200, 200)
HUD_VALUE = (255, 255, 255)
LIVES_COLOR = (255, 100, 100)
SCORE_COLOR = (100, 255, 100)
DIFFICULTY_COLOR = (100, 100, 255)
PAUSE_OVERLAY = (0, 0, 0, 180)
CALIBRATION_BG = (20, 20, 40)
CALIBRATION_TEXT = (200, 200, 255)
CALIBRATION_HIGHLIGHT = (255, 200, 0)
EXPLOSION_COLORS = [(255, 255, 0), (255, 200, 0), (255, 150, 0), (255, 100, 0), (255, 50, 0)]

# Finger colors for identification (10 unique colors for 10 fingers)
FINGER_COLORS = {
    'left_pinky': (148, 0, 211),    # Violet
    'left_ring': (75, 0, 130),      # Indigo
    'left_middle': (0, 0, 255),     # Blue
    'left_index': (0, 255, 0),      # Green
    'left_thumb': (255, 255, 0),    # Yellow
    'right_thumb': (255, 200, 0),   # Gold
    'right_index': (255, 165, 0),   # Orange
    'right_middle': (255, 100, 0),  # Dark Orange
    'right_ring': (255, 0, 0),      # Red
    'right_pinky': (255, 0, 127),   # Rose
}

# Difficulty level colors
DIFFICULTY_COLORS = {
    'Easy': (100, 255, 100),
    'Medium': (255, 255, 100),
    'Hard': (255, 165, 0),
    'Expert': (255, 50, 50),
}
