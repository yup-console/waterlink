# Clean Metadata

Free sources like YouTube are usually uploaded by a label or channel, not
the performing artist, so raw Lavalink metadata often looks like this:

```
title:  "Tere Liye | Arijit Singh | Viral | T-Series"
author: "T-Series"
```

waterlink can turn that into what you actually want to display:

```
title:  "Tere Liye"
author: "Arijit Singh"
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

## How it decides what's noise vs. an artist

1. The title is split on separators (`|`, `•`, ` - `, etc.) into segments.
   The first segment becomes the cleaned title, with bracketed tags like
   `(Official Video)` and marketing phrases stripped.
2. Remaining segments are classified as either a likely **artist name**
   or a **label/noise tag** — using a built-in list of common record
   labels (T-Series, Zee Music, Sony Music, Universal, etc.), plus
   heuristics for movie/album names vs. comma-separated person names.
3. If the uploader field itself matches a known label, and a plausible
   artist was found in the title, the label is replaced by that artist.
   The original uploader is **never discarded** blindly — it's only
   replaced when there's a real signal from the title.
4. YouTube's auto-generated `"<Artist> - Topic"` and `"<Artist>VEVO"`
   channel names are recognized and trimmed to the plain artist name.

The cleaner is conservative: if it isn't confident, it leaves the
original title/author alone rather than guessing. Original values are
always preserved on the cleaned `Track` under
`track.extra["raw_title"]` / `track.extra["raw_author"]`.

## Extending the label list

```python
cleaner = waterlink.TitleCleaner(
    extra_label_names=("my regional label", "another uploader"),
    extra_noise_phrases=("official channel",),
)
client = waterlink.WaterlinkClient(bot=bot, clean_metadata=True, title_cleaner=cleaner)
```
