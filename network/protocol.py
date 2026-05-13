import struct
from game.command import PlayerCommand
from game.state import GameState, Player, Bullet, GoldIngot

# --- Packet types ---
PKT_JOIN        = 0x01
PKT_JOINED      = 0x02
PKT_CMD         = 0x03
PKT_STATE       = 0x04
PKT_CHAR_SELECT = 0x05   # client → server: 選好角色（2 bytes: type + char_id）
PKT_GAME_START  = 0x06   # server → clients: 雙方都選完，遊戲開始

# PKT_STATE 格式:
#   | type(1) | tick(I) |
#   | p_count(B) | [id(B) x(f) y(f) hp(H) max_hp(H) aim_angle_i16(h) stance_u8(B) gold(H)] * p_count |
#   | b_count(B) | [id(B) owner(B) x(f) y(f) angle_i16(h)] * b_count |
#   | d_count(B) | [obstacle_id(B)] * d_count |
#   | g_count(B) | [id(B) x(f) y(f)] * g_count |

_JOINED_STRUCT = struct.Struct("!BB")
_CMD_STRUCT    = struct.Struct("!BBffBffH")  # +H: speed_mult×1000
_STATE_HDR     = struct.Struct("!BI")
_PLAYER_ENTRY  = struct.Struct("!BffHHhBH")  # id x y hp max_hp aim_angle stance gold
_BULLET_ENTRY  = struct.Struct("!BBffh")      # id owner x y angle_i16
_GOLD_ENTRY    = struct.Struct("!BffB")       # id x y kind(0=gold,1=health)

# stance 編碼表
_STANCE_TO_INT = {"stand": 0, "machine": 1, "hold": 2}
_INT_TO_STANCE = {0: "stand", 1: "machine", 2: "hold"}


def pack_join() -> bytes:
    return bytes([PKT_JOIN])


def pack_joined(player_id: int) -> bytes:
    return _JOINED_STRUCT.pack(PKT_JOINED, player_id)


def unpack_joined(data: bytes) -> int:
    _, player_id = _JOINED_STRUCT.unpack(data[:_JOINED_STRUCT.size])
    return player_id


def pack_command(cmd: PlayerCommand) -> bytes:
    # bit 0 = shooting, bit 1 = running, bits 2-3 = stance
    stance_bits = _STANCE_TO_INT.get(cmd.stance, 0) << 2
    flags = int(cmd.shooting) | (int(cmd.running) << 1) | stance_bits
    speed_raw = max(0, min(65535, int(cmd.speed_mult * 1000)))
    return _CMD_STRUCT.pack(
        PKT_CMD, cmd.player_id,
        cmd.move_x, cmd.move_y,
        flags,
        cmd.aim_x, cmd.aim_y,
        speed_raw,
    )


def unpack_command(data: bytes) -> PlayerCommand:
    _, pid, mx, my, flags, ax, ay, speed_raw = _CMD_STRUCT.unpack(data[:_CMD_STRUCT.size])
    stance = _INT_TO_STANCE.get((flags >> 2) & 0x03, "machine")
    return PlayerCommand(player_id=pid, move_x=mx, move_y=my,
                         shooting=bool(flags & 0x01), aim_x=ax, aim_y=ay,
                         running=bool(flags & 0x02), stance=stance,
                         speed_mult=speed_raw / 1000.0)


def pack_state(state: GameState) -> bytes:
    header = _STATE_HDR.pack(PKT_STATE, state.tick)

    players = list(state.players.values())
    p_data  = bytes([len(players)]) + b"".join(
        _PLAYER_ENTRY.pack(
            p.id, p.x, p.y, max(0, p.hp), max(1, p.max_hp),
            int(p.aim_angle),
            _STANCE_TO_INT.get(p.stance, 0),
            state.gold_counts.get(p.id, 0),
        )
        for p in players
    )

    bullets = list(state.bullets.values())
    b_data  = bytes([len(bullets)]) + b"".join(
        _BULLET_ENTRY.pack(b.id, b.owner_id, b.x, b.y,
                           int(b.aim_angle) if -32768 <= int(b.aim_angle) <= 32767
                           else 0)
        for b in bullets
    )

    # 已摧毀障礙物 ID（最多 255 個，每個 1 byte）
    destroyed = [d for d in state.destroyed_obstacles if 0 <= d <= 255]
    d_data    = bytes([len(destroyed)]) + bytes(destroyed)

    # 金錠
    ingots = list(state.gold_ingots.values())
    g_data = bytes([len(ingots)]) + b"".join(
        _GOLD_ENTRY.pack(g.id, g.x, g.y, 1 if g.kind == "health" else 0)
        for g in ingots
    )

    return header + p_data + b_data + d_data + g_data


def unpack_state(data: bytes) -> GameState:
    offset = _STATE_HDR.size
    _, tick = _STATE_HDR.unpack(data[:offset])
    state = GameState(tick=tick)

    p_count = data[offset]; offset += 1
    for _ in range(p_count):
        pid, x, y, hp, max_hp, aim_i16, stance_u8, gold = _PLAYER_ENTRY.unpack(
            data[offset: offset + _PLAYER_ENTRY.size])
        stance = _INT_TO_STANCE.get(stance_u8, "stand")
        p = Player(id=pid, x=x, y=y, hp=hp, max_hp=max_hp,
                   aim_angle=float(aim_i16), stance=stance)
        state.players[pid] = p
        state.gold_counts[pid] = gold
        offset += _PLAYER_ENTRY.size

    b_count = data[offset]; offset += 1
    for _ in range(b_count):
        bid, owner, bx, by, angle_i16 = _BULLET_ENTRY.unpack(
            data[offset: offset + _BULLET_ENTRY.size])
        state.bullets[bid] = Bullet(id=bid, owner_id=owner, x=bx, y=by,
                                    dx=0.0, dy=0.0, aim_angle=float(angle_i16))
        offset += _BULLET_ENTRY.size

    d_count = data[offset]; offset += 1
    state.destroyed_obstacles = set(data[offset: offset + d_count])
    offset += d_count

    g_count = data[offset]; offset += 1
    for _ in range(g_count):
        gid, gx, gy, kind_byte = _GOLD_ENTRY.unpack(data[offset: offset + _GOLD_ENTRY.size])
        state.gold_ingots[gid] = GoldIngot(id=gid, x=gx, y=gy,
                                            kind="health" if kind_byte == 1 else "gold")
        offset += _GOLD_ENTRY.size

    return state


def pack_char_select(char_id: int) -> bytes:
    return bytes([PKT_CHAR_SELECT, char_id & 0xFF])


def pack_game_start(chars: dict = None) -> bytes:
    """
    chars: {pid: char_id}（最多 2 對）
    格式: PKT_GAME_START [pid char_id] ...
    """
    data = [PKT_GAME_START]
    if chars:
        for pid, char_id in sorted(chars.items()):
            data += [int(pid) & 0xFF, int(char_id) & 0xFF]
    return bytes(data)


def unpack_game_start(data: bytes) -> dict:
    """回傳 {pid: char_id}。"""
    chars = {}
    i = 1
    while i + 1 < len(data):
        chars[data[i]] = data[i + 1]
        i += 2
    return chars


def packet_type(data: bytes) -> int:
    return data[0] if data else -1
