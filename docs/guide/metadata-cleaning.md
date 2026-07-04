# Clean Metadata

Different sources report the artist very differently, so waterlink treats
YouTube and everything else separately instead of guessing with one
heuristic:

- **YouTube / YouTube Music**: Lavalink only gives you the video title and
  the name of the channel that uploaded it — there's no real "artist"
  field. The channel name is used as the artist. Title text is *not*
  mined to guess a "real" performer, since that's inherently unreliable
  (a Title-Case segment could be a singer, a movie name, or a cast list,
  and there's no way to tell from text alone).
- **Every other source** (Spotify, Apple Music, Deezer, SoundCloud with
  proper tags, etc.): these platforms already give Lavalink real,
  structured artist metadata. The `author` field is trusted as-is and
  never rewritten.

Example — a YouTube result:

```
title:  "Tere Liye | Arijit Singh | Viral | T-Series"
author: "T-Series"
```

becomes:

```
title:  "Tere Liye"
author: "T-Series"        # the channel name, not a guessed performer
extra_tags: ("Arijit Singh",)   # other title segments, kept for optional display
```

A Spotify result is left as-is (bracket noise like `(Official Audio)` is
still stripped from the title, but the author is never touched):

```
title:  "Tere Liye"
author: "Arijit Singh"    # trusted verbatim — this is real metadata
```

## Enabling it

Per-client default:

```python
client = waterlink.WaterlinkClient(bot=bot, clean_metadata=True)
```

Per search call (overrides the client default either way):

```python
result = await client.search("tere liye arijit singh", clean=True)
```

Directly on a track you already have:

```python
cleaned = waterlink.clean_track(track)
```

## How it decides what to do

1. `Track.source_name` (Lavalink's `sourceName`) determines the strategy.
   `"youtube"` and `"youtube_music"` / `"ytmusic"` use the YouTube path;
   everything else uses the trust-the-author path.
2. **YouTube path**: the title is split on separators (`|`, `•`, ` - `,
   etc.). The first segment becomes the cleaned title (bracketed tags
   like `(Official Video)` and marketing phrases are stripped from it).
   The channel name — with YouTube's auto-generated `"<Artist> - Topic"`
   and `"<Artist>VEVO"` suffixes trimmed — is always the artist. Other
   title segments (movie name, cast, label name, etc.) are kept on
   `CleanedMetadata.extra_tags` in case you want to show them, but they're
   never promoted to "artist".
3. **Non-YouTube path**: only cosmetic bracketed noise is stripped from
   the title. `author` is never rewritten.

Original values are always preserved on the cleaned `Track` under
`track.extra["raw_title"]` / `track.extra["raw_author"]`.

## Notes on the old `extra_label_names` / `extra_movie_titles` options

Earlier versions tried to guess a "real artist" out of YouTube title text
using a list of known record labels and movie titles. That approach could
easily pick the wrong segment (e.g. a cast member instead of the singer),
so it's been replaced with the channel name, which is always correct for
what it actually represents. `TitleCleaner(extra_label_names=..., extra_movie_titles=...)`
are still accepted as no-op parameters so existing code doesn't break, but
they no longer do anything — use `extra_noise_phrases` if you want extra
marketing phrases stripped from displayed titles.
