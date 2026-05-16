"""
Lobby SHOP page — placeholder.
"""
import pygame
from game.pages.layout import LOGICAL_W, LOGICAL_H, _TB, _SW, COL_HINT


def draw(screen: pygame.Surface,
         font_lg: pygame.font.Font,
         font_sm: pygame.font.Font) -> None:
    CX = (_SW + LOGICAL_W) // 2
    CY = (_TB + LOGICAL_H) // 2

    title = font_lg.render("SHOP", True, (40, 52, 78))
    screen.blit(title, (CX - title.get_width() // 2, CY - 30))

    sub = font_sm.render("Coming soon", True, (35, 45, 65))
    screen.blit(sub, (CX - sub.get_width() // 2, CY + 4))
