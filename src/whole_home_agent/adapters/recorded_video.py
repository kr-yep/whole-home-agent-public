"""PyAV reader for one hash-validated, prerecorded D0 manifest."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ErrorCode, SourceError
from ..model import SourcePosition, TimestampBasis
from ..video_manifest import VideoSourceManifest


@dataclass(frozen=True, slots=True)
class DecodedVideoFrame:
    position: SourcePosition
    rgb: object


def iter_decoded_frames(manifest: VideoSourceManifest):
    """Yield RGB frames with integer PTS and rational time base."""

    try:
        import av
    except ImportError as error:  # pragma: no cover - exercised without video extra.
        raise SourceError(
            "recorded video support requires the 'video' optional dependency",
            error_code=ErrorCode.SOURCE_FAILURE,
        ) from error

    container = None
    decoded_count = 0
    try:
        container = av.open(str(manifest.media_path), mode="r")
        streams = list(container.streams.video)
        if len(streams) != 1:
            raise SourceError(
                "recorded D0 media must contain exactly one video stream",
                error_code=ErrorCode.INVALID_SOURCE,
            )
        stream = streams[0]
        for index, frame in enumerate(container.decode(stream)):
            time_base = frame.time_base or stream.time_base
            if frame.pts is None or time_base is None:
                raise SourceError(
                    "decoded frame is missing PTS or time base",
                    error_code=ErrorCode.INVALID_SOURCE,
                )
            numerator = int(time_base.numerator)
            denominator = int(time_base.denominator)
            if denominator <= 0:
                raise SourceError(
                    "decoded frame has an invalid time base",
                    error_code=ErrorCode.INVALID_SOURCE,
                )
            rgb = frame.to_ndarray(format="rgb24")
            if rgb.shape != (manifest.height, manifest.width, 3):
                raise SourceError(
                    "decoded frame dimensions disagree with the manifest",
                    error_code=ErrorCode.INVALID_SOURCE,
                )
            decoded_count += 1
            yield DecodedVideoFrame(
                position=SourcePosition(
                    source_sequence=index,
                    source_offset=index,
                    timestamp_basis=TimestampBasis.MEDIA_PTS,
                    frame_index=index,
                    pts=int(frame.pts),
                    time_base_numerator=numerator,
                    time_base_denominator=denominator,
                ),
                rgb=rgb,
            )
        if decoded_count != manifest.frame_count:
            raise SourceError(
                "decoded frame count disagrees with the manifest",
                error_code=ErrorCode.INVALID_SOURCE,
                details={
                    "decoded_frame_count": decoded_count,
                    "manifest_frame_count": manifest.frame_count,
                },
            )
    except SourceError:
        raise
    except Exception as error:
        raise SourceError(
            "recorded video decode failed",
            error_code=ErrorCode.SOURCE_FAILURE,
        ) from error
    finally:
        if container is not None:
            container.close()
