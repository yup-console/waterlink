from __future__ import annotations

from waterlink.errors import TrackLoadError
from waterlink.search import SearchPrefix, build_query, parse_load_result
from waterlink.tracks import (
    EmptyResult,
    ErrorResult,
    PlaylistResult,
    SearchTracksResult,
    Track,
    TrackResult,
)

TRACK_PAYLOAD = {
    "encoded": "QAAA...",
    "info": {
        "identifier": "dQw4w9WgXcQ",
        "isSeekable": True,
        "author": "Rick Astley",
        "length": 213000,
        "isStream": False,
        "position": 0,
        "title": "Never Gonna Give You Up",
        "sourceName": "youtube",
        "uri": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "artworkUrl": "https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg",
        "isrc": None,
    },
    "pluginInfo": {},
}


def test_track_from_payload_roundtrip():
    track = Track.from_payload(TRACK_PAYLOAD)
    assert track.title == "Never Gonna Give You Up"
    assert track.author == "Rick Astley"
    assert track.length_ms == 213000
    assert not track.is_stream
    assert track.is_finite

    rebuilt = track.to_payload()
    assert rebuilt["info"]["title"] == track.title
    assert rebuilt["encoded"] == track.encoded


def test_track_with_requester_and_extra_are_immutable():
    track = Track.from_payload(TRACK_PAYLOAD)
    with_requester = track.with_requester(12345)
    assert track.requester_id is None
    assert with_requester.requester_id == 12345

    with_extra = track.with_extra(playlist_index=3)
    assert with_extra.extra["playlist_index"] == 3
    assert track.extra == {}


def test_build_query_uses_prefix_for_plain_text():
    assert build_query("rick astley") == f"{SearchPrefix.YOUTUBE}:rick astley"
    assert build_query("rick astley", prefix=SearchPrefix.SPOTIFY) == "spsearch:rick astley"


def test_build_query_passes_through_uris():
    uri = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert build_query(uri) == uri
    assert build_query("spotify:track:abc123") == "spotify:track:abc123"


def test_parse_load_result_track():
    result = parse_load_result({"loadType": "track", "data": TRACK_PAYLOAD})
    assert isinstance(result, TrackResult)
    assert result.track.title == "Never Gonna Give You Up"


def test_parse_load_result_search():
    result = parse_load_result({"loadType": "search", "data": [TRACK_PAYLOAD, TRACK_PAYLOAD]})
    assert isinstance(result, SearchTracksResult)
    assert len(result.tracks) == 2


def test_parse_load_result_playlist():
    payload = {
        "loadType": "playlist",
        "data": {
            "info": {"name": "My Playlist", "selectedTrack": 0},
            "pluginInfo": {},
            "tracks": [TRACK_PAYLOAD],
        },
    }
    result = parse_load_result(payload)
    assert isinstance(result, PlaylistResult)
    assert result.playlist.name == "My Playlist"
    assert result.playlist.selected_track is not None
    assert len(result.playlist) == 1


def test_parse_load_result_empty():
    result = parse_load_result({"loadType": "empty", "data": None})
    assert isinstance(result, EmptyResult)


def test_parse_load_result_error():
    payload = {
        "loadType": "error",
        "data": {"message": "boom", "severity": "FAULT", "cause": "unknown"},
    }
    result = parse_load_result(payload)
    assert isinstance(result, ErrorResult)
    assert result.message == "boom"
