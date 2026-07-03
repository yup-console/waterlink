from __future__ import annotations

from waterlink.metadata import TitleCleaner, clean_track
from waterlink.tracks import Track


def make_track(title: str, author: str) -> Track:
    return Track(
        encoded="enc", identifier="1", is_seekable=True, author=author,
        length_ms=200_000, is_stream=False, position_ms=0,
        title=title, source_name="youtube",
    )


def test_strips_label_and_marketing_tags():
    c = TitleCleaner()
    r = c.clean(title="Tere Liye | Arijit Singh | Viral | T-Series", author="T-Series")
    assert r.title == "Tere Liye"
    assert r.artist == "Arijit Singh"
    assert "T-Series" in r.extra_tags


def test_strips_bracketed_video_noise():
    c = TitleCleaner()
    r = c.clean(title="Kesariya (Official Video) | Arijit Singh | Brahmastra", author="Zee Music Company")
    assert r.title == "Kesariya"
    assert r.artist == "Arijit Singh"


def test_extracts_feat_artist_from_title():
    c = TitleCleaner()
    r = c.clean(title="Song Name feat. Real Artist | T-Series", author="T-Series")
    assert r.title == "Song Name"
    assert r.artist == "Real Artist"


def test_prefers_name_segment_immediately_after_title_over_single_movie_name():
    c = TitleCleaner()
    r = c.clean(
        title="Kal Ho Naa Ho | Sonu Nigam | Full Song",
        author="Zee Music Company",
    )
    assert r.title == "Kal Ho Naa Ho"
    assert r.artist == "Sonu Nigam"


def test_picks_real_singer_over_cast_names_in_merged_segment():
    # Real-world bug report: a single comma-separated segment mixing
    # actors (Ranveer Singh, Sara Arjun) with the actual singer/composer
    # (Shashwat Sachdev, Arijit Singh) must resolve to the trailing
    # singer/composer names, not the leading cast names.
    c = TitleCleaner()
    r = c.clean(
        title="Gehra Hua | Ranveer Singh, Sara Arjun, Shashwat Sachdev, Arijit Singh",
        author="T-Series",
    )
    assert r.title == "Gehra Hua"
    assert r.artist == "Shashwat Sachdev, Arijit Singh"


def test_picks_real_singer_over_separate_cast_segment():
    c = TitleCleaner()
    r = c.clean(
        title="Kesariya | Arijit Singh | Brahmastra | Ranbir Kapoor, Alia Bhatt",
        author="T-Series",
    )
    assert r.artist == "Arijit Singh"


def test_explicit_singer_label_wins_outright():
    c = TitleCleaner()
    r = c.clean(
        title="Gehra Hua - Dhurandhar | Singer: Arijit Singh | Ranveer Singh, Sara Arjun",
        author="T-Series",
    )
    assert r.artist == "Arijit Singh"


def test_composer_label_is_not_used_as_artist():
    # Composer/lyricist is a different role than the performing artist —
    # waterlink should never report a composer as "the artist".
    c = TitleCleaner()
    r = c.clean(title="Some Song | Composed by Pritam | Cast: Actor One, Actor Two", author="T-Series")
    assert r.artist != "Pritam"


def test_singer_label_wins_even_when_composer_label_present():
    c = TitleCleaner()
    r = c.clean(
        title="Some Song | Composed by Pritam | Singer: Arijit Singh | Cast: Actor One, Actor Two",
        author="T-Series",
    )
    assert r.artist == "Arijit Singh"


def test_leaves_clean_metadata_unchanged():
    c = TitleCleaner()
    r = c.clean(title="Blinding Lights", author="The Weeknd")
    assert r.title == "Blinding Lights"
    assert r.artist == "The Weeknd"
    assert not r.was_changed


def test_strips_youtube_topic_channel_suffix():
    c = TitleCleaner()
    r = c.clean(title="Believer", author="Imagine Dragons - Topic")
    assert r.artist == "Imagine Dragons"


def test_strips_vevo_suffix():
    c = TitleCleaner()
    r = c.clean(title="Blinding Lights", author="TheWeekndVEVO")
    assert r.artist == "TheWeeknd"


def test_clean_track_preserves_raw_values():
    track = make_track("Tere Liye | Arijit Singh | T-Series", "T-Series")
    cleaned = clean_track(track)
    assert cleaned.title == "Tere Liye"
    assert cleaned.author == "Arijit Singh"
    assert cleaned.extra["raw_title"] == "Tere Liye | Arijit Singh | T-Series"
    assert cleaned.extra["raw_author"] == "T-Series"
    # Original track is untouched (Track is frozen / immutable-by-convention).
    assert track.title == "Tere Liye | Arijit Singh | T-Series"


def test_clean_track_no_op_when_nothing_changes():
    track = make_track("Blinding Lights", "The Weeknd")
    cleaned = clean_track(track)
    assert cleaned is track


def test_extra_label_names_are_configurable():
    c = TitleCleaner(extra_label_names=("my custom label",))
    r = c.clean(title="Song | Real Artist | My Custom Label", author="My Custom Label")
    assert r.artist == "Real Artist"
