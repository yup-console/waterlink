"""Clean up messy track titles and resolve a sensible "artist" per source.

Different Lavalink sources report the artist very differently, so this
module branches on ``Track.source_name`` rather than applying one
heuristic to everything:

- **YouTube / YouTube Music**: there is no reliable "real artist" field —
  Lavalink only gives us the title text and the name of the channel that
  uploaded the video. Trying to guess a performer's name out of the title
  (splitting on ``|``, matching "Singer:" labels, guessing which
  Title-Case segment is a person vs. a movie, etc.) is inherently
  unreliable and produces wrong answers as often as right ones. Instead,
  the channel name is used as the artist, since that's the one piece of
  information that's actually true - e.g.::

      title:  "Tere Liye | Arijit Singh | Viral | T-Series"
      author: "T-Series"
      -> artist: "T-Series" (channel name; YouTube-only cosmetic
         suffixes like " - Topic" / "VEVO" are still trimmed)

- **Every other source** (Spotify, Apple Music, Deezer, SoundCloud with
  proper tags, etc.): these platforms already carry real, structured
  artist metadata, and Lavalink passes it straight through as
  ``author``. No guessing is needed or wanted here - the author field
  *is* the artist, so it's used as-is. Only cosmetic title noise (e.g.
  bracketed "(Official Audio)" tags some catalogs still include) is
  stripped from the title; the author is left untouched.

This module never calls out to the network — it's a pure, deterministic
text-processing layer over metadata already returned by Lavalink.

Wire it in either per-track (:func:`clean_track`) or automatically for
every search result (:class:`TitleCleaner` + :meth:`Player`/`WaterlinkClient`
hooks — see the ``clean`` parameter on :meth:`WaterlinkClient.search`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .tracks import Track

__all__ = [
    "CleanedMetadata",
    "TitleCleaner",
    "clean_track",
    "YOUTUBE_SOURCE_NAMES",
]

# Segment separators commonly used to pack multiple metadata fields into
# one YouTube title: pipes, bullets, en/em dashes, double dashes, standalone
# hyphens surrounded by whitespace, and slashes when clearly used as a
# separator (not part of a word like "AC/DC" — slash splitting only
# triggers with surrounding whitespace to reduce false positives).
_SEGMENT_SPLIT_RE = re.compile(r"\s*(?:\||•|·|~|\u2013|\u2014|--|\s-\s|\s/\s)\s*")

# Trailing/leading bracketed noise: (Official Video), [Lyrics], "Full Song",
# "4K", "HD", year tags, etc.
_BRACKET_NOISE_RE = re.compile(
    r"[\(\[\{]\s*"
    r"(?:official\s*)?(?:music\s*)?(?:lyric(?:al|s)?\s*)?(?:video|audio|song)?"
    r"[^\)\]\}]*?"
    r"(?:video|audio|lyrics?|hd|4k|full\s*song|visualizer|out\s*now)"
    r"[^\)\]\}]*?[\)\]\}]",
    re.IGNORECASE,
)

_PLAIN_NOISE_PHRASES = (
    "official video",
    "official music video",
    "official audio",
    "official lyric video",
    "lyrical video",
    "lyrics video",
    "full video song",
    "full song",
    "full audio",
    "audio jukebox",
    "video jukebox",
    "out now",
    "new song 2024",
    "new song 2025",
    "new song 2026",
    "latest song",
    "trending song",
    "viral song",
    "viral",
    "4k video",
    "hd video",
)

_FEAT_RE = re.compile(r"\b(?:feat\.?|ft\.?|featuring)\b", re.IGNORECASE)
_MULTI_SPACE_RE = re.compile(r"\s{2,}")
_TRAILING_PUNCT_RE = re.compile(r"^[\s\-\|:–—]+|[\s\-\|:–—]+$")

# YouTube auto-generates "<Artist> - Topic" channels for algorithmically
# organized music uploads. The channel name IS the artist name here, just
# with this suffix tacked on.
_TOPIC_CHANNEL_RE = re.compile(r"\s*-\s*topic\s*$", re.IGNORECASE)
_VEVO_SUFFIX_RE = re.compile(r"vevo\s*$", re.IGNORECASE)

# Lavalink `sourceName` values that represent YouTube. Everything else is
# treated as a "structured metadata" source where the author field is
# trusted as the real artist. Some plugins report YouTube Music results
# under a different sourceName, so both variants are included defensively.
YOUTUBE_SOURCE_NAMES: frozenset[str] = frozenset({"youtube", "youtube_music", "ytmusic"})

# Cosmetic-only noise that can still show up in titles from non-YouTube,
# already-tagged sources (e.g. a track re-uploaded with leftover
# "(Official Audio)" text baked into the title). This is title-only
# cleanup — the author from these sources is never touched.
_TITLE_ONLY_BRACKET_NOISE_RE = re.compile(
    r"[\(\[]\s*(?:official\s*)?(?:music\s*)?(?:audio|video|lyric(?:s|al)?)\s*[\)\]]",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class CleanedMetadata:
    """Result of cleaning a raw title/author pair."""

    title: str
    artist: str
    original_title: str
    original_author: str
    extra_tags: tuple[str, ...] = ()
    """Other segments found in a YouTube title (movie name, cast, "Viral",
    label name, etc.) — kept around in case a caller wants to display or
    log them. Empty for non-YouTube sources, since their titles aren't
    segmented."""

    @property
    def was_changed(self) -> bool:
        return self.title != self.original_title or self.artist != self.original_author


class TitleCleaner:
    """Cleans noisy titles and resolves the artist per-source.

    - **YouTube**: the title is split on common separators (``|``, ``•``,
      `` - ``, etc.); the first segment (noise-stripped) becomes the
      display title, and the channel name (``author``, with cosmetic
      "- Topic"/"VEVO" suffixes trimmed) is always the artist. See the
      module docstring for why title text isn't mined for a performer
      name.
    - **Everything else**: ``author`` is trusted as the artist as-is;
      only cosmetic bracketed noise is stripped from the title.
    """

    def __init__(
        self,
        *,
        extra_label_names: tuple[str, ...] = (),
        extra_noise_phrases: tuple[str, ...] = (),
        extra_movie_titles: tuple[str, ...] = (),
    ) -> None:
        # `extra_label_names` / `extra_movie_titles` are accepted but no
        # longer used: they only fed the old title-mining heuristic that
        # tried to guess a "real artist" out of YouTube title text, which
        # has been replaced with always using the channel name (see the
        # module docstring). Kept as no-op parameters so existing
        # `TitleCleaner(extra_label_names=[...])` call sites don't break.
        self._noise_phrases = tuple(
            p.lower() for p in (*_PLAIN_NOISE_PHRASES, *extra_noise_phrases)
        )

    # -- public API ---------------------------------------------------------- #

    def clean(
        self, *, title: str, author: str, source_name: str = "youtube"
    ) -> CleanedMetadata:
        """Clean a raw title/author pair.

        Parameters
        ----------
        source_name:
            The Lavalink ``sourceName`` this metadata came from (e.g.
            ``"youtube"``, ``"spotify"``, ``"applemusic"``). Determines
            the strategy used:

            - YouTube sources: the channel name (``author``) is used as
              the artist, with only cosmetic YouTube suffixes (``" -
              Topic"``, ``"VEVO"``) trimmed. Title text is *not* mined
              for a "real" performer name — see the module docstring for
              why that's unreliable.
            - Any other source: ``author`` is trusted as-is (these
              platforms already carry real artist metadata); only
              cosmetic bracketed noise is stripped from the title.

            Defaults to ``"youtube"`` for backwards compatibility with
            callers that don't pass it.
        """

        if source_name not in YOUTUBE_SOURCE_NAMES:
            return self._clean_non_youtube(title=title, author=author)

        original_title, original_author = title, author

        # "<Artist> - Topic" and "<Artist>VEVO" are YouTube auto-generated
        # channel naming conventions where the channel name already *is*
        # the real artist name — just strip the suffix, no replacement.
        author = _TOPIC_CHANNEL_RE.sub("", author)
        author = _VEVO_SUFFIX_RE.sub("", author).strip()

        segments = self._split_segments(title)
        if not segments:
            return CleanedMetadata(
                title=title.strip(),
                artist=author.strip(),
                original_title=original_title,
                original_author=original_author,
            )

        song_title = self._strip_noise(segments[0])
        remaining = segments[1:]

        # YouTube's title text is just free-form text a human typed — it's
        # not structured artist metadata. Anything else in the title
        # (movie names, cast lists, composer credits, marketing tags) is
        # kept around as `extra_tags` for callers that want it (e.g. to
        # show a "from <movie>" line), but none of it is *guessed* to be
        # the performer, because there's no reliable way to tell a singer
        # credit apart from a cast/movie/label segment from text alone.
        # The channel name is the one piece of metadata that's actually
        # trustworthy, so it's always used as the artist here.
        extra_tags: list[str] = [
            cleaned for segment in remaining if (cleaned := self._strip_noise(segment))
        ]

        # A "feat./ft." credit in the title is still worth trimming out of
        # the displayed song title (it reads better without it), even
        # though it no longer overrides the artist.
        feat_match = _FEAT_RE.search(song_title)
        if feat_match:
            song_title = song_title[: feat_match.start()].strip(" .,-")

        if not song_title:
            song_title = original_title.strip()

        channel_name = author.strip() or original_author.strip()

        return CleanedMetadata(
            title=song_title,
            artist=channel_name,
            original_title=original_title,
            original_author=original_author,
            extra_tags=tuple(extra_tags),
        )

    def _clean_non_youtube(self, *, title: str, author: str) -> CleanedMetadata:
        """Clean metadata for any non-YouTube source.

        These platforms (Spotify, Apple Music, Deezer, etc.) already give
        Lavalink real, structured artist metadata via ``author`` — it is
        never rewritten or second-guessed here. Only cosmetic bracketed
        noise that occasionally leaks into the title is stripped.
        """

        original_title, original_author = title, author
        cleaned_title = _TITLE_ONLY_BRACKET_NOISE_RE.sub("", title)
        cleaned_title = _MULTI_SPACE_RE.sub(" ", cleaned_title)
        cleaned_title = _TRAILING_PUNCT_RE.sub("", cleaned_title).strip()

        return CleanedMetadata(
            title=cleaned_title or original_title.strip(),
            artist=author.strip() or original_author.strip(),
            original_title=original_title,
            original_author=original_author,
        )

    def clean_track(self, track: Track) -> Track:
        """Return a new :class:`Track` with a cleaned title/author.

        The original values are preserved in ``track.extra`` under
        ``raw_title`` / ``raw_author`` so nothing is lost.
        """

        result = self.clean(
            title=track.title, author=track.author, source_name=track.source_name
        )
        if not result.was_changed:
            return track
        return replace(
            track,
            title=result.title,
            author=result.artist,
            extra={
                **track.extra,
                "raw_title": result.original_title,
                "raw_author": result.original_author,
            },
        )

    # -- internals ------------------------------------------------------------ #

    def _split_segments(self, title: str) -> list[str]:
        parts = [p.strip() for p in _SEGMENT_SPLIT_RE.split(title) if p.strip()]
        return parts

    def _strip_noise(self, segment: str) -> str:
        text = _BRACKET_NOISE_RE.sub("", segment)
        lowered = text.lower()
        for phrase in self._noise_phrases:
            if phrase in lowered:
                # Remove case-insensitively while preserving surrounding text.
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                text = pattern.sub("", text)
                lowered = text.lower()
        text = _MULTI_SPACE_RE.sub(" ", text)
        text = _TRAILING_PUNCT_RE.sub("", text)
        return text.strip()


_default_cleaner = TitleCleaner()


def clean_track(track: Track, *, cleaner: TitleCleaner | None = None) -> Track:
    """Convenience function using a shared default :class:`TitleCleaner`.

    Pass a custom ``cleaner`` (e.g. with extra label names for regional
    labels not in the default list) to override behavior.
    """

    return (cleaner or _default_cleaner).clean_track(track)
