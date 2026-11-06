"""
PolarSnap UI & Presentation Contracts & Oracles (Milestone 4: Features 20-25)
"""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import List, Dict, Optional, Tuple


class MascotMood(str, Enum):
    HAPPY_IDLE = "HAPPY_IDLE"
    DOWNLOADING_ACTIVE = "DOWNLOADING_ACTIVE"
    EARMUFFS_OFFLINE = "EARMUFFS_OFFLINE"
    SLEEPING_EMPTY_VAULT = "SLEEPING_EMPTY_VAULT"
    REMASTERING_CINEMATIC = "REMASTERING_CINEMATIC"


class ScreenDestination(str, Enum):
    HOME = "home"
    DOWNLOADS = "downloads"
    SETTINGS = "settings"
    BOTTOM_SHEET_CONFIG = "bottom_sheet_config"


@dataclass(frozen=True)
class ArcticColorToken:
    name: str
    hex_code: str
    red: int
    green: int
    blue: int

    @staticmethod
    def from_hex(name: str, hex_str: str) -> "ArcticColorToken":
        cleaned = hex_str.lstrip("#")
        r = int(cleaned[0:2], 16)
        g = int(cleaned[2:4], 16)
        b = int(cleaned[4:6], 16)
        return ArcticColorToken(name=name, hex_code=f"#{cleaned.upper()}", red=r, green=g, blue=b)

    def relative_luminance(self) -> float:
        """Calculates WCAG 2.1 relative luminance."""
        def channel_srgb(c_byte: int) -> float:
            c = c_byte / 255.0
            return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)

        return 0.2126 * channel_srgb(self.red) + 0.7152 * channel_srgb(self.green) + 0.0722 * channel_srgb(self.blue)


class ArcticPaletteContract:
    """
    Authoritative Arctic Streamline Design System color palette.
    """
    PRIMARY_DEEP_CYAN = ArcticColorToken.from_hex("PrimaryDeepCyan", "#004E5C")
    BRIGHT_CYAN = ArcticColorToken.from_hex("BrightCyan", "#00687A")
    ABYSSAL_INDIGO = ArcticColorToken.from_hex("AbyssalIndigo", "#1B365D")
    GLACIER_TEAL = ArcticColorToken.from_hex("GlacierTeal", "#00A896")
    POLAR_SURFACE_LIGHT = ArcticColorToken.from_hex("PolarSurfaceLight", "#F5FAFF")
    POLAR_SURFACE_DARK = ArcticColorToken.from_hex("PolarSurfaceDark", "#0A141E")

    @staticmethod
    def contrast_ratio(color_a: ArcticColorToken, color_b: ArcticColorToken) -> float:
        l1 = color_a.relative_luminance()
        l2 = color_b.relative_luminance()
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)


class MascotIdentityContract:
    @staticmethod
    def resolve_mood(
        is_online: bool,
        is_queue_empty: bool,
        active_downloads_count: int,
        is_remastering_active: bool
    ) -> MascotMood:
        if not is_online:
            return MascotMood.EARMUFFS_OFFLINE
        if is_remastering_active:
            return MascotMood.REMASTERING_CINEMATIC
        if active_downloads_count > 0:
            return MascotMood.DOWNLOADING_ACTIVE
        if is_queue_empty:
            return MascotMood.SLEEPING_EMPTY_VAULT
        return MascotMood.HAPPY_IDLE


class DeveloperConsoleContract:
    SECRET_TAP_THRESHOLD = 7

    def __init__(self):
        self.tap_count: int = 0
        self.is_unlocked: bool = False

    def tap_engine_version_banner(self) -> bool:
        if self.is_unlocked:
            return True
        self.tap_count += 1
        if self.tap_count >= self.SECRET_TAP_THRESHOLD:
            self.is_unlocked = True
        return self.is_unlocked

    def reset(self):
        self.tap_count = 0
        self.is_unlocked = False
