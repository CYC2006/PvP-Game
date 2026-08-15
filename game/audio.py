import os
import pygame

_SFX_DIR = os.path.join("assets", "sfx")
_cache: dict = {}   # relpath → Sound

VOLUME_SELF  = 1.0   # 自己造成的音效
VOLUME_OTHER = 0.5   # 對手造成的音效


def play(relpath: str, volume: float = 1.0) -> None:
    sound = _cache.get(relpath)
    if sound is None:
        sound = pygame.mixer.Sound(os.path.join(_SFX_DIR, relpath))
        _cache[relpath] = sound
    # 用回傳的 Channel 設定音量，而非 Sound.set_volume()：
    # 後者是共用同一個快取 Sound 物件的全域音量，會影響到其他正在播放的 channel。
    channel = sound.play()
    if channel is not None:
        channel.set_volume(volume)
