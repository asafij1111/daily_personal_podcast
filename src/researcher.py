"""RSS + Gemini: gather today's news and rank by relevance for CE students."""

import json
import os
import time
from datetime import datetime, timedelta, timezone

import feedparser
from google import genai


def _load_prompt(path: str) -> str:
    with open(path) as f:
        return f.read()


def _fetch_articles(sources: list[dict], hours: int = 48) -> list[dict]:
    """Fetch recent articles from all RSS feeds."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for source in sources:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries:
                # Try multiple date fields
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                # Some feeds don't have dates — include them anyway
                articles.append({
                    "title": entry.get("title", "Untitled"),
                    "summary": entry.get("summary", entry.get("description", "")),
                    "link": entry.get("link", ""),
                    "source": source["name"],
                    "published": str(published[:6]) if published else "unknown",
                })
        except Exception as e:
            print(f"  Warning: failed to fetch {source['name']}: {e}")

    print(f"  Fetched {len(articles)} articles from {len(sources)} feeds")
    return articles


def _rank_with_gemini(articles: list[dict], config: dict) -> dict:
    """Send articles to Gemini for ranking and curation."""
    prompt_template = _load_prompt("prompts/research_system.txt")

    topics = config["topics"]
    prompt = prompt_template.format(
        topics_primary=", ".join(topics["primary"]),
        topics_secondary=", ".join(topics["secondary"]),
    )

    # Build article list for the prompt
    article_text = "\n\n".join(
        f"[{a['source']}] {a['title']}\n{a['summary']}\nURL: {a['link']}"
        for a in articles[:80]  # Cap to avoid token limits
    )

    full_prompt = f"{prompt}\n\nARTICLES:\n{article_text}"

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Try up to 2 times if JSON parsing fails
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
            )
            # Strip markdown code fences if Gemini wraps the JSON
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]  # Remove ```json line
                text = text.rsplit("```", 1)[0]  # Remove closing ```
                text = text.strip()
            result = json.loads(text)
            return result
        except json.JSONDecodeError as e:
            if attempt == 0:
                print(f"  Warning: Gemini returned invalid JSON, retrying... ({e})")
                time.sleep(2)
            else:
                print(f"  Error: Gemini JSON parsing failed after retry: {e}")
                print(f"  Raw response: {response.text[:500]}")
                raise


def gather_news(config: dict) -> dict:
    """Main entry point: fetch RSS feeds and rank with Gemini.

    Returns dict with top_stories, deep_dive_topic, and learning_concept.
    """
    articles = _fetch_articles(config["sources"]["rss"])

    if not articles:
        raise RuntimeError("No articles fetched from any RSS feed. Check network.")

    research = _rank_with_gemini(articles, config)

    # Basic validation
    for key in ("top_stories", "deep_dive_topic", "learning_concept"):
        if key not in research:
            raise ValueError(f"Gemini response missing required key: {key}")

    print(f"  Selected {len(research['top_stories'])} stories")
    print(f"  Deep dive: {research['deep_dive_topic']['title']}")
    print(f"  Learning: {research['learning_concept']['concept']}")

    return research


# Allow standalone testing: python -m src.researcher
if __name__ == "__main__":
    import yaml
    from dotenv import load_dotenv

    load_dotenv()
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    research = gather_news(config)
    print(json.dumps(research, indent=2))

    # Save for script_writer testing
    os.makedirs("output/scripts", exist_ok=True)
    with open("output/scripts/latest_research.json", "w") as f:
        json.dump(research, f, indent=2)
    print("\nSaved to output/scripts/latest_research.json")
