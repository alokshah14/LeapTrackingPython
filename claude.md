# Leap Motion Finger Individuation Space Invaders Game

## Project Overview
A rehabilitation/training game that uses Leap Motion hand tracking to practice finger individuation. Players must press specific fingers to shoot down incoming missiles.

## Features

### Core Gameplay
- Missiles descend from the top of the screen toward target zones
- Each missile is assigned to a specific finger (left or right hand)
- Player must press the correct finger to shoot and destroy the missile
- Wrong finger press fires a missile that misses the target
- Visual hand model shows which fingers need to be pressed

### Calibration System
- First-time setup calibrates hand position and finger press detection
- Records baseline finger positions and press thresholds
- Saves calibration to `calibration_data.json` for future sessions
- Option to recalibrate or use existing calibration on startup

### Hand Tracking
- Real-time Leap Motion hand tracking
- Visual representation of both hands with fingertip highlighting
- Game pauses automatically when hands leave tracking area
- Finger press detection based on calibrated thresholds

### Difficulty & Scoring
- **Lives**: Start with 3 lives, lose one when missile reaches bottom
- **Score**: +10 points for correct hit, -5 for wrong finger
- **Difficulty**: Adjusts dynamically based on performance
  - Correct answers increase missile speed and spawn rate
  - Wrong answers decrease difficulty slightly
  - Difficulty levels: Easy, Medium, Hard, Expert

### Session Data Logging
- Automatic session logging to `session_logs/` directory
- Each session creates a JSON file with timestamp (e.g., `session_20240130_143052.json`)
- Logs every finger press with:
  - Timestamp (ISO format and elapsed seconds)
  - Finger pressed and target finger
  - Whether press was correct or wrong
  - Full hand tracking data (X, Y, Z coordinates for both hands)
  - All fingertip positions
  - Current game state (score, lives, difficulty)
- Logs missed missiles with hand positions
- Session summary with accuracy percentage

## File Structure

```
LeapTrackingPython/
├── main.py                 # Main entry point
├── game/
│   ├── __init__.py
│   ├── game_engine.py      # Core game loop and state management
│   ├── missile.py          # Missile class and behavior
│   ├── player_missile.py   # Player shot missiles
│   └── constants.py        # Game constants and settings
├── tracking/               # Leap Motion integration (renamed from leap/)
│   ├── __init__.py
│   ├── leap_controller.py  # Leap Motion interface using official bindings
│   ├── hand_tracker.py     # Hand and finger tracking
│   ├── calibration.py      # Calibration system with user confirmation
│   └── session_logger.py   # Session data logging for analysis
├── session_logs/           # Session data files (generated)
├── ui/
│   ├── __init__.py
│   ├── hand_renderer.py    # Hand visualization
│   ├── game_ui.py          # HUD, menus, overlays
│   └── colors.py           # Color definitions
├── calibration_data.json   # Saved calibration (generated)
├── requirements.txt        # Python dependencies
├── claude.md               # This documentation file
└── README.md               # User-facing documentation
```

## Dependencies
- Python 3.8+
- pygame >= 2.5.0
- leapc-python-bindings (Official Ultraleap Python SDK from GitHub)
- numpy

## Installation

1. Install Ultraleap Hand Tracking software and ensure service is running
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   pip install git+https://github.com/ultraleap/leapc-python-bindings.git#subdirectory=leapc-python-api
   ```
3. Run the game:
   ```bash
   python main.py
   ```

## Controls
- **Finger Press**: Shoot at corresponding missile lane
- **ESC**: Pause/Menu
- **SPACE**: Start game / Continue
- **R**: Recalibrate

## Finger Mapping
```
Left Hand:              Right Hand:
[Pinky][Ring][Mid][Idx][Thumb] | [Thumb][Idx][Mid][Ring][Pinky]
  L5    L4   L3   L2    L1    |   R1    R2   R3   R4    R5
```

## Calibration Process
1. Select "Calibrate" from menu and press SPACE to begin
2. Place the required hand above the Leap Motion sensor
3. For each finger:
   - Keep finger RELAXED while system collects rest position samples
   - Press SPACE when prompted, then PRESS finger DOWN
   - Hold pressed position while system collects press samples
4. System calculates threshold as midpoint between rest and press positions
5. Calibration is saved automatically to `calibration_data.json`

## Technical Notes

### Finger Press Detection
- Uses finger tip Y-position relative to hand palm
- Press detected when tip drops below calibrated threshold
- Debounce timer prevents multiple triggers from single press

### Difficulty Scaling
- Base missile speed: 2 pixels/frame
- Speed multiplier increases 0.1 per correct answer (max 2.0)
- Spawn interval decreases with difficulty
- Wrong answers reduce multiplier by 0.05 (min 0.5)

## Development History
- v1.0.0 - Initial implementation with full feature set
- v1.0.1 - Fixed Leap Motion integration:
  - Renamed `leap/` to `tracking/` to avoid SDK naming conflict
  - Integrated official ultraleap/leapc-python-bindings
  - Calibration now uses event-driven API with user confirmation (SPACE key)
  - Added proper hand detection waiting before calibration starts
- v1.0.2 - Added session data logging:
  - New `SessionLogger` class tracks all finger presses
  - Logs timestamps, correctness, and full hand X/Y/Z coordinates
  - Session files saved to `session_logs/` directory as JSON
  - Includes session summary with accuracy statistics
  - Calibration data included in session for reference

## Known Issues
- Leap Motion SDK must be properly installed separately
- Game requires good lighting for optimal hand tracking

## Future Enhancements
- [ ] Multiple game modes (timed, endless, challenge)
- [ ] Sound effects and music
- [ ] High score persistence
- [ ] Multiplayer support
- [x] Analytics and progress tracking (session logging implemented)

---

## Conversation Log

### 2026-02-03
- **Session started**: User requested to track conversations in CLAUDE.md and commit changes
- Project context reviewed: Leap Motion finger individuation game for rehabilitation/training

#### Calibration System Overhaul (Angle-Based)
**User Request**: Redesign calibration to use finger flexion angles instead of Y-position thresholds

**Changes Made**:
1. **constants.py**: Added `FINGER_PRESS_ANGLE_THRESHOLD = 30` (degrees)

2. **leap_controller.py**:
   - Extract bone direction vectors (proximal and intermediate) for angle calculation
   - Updated both real controller and simulated controller

3. **hand_tracker.py**:
   - Added `finger_angles` dictionary to track flexion angles
   - Added `baseline_angles` for storing rest positions
   - New methods: `_calculate_flexion_angle()`, `get_finger_angle()`, `get_finger_angle_from_baseline()`, `set_baseline_angle()`, `get_all_finger_angles()`

4. **calibration.py** (Complete Rewrite):
   - New calibration phases: `waiting_hands` -> `capturing_baseline` -> `calibrating_finger` -> `complete`
   - First captures baseline (rest angles) for ALL fingers simultaneously
   - Then calibrates each finger by waiting for 30-degree press
   - Auto-advances to next finger (no spacebar needed)
   - 500ms hold requirement to confirm press
   - Stores both angle-based and Y-position thresholds for compatibility

5. **hand_renderer.py**:
   - `CalibrationHandRenderer` now displays real-time angle readout
   - Large numerical display showing current angle in degrees
   - Visual gauge bar with threshold marker
   - Hold progress indicator when threshold reached

6. **game_ui.py**:
   - Updated calibration menu to explain new angle-based process
   - Highlighted key info about 30-degree threshold and auto-advance

7. **main.py**:
   - Updated `_update_calibration()` to pass finger angles to calibration system
   - Added angle data updates to calibration renderer
