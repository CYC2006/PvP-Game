from dataclasses import dataclass


@dataclass
class PlayerCommand:
    player_id: int
    move_x: float       # -1.0 / 0.0 / 1.0
    move_y: float
    shooting: bool      # left mouse button held
    aim_x: float        # world-space direction vector (not normalised)
    aim_y: float
    running: bool = False    # shift held → run, 1.2× speed
    stance: str = "machine" # "machine" | "reload"（同步給對手）
