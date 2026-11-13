"""Keep filenames readable and reuse explicitly imported legacy playlist names."""
from collections import defaultdict
from pathlib import Path
import json
import shutil
import tempfile
import unicodedata


def name_key(text):
    return unicodedata.normalize("NFC", text).casefold()


def match_key(filename):
    artist, separator, title = Path(filename).stem.partition(" - ")
    if not separator:
        return None
    def normalize(text):
        text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
        return "".join(char for char in text if char.isalnum())
    return normalize(artist), normalize(title)


def without_id(filename, video_id):
    suffix = f" [{video_id}].opus"
    return filename[:-len(suffix)] + ".opus" if filename.endswith(suffix) else filename


def read_legacy_playlist(path):
    import ytmusic_downloader as engine
    names = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = engine.safe_manifest_filename(line, ".opus")
        if name:
            names.append(name)
    return names


def assign_filenames(tracks, folder, known, legacy_names=(), migrate=False):
    """Assign stable names; scan stays read-only, downloading can migrate owned files."""
    import ytmusic_downloader as engine
    exact, normalized = {}, defaultdict(set)
    for name in legacy_names:
        if engine.safe_manifest_filename(name, ".opus"):
            exact[name_key(name)] = name
            if match_key(name):
                normalized[match_key(name)].add(name)
    reserved = {}
    for video_id, entry in known.items():
        name = engine.safe_manifest_filename(entry.get("output_filename"), ".opus")
        if name and without_id(name, video_id) == name:
            reserved[name_key(name)] = video_id
    # Audio copied into the folder by hand (e.g. from a phone) may use an older artist
    # separator such as "A & B" instead of "A, B". Offer unowned files as fuzzy candidates.
    if folder.is_dir():
        for path in folder.iterdir():
            name = path.name
            if (path.is_file() and engine.safe_manifest_filename(name, ".opus")
                    and name_key(name) not in reserved and match_key(name)):
                normalized[match_key(name)].add(name)
    assigned, renamed, backup = {}, [], None
    for track in tracks:
        if track.video_id in assigned:
            track.filename = assigned[track.video_id]
            continue
        old = engine.safe_manifest_filename(known.get(track.video_id, {}).get("output_filename"), ".opus")
        old = old or engine.safe_manifest_filename(track.filename, ".opus") or engine.build_filename(track.artists, track.title, track.video_id)
        clean = without_id(old, track.video_id)
        canonical = engine.build_filename(track.artists, track.title, track.video_id)
        desired = clean
        if old != clean or not (folder / old).is_file():
            for candidate in (clean, canonical):
                if name_key(candidate) in exact:
                    desired = exact[name_key(candidate)]
                    break
                matches = normalized.get(match_key(candidate), set())
                if len(matches) == 1:
                    desired = next(iter(matches))
                    break
        if not migrate and (folder / old).is_file():
            desired = old
        base, counter = desired, 2
        while (name_key(desired) in reserved and reserved[name_key(desired)] != track.video_id) or (
            migrate and old != desired and (folder / old).is_file() and (folder / desired).exists()
        ):
            desired = f"{Path(base).stem[:235]} ({counter}).opus"
            counter += 1
        if migrate and old != desired and (folder / old).is_file():
            try:
                if backup is None:
                    backup_root = folder / ".filename-backups"
                    backup_root.mkdir(exist_ok=True)
                    backup = Path(tempfile.mkdtemp(prefix="migration-", dir=backup_root))
                    for source in [folder / engine.MANIFEST_NAME, *folder.glob("*.m3u8")]:
                        if source.is_file():
                            shutil.copy2(source, backup / source.name)
                # Record recovery information before touching audio; do not copy/re-encode it.
                (backup / "renames.json").write_text(
                    json.dumps(renamed + [(old, desired)], ensure_ascii=False, indent=2), encoding="utf-8")
                (folder / old).rename(folder / desired)  # Never overwrite another recording.
            except OSError:
                for before, after in reversed(renamed):
                    if (folder / after).is_file() and not (folder / before).exists():
                        (folder / after).rename(folder / before)
                raise
            renamed.append((old, desired))
        reserved[name_key(desired)] = track.video_id
        assigned[track.video_id] = desired
        track.filename = desired
    return renamed
