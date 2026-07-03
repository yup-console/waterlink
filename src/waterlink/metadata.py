"""Clean up messy YouTube-style track titles and uploader/label names.

YouTube search results (and many other free sources) are frequently
uploaded by record labels rather than the artist, so the raw metadata
Lavalink hands back tends to look like this::

    title:  "Tere Liye | Arijit Singh | Viral | T-Series"
    author: "T-Series"

...when what a user actually wants displayed is::

    title:  "Tere Liye"
    author: "Arijit Singh"

This module never calls out to the network — it's a pure, deterministic
text-processing layer over metadata already returned by Lavalink. It's
intentionally conservative: when it isn't confident about a piece of
metadata it leaves the original value alone rather than guessing wrong.

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
    "DEFAULT_LABEL_SUFFIXES",
]

# --------------------------------------------------------------------------- #
# Known record label / channel suffixes that should never be shown as an
# "artist" on their own. This list is deliberately focused on labels that
# commonly upload under their own channel name rather than the performer's.
# It's easy to extend via TitleCleaner(extra_label_names=[...]).
# --------------------------------------------------------------------------- #

DEFAULT_LABEL_SUFFIXES: tuple[str, ...] = (
    "t-series",
    "tseries",
    "zee music company",
    "zee music",
    "sony music",
    "sony music entertainment",
    "sony music india",
    "universal music",
    "universal music group",
    "warner music",
    "warner records",
    "believe digital",
    "believe music",
    "the orchard",
    "orchard music",
    "vevo",
    "records",
    "official",
    "music company",
    "entertainment",
    "worldwide records",
    "speed records",
    "saregama",
    "saregama music",
    "tips official",
    "tips music",
    "eros now music",
    "yrf",
    "yash raj films",
    "venus",
    "venus movies",
    "aditya music",
    "lahari music",
    "think music",
    "sun music",
    "wave music",
    "desi music factory",
    "white hill music",
    "geet mp3",
    "jjust music",
    "juke dock",
    "gaana originals",
)

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

# Explicit role labels sometimes present in a segment, e.g.
# "Singer: Arijit Singh" or "Music by Pritam" or "Cast: Ranveer Singh".
# When present, these are the strongest possible signal and are checked
# before any other heuristic.
_SINGER_LABEL_RE = re.compile(
    r"^(?:singer|sung\s*by|vocals?(?:\s*by)?|singers?)\s*[:\-]?\s*", re.IGNORECASE
)
_COMPOSER_LABEL_RE = re.compile(
    r"^(?:music(?:\s*(?:by|composed\s*by))?|composed\s*by|composer|"
    r"lyrics?(?:\s*by)?|written\s*by)\s*[:\-]?\s*",
    re.IGNORECASE,
)
_CAST_LABEL_RE = re.compile(
    r"^(?:starring|cast(?:\s*by)?|actors?|feat(?:uring)?\s*cast)\s*[:\-]?\s*",
    re.IGNORECASE,
)
_MOVIE_LABEL_RE = re.compile(r"^(?:movie|film|from\s*the\s*movie|album)\s*[:\-]?\s*", re.IGNORECASE)

# Words that mark a segment as a cast/starring credit even without an
# explicit "Cast:" label — this is the single most common failure mode
# for Bollywood-style titles, where a comma-separated list of lead actors
# is placed *before* the singer/composer segment and both look equally
# "name-shaped" to a naive heuristic.
_CAST_CONTEXT_WORDS = (
    "starring", "cast", "movie", "film", "ft. cast", "actor", "actress",
)

# YouTube auto-generates "<Artist> - Topic" channels for algorithmically
# organized music uploads. The channel name IS the artist name here, just
# with this suffix tacked on, so it's handled separately from the label
# suffix list (which are uploader/label names to be *replaced*, not
# artist names to be *trimmed*).
_TOPIC_CHANNEL_RE = re.compile(r"\s*-\s*topic\s*$", re.IGNORECASE)
_VEVO_SUFFIX_RE = re.compile(r"vevo\s*$", re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class CleanedMetadata:
    """Result of cleaning a raw title/author pair."""

    title: str
    artist: str
    original_title: str
    original_author: str
    extra_tags: tuple[str, ...] = ()
    """Segments that were stripped from the title but didn't look like an
    artist name either (e.g. "Viral", "T-Series") — kept around in case a
    caller wants to display or log them."""

    @property
    def was_changed(self) -> bool:
        return self.title != self.original_title or self.artist != self.original_author


class TitleCleaner:
    """Configurable engine for extracting a clean song title + artist name
    from noisy source metadata (typically YouTube).

    The algorithm:

    1. Split the title on common separators (``|``, ``•``, `` - ``, etc.)
       into segments.
    2. The first segment is treated as the song title; noise phrases and
       bracketed tags ("(Official Video)", "[Lyrics]") are stripped from it.
    3. Remaining segments are classified as either a likely artist name or
       a label/noise tag, using the label suffix list and a few heuristics
       (ALL CAPS short codes, "records"/"music" suffixes, numeric/year-only
       segments, generic marketing words).
    4. If the uploader/author field itself matches a known label, and a
       plausible artist segment was found in the title, the label is
       replaced by that artist. Otherwise the original author is kept
       unchanged — the cleaner never invents an artist name it didn't see.
    """

    def __init__(
        self,
        *,
        extra_label_names: tuple[str, ...] = (),
        extra_noise_phrases: tuple[str, ...] = (),
    ) -> None:
        self._label_names = {s.lower() for s in DEFAULT_LABEL_SUFFIXES} | {
            s.lower() for s in extra_label_names
        }
        self._noise_phrases = tuple(
            p.lower() for p in (*_PLAIN_NOISE_PHRASES, *extra_noise_phrases)
        )

    # -- public API ---------------------------------------------------------- #

    def clean(self, *, title: str, author: str) -> CleanedMetadata:
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

        candidates: list[str] = []
        extra_tags: list[str] = []
        labeled_singer: str | None = None

        # A "feat./ft." credit inside the title segment itself (not yet
        # split off) is a strong, unambiguous artist signal even though
        # it lives in segment 0 — extract it before stripping.
        feat_match = _FEAT_RE.search(song_title)
        if feat_match:
            featured_artist = song_title[feat_match.end():].strip(" .,-")
            song_title = song_title[: feat_match.start()].strip(" .,-")
            if featured_artist:
                candidates.append(featured_artist)

        for segment in remaining:
            cleaned_segment = self._strip_noise(segment)
            if not cleaned_segment:
                continue

            # An explicit "Singer:" label is the strongest possible signal
            # and always wins outright, regardless of position or shape.
            singer_match = _SINGER_LABEL_RE.match(cleaned_segment)
            if singer_match:
                labeled_singer = cleaned_segment[singer_match.end():].strip(" .,-")
                continue

            # Composer/lyricist credits are a different role than the
            # performing artist — waterlink only reports the singer, so
            # these are dropped rather than used as the artist.
            composer_match = _COMPOSER_LABEL_RE.match(cleaned_segment)
            if composer_match:
                extra_tags.append(cleaned_segment)
                continue

            if _CAST_LABEL_RE.match(cleaned_segment) or _MOVIE_LABEL_RE.match(cleaned_segment):
                extra_tags.append(cleaned_segment)
                continue

            if self._looks_like_label_or_noise(cleaned_segment):
                extra_tags.append(cleaned_segment)
                continue

            candidates.append(self._normalize_artist(cleaned_segment))

        if labeled_singer:
            artist_candidate: str | None = labeled_singer
            extra_tags.extend(candidates)
        else:
            artist_candidate = self._pick_best_artist_candidate(candidates)
            for candidate in candidates:
                if candidate != artist_candidate:
                    extra_tags.append(candidate)

        final_author = author.strip()
        if self._looks_like_label_or_noise(final_author) and artist_candidate:
            final_author = artist_candidate
        elif artist_candidate and not final_author:
            final_author = artist_candidate

        if not song_title:
            song_title = original_title.strip()

        return CleanedMetadata(
            title=song_title,
            artist=final_author or original_author.strip(),
            original_title=original_title,
            original_author=original_author,
            extra_tags=tuple(extra_tags),
        )

    def clean_track(self, track: Track) -> Track:
        """Return a new :class:`Track` with a cleaned title/author.

        The original values are preserved in ``track.extra`` under
        ``raw_title`` / ``raw_author`` so nothing is lost.
        """

        result = self.clean(title=track.title, author=track.author)
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

    def _looks_like_label_or_noise(self, segment: str) -> bool:
        lowered = segment.lower().strip()
        if not lowered:
            return True
        if lowered in self._label_names:
            return True
        for label in self._label_names:
            if label in lowered:
                return True
        if lowered in self._noise_phrases:
            return True
        # Pure year or numeric tag, e.g. "2024", "#1".
        if re.fullmatch(r"#?\d{1,4}", lowered):
            return True
        # Generic single marketing words.
        if lowered in {
            "viral", "trending", "new", "latest", "exclusive", "hd", "4k",
            "lyrics", "lyrical", "lyric video", "audio", "video", "full song",
            "full video", "out now", "clip", "teaser", "trailer",
        }:
            return True
        return False

    def _pick_best_artist_candidate(self, candidates: list[str]) -> str | None:
        """Pick the most likely singer/artist segment among several.

        The dominant real-world convention (Bollywood soundtracks
        especially) is: song title, then singer(s)/composer(s) segment,
        then movie/cast segment(s) — e.g.::

            Kesariya | Arijit Singh | Brahmastra | Ranbir Kapoor, Alia Bhatt
            Chaleya | Anirudh, Arijit Singh, Shilpa Rao | Shah Rukh Khan, Nayanthara

        So among segments that plausibly look like person names, the
        *first* one is preferred outright — position (proximity to the
        title) is a stronger signal than how name-dense a later segment
        looks, since cast segments are often just as (or more) name-dense
        than the singer segment. Density is only used to filter out
        segments that don't look like names at all (already done by the
        caller via `_looks_like_label_or_noise`), not to rank among ones
        that do. The exception is a single merged segment mixing cast and
        singers with no separator, handled by :meth:`_trim_trailing_names`.
        """

        if not candidates:
            return None

        name_like = [c for c in candidates if self._has_person_name_shape(c)]
        pool = name_like or candidates
        return self._trim_trailing_names(pool[0])

    def _has_person_name_shape(self, segment: str) -> bool:
        """Whether a segment looks like it's made of person name(s) rather
        than a movie/album/project title.

        Movie titles are usually a single run of Title Case words with no
        list separator (e.g. "Rocky Aur Rani Kii Prem Kahaani",
        "Shershaah"). Person-name lists are either a single short
        (<= 3 word) name, or multiple names joined by a comma/ampersand.
        This isn't foolproof — some movie titles are short enough to look
        like a name, and some singer credits are a single word — but it
        correctly separates the common cases in practice.
        """

        words = [w for w in re.split(r"[\s,&]+", segment) if w]
        if not words:
            return False
        title_case_ratio = sum(1 for w in words if w[:1].isupper()) / len(words)
        if title_case_ratio < 0.6:
            return False
        has_list_separator = bool(re.search(r",|&|\band\b", segment, re.IGNORECASE))
        # A short (<=3 word) Title Case phrase is plausibly a single
        # person's name (e.g. "Arijit Singh", "Sonu Nigam"). Anything
        # longer without a list separator reads as a title/phrase instead
        # (e.g. "Rocky Aur Rani Kii Prem Kahaani").
        return has_list_separator or len(words) <= 3

    def _trim_trailing_names(self, segment: str) -> str:
        """When a single segment is a comma-separated list of 4+ names,
        real-world credit ordering strongly suggests the list mixes
        cast/movie names first and singer(s)/composer(s) last. Long lists
        (4+ names) are trimmed to roughly the trailing half; shorter lists
        (2-3 names, typically all singers on a duet/trio track) are left
        intact since trimming would likely remove a real co-singer.
        """

        parts = [p.strip() for p in segment.split(",") if p.strip()]
        if len(parts) < 4:
            return segment
        midpoint = len(parts) // 2
        return ", ".join(parts[midpoint:])

    def _normalize_artist(self, segment: str) -> str:
        # If it's a "feat. X" style segment, keep only the featured artist
        # name portion since that's the most useful bit for display.
        if _FEAT_RE.search(segment):
            parts = _FEAT_RE.split(segment, maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                return parts[1].strip()
        return segment.strip()


_default_cleaner = TitleCleaner()


def clean_track(track: Track, *, cleaner: TitleCleaner | None = None) -> Track:
    """Convenience function using a shared default :class:`TitleCleaner`.

    Pass a custom ``cleaner`` (e.g. with extra label names for regional
    labels not in the default list) to override behavior.
    """

    return (cleaner or _default_cleaner).clean_track(track)
