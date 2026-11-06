package com.trandif.polarsnap.domain.engine

enum class FormatContainer(val extension: String, val isAudio: Boolean = false) {
    MP4("mp4", false),
    MKV("mkv", false),
    WEBM("webm", false),
    MP3("mp3", true),
    M4A("m4a", true),
    FLAC("flac", true),
    OPUS("opus", true)
}
