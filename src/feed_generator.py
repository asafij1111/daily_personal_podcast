"""Generate and update the podcast RSS XML feed for Apple Podcasts."""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import formatdate


# iTunes namespace
ITUNES_NS = "http://www.itunes.apple.com/dtds/podcast-1.0.dtd"


def _register_namespaces():
    """Register iTunes namespace so it serializes correctly."""
    ET.register_namespace("itunes", ITUNES_NS)


def _rfc2822_now() -> str:
    """Current time in RFC 2822 format for RSS pubDate."""
    return formatdate(timeval=datetime.now(timezone.utc).timestamp(), usegmt=True)


def _create_new_feed(config: dict) -> ET.ElementTree:
    """Create a brand new podcast RSS feed from config."""
    show = config["show"]
    hosting = config["hosting"]
    public_url = os.getenv("R2_PUBLIC_URL", "https://example.com")

    rss = ET.Element("rss", {
        "version": "2.0",
        "xmlns:itunes": ITUNES_NS,
    })
    channel = ET.SubElement(rss, "channel")

    # Required channel elements
    ET.SubElement(channel, "title").text = show["name"]
    ET.SubElement(channel, "link").text = public_url
    ET.SubElement(channel, "language").text = show["language"]
    ET.SubElement(channel, "description").text = show["description"]

    # iTunes-specific
    ET.SubElement(channel, f"{{{ITUNES_NS}}}author").text = show["author"]
    ET.SubElement(channel, f"{{{ITUNES_NS}}}explicit").text = str(show["explicit"]).lower()
    ET.SubElement(channel, f"{{{ITUNES_NS}}}category", {"text": show["category"]})
    ET.SubElement(channel, f"{{{ITUNES_NS}}}image", {
        "href": f"{public_url}/{hosting['cover_art_filename']}"
    })

    owner = ET.SubElement(channel, f"{{{ITUNES_NS}}}owner")
    ET.SubElement(owner, f"{{{ITUNES_NS}}}name").text = show["author"]
    ET.SubElement(owner, f"{{{ITUNES_NS}}}email").text = show["email"]

    return ET.ElementTree(rss)


def _add_episode_item(channel: ET.Element, metadata: dict, episode_url: str,
                      file_size: int, duration_seconds: int):
    """Add a new <item> to the channel."""
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = metadata["title"]
    ET.SubElement(item, "description").text = metadata["description"]
    ET.SubElement(item, "enclosure", {
        "url": episode_url,
        "length": str(file_size),
        "type": "audio/mpeg",
    })
    ET.SubElement(item, "guid").text = episode_url
    ET.SubElement(item, "pubDate").text = _rfc2822_now()
    ET.SubElement(item, f"{{{ITUNES_NS}}}duration").text = str(duration_seconds)


def _get_duration_seconds(episode_path: str) -> int:
    """Get MP3 duration in seconds using pydub."""
    from pydub import AudioSegment
    audio = AudioSegment.from_mp3(episode_path)
    return int(len(audio) / 1000)


def update_feed(metadata: dict, episode_url: str, file_size: int,
                config: dict, episode_path: str = None):
    """Add a new episode to the feed and write to output/feed.xml.

    If output/feed.xml exists, parse and prepend. Otherwise create new feed.
    """
    _register_namespaces()

    feed_path = "output/feed.xml"

    if os.path.exists(feed_path):
        tree = ET.parse(feed_path)
        rss = tree.getroot()
        channel = rss.find("channel")
    else:
        tree = _create_new_feed(config)
        rss = tree.getroot()
        channel = rss.find("channel")

    # Calculate duration if episode file is available
    duration = 0
    if episode_path and os.path.exists(episode_path):
        duration = _get_duration_seconds(episode_path)

    _add_episode_item(channel, metadata, episode_url, file_size, duration)

    # Trim to 90 episodes max
    items = channel.findall("item")
    if len(items) > 90:
        for old_item in items[90:]:
            channel.remove(old_item)

    # Write with XML declaration
    tree.write(feed_path, encoding="unicode", xml_declaration=True)
    print(f"  Feed updated: {feed_path} ({len(channel.findall('item'))} episodes)")


# Allow standalone testing: python -m src.feed_generator
if __name__ == "__main__":
    import yaml
    from dotenv import load_dotenv

    load_dotenv()
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    test_metadata = {
        "title": "Morning Compile — Test Episode",
        "description": "This is a test episode for feed validation.",
        "date": "2026-03-29",
    }
    update_feed(test_metadata, "https://example.com/test.mp3", 1024000, config)
    print("Feed written to output/feed.xml")
