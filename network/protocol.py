import struct
from game.command import PlayerCommand
from game.state import GameState, Player, Bullet

# --- Packet types ---
PKT_JOIN   = 0x01
PKT_JOINED = 0x02
PKT_CMD    = 0x03
PKT_STATE  = 0x04

# PKT_STATE 格式:
#   | type(1) | tick(I) |
#   | p_count(B) | [id(B) x(f) y(f) hp(B) aim_angle_i16(h) stance_u8(B)] * p_count |
#   | b_count(B) | [id(B) owner(B) x(f) y(f)] * b_count |
#   | d_count(B) | [obstacle_id(B)] * d_count |

_JOINED_STRUCT = struct.Struct("!BB")
_CMD_STRUCT    = struct.Struct("!BBffBff")
_STATE_HDR     = struct.Struct("!BI")
_PLAYER_ENTRY  = struct.Struct("!BffBhB")   # id x y hp aim_angle_i16 stance_u8
_BULLET_ENTRY  = struct.Struct("!BBff")

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
    # bit 0 = shooting, bit 1 = crouching, bits 2-3 = stance
    stance_bits = _STANCE_TO_INT.get(cmd.stance, 0) << 2
    flags = int(cmd.shooting) | (int(cmd.crouching) << 1) | stance_bits
    return _CMD_STRUCT.pack(
        PKT_CMD, cmd.player_id,
        cmd.move_x, cmd.move_y,
        flags,
        cmd.aim_x, cmd.aim_y,
    )


def unpack_command(data: bytes) -> PlayerCommand:
    _, pid, mx, my, flags, ax, ay = _CMD_STRUCT.unpack(data[:_CMD_STRUCT.size])
    stance = _INT_TO_STANCE.get((flags >> 2) & 0x03, "stand")
    return PlayerCommand(player_id=pid, move_x=mx, move_y=my,
                         shooting=bool(flags & 0x01), aim_x=ax, aim_y=ay,
                         crouching=bool(flags & 0x02), stance=stance)


def pack_state(state: GameState) -> bytes:
    header = _STATE_HDR.pack(PKT_STATE, state.tick)

    players = list(state.players.values())
    p_data  = bytes([len(players)]) + b"".join(
        _PLAYER_ENTRY.pack(
            p.id, p.x, p.y, max(0, p.hp),
            int(p.aim_angle),                   # signed int16，struct '!' 會正確處理負值
            _STANCE_TO_INT.get(p.stance, 0),
        )
        for p in players
    )

    bullets = list(state.bullets.values())
    b_data  = bytes([len(bullets)]) + b"".join(
        _BULLET_ENTRY.pack(b.id, b.owner_id, b.x, b.y) for b in bullets
    )

    # 已摧毀障礙物 ID（最多 255 個，每個 1 byte）
    destroyed = [d for d in state.destroyed_obstacles if 0 <= d <= 255]
    d_data    = bytes([len(destroyed)]) + bytes(destroyed)

    return header + p_data + b_data + d_data


def unpack_state(data: bytes) -> GameState:
    offset = _STATE_HDR.size
    _, tick = _STATE_HDR.unpack(data[:offset])
    state = GameState(tick=tick)

    p_count = data[offset]; offset += 1
    for _ in range(p_count):
        pid, x, y, hp, aim_i16, stance_u8 = _PLAYER_ENTRY.unpack(
            data[offset: offset + _PLAYER_ENTRY.size])
        stance = _INT_TO_STANCE.get(stance_u8, "stand")
        state.players[pid] = Player(id=pid, x=x, y=y, hp=hp,
                                    aim_angle=float(aim_i16), stance=stance)
        offset += _PLAYER_ENTRY.size

    b_count = data[offset]; offset += 1
    for _ in range(b_count):
        bid, owner, bx, by = _BULLET_ENTRY.unpack(data[offset: offset + _BULLET_ENTRY.size])
        state.bullets[bid] = Bullet(id=bid, owner_id=owner, x=bx, y=by, dx=0.0, dy=0.0)
        offset += _BULLET_ENTRY.size

    d_count = data[offset]; offset += 1
    state.destroyed_obstacles = set(data[offset: offset + d_count])

    return state


def packet_type(data: bytes) -> int:
    return data[0] if data else -1
