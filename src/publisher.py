"""Upload episode MP3 and RSS feed to Cloudflare R2."""

import os
from datetime import date

import boto3


def _get_r2_client():
    """Create an S3-compatible client for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("R2_SECRET_KEY"),
    )


def upload_to_r2(local_path: str, remote_key: str):
    """Upload a single file to R2."""
    s3 = _get_r2_client()
    content_type = "audio/mpeg" if remote_key.endswith(".mp3") else "application/xml"
    s3.upload_file(
        local_path,
        os.getenv("R2_BUCKET"),
        remote_key,
        ExtraArgs={"ContentType": content_type},
    )
    print(f"  Uploaded: {remote_key}")


def publish(episode_path: str, metadata: dict, config: dict):
    """Upload episode and update RSS feed on R2.

    Args:
        episode_path: Local path to the MP3 file.
        metadata: Episode metadata (title, description, date).
        config: Full config dict.
    """
    public_url = os.getenv("R2_PUBLIC_URL")
    episode_key = f"episodes/{date.today().isoformat()}.mp3"
    episode_url = f"{public_url}/{episode_key}"
    file_size = os.path.getsize(episode_path)

    # Generate/update the RSS feed
    from src.feed_generator import update_feed
    update_feed(metadata, episode_url, file_size, config, episode_path=episode_path)

    # Upload MP3
    print(f"  Uploading episode ({file_size / 1024 / 1024:.1f} MB)...")
    upload_to_r2(episode_path, episode_key)

    # Upload feed
    upload_to_r2("output/feed.xml", config["hosting"]["feed_filename"])

    feed_url = f"{public_url}/{config['hosting']['feed_filename']}"
    print(f"  Published! Feed: {feed_url}")


# Allow standalone testing: python -m src.publisher
if __name__ == "__main__":
    print("Publisher module loaded. Use via generate_episode.py or import directly.")
    print("Required env vars: R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET, R2_PUBLIC_URL")
