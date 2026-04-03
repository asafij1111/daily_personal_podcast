"""pydub: stitch WAV segments into a final MP3 episode."""

import os
from datetime import date

from pydub import AudioSegment


def assemble_episode(segment_files: list[str], config: dict) -> str:
    """Combine WAV segments into a single MP3 file.

    Args:
        segment_files: List of WAV file paths in episode order.
        config: Full config dict (uses audio settings).

    Returns:
        Path to the final MP3 file.
    """
    segment_gap = config["audio"]["segment_gap_ms"]
    section_gap = config["audio"]["section_gap_ms"]
    silence_short = AudioSegment.silent(duration=segment_gap)
    silence_long = AudioSegment.silent(duration=section_gap)

    episode = AudioSegment.empty()
    prev_type = None

    for i, filepath in enumerate(segment_files):
        segment = AudioSegment.from_wav(filepath)

        if i > 0:
            # Determine segment type from filename: e.g., 003_host_a.wav
            # Use longer silence between different section types
            curr_speaker = os.path.basename(filepath).split("_", 1)[1].replace(".wav", "")

            # Longer gap when switching between narrator and hosts (section change)
            if prev_type and prev_type != curr_speaker:
                # Check if it's a major section transition
                prev_is_narrator = "narrator" in (prev_type or "")
                curr_is_narrator = "narrator" in curr_speaker
                if prev_is_narrator != curr_is_narrator:
                    episode += silence_long
                else:
                    episode += silence_short
            else:
                episode += silence_short

            prev_type = curr_speaker
        else:
            prev_type = os.path.basename(filepath).split("_", 1)[1].replace(".wav", "")

        episode += segment

    # Export: write intermediate WAV then convert to MP3 with ffmpeg directly
    # (pydub's temp-file approach can fail on large episodes)
    os.makedirs("output/episodes", exist_ok=True)
    wav_path = f"output/episodes/{date.today().isoformat()}.wav"
    output_path = f"output/episodes/{date.today().isoformat()}.mp3"

    episode.export(wav_path, format="wav")

    import subprocess
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-b:a", config["audio"]["mp3_bitrate"], output_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr}")
        raise RuntimeError(f"ffmpeg encoding failed with code {result.returncode}")

    # Clean up intermediate WAV
    os.remove(wav_path)

    duration_min = len(episode) / 1000 / 60
    print(f"  Episode duration: {duration_min:.1f} minutes")
    print(f"  Saved to: {output_path}")
    return output_path


# Allow standalone testing: python -m src.audio_assembler
if __name__ == "__main__":
    import glob
    import yaml

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    wavs = sorted(glob.glob("output/segments/*.wav"))
    if not wavs:
        print("No WAV files found in output/segments/. Run tts_engine first.")
        exit(1)

    print(f"Assembling {len(wavs)} segments...")
    path = assemble_episode(wavs, config)
    print(f"Done: {path}")
