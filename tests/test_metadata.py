from __future__ import annotations

from waterlink.metadata import TitleCleaner, clean_track
from waterlink.tracks import Track


def make_track(title: str, author: str, source_name: str = "youtube") -> Track:
    return Track(
        encoded="enc", identifier="1", is_seekable=True, author=author,
        length_ms=200_000, is_stream=False, position_ms=0,
        title=title, source_name=source_name,
    )


# -- YouTube: channel name is always the artist ------------------------------ #

def test_youtube_uses_channel_name_as_artist_not_a_guessed_name():
    c = TitleCleaner()
    r = c.clean(
        title="Tere Liye | Arijit Singh | Viral | T-Series",
        author="T-Series",
        source_name="youtube",
    )
    assert r.title == "Tere Liye"
    assert r.artist == "T-Series"
    # The other title segments are preserved for callers that want them,
    # just not elevated to "artist". Pure marketing noise like "Viral" is
    # still stripped out entirely (it's noise, not information).
    assert "Arijit Singh" in r.extra_tags
    assert "Viral" not in r.extra_tags


def test_youtube_strips_bracketed_video_noise_from_title_only():
    c = TitleCleaner()
    r = c.clean(
        title="Kesariya (Official Video) | Arijit Singh | Brahmastra",
        author="Zee Music Company",
        source_name="youtube",
    )
    assert r.title == "Kesariya"
    assert r.artist == "Zee Music Company"


def test_youtube_strips_topic_channel_suffix():
    c = TitleCleaner()
    r = c.clean(title="Believer", author="Imagine Dragons - Topic", source_name="youtube")
    assert r.artist == "Imagine Dragons"


def test_youtube_strips_vevo_suffix():
    c = TitleCleaner()
    r = c.clean(title="Blinding Lights", author="TheWeekndVEVO", source_name="youtube")
    assert r.artist == "TheWeeknd"


def test_youtube_feat_credit_trimmed_from_title_but_not_used_as_artist():
    c = TitleCleaner()
    r = c.clean(
        title="Song Name feat. Real Artist | T-Series",
        author="T-Series",
        source_name="youtube",
    )
    assert r.title == "Song Name"
    assert r.artist == "T-Series"


def test_youtube_defaults_to_youtube_when_source_name_omitted():
    # Backwards-compatible default for callers not yet passing source_name.
    c = TitleCleaner()
    r = c.clean(title="Song | T-Series", author="T-Series")
    assert r.artist == "T-Series"


def test_youtube_music_source_name_treated_as_youtube():
    c = TitleCleaner()
    r = c.clean(title="Believer", author="Imagine Dragons - Topic", source_name="youtube_music")
    assert r.artist == "Imagine Dragons"


# -- Non-YouTube: author is trusted as the real artist, never rewritten ------ #

def test_spotify_author_is_trusted_as_artist_verbatim():
    c = TitleCleaner()
    r = c.clean(
        title="Tere Liye",
        author="Arijit Singh",
        source_name="spotify",
    )
    assert r.title == "Tere Liye"
    assert r.artist == "Arijit Singh"
    assert not r.was_changed


def test_spotify_title_with_separators_is_not_split_or_mined_for_artist():
    # Even if a Spotify title happens to contain a pipe or dash, none of
    # it should be reinterpreted as a different artist - Spotify's author
    # field is already correct.
    c = TitleCleaner()
    r = c.clean(
        title="Song Title - Remix",
        author="Real Artist",
        source_name="spotify",
    )
    assert r.artist == "Real Artist"


def test_apple_music_bracket_noise_stripped_from_title_author_untouched():
    c = TitleCleaner()
    r = c.clean(
        title="Blinding Lights (Official Audio)",
        author="The Weeknd",
        source_name="applemusic",
    )
    assert r.title == "Blinding Lights"
    assert r.artist == "The Weeknd"


def test_deezer_author_never_replaced_even_if_it_looks_like_a_label():
    # Author is never second-guessed for non-YouTube sources, even if it
    # happens to contain a word that looked like a "label" under the old
    # YouTube-only heuristic.
    c = TitleCleaner()
    r = c.clean(
        title="Some Song",
        author="Records Label Artist",
        source_name="deezer",
    )
    assert r.artist == "Records Label Artist"


def test_leaves_clean_metadata_unchanged():
    c = TitleCleaner()
    r = c.clean(title="Blinding Lights", author="The Weeknd", source_name="spotify")
    assert r.title == "Blinding Lights"
    assert r.artist == "The Weeknd"
    assert not r.was_changed


# -- clean_track integration -------------------------------------------------- #

def test_clean_track_preserves_raw_values_for_youtube():
    track = make_track("Tere Liye | Arijit Singh | T-Series", "T-Series", source_name="youtube")
    cleaned = clean_track(track)
    assert cleaned.title == "Tere Liye"
    assert cleaned.author == "T-Series"
    assert cleaned.extra["raw_title"] == "Tere Liye | Arijit Singh | T-Series"
    assert cleaned.extra["raw_author"] == "T-Series"
    # Original track is untouched (Track is frozen / immutable-by-convention).
    assert track.title == "Tere Liye | Arijit Singh | T-Series"


def test_clean_track_no_op_when_nothing_changes():
    track = make_track("Blinding Lights", "The Weeknd", source_name="spotify")
    cleaned = clean_track(track)
    assert cleaned is track


def test_clean_track_uses_source_name_from_track():
    track = make_track("Tere Liye", "Arijit Singh", source_name="spotify")
    cleaned = clean_track(track)
    # Spotify author trusted as-is, no-op since nothing needed cleaning.
    assert cleaned is track
