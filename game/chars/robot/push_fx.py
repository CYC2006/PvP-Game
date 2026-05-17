import math
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H
from game.chars.robot.push_state import PUSH_WIND_UP, PUSH_ACTIVE, PUSH_HEIGHT, PUSH_WIDTH


def draw(screen, state, my_player_id: int, cx: float, cy: float) -> None:
    """繪製推力矩形。
    Wind-up 階段（age < PUSH_WIND_UP）：只有施法者看到（白色預覽框）。
    Active 階段（age < PUSH_WIND_UP + PUSH_ACTIVE）：雙方都看到（黃色閃光框）。
    """
    for zone in state.push_zones.values():
        age = state.tick - zone.spawn_tick
        in_windup = age < PUSH_WIND_UP

        # wind-up 只顯示給施法者
        if in_windup and zone.owner_id != my_player_id:
            continue

        angle_rad = math.radians(zone.angle)
        fwd_x  =  math.cos(angle_rad)
        fwd_y  =  math.sin(angle_rad)
        right_x = -fwd_y
        right_y =  fwd_x

        ox, oy = zone.x, zone.y
        hw = PUSH_WIDTH / 2  # half-width

        # 四個角（世界座標）
        corners_world = [
            (ox - right_x * hw,                        oy - right_y * hw),
            (ox + right_x * hw,                        oy + right_y * hw),
            (ox + fwd_x * PUSH_HEIGHT + right_x * hw, oy + fwd_y * PUSH_HEIGHT + right_y * hw),
            (ox + fwd_x * PUSH_HEIGHT - right_x * hw, oy + fwd_y * PUSH_HEIGHT - right_y * hw),
        ]
        corners_screen = [ws(wx, wy, cx, cy) for wx, wy in corners_world]

        if in_windup:
            # 白色漸亮框：隨 wind-up 進度從半透明到明顯
            t = age / max(1, PUSH_WIND_UP)
            alpha = int(80 + 120 * t)
            color = (220, 220, 255, alpha)
        else:
            # 黃色快速淡出框
            active_age = age - PUSH_WIND_UP
            t = active_age / max(1, PUSH_ACTIVE)
            alpha = int(200 * (1.0 - t))
            color = (255, 230, 60, alpha)

        if alpha <= 0:
            continue

        # 計算 blit 區域
        xs = [c[0] for c in corners_screen]
        ys = [c[1] for c in corners_screen]
        min_x, max_x = min(xs) - 2, max(xs) + 2
        min_y, max_y = min(ys) - 2, max(ys) + 2

        # 視窗外跳過
        if max_x < 0 or min_x > SCREEN_W or max_y < 0 or min_y > SCREEN_H:
            continue

        sw = max(1, int(max_x - min_x))
        sh = max(1, int(max_y - min_y))
        surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        local_pts = [(int(c[0] - min_x), int(c[1] - min_y)) for c in corners_screen]
        pygame.draw.polygon(surf, color, local_pts, 2)
        screen.blit(surf, (int(min_x), int(min_y)))
