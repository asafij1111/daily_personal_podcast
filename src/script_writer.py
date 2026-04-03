"""Gemini: turn research into TTS-ready podcast scripts."""

import json
import os
import time
from datetime import date

from google import genai


def _load_prompt(path: str) -> str:
    with open(path) as f:
        return f.read()


def _call_gemini(prompt: str) -> str:
    """Make a single Gemini API call with one retry on failure."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return response.text
        except Exception as e:
            if attempt == 0:
                print(f"  Warning: Gemini call failed, retrying... ({e})")
                time.sleep(2)
            else:
                raise


def _generate_news_script(research: dict) -> list[dict]:
    """Generate intro, news roundup, and wrap-up narration."""
    prompt_template = _load_prompt("prompts/narrator_system.txt")

    # Format stories for the prompt
    stories_text = "\n\n".join(
        f"{i+1}. {s['title']} ({s['source']})\n{s['summary']}"
        for i, s in enumerate(research["top_stories"])
    )

    prompt = prompt_template.format(stories=stories_text)
    raw_text = _call_gemini(prompt)

    # Split into paragraphs — each becomes a TTS segment
    paragraphs = [p.strip() for p in raw_text.strip().split("\n\n") if p.strip()]

    segments = []
    for i, para in enumerate(paragraphs):
        if i == 0:
            seg_type = "intro"
        elif i == len(paragraphs) - 1:
            seg_type = "outro"
        else:
            seg_type = "news"
        segments.append({
            "speaker": "narrator",
            "text": para,
            "segment_type": seg_type,
        })

    return segments


def _generate_conversation(research: dict) -> list[dict]:
    """Generate the two-host deep dive conversation."""
    topic = research["deep_dive_topic"]
    prompt_template = _load_prompt("prompts/conversation_system.txt")

    prompt = prompt_template.format(
        deep_dive_topic=f"{topic['title']}\n{topic['summary']}\nAngle: {topic['angle']}",
        key_points="\n".join(f"- {p}" for p in topic["key_points"]),
    )

    raw_text = _call_gemini(prompt)

    # Parse HOST_A: / HOST_B: lines
    segments = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("HOST_A:"):
            segments.append({
                "speaker": "host_a",
                "text": line[len("HOST_A:"):].strip(),
                "segment_type": "deep_dive",
            })
        elif line.startswith("HOST_B:"):
            segments.append({
                "speaker": "host_b",
                "text": line[len("HOST_B:"):].strip(),
                "segment_type": "deep_dive",
            })
        else:
            # Continuation of previous speaker's text, or unprefixed line
            if segments:
                segments[-1]["text"] += " " + line
            else:
                # Fallback: treat as host_a
                segments.append({
                    "speaker": "host_a",
                    "text": line,
                    "segment_type": "deep_dive",
                })

    return segments


def _generate_learning_corner(research: dict) -> list[dict]:
    """Generate the learning corner narration."""
    concept = research["learning_concept"]
    prompt_template = _load_prompt("prompts/learning_system.txt")

    prompt = prompt_template.format(
        learning_concept=concept["concept"],
        connection=concept["connection"],
    )

    raw_text = _call_gemini(prompt)

    paragraphs = [p.strip() for p in raw_text.strip().split("\n\n") if p.strip()]

    return [
        {"speaker": "narrator", "text": para, "segment_type": "learning"}
        for para in paragraphs
    ]


def write_script(research: dict, config: dict) -> dict:
    """Main entry point: generate all script segments from research.

    Returns dict with 'segments' list and 'metadata' dict.
    """
    print("  Generating news narration...")
    news_segments = _generate_news_script(research)

    print("  Generating deep dive conversation...")
    conversation_segments = _generate_conversation(research)

    print("  Generating learning corner...")
    learning_segments = _generate_learning_corner(research)

    # Assemble in episode order: news (includes intro), conversation, learning, outro
    # Pull the outro from news_segments (last segment) and place it at the end
    outro = news_segments.pop() if news_segments and news_segments[-1]["segment_type"] == "outro" else None

    all_segments = news_segments + conversation_segments + learning_segments
    if outro:
        all_segments.append(outro)

    # Build metadata
    top_story = research["top_stories"][0]["title"] if research["top_stories"] else "Today's News"
    metadata = {
        "title": f"Morning Compile — {date.today().strftime('%B %d, %Y')}",
        "description": f"Today's top story: {top_story}. Plus a deep dive into {research['deep_dive_topic']['title']} and learning about {research['learning_concept']['concept']}.",
        "date": date.today().isoformat(),
    }

    result = {"segments": all_segments, "metadata": metadata}

    # Save script for debugging
    os.makedirs("output/scripts", exist_ok=True)
    script_path = f"output/scripts/{date.today().isoformat()}.json"
    with open(script_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  Script saved to {script_path}")
    print(f"  Total segments: {len(all_segments)}")

    return result


# Allow standalone testing: python -m src.script_writer
if __name__ == "__main__":
    import yaml
    from dotenv import load_dotenv

    load_dotenv()
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    # Load saved research from researcher.py test run
    research_path = "output/scripts/latest_research.json"
    if not os.path.exists(research_path):
        print(f"No research file found at {research_path}")
        print("Run 'python -m src.researcher' first.")
        exit(1)

    with open(research_path) as f:
        research = json.load(f)

    script = write_script(research, config)
    for seg in script["segments"]:
        speaker = seg["speaker"].upper()
        preview = seg["text"][:80] + "..." if len(seg["text"]) > 80 else seg["text"]
        print(f"  [{seg['segment_type']}] {speaker}: {preview}")
