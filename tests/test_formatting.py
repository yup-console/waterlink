from __future__ import annotations

from waterlink.formatting import format_duration, progress_bar, queue_page, track_line
from waterlink.tracks import Track


def make_track(i: int) -> Track:
    return Track(
        encoded=f"enc{i}",
        identifier=str(i),
        is_seekable=True,
        author="Author",
        length_ms=125_000,
        is_stream=False,
        position_ms=0,
        title=f"Track {i}",
        source_name="youtube",
    )


def test_format_duration_minutes_seconds():
    assert format_duration(65_000) == "1:05"


def test_format_duration_hours():
    assert format_duration(3_661_000) == "1:01:01"


def test_format_duration_negative_is_live():
    assert format_duration(-1) == "LIVE"


def test_progress_bar_contains_timestamps():
    bar = progress_bar(30_000, 120_000, width=10)
    assert "0:30" in bar
    assert "2:00" in bar


def test_track_line_includes_title_and_duration():
    track = make_track(1)
    line = track_line(track, index=1)
    assert "Track 1" in line
    assert "2:05" in line


def test_queue_page_pagination():
    tracks = [make_track(i) for i in range(25)]
    text, total_pages = queue_page(tracks, page=1, per_page=10)
    assert total_pages == 3
    assert "Track 0" in text
    assert "Track 9" in text
    assert "Track 10" not in text


def test_queue_page_empty():
    text, total_pages = queue_page([], page=1)
    assert "empty" in text.lower()
    assert total_pages == 1
