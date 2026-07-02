"""Automated ingestion — monitor Parker's YouTube channel for new videos."""
import logging
import urllib.request
import xml.etree.ElementTree as ET

from parker.crud import get_debate_by_youtube_id
from parker.db import get_session

logger = logging.getLogger(__name__)

PARKER_CHANNEL_ID = "UCBDRBytEt3WJ0deCBT9-clA"

_ATOM_NS = "http://www.w3.org/2005/Atom"
_YT_NS = "http://www.youtube.com/xml/schemas/2015"


def fetch_rss_xml(channel_id: str) -> str:
    """Fetch the YouTube RSS feed XML for a channel."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return resp.read().decode()


def parse_rss_feed(xml_text: str) -> list[dict]:
    """Parse YouTube RSS XML into a list of video dicts.

    Each dict has: video_id, title, published, url.
    Returns empty list on parse failure.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse RSS XML")
        return []

    videos = []
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        video_id_elem = entry.find(f"{{{_YT_NS}}}videoId")
        title_elem = entry.find(f"{{{_ATOM_NS}}}title")
        published_elem = entry.find(f"{{{_ATOM_NS}}}published")

        if video_id_elem is None or title_elem is None:
            continue

        video_id = video_id_elem.text or ""
        title = title_elem.text or ""
        published = published_elem.text if published_elem is not None else ""

        videos.append({
            "video_id": video_id,
            "title": title,
            "published": published,
            "url": f"https://youtube.com/watch?v={video_id}",
        })

    return videos


def find_new_videos(engine, channel_id: str = PARKER_CHANNEL_ID) -> list[dict]:
    """Check the RSS feed for videos not yet in the database.

    Returns list of new video dicts (video_id, title, published, url).
    """
    try:
        xml_text = fetch_rss_xml(channel_id)
    except Exception as e:
        logger.error("Failed to fetch RSS feed: %s", e)
        return []

    all_videos = parse_rss_feed(xml_text)
    if not all_videos:
        return []

    new_videos = []
    with get_session(engine) as session:
        for video in all_videos:
            existing = get_debate_by_youtube_id(session, video["video_id"])
            if not existing:
                new_videos.append(video)

    logger.info("RSS feed: %d total, %d new", len(all_videos), len(new_videos))
    return new_videos
