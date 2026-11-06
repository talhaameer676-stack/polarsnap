"""
PolarSnap Engine Contracts & Reference Oracles (Milestone 1: Features 1-8)
"""
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import List, Dict, Any, Optional, Tuple


class ResolutionLimit(str, Enum):
    RES_4K = "4K_2160P"
    RES_1440P = "QHD_1440P"
    RES_1080P = "FHD_1080P"
    RES_720P = "HD_720P"
    AUDIO_ONLY = "AUDIO_ONLY"


class FormatContainer(str, Enum):
    MP4 = "MP4"
    MKV = "MKV"
    MP3 = "MP3"
    FLAC = "FLAC"


@dataclass
class EngineOptions:
    turbo_acceleration: bool = True
    lossless_audio: bool = False
    clean_watermark: bool = True
    sponsor_stripper: bool = True
    custom_format_container: FormatContainer = FormatContainer.MP4
    resolution_limit: ResolutionLimit = ResolutionLimit.RES_1080P


@dataclass
class SanitizedStreamEvent:
    progress_percent: float
    speed_formatted: str
    eta_formatted: str
    total_size_formatted: str
    status_message: str


class PolarErrorType(str, Enum):
    STREAM_PROTECTED = "StreamProtected"
    ANTI_BOT_VERIFICATION = "AntiBotVerification"
    MEDIA_UNREACHABLE = "MediaUnreachable"
    SERVICE_COOLDOWN = "ServiceCooldown"
    INVALID_MEDIA_URL = "InvalidMediaUrl"
    ENGINE_OPERATION_FAILED = "EngineOperationFailed"


@dataclass
class PolarException(Exception):
    error_type: PolarErrorType
    user_message: str
    code: int


class ELFAlignmentChecker:
    PAGE_SIZE_16KB = 16384

    @staticmethod
    def is_16kb_aligned(load_offset: int, vaddr: int, p_align: int) -> bool:
        """
        Android 15 requires 16KB ELF page alignment:
        1. p_align must be >= 16384 and a power of 2.
        2. (vaddr - load_offset) % p_align == 0.
        """
        if p_align < ELFAlignmentChecker.PAGE_SIZE_16KB:
            return False
        if (p_align & (p_align - 1)) != 0:
            return False
        return (vaddr - load_offset) % p_align == 0


class PolarCommandTranslatorContract:
    FORBIDDEN_LEAK_WORDS = [
        "yt-dlp",
        "youtube-dl",
        "python",
        "cpython",
        "site-packages",
        "libaria2c.so",
        "-N 16",
        "--remux-video",
    ]

    @staticmethod
    def translate(url: str, options: EngineOptions) -> List[str]:
        args: List[str] = ["--no-call-home", "--no-check-certificates"]

        # Turbo Acceleration
        if options.turbo_acceleration:
            args.extend(["-N", "16", "--downloader", "aria2c"])

        # Sponsor Stripper
        if options.sponsor_stripper:
            args.extend(["--sponsorblock-remove", "default"])

        # Format & Container Logic
        if options.lossless_audio or options.resolution_limit == ResolutionLimit.AUDIO_ONLY:
            args.extend(["-x"])
            if options.custom_format_container == FormatContainer.FLAC or options.lossless_audio:
                args.extend(["--audio-format", "flac"])
            else:
                args.extend(["--audio-format", "mp3"])
        else:
            # Video container & quality
            if options.resolution_limit == ResolutionLimit.RES_4K:
                format_spec = "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
            elif options.resolution_limit == ResolutionLimit.RES_1440P:
                format_spec = "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best"
            elif options.resolution_limit == ResolutionLimit.RES_1080P:
                format_spec = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            else:
                format_spec = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"

            args.extend(["-f", format_spec])
            container_str = options.custom_format_container.value.lower()
            args.extend(["--merge-output-format", container_str])

        # Clean Watermark (TikTok / Douyin / Instagram / Reels)
        if options.clean_watermark:
            args.extend(["--extractor-args", "tiktok:no_watermark=1"])

        args.append(url)
        return args


class PolarLogSanitizerContract:
    FORBIDDEN_PATTERNS = [
        re.compile(r"yt[-_]?dlp", re.IGNORECASE),
        re.compile(r"youtube[-_]?dl", re.IGNORECASE),
        re.compile(r"python\s*(3\.\d+)?", re.IGNORECASE),
        re.compile(r"/data/data/[^/]+/files/python", re.IGNORECASE),
        re.compile(r"traceback\s+\(most\s+recent\s+call\s+last\):", re.IGNORECASE),
        re.compile(r"File\s+\".*?\.py\",\s+line\s+\d+", re.IGNORECASE),
        re.compile(r"libaria2c\.so", re.IGNORECASE),
    ]

    PROGRESS_REGEX = re.compile(
        r"\[download\]\s+(?P<percent>[\d\.]+)%\s+of\s+(?P<size>[\d\.]+\w+)\s+at\s+(?P<speed>[\d\.]+\w+/s)\s+ETA\s+(?P<eta>[\d:]+)",
        re.IGNORECASE
    )

    @staticmethod
    def sanitize(raw_log: str) -> str:
        sanitized = raw_log
        # Scrub binary and package references
        sanitized = re.sub(r"\[yt-dlp\]", "[Polar Core v2.4]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"\[youtube-dl\]", "[Polar Core v2.4]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"\[download\]", "[Polar Engine]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"yt[-_]?dlp", "Polar Core", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"youtube[-_]?dl", "Polar Engine", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"python\s*3\.\d+", "Polar Runtime", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"/data/data/[^/]+/files/[^\s]+", "/system/lib/polarengine", sanitized)
        sanitized = re.sub(r"libaria2c\.so", "PolarTurboAccel", sanitized)
        return sanitized

    @staticmethod
    def extract_telemetry(raw_line: str) -> Optional[SanitizedStreamEvent]:
        match = PolarLogSanitizerContract.PROGRESS_REGEX.search(raw_line)
        if match:
            percent = float(match.group("percent"))
            return SanitizedStreamEvent(
                progress_percent=percent / 100.0,
                speed_formatted=match.group("speed"),
                eta_formatted=match.group("eta"),
                total_size_formatted=match.group("size"),
                status_message=f"Downloading: {percent:.1f}% ({match.group('speed')})"
            )
        return None

    @staticmethod
    def contains_leak(text: str) -> bool:
        for pat in PolarLogSanitizerContract.FORBIDDEN_PATTERNS:
            if pat.search(text):
                return True
        return False


class PolarExceptionSanitizerContract:
    @staticmethod
    def sanitize_exception(raw_error: str, exit_code: int = 1) -> PolarException:
        lower = raw_error.lower()
        if "sign in to confirm you're not a bot" in lower or "bot verification" in lower or "http error 403" in lower:
            return PolarException(
                error_type=PolarErrorType.ANTI_BOT_VERIFICATION,
                user_message="Stream requires anti-bot verification. Please try again later or adjust network.",
                code=403
            )
        elif "too many requests" in lower or "http error 429" in lower or "rate limit" in lower:
            return PolarException(
                error_type=PolarErrorType.SERVICE_COOLDOWN,
                user_message="Streaming provider rate limit reached. Polar Engine is cooling down.",
                code=429
            )
        elif "private video" in lower or "copyright" in lower or "drm" in lower or "geo-restricted" in lower:
            return PolarException(
                error_type=PolarErrorType.STREAM_PROTECTED,
                user_message="This stream is protected or restricted by the media provider.",
                code=451
            )
        elif "network is unreachable" in lower or "timed out" in lower or "connection refused" in lower:
            return PolarException(
                error_type=PolarErrorType.MEDIA_UNREACHABLE,
                user_message="Remote media server is unreachable. Check internet connection.",
                code=504
            )
        elif "is not a valid url" in lower or "unsupported url" in lower:
            return PolarException(
                error_type=PolarErrorType.INVALID_MEDIA_URL,
                user_message="Invalid or unsupported media link provided.",
                code=400
            )
        else:
            return PolarException(
                error_type=PolarErrorType.ENGINE_OPERATION_FAILED,
                user_message="Polar Engine encountered an issue processing media.",
                code=500
            )
