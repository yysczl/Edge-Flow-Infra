import struct
import wave
from io import BytesIO
from typing import Iterator, List


class AudioFormatError(ValueError):
    pass


def wav_pcm16_chunks(
    wav_bytes: bytes,
    chunk_milliseconds: int = 100,
) -> Iterator[List[int]]:
    try:
        wav = wave.open(BytesIO(wav_bytes), "rb")
    except (EOFError, wave.Error) as exc:
        raise AudioFormatError(f"invalid WAV file: {exc}")

    with wav:
        try:
            if wav.getnchannels() != 1:
                raise AudioFormatError("WAV must be mono")
            if wav.getsampwidth() != 2:
                raise AudioFormatError("WAV must use signed PCM16 samples")
            if wav.getframerate() != 16000:
                raise AudioFormatError("WAV sample rate must be 16000 Hz")
            if wav.getcomptype() != "NONE":
                raise AudioFormatError("WAV must be uncompressed PCM")

            frames_per_chunk = wav.getframerate() * chunk_milliseconds // 1000
            while True:
                raw = wav.readframes(frames_per_chunk)
                if not raw:
                    break
                sample_count = len(raw) // 2
                yield list(struct.unpack(f"<{sample_count}h", raw))
        except wave.Error as exc:
            raise AudioFormatError(f"invalid WAV file: {exc}")
