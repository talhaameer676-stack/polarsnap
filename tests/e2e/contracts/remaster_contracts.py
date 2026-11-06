"""
PolarSnap Remaster & CapCut LUT Contracts & Oracles (Milestone 2: Features 9-14)
"""
from dataclasses import dataclass
from enum import Enum
import math
from typing import Tuple, List, Dict, Optional


class CapCutPreset(str, Enum):
    NONE = "NONE"
    TEAL_AND_ORANGE = "TEAL_AND_ORANGE"
    VIRAL_WARM_POP = "VIRAL_WARM_POP"
    MOODY_NOIR = "MOODY_NOIR"
    STUDIO_BRIGHT = "STUDIO_BRIGHT"


class TargetResolution(str, Enum):
    FHD_1080P = "1920x1080"
    QHD_1440P = "2560x1440"
    UHD_4K = "3840x2160"


@dataclass
class RemasterConfig:
    enable_super_resolution: bool = True
    target_resolution: TargetResolution = TargetResolution.UHD_4K
    enable_sharpening: bool = True
    color_grading_preset: CapCutPreset = CapCutPreset.NONE
    lut_intensity: float = 1.0


class HardwareEncoder(str, Enum):
    HEVC_MEDIACODEC = "hevc_mediacodec"
    H264_MEDIACODEC = "h264_mediacodec"
    SOFTWARE_LIBX264 = "libx264"


class BijectiveLUTTransformer:
    """
    Mathematical bijective coordinate mapping between CapCut 8x8 tiled 64^3 LUT
    and FFmpeg Hald CLUT Level 8 (both 512x512).
    """
    GRID_SIZE = 64        # 64 samples per channel: R in [0..63], G in [0..63], B in [0..63]
    LEVEL = 8             # Hald level 8: 8^3 = 512x512 pixels
    IMAGE_WIDTH = 512
    IMAGE_HEIGHT = 512
    TILES_PER_ROW = 8     # 8x8 tiles of 64x64

    @staticmethod
    def rgb_to_capcut_coord(r: int, g: int, b: int) -> Tuple[int, int]:
        """Maps (r, g, b) in [0..63] to (x, y) in CapCut tiled 512x512 image."""
        tile_x = b % BijectiveLUTTransformer.TILES_PER_ROW
        tile_y = b // BijectiveLUTTransformer.TILES_PER_ROW
        x = tile_x * BijectiveLUTTransformer.GRID_SIZE + r
        y = tile_y * BijectiveLUTTransformer.GRID_SIZE + g
        return (x, y)

    @staticmethod
    def capcut_coord_to_rgb(x: int, y: int) -> Tuple[int, int, int]:
        """Inverts CapCut (x, y) back to (r, g, b) coordinates."""
        tile_x = x // BijectiveLUTTransformer.GRID_SIZE
        r = x % BijectiveLUTTransformer.GRID_SIZE
        tile_y = y // BijectiveLUTTransformer.GRID_SIZE
        g = y % BijectiveLUTTransformer.GRID_SIZE
        b = tile_y * BijectiveLUTTransformer.TILES_PER_ROW + tile_x
        return (r, g, b)

    @staticmethod
    def rgb_to_hald_coord(r: int, g: int, b: int) -> Tuple[int, int]:
        """
        Maps (r, g, b) in [0..63] to FFmpeg Hald CLUT Level 8 (x, y).
        Index i = r + g * 64 + b * 4096.
        x = i % 512, y = i // 512.
        """
        i = r + g * BijectiveLUTTransformer.GRID_SIZE + b * (BijectiveLUTTransformer.GRID_SIZE ** 2)
        x = i % BijectiveLUTTransformer.IMAGE_WIDTH
        y = i // BijectiveLUTTransformer.IMAGE_WIDTH
        return (x, y)

    @staticmethod
    def hald_coord_to_rgb(x: int, y: int) -> Tuple[int, int, int]:
        """Inverts FFmpeg Hald CLUT (x, y) back to (r, g, b)."""
        i = y * BijectiveLUTTransformer.IMAGE_WIDTH + x
        r = i % BijectiveLUTTransformer.GRID_SIZE
        rem = i // BijectiveLUTTransformer.GRID_SIZE
        g = rem % BijectiveLUTTransformer.GRID_SIZE
        b = rem // BijectiveLUTTransformer.GRID_SIZE
        return (r, g, b)

    @classmethod
    def capcut_to_hald_coord(cls, cc_x: int, cc_y: int) -> Tuple[int, int]:
        """Direct bijective transformation from CapCut coordinate to Hald coordinate."""
        r, g, b = cls.capcut_coord_to_rgb(cc_x, cc_y)
        return cls.rgb_to_hald_coord(r, g, b)

    @classmethod
    def hald_to_capcut_coord(cls, h_x: int, h_y: int) -> Tuple[int, int]:
        """Direct inverse bijective transformation from Hald coordinate to CapCut coordinate."""
        r, g, b = cls.hald_coord_to_rgb(h_x, h_y)
        return cls.rgb_to_capcut_coord(r, g, b)


class MemoryOptimizationOracle:
    BYTES_PER_PIXEL_RGB = 3

    @staticmethod
    def compute_frame_ram_bytes(width: int, height: int) -> int:
        return width * height * MemoryOptimizationOracle.BYTES_PER_PIXEL_RGB

    @staticmethod
    def compute_memory_savings_ratio(input_res: Tuple[int, int], target_res: Tuple[int, int]) -> float:
        """
        Calculates memory savings ratio achieved by applying color grading & sharpening
        before scaling rather than post-scaling.
        """
        ram_pre = MemoryOptimizationOracle.compute_frame_ram_bytes(*input_res)
        ram_post = MemoryOptimizationOracle.compute_frame_ram_bytes(*target_res)
        return (ram_post - ram_pre) / ram_post


class RemasterFiltergraphBuilder:
    @staticmethod
    def build(config: RemasterConfig, lut_file_path: Optional[str] = None) -> str:
        """
        Builds the 5-stage FFmpeg filtergraph:
        Stage 1: CAS / sharpening (pre-upscale)
        Stage 2: eq / vibrancy (pre-upscale)
        Stage 3: Hald CLUT grading (pre-upscale)
        Stage 4: Lanczos super-resolution scaling
        Stage 5: unsharp edge recovery (post-upscale)
        """
        stages: List[str] = []

        # Stage 1: Sharpening
        if config.enable_sharpening:
            stages.append("cas=strength=0.5")

        # Stage 2: Vibrancy & Contrast
        stages.append("eq=contrast=1.06:saturation=1.10")

        # Stage 3: CapCut Hald CLUT
        if config.color_grading_preset != CapCutPreset.NONE and lut_file_path:
            stages.append(f"haldclut=shortest=1:repeatlast=1")

        # Stage 4: Lanczos Super-Resolution Upscaling
        if config.enable_super_resolution:
            w, h = config.target_resolution.value.split("x")
            stages.append(f"scale={w}:{h}:flags=lanczos")

        # Stage 5: Post-Upscale Unsharp Recovery
        if config.enable_super_resolution and config.enable_sharpening:
            stages.append("unsharp=lx=5:ly=5:la=0.4")

        return ",".join(stages)


class MediaCodecEncoderSelector:
    @staticmethod
    def select_encoder(supported_codecs: List[str], force_software: bool = False) -> Tuple[HardwareEncoder, str]:
        """
        3-tier fallback matrix:
        Tier 1: hevc_mediacodec
        Tier 2: h264_mediacodec
        Tier 3: libx264
        """
        if not force_software:
            if "hevc_mediacodec" in supported_codecs:
                return (HardwareEncoder.HEVC_MEDIACODEC, "-c:v hevc_mediacodec -b:v 18M -tag:v hvc1")
            elif "h264_mediacodec" in supported_codecs:
                return (HardwareEncoder.H264_MEDIACODEC, "-c:v h264_mediacodec -b:v 25M")

        return (HardwareEncoder.SOFTWARE_LIBX264, "-c:v libx264 -preset fast -crf 18")
