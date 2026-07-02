"""Tests for automated ingestion — YouTube RSS feed monitoring."""

from pathlib import Path
from unittest.mock import patch

from parker.crud import create_debate
from parker.db import get_engine, get_session, init_db
from parker.monitor import find_new_videos, parse_rss_feed

MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <title>Parkergetajob</title>
  <entry>
    <yt:videoId>newVid000001</yt:videoId>
    <title>New Debate Today</title>
    <published>2026-07-02T17:03:01+00:00</published>
  </entry>
  <entry>
    <yt:videoId>oldVid000002</yt:videoId>
    <title>Old Debate</title>
    <published>2026-06-15T20:00:00+00:00</published>
  </entry>
  <entry>
    <yt:videoId>anothr00003</yt:videoId>
    <title>Another Debate</title>
    <published>2026-06-20T18:00:00+00:00</published>
  </entry>
</feed>"""


def test_parse_rss_feed_extracts_videos():
    videos = parse_rss_feed(MOCK_RSS_XML)
    assert len(videos) == 3
    assert videos[0]["video_id"] == "newVid000001"
    assert videos[0]["title"] == "New Debate Today"
    assert videos[1]["video_id"] == "oldVid000002"
    assert videos[2]["video_id"] == "anothr00003"


def test_parse_rss_feed_includes_published_date():
    videos = parse_rss_feed(MOCK_RSS_XML)
    assert "2026-07-02" in videos[0]["published"]
    assert "2026-06-15" in videos[1]["published"]


def test_find_new_videos_filters_existing(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    with get_session(engine) as session:
        create_debate(
            session,
            youtube_id="oldVid000002",
            title="Old Debate",
            url="https://youtube.com/watch?v=oldVid000002",
        )

    with patch("parker.monitor.fetch_rss_xml", return_value=MOCK_RSS_XML):
        new = find_new_videos(engine, "UCtest_channel")

    assert len(new) == 2
    ids = [v["video_id"] for v in new]
    assert "newVid000001" in ids
    assert "anothr00003" in ids
    assert "oldVid000002" not in ids


def test_find_new_videos_returns_all_when_db_empty(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    with patch("parker.monitor.fetch_rss_xml", return_value=MOCK_RSS_XML):
        new = find_new_videos(engine, "UCtest_channel")

    assert len(new) == 3


def test_find_new_videos_returns_empty_on_bad_feed(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    with patch("parker.monitor.fetch_rss_xml", return_value="<html>not xml</html>"):
        new = find_new_videos(engine, "UCtest_channel")

    assert new == []
