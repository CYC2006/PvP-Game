import struct
from game.command import PlayerCommand
from game.state import GameState, Player, Bullet, GoldIngot, SmokePatch, BladeArc, AirStrike, LogBarrier, Mine, PoisonPool, PushZone, RobotMark, RobotEMark, RobotERing, Turret, BarrageStrike, Shield, ZombieOrb

# --- Packet types ---
PKT_JOIN        = 0x01
PKT_JOINED      = 0x02
PKT_CMD         = 0x03
PKT_STATE       = 0x04
PKT_CHAR_SELECT = 0x05   # client → server: 選好角色（2 bytes: type + char_id）
PKT_GAME_START  = 0x06   # server → clients: 雙方都選完，遊戲開始
PKT_ALL_JOINED  = 0x07   # server → clients: 所有玩家都已連線，可進入選角
PKT_QUIT        = 0x08   # client → server: 玩家主動離開
PKT_GAME_OVER   = 0x09   # server → clients: 一方離開，遊戲結束
PKT_PING        = 0x0A   # client → server: liveness probe（不改任何 session 狀態）
PKT_PONG        = 0x0B   # server → client: probe 回應

# PKT_STATE 格式:
#   | type(1) | tick(I) |
#   | p_count(B) | [id(B) x(f) y(f) hp(H) max_hp(H) aim_angle_i16(h) stance_u8(B) gold(H)] * p_count |
#   | b_count(B) | [id(B) owner(B) x(f) y(f) angle_i16(h)] * b_count |
#   | d_count(B) | [obstacle_id(B)] * d_count |
#   | g_count(B) | [id(B) x(f) y(f)] * g_count |
#   | s_count(B) | [id(B) x(f) y(f) radius_u16(H) spawn_tick(I)] * s_count |
#   | ba_count(B) | [id(B) x(h) y(h) age(B) dir(b) owner(B)] * ba_count |

_JOINED_STRUCT = struct.Struct("!BB")
_CMD_STRUCT    = struct.Struct("!BBffBBffH")  # +B: flags2（bit0=use_rune bit1=rmb_held）
_STATE_HDR     = struct.Struct("!BI")
_PLAYER_ENTRY  = struct.Struct("!BffHHhBHBHBBBBBBBBBBBBBBBBHBBBBBBHBHHHBBBB")  # id x y hp max_hp aim_angle stance gold flash_ticks giant_age stun_ticks burst_shots_left clone_ticks jump_age cloak_rem vince_dash zombie_jump_age vince_taunt_age poison_stacks e_shockwave_seq air_cannon_hit_seq zombie_rage_age agent_dash assassin_smoke zombie_spit r_skill_phase zombie_energy marksman_barrage hunter_bomb agent_powershot mercury_barrage assassin_speed_boost assassin_blade | damage_dealt obstacles_destroyed healing_received distance_traveled lmb_uses rmb_uses space_uses e_uses f_uses
_AIR_CANNON_ENTRY = struct.Struct("!BhhB")  # id x_i16 y_i16 owner_id
_BULLET_ENTRY  = struct.Struct("!BBffhBB")    # id owner x y angle_i16 bullet_type bullet_scale_u8(×10)
_GOLD_ENTRY    = struct.Struct("!BffB")       # id x y kind(0=gold,1=health)
_SMOKE_ENTRY   = struct.Struct("!BffHIB")    # id x y radius*10 spawn_tick owner_id
_BLADE_ENTRY      = struct.Struct("!BhhBbB")   # id x_i16 y_i16 age dir owner_id
_AIRSTRIKE_ENTRY  = struct.Struct("!BhhBB")    # id cx_i16 cy_i16 age(u8) owner_id
_LOG_BARRIER_ENTRY = struct.Struct("!BhhBBB")  # id x_i16 y_i16 hp(u8) owner_id radius_u8
_MINE_ENTRY        = struct.Struct("!BhhHB")  # id x_i16 y_i16 triggered_age_u16(65535=idle) owner_id
_POOL_ENTRY        = struct.Struct("!BhhHBBB") # id x_i16 y_i16 age_u16 owner_id source_u8(0=rmb,1=space) radius_u8
_PUSH_ENTRY        = struct.Struct("!BhhHhB") # id x_i16 y_i16 age_u16 angle_i16 owner_id
_ROBOT_MARK_ENTRY  = struct.Struct("!BhhH")  # owner_id x_i16 y_i16 age_u16
_TURRET_ENTRY      = struct.Struct("!BhhHB")  # id x_i16 y_i16 hp_u16 owner_id
_BARRAGE_ENTRY     = struct.Struct("!BhhBB")  # id x_i16 y_i16 age_u8 owner_id
_SHIELD_ENTRY      = struct.Struct("!BHHB")   # owner_id hp_u16 max_hp_u16 status_u8(0=active,1=broken)
_E_RING_ENTRY      = struct.Struct("!BhhH")  # owner_id cx_i16 cy_i16 age_u16
_E_MARK_ENTRY      = struct.Struct("!BhhHB") # owner_id cx_i16 cy_i16 age_u16 start_angle_u8(idx: 0=0°,1=90°,2=180°,3=270°)
_ZOMBIE_ORB_ENTRY  = struct.Struct("!BhhBBBB") # id x_i16 y_i16 radius_u8 age_u8 fade_u8 owner_id

# stance 編碼表
_STANCE_TO_INT = {"stand": 0, "machine": 1, "hold": 2}
_INT_TO_STANCE = {0: "stand", 1: "machine", 2: "hold"}


def pack_all_joined() -> bytes:
    return bytes([PKT_ALL_JOINED])


def pack_join(room_code: int, map_id: int = 0, game_mode: int = 0) -> bytes:
    """game_mode: 0=deathmatch, 1=endless"""
    return bytes([PKT_JOIN]) + struct.pack('>H', room_code) + bytes([map_id & 0xFF, game_mode & 0xFF])


def unpack_join(data: bytes) -> tuple:
    """Returns (room_code, map_id, game_mode)."""
    room_code = struct.unpack('>H', data[1:3])[0] if len(data) >= 3 else 0
    map_id    = data[3] if len(data) >= 4 else 0
    game_mode = data[4] if len(data) >= 5 else 0
    return room_code, map_id, game_mode


def pack_joined(player_id: int) -> bytes:
    return _JOINED_STRUCT.pack(PKT_JOINED, player_id)


def unpack_joined(data: bytes) -> int:
    _, player_id = _JOINED_STRUCT.unpack(data[:_JOINED_STRUCT.size])
    return player_id


def pack_command(cmd: PlayerCommand) -> bytes:
    # flags bit 0=shooting  bit 1=running  bits 2-3=stance  bit 4=use_skill_e
    #       bit 5=use_skill_rmb  bit 6=use_skill_space  bit 7=use_skill_r
    # flags2 bit 0=use_rune  bit 1=rmb_held（持續狀態，非邊緣觸發；Zombie 體力衝刺用）
    stance_bits = _STANCE_TO_INT.get(cmd.stance, 0) << 2
    flags = (int(cmd.shooting)
             | (int(cmd.running)          << 1)
             | stance_bits
             | (int(cmd.use_skill_e)     << 4)
             | (int(cmd.use_skill_rmb)   << 5)
             | (int(cmd.use_skill_space) << 6)
             | (int(cmd.use_skill_r)     << 7))
    flags2    = int(cmd.use_rune) | (int(cmd.rmb_held) << 1)
    speed_raw = max(0, min(65535, int(cmd.speed_mult * 1000)))
    return _CMD_STRUCT.pack(
        PKT_CMD, cmd.player_id,
        cmd.move_x, cmd.move_y,
        flags, flags2,
        cmd.aim_x, cmd.aim_y,
        speed_raw,
    )


def unpack_command(data: bytes) -> PlayerCommand:
    _, pid, mx, my, flags, flags2, ax, ay, speed_raw = _CMD_STRUCT.unpack(data[:_CMD_STRUCT.size])
    stance = _INT_TO_STANCE.get((flags >> 2) & 0x03, "machine")
    return PlayerCommand(player_id=pid, move_x=mx, move_y=my,
                         shooting=bool(flags & 0x01), aim_x=ax, aim_y=ay,
                         running=bool(flags & 0x02), stance=stance,
                         speed_mult=speed_raw / 1000.0,
                         use_skill_e=bool((flags >> 4) & 0x01),
                         use_skill_rmb=bool((flags >> 5) & 0x01),
                         use_skill_space=bool((flags >> 6) & 0x01),
                         use_skill_r=bool((flags >> 7) & 0x01),
                         use_rune=bool(flags2 & 0x01),
                         rmb_held=bool((flags2 >> 1) & 0x01))


def pack_state(state: GameState) -> bytes:
    header = _STATE_HDR.pack(PKT_STATE, state.tick)

    players = list(state.players.values())
    p_data  = bytes([len(players)]) + b"".join(
        _PLAYER_ENTRY.pack(
            p.id, p.x, p.y, max(0, p.hp), max(1, p.max_hp),
            int(p.aim_angle),
            _STANCE_TO_INT.get(p.stance, 0),
            (min(255, state.kill_counts.get(p.id, 0)) << 8) | min(255, state.gold_counts.get(p.id, 0)),
            min(255, max(0, p.flash_ticks)),
            min(65535, state.tick - p.giant_tick) if p.giant_tick >= 0 else 65535,
            min(255, p.stun_until - state.tick) if p.stun_until > state.tick else 0,
            max(0, 6 - p.burst_shots_fired) if p.burst_next_tick >= 0 else 0,
            min(255, p.clone_until - state.tick) if p.clone_until > state.tick else 0,
            min(254, state.tick - p.jump_tick) if p.jump_tick >= 0 else 255,
            min(254, p.cloak_until - state.tick) if p.cloak_until > state.tick else 255,
            1 if p.vince_dash_tick >= 0 else 0,
            min(254, state.tick - p.zombie_jump_tick) if p.zombie_jump_tick >= 0 else 255,
            min(254, state.tick - p.vince_taunt_tick) if p.vince_taunt_tick >= 0 else 255,
            min(255, max(0, p.poison_stacks)),
            p.poisoner_e_shockwave_seq,
            p.air_cannon_hit_seq & 0xFF,
            min(254, state.tick - p.zombie_rage_tick) if p.zombie_rage_tick >= 0 else 255,
            1 if p.agent_dash_tick >= 0 else 0,
            1 if p.assassin_smoke_tick >= 0 else 0,
            1 if p.zombie_spit_tick >= 0 else 0,
            1 if p.r_skill_phase > 0 else 0,
            max(0, min(300, int(round(p.zombie_energy)))),
            1 if p.marksman_barrage_tick >= 0 else 0,
            1 if p.hunter_bomb_tick >= 0 else 0,
            1 if p.agent_powershot_tick >= 0 else 0,
            1 if p.mercury_start_tick >= 0 else 0,
            1 if p.speed_boost_ticks > 0 else 0,
            1 if p.assassin_blade_tick >= 0 else 0,
            min(65535, p.damage_dealt),
            min(255,   p.obstacles_destroyed),
            min(65535, p.healing_received),
            min(65535, p.distance_traveled // 10),
            min(65535, p.lmb_uses),
            min(255,   p.rmb_uses),
            min(255,   p.space_uses),
            min(255,   p.e_uses),
            min(255,   p.f_uses),
        )
        for p in players
    )

    bullets = list(state.bullets.values())
    b_data  = bytes([len(bullets)]) + b"".join(
        _BULLET_ENTRY.pack(b.id, b.owner_id, b.x, b.y,
                           int(b.aim_angle) if -32768 <= int(b.aim_angle) <= 32767
                           else 0,
                           b.bullet_type,
                           min(255, max(1, int(b.bullet_scale * 10))))
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

    smokes = list(state.smoke_patches.values())
    s_data = bytes([len(smokes)]) + b"".join(
        _SMOKE_ENTRY.pack(s.id, s.x, s.y, int(s.radius * 10), s.spawn_tick, s.owner_id)
        for s in smokes
    )

    blades = list(state.blade_arcs.values())
    ba_data = bytes([len(blades)]) + b"".join(
        _BLADE_ENTRY.pack(b.id, int(b.x), int(b.y),
                          min(255, b.age), b.direction, b.owner_id)
        for b in blades
    )

    strikes = list(state.air_strikes.values())
    as_data = bytes([len(strikes)]) + b"".join(
        _AIRSTRIKE_ENTRY.pack(
            s.id, int(s.cx), int(s.cy),
            min(255, state.tick - s.spawn_tick), s.owner_id)
        for s in strikes
    )

    barriers = list(state.log_barriers.values())
    lb_data = bytes([len(barriers)]) + b"".join(
        _LOG_BARRIER_ENTRY.pack(lb.id, int(lb.x), int(lb.y), max(0, lb.hp), lb.owner_id, int(lb.radius))
        for lb in barriers
    )

    mine_list = list(state.mines.values())
    mine_data = bytes([len(mine_list)]) + b"".join(
        _MINE_ENTRY.pack(
            m.id, int(m.x), int(m.y),
            min(65534, state.tick - m.triggered_tick) if m.triggered_tick >= 0 else 65535,
            m.owner_id)
        for m in mine_list
    )

    pool_list = list(state.poison_pools.values())
    pool_data = bytes([len(pool_list)]) + b"".join(
        _POOL_ENTRY.pack(p.id, int(p.x), int(p.y),
                         min(65534, state.tick - p.spawn_tick), p.owner_id,
                         1 if p.pool_source == 'space' else 0, int(p.radius))
        for p in pool_list
    )

    push_list = list(state.push_zones.values())
    push_data = bytes([len(push_list)]) + b"".join(
        _PUSH_ENTRY.pack(pz.id, int(pz.x), int(pz.y),
                         min(65534, state.tick - pz.spawn_tick),
                         int(pz.angle) % 360 - (360 if int(pz.angle) % 360 > 180 else 0),
                         pz.owner_id)
        for pz in push_list
    )

    mark_list = list(state.robot_marks.values())
    mark_data = bytes([len(mark_list)]) + b"".join(
        _ROBOT_MARK_ENTRY.pack(
            m.owner_id, int(m.x), int(m.y),
            min(65534, state.tick - m.spawn_tick))
        for m in mark_list
    )

    turret_list = list(state.turrets.values())
    turret_data = bytes([len(turret_list)]) + b"".join(
        _TURRET_ENTRY.pack(t.id, int(t.x), int(t.y), max(0, t.hp), t.owner_id)
        for t in turret_list
    )

    barrage_list = list(state.barrage_strikes.values())
    barrage_data = bytes([len(barrage_list)]) + b"".join(
        _BARRAGE_ENTRY.pack(s.id, int(s.x), int(s.y),
                            min(255, state.tick - s.spawn_tick), s.owner_id)
        for s in barrage_list
    )

    shield_list = list(state.shields.values())
    shield_data = bytes([len(shield_list)]) + b"".join(
        _SHIELD_ENTRY.pack(sh.owner_id, max(0, sh.hp), max(1, sh.max_hp),
                           1 if sh.broken_tick >= 0 else 0)
        for sh in shield_list
    )

    cannon_list = list(state.air_cannons.values())
    cannon_data = bytes([len(cannon_list)]) + b"".join(
        _AIR_CANNON_ENTRY.pack(c.id, int(c.x), int(c.y), c.owner_id)
        for c in cannon_list
    )

    _E_ANGLE_IDX = {0: 0, 90: 1, 180: 2, 270: 3}
    e_ring_list = list(state.robot_e_rings.values())
    e_ring_data = bytes([len(e_ring_list)]) + b"".join(
        _E_RING_ENTRY.pack(r.owner_id, int(r.x), int(r.y),
                           min(65534, state.tick - r.spawn_tick))
        for r in e_ring_list
    )
    e_mark_list = list(state.robot_e_marks.values())
    e_mark_data = bytes([len(e_mark_list)]) + b"".join(
        _E_MARK_ENTRY.pack(m.owner_id, int(m.center_x), int(m.center_y),
                           min(65534, state.tick - m.spawn_tick),
                           _E_ANGLE_IDX.get(m.start_angle, 0))
        for m in e_mark_list
    )

    orb_list = list(state.zombie_orbs.values())
    orb_data = bytes([len(orb_list)]) + b"".join(
        _ZOMBIE_ORB_ENTRY.pack(o.id, int(o.x), int(o.y),
                               min(255, int(o.radius)),
                               min(255, state.tick - o.spawn_tick),
                               max(0, min(255, o.fade)),
                               o.owner_id)
        for o in orb_list
    )

    # lives（deathmatch 用）
    lives_entries = sorted(state.lives.items())
    lives_data    = bytes([len(lives_entries)]) + b"".join(
        bytes([pid & 0xFF, min(255, lv)]) for pid, lv in lives_entries
    )

    return header + p_data + b_data + d_data + g_data + s_data + ba_data + as_data + lb_data + mine_data + pool_data + push_data + mark_data + turret_data + barrage_data + shield_data + cannon_data + e_ring_data + e_mark_data + orb_data + lives_data


def unpack_state(data: bytes) -> GameState:
    offset = _STATE_HDR.size
    _, tick = _STATE_HDR.unpack(data[:offset])
    state = GameState(tick=tick)

    p_count = data[offset]; offset += 1
    for _ in range(p_count):
        (pid, x, y, hp, max_hp, aim_i16, stance_u8, gold, flash,
         giant_age, stun_b, burst_b, clone_b, jump_age, cloak_rem,
         vince_dash, zombie_jump_age, vince_taunt_age,
         poison_stacks_b, e_sw_seq_b, ac_hit_seq_b, zombie_rage_age,
         agent_dash, assassin_smoke, zombie_spit, r_skill_active,
         zombie_energy, marksman_barrage, hunter_bomb,
         agent_powershot, mercury_barrage,
         assassin_speed_boost, assassin_blade,
         dmg_dealt, obs_destr, heal_recv, dist_raw,
         lmb_u, rmb_u, space_u, e_u, f_u) = _PLAYER_ENTRY.unpack(
            data[offset: offset + _PLAYER_ENTRY.size])
        stance = _INT_TO_STANCE.get(stance_u8, "stand")
        p = Player(id=pid, x=x, y=y, hp=hp, max_hp=max_hp,
                   aim_angle=float(aim_i16), stance=stance, flash_ticks=flash)
        p.giant_tick             = tick - giant_age if giant_age != 65535 else -1
        p.clone_until            = tick + clone_b if clone_b > 0 else -1
        p.stun_until             = tick + stun_b if stun_b > 0 else -1
        p.burst_shots_fired      = 6 - burst_b   # used client-side only to detect active burst
        p.jump_tick              = tick - jump_age if jump_age != 255 else -1
        p.cloak_until            = tick + cloak_rem if cloak_rem != 255 else -1
        p.vince_dash_tick        = 0 if vince_dash else -1
        p.zombie_jump_tick       = tick - zombie_jump_age if zombie_jump_age != 255 else -1
        p.vince_taunt_tick       = tick - vince_taunt_age if vince_taunt_age != 255 else -1
        p.poison_stacks            = poison_stacks_b
        p.poisoner_e_shockwave_seq = e_sw_seq_b
        p.air_cannon_hit_seq       = ac_hit_seq_b
        p.zombie_rage_tick         = tick - zombie_rage_age if zombie_rage_age != 255 else -1
        p.agent_dash_tick          = 0 if agent_dash else -1
        p.assassin_smoke_tick      = 0 if assassin_smoke else -1
        p.zombie_spit_tick         = 0 if zombie_spit else -1
        p.r_skill_phase            = 1 if r_skill_active else 0
        p.zombie_energy            = float(zombie_energy)
        p.marksman_barrage_tick    = 0 if marksman_barrage else -1
        p.hunter_bomb_tick         = 0 if hunter_bomb else -1
        p.agent_powershot_tick     = 0 if agent_powershot else -1
        p.mercury_start_tick       = 0 if mercury_barrage else -1
        p.speed_boost_ticks        = 1 if assassin_speed_boost else 0
        p.assassin_blade_tick      = 0 if assassin_blade else -1
        p.damage_dealt             = dmg_dealt
        p.obstacles_destroyed      = obs_destr
        p.healing_received         = heal_recv
        p.distance_traveled        = dist_raw * 10
        p.lmb_uses                 = lmb_u
        p.rmb_uses                 = rmb_u
        p.space_uses               = space_u
        p.e_uses                   = e_u
        p.f_uses                   = f_u
        state.players[pid]     = p
        state.gold_counts[pid] = gold & 0xFF          # lower byte = gem count
        state.kill_counts[pid] = (gold >> 8) & 0xFF   # upper byte = kill count
        offset += _PLAYER_ENTRY.size

    b_count = data[offset]; offset += 1
    for _ in range(b_count):
        bid, owner, bx, by, angle_i16, btype, bscale_u8 = _BULLET_ENTRY.unpack(
            data[offset: offset + _BULLET_ENTRY.size])
        state.bullets[bid] = Bullet(id=bid, owner_id=owner, x=bx, y=by,
                                    dx=0.0, dy=0.0, aim_angle=float(angle_i16),
                                    bullet_type=btype,
                                    bullet_scale=bscale_u8 / 10.0)
        offset += _BULLET_ENTRY.size

    d_count = data[offset]; offset += 1
    state.destroyed_obstacles = set(data[offset: offset + d_count])
    offset += d_count

    g_count = data[offset]; offset += 1
    for _ in range(g_count):
        gid, gx, gy, kind_byte = _GOLD_ENTRY.unpack(data[offset: offset + _GOLD_ENTRY.size])
        state.gold_ingots[gid] = GoldIngot(id=gid, x=gx, y=gy,
                                            kind="health" if kind_byte == 1 else "gem")
        offset += _GOLD_ENTRY.size

    if offset < len(data):
        s_count = data[offset]; offset += 1
        for _ in range(s_count):
            sid, sx, sy, r_u16, stick, sowner = _SMOKE_ENTRY.unpack(
                data[offset: offset + _SMOKE_ENTRY.size])
            state.smoke_patches[sid] = SmokePatch(
                id=sid, x=sx, y=sy, radius=r_u16 / 10.0, spawn_tick=stick, owner_id=sowner)
            offset += _SMOKE_ENTRY.size

    if offset < len(data):
        ba_count = data[offset]; offset += 1
        for _ in range(ba_count):
            bid, bx, by, age, direction, owner = _BLADE_ENTRY.unpack(
                data[offset: offset + _BLADE_ENTRY.size])
            state.blade_arcs[bid] = BladeArc(
                id=bid, owner_id=owner,
                x=float(bx), y=float(by),
                orbit_radius=0.0, orbit_angle=0.0,
                direction=direction, damage=0, age=age,
            )
            offset += _BLADE_ENTRY.size

    if offset < len(data):
        as_count = data[offset]; offset += 1
        for _ in range(as_count):
            sid, scx, scy, age, owner = _AIRSTRIKE_ENTRY.unpack(
                data[offset: offset + _AIRSTRIKE_ENTRY.size])
            state.air_strikes[sid] = AirStrike(
                id=sid, owner_id=owner,
                cx=float(scx), cy=float(scy),
                spawn_tick=state.tick - age,
            )
            offset += _AIRSTRIKE_ENTRY.size

    if offset < len(data):
        lb_count = data[offset]; offset += 1
        for _ in range(lb_count):
            lid, lx, ly, lhp, lowner, lradius = _LOG_BARRIER_ENTRY.unpack(
                data[offset: offset + _LOG_BARRIER_ENTRY.size])
            state.log_barriers[lid] = LogBarrier(
                id=lid, owner_id=lowner, x=float(lx), y=float(ly), hp=lhp,
                radius=float(lradius))
            offset += _LOG_BARRIER_ENTRY.size

    if offset < len(data):
        mine_count = data[offset]; offset += 1
        for _ in range(mine_count):
            mid, mx, my, trig_age, mowner = _MINE_ENTRY.unpack(
                data[offset: offset + _MINE_ENTRY.size])
            m = Mine(id=mid, owner_id=mowner, x=float(mx), y=float(my))
            m.triggered_tick = state.tick - trig_age if trig_age != 65535 else -1
            state.mines[mid] = m
            offset += _MINE_ENTRY.size

    if offset < len(data):
        pool_count = data[offset]; offset += 1
        for _ in range(pool_count):
            ppid, px, py, page, powner, src_b, r_u8 = _POOL_ENTRY.unpack(
                data[offset: offset + _POOL_ENTRY.size])
            src = 'space' if src_b == 1 else 'rmb'
            pp  = PoisonPool(id=ppid, owner_id=powner, x=float(px), y=float(py),
                             spawn_tick=state.tick - page,
                             radius=float(r_u8),
                             pool_source=src)
            state.poison_pools[ppid] = pp
            offset += _POOL_ENTRY.size

    if offset < len(data):
        push_count = data[offset]; offset += 1
        for _ in range(push_count):
            pzid, pzx, pzy, pzage, pzangle, pzowner = _PUSH_ENTRY.unpack(
                data[offset: offset + _PUSH_ENTRY.size])
            state.push_zones[pzid] = PushZone(
                id=pzid, owner_id=pzowner,
                x=float(pzx), y=float(pzy),
                angle=float(pzangle),
                spawn_tick=state.tick - pzage,
            )
            offset += _PUSH_ENTRY.size

    if offset < len(data):
        mark_count = data[offset]; offset += 1
        for _ in range(mark_count):
            mowner, mx, my, mage = _ROBOT_MARK_ENTRY.unpack(
                data[offset: offset + _ROBOT_MARK_ENTRY.size])
            state.robot_marks[mowner] = RobotMark(
                owner_id=mowner, x=float(mx), y=float(my),
                spawn_tick=state.tick - mage,
            )
            offset += _ROBOT_MARK_ENTRY.size

    if offset < len(data):
        turret_count = data[offset]; offset += 1
        for _ in range(turret_count):
            tid, tx, ty, thp, towner = _TURRET_ENTRY.unpack(
                data[offset: offset + _TURRET_ENTRY.size])
            state.turrets[tid] = Turret(
                id=tid, owner_id=towner, x=float(tx), y=float(ty), hp=thp)
            offset += _TURRET_ENTRY.size

    if offset < len(data):
        barrage_count = data[offset]; offset += 1
        for _ in range(barrage_count):
            sid, bx, by, bage, bowner = _BARRAGE_ENTRY.unpack(
                data[offset: offset + _BARRAGE_ENTRY.size])
            state.barrage_strikes[sid] = BarrageStrike(
                id=sid, owner_id=bowner, x=float(bx), y=float(by),
                spawn_tick=state.tick - bage)
            offset += _BARRAGE_ENTRY.size

    if offset < len(data):
        shield_count = data[offset]; offset += 1
        for _ in range(shield_count):
            sowner, shp, smaxhp, sstatus = _SHIELD_ENTRY.unpack(
                data[offset: offset + _SHIELD_ENTRY.size])
            sh = Shield(owner_id=sowner, hp=shp, max_hp=smaxhp)
            sh.broken_tick = 0 if sstatus == 1 else -1
            state.shields[sowner] = sh
            offset += _SHIELD_ENTRY.size

    if offset < len(data):
        cannon_count = data[offset]; offset += 1
        for _ in range(cannon_count):
            cid, cx, cy, cowner = _AIR_CANNON_ENTRY.unpack(
                data[offset: offset + _AIR_CANNON_ENTRY.size])
            from game.state import AirCannon
            state.air_cannons[cid] = AirCannon(
                id=cid, owner_id=cowner,
                x=float(cx), y=float(cy),
                dx=0.0, dy=0.0, spawn_tick=state.tick)
            offset += _AIR_CANNON_ENTRY.size

    _E_IDX_ANGLE = {0: 0, 1: 90, 2: 180, 3: 270}
    if offset < len(data):
        er_count = data[offset]; offset += 1
        for _ in range(er_count):
            er_owner, er_cx, er_cy, er_age = _E_RING_ENTRY.unpack(
                data[offset: offset + _E_RING_ENTRY.size])
            state.robot_e_rings[er_owner] = RobotERing(
                owner_id=er_owner, x=float(er_cx), y=float(er_cy),
                spawn_tick=state.tick - er_age)
            offset += _E_RING_ENTRY.size

    if offset < len(data):
        em_count = data[offset]; offset += 1
        for _ in range(em_count):
            em_owner, em_cx, em_cy, em_age, em_aidx = _E_MARK_ENTRY.unpack(
                data[offset: offset + _E_MARK_ENTRY.size])
            state.robot_e_marks[em_owner] = RobotEMark(
                owner_id=em_owner,
                center_x=float(em_cx), center_y=float(em_cy),
                start_angle=_E_IDX_ANGLE.get(em_aidx, 0),
                spawn_tick=state.tick - em_age)
            offset += _E_MARK_ENTRY.size

    if offset < len(data):
        orb_count = data[offset]; offset += 1
        for _ in range(orb_count):
            oid, ox, oy, oradius, oage, ofade, oowner = _ZOMBIE_ORB_ENTRY.unpack(
                data[offset: offset + _ZOMBIE_ORB_ENTRY.size])
            state.zombie_orbs[oid] = ZombieOrb(
                id=oid, owner_id=oowner, x=float(ox), y=float(oy),
                radius=float(oradius), spawn_tick=state.tick - oage,
                fade=ofade)
            offset += _ZOMBIE_ORB_ENTRY.size

    if offset < len(data):
        lv_count = data[offset]; offset += 1
        for _ in range(lv_count):
            if offset + 1 <= len(data):
                lv_pid   = data[offset]
                lv_lives = data[offset + 1]
                state.lives[lv_pid] = lv_lives
                offset += 2

    return state


def pack_char_select(char_id: int, rune_id: int = 0) -> bytes:
    return bytes([PKT_CHAR_SELECT, char_id & 0xFF, rune_id & 0xFF])


def pack_game_start(chars: dict = None, map_id: int = 0,
                    game_mode: int = 0, side_flip: bool = False,
                    obstacle_seed: int = 0) -> bytes:
    """
    格式: PKT_GAME_START [pid char_id]... map_id game_mode side_flip seed_hi seed_lo
    game_mode: 0=deathmatch, 1=endless
    obstacle_seed: 0 = load from file; >0 = generate dynamically with this seed
    """
    data = [PKT_GAME_START]
    if chars:
        for pid, char_id in sorted(chars.items()):
            data += [int(pid) & 0xFF, int(char_id) & 0xFF]
    data += [int(map_id) & 0xFF, int(game_mode) & 0xFF, 1 if side_flip else 0]
    data += [(obstacle_seed >> 8) & 0xFF, obstacle_seed & 0xFF]
    return bytes(data)


def unpack_game_start(data: bytes) -> tuple:
    """回傳 ({pid: char_id}, map_id, game_mode, side_flip, obstacle_seed)。
    格式固定為 2 對 [pid char_id]，後接 map_id, game_mode, side_flip, seed_hi, seed_lo。
    """
    chars = {}
    i = 1
    for _ in range(2):   # MAX_PLAYERS = 2
        if i + 1 < len(data):
            chars[data[i]] = data[i + 1]
            i += 2
    map_id        = data[i]     if i     < len(data) else 0
    game_mode     = data[i + 1] if i + 1 < len(data) else 0
    side_flip     = bool(data[i + 2]) if i + 2 < len(data) else False
    obstacle_seed = (((data[i + 3] << 8) | data[i + 4])
                     if i + 4 < len(data) else 0)
    return chars, map_id, game_mode, side_flip, obstacle_seed


def pack_quit(player_id: int) -> bytes:
    """client → server: 主動離場通知。"""
    return bytes([PKT_QUIT, player_id & 0xFF])


def pack_game_over() -> bytes:
    """server → clients: 廣播遊戲結束。"""
    return bytes([PKT_GAME_OVER])


def pack_ping() -> bytes:
    """client → server: liveness probe, no session state change."""
    return bytes([PKT_PING])


def packet_type(data: bytes) -> int:
    return data[0] if data else -1
