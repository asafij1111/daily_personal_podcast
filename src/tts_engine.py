"""Kokoro TTS: render script segments to audio WAV files."""

import os

import numpy as np
import soundfile as sf
from kokoro import KPipeline


def generate_audio(segments: list[dict], voice_config: dict) -> list[str]:
    """Convert script segments to WAV files.

    Args:
        segments: List of dicts with 'speaker' and 'text' keys.
        voice_config: Maps speaker keys to Kokoro voice names.

    Returns:
        List of WAV file paths in episode order.
    """
    os.makedirs("output/segments", exist_ok=True)

    # Cache pipelines per voice to avoid reloading the model
    pipelines: dict[str, KPipeline] = {}
    audio_files = []

    for i, segment in enumerate(segments):
        voice_key = segment["speaker"]
        voice_name = voice_config.get(voice_key, voice_config["narrator"])

        # Load pipeline for this voice if not already cached
        if voice_name not in pipelines:
            print(f"  Loading Kokoro pipeline for voice: {voice_name}")
            pipelines[voice_name] = KPipeline(lang_code="a")

        # Generate audio chunks for this segment's text
        all_audio = []
        for _, _, audio in pipelines[voice_name](segment["text"], voice=voice_name):
            all_audio.append(audio)

        if not all_audio:
            print(f"  Warning: no audio generated for segment {i}, skipping")
            continue

        combined = np.concatenate(all_audio)
        path = f"output/segments/{i:03d}_{voice_key}.wav"
        sf.write(path, combined, 24000)
        audio_files.append(path)

        duration = len(combined) / 24000
        print(f"  Segment {i+1}/{len(segments)}: {duration:.1f}s — {path}")

    return audio_files


# Allow standalone testing: python -m src.tts_engine
if __name__ == "__main__":
    test_segments = [
        {"speaker": "narrator", "text": "Good morning. Welcome to Morning Compile, your daily computer engineering briefing.", "segment_type": "intro"},
        {"speaker": "host_a", "text": "So today we're talking about the latest RISC-V developments. There's been a really interesting announcement about vector extensions.", "segment_type": "deep_dive"},
        {"speaker": "host_b", "text": "That's fascinating. How does that compare to what ARM is doing with their SVE extensions?", "segment_type": "deep_dive"},
    ]

    voice_config = {
        "narrator": "af_sarah",
        "host_a": "am_adam",
        "host_b": "af_sarah",
    }

    files = generate_audio(test_segments, voice_config)
    print(f"\nGenerated {len(files)} audio files")
