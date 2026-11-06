package com.trandif.polarsnap.domain.engine

sealed class PolarEngineException(
    val userTitle: String,
    val userDescription: String,
    cause: Throwable? = null
) : Exception("$userTitle: $userDescription", cause) {

    class StreamProtected(
        userDescription: String = "This content requires creator authentication, membership, or age verification.",
        cause: Throwable? = null
    ) : PolarEngineException("Stream Protected", userDescription, cause)

    class AntiBotVerification(
        userDescription: String = "Platform security verification detected. Please try again shortly.",
        cause: Throwable? = null
    ) : PolarEngineException("Anti-Bot Verification", userDescription, cause)

    class MediaUnreachable(
        userDescription: String = "The requested media has been removed, made private, or is geographically restricted.",
        cause: Throwable? = null
    ) : PolarEngineException("Media Unreachable", userDescription, cause)

    class ServiceCooldown(
        userDescription: String = "Platform rate limit reached. PolarSnap will automatically retry.",
        cause: Throwable? = null
    ) : PolarEngineException("Service Cooldown", userDescription, cause)

    class StorageFull(
        userDescription: String = "Insufficient local storage space to complete media extraction.",
        cause: Throwable? = null
    ) : PolarEngineException("Storage Full", userDescription, cause)

    class ConnectionDisruption(
        userDescription: String = "Network connection dropped or unreachable. Reconnecting...",
        cause: Throwable? = null
    ) : PolarEngineException("Connection Disruption", userDescription, cause)

    class ProcessCancelled(
        userDescription: String = "Media capture process was cancelled by user.",
        cause: Throwable? = null
    ) : PolarEngineException("Process Cancelled", userDescription, cause)

    class EngineInternalError(
        userDescription: String = "Polar Core was unable to complete stream processing.",
        cause: Throwable? = null
    ) : PolarEngineException("Engine Processing Error", userDescription, cause)
}
