#!/usr/bin/env python3
"""Generate today's Morning Compile episode.

Usage:
    python generate_episode.py              # Normal run
    python generate_episode.py --scheduled  # Scheduled run (waits for wifi, sleeps after)
"""

import logging
import os
import sys
import time
from datetime import date

import yaml
from dotenv import load_dotenv


def main():
    load_dotenv()

    # Wait for wifi if running from scheduled wake
    if "--scheduled" in sys.argv:
        print("Waiting 30s for network...")
        time.sleep(30)

    # Set up logging to both file and console
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(f"logs/{date.today()}.log"),
            logging.StreamHandler(),
        ],
    )
    log = logging.getLogger(__name__)

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    start = time.time()

    log.info("Step 1/5: Researching today's news...")
    from src.researcher import gather_news
    research = gather_news(config)

    log.info("Step 2/5: Writing script...")
    from src.script_writer import write_script
    script = write_script(research, config)

    log.info("Step 3/5: Generating audio...")
    from src.tts_engine import generate_audio
    segment_files = generate_audio(script["segments"], config["voices"])

    log.info("Step 4/5: Assembling episode...")
    from src.audio_assembler import assemble_episode
    episode_path = assemble_episode(segment_files, config)

    log.info("Step 5/5: Publishing...")
    from src.publisher import publish
    publish(episode_path, script["metadata"], config)

    elapsed = time.time() - start
    log.info(f"Done in {elapsed / 60:.1f} min! Episode: {episode_path}")

    # If running scheduled, put Mac back to sleep
    if "--scheduled" in sys.argv:
        import subprocess
        log.info("Putting Mac to sleep...")
        subprocess.run(["pmset", "sleepnow"])


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    os.makedirs("output/segments", exist_ok=True)
    os.makedirs("output/episodes", exist_ok=True)
    os.makedirs("output/scripts", exist_ok=True)
    main()
