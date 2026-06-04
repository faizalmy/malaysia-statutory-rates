"""Audit changelog for scraper data changes.

Appends field-level diffs to data/_changelog.jsonl whenever a scraper
detects and saves new data. Enables change tracking, alerting, and
investigation of scrape errors.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def diff_changes(old: dict, new: dict, path: str = "") -> list[dict]:
    """Compute field-level diffs between two dicts.

    Args:
        old: Previous data (without _metadata).
        new: New data (without _metadata).
        path: Dot-separated path prefix for nested keys.

    Returns:
        List of change dicts with keys: path, type, old, new.
        type is one of: "modified", "added", "removed".
    """
    changes: list[dict] = []

    all_keys = set(old.keys()) | set(new.keys())

    for key in sorted(all_keys):
        current_path = f"{path}.{key}" if path else key

        if key not in old:
            # Added
            changes.append({
                "path": current_path,
                "type": "added",
                "old": None,
                "new": new[key],
            })
        elif key not in new:
            # Removed
            changes.append({
                "path": current_path,
                "type": "removed",
                "old": old[key],
                "new": None,
            })
        elif isinstance(old[key], dict) and isinstance(new[key], dict):
            # Recurse into nested dicts
            changes.extend(diff_changes(old[key], new[key], current_path))
        elif isinstance(old[key], list) and isinstance(new[key], list):
            # Diff lists by index (simple approach)
            _diff_lists(old[key], new[key], current_path, changes)
        elif old[key] != new[key]:
            # Modified scalar
            changes.append({
                "path": current_path,
                "type": "modified",
                "old": old[key],
                "new": new[key],
            })

    return changes


def _diff_lists(
    old_list: list, new_list: list, path: str, changes: list[dict]
) -> None:
    """Diff two lists, appending changes to the provided list.

    For lists of dicts (e.g. holidays), tries to match by identity key
    (name, date, or id). Falls back to index-based comparison.
    """
    # Try identity-key matching for lists of dicts
    if old_list and new_list and isinstance(old_list[0], dict):
        identity_keys = ["name", "date", "id", "code"]
        id_key = None
        for k in identity_keys:
            if k in old_list[0]:
                id_key = k
                break

        if id_key:
            old_by_id = {item.get(id_key): item for item in old_list}
            new_by_id = {item.get(id_key): item for item in new_list}

            for key_val in sorted(set(old_by_id.keys()) | set(new_by_id.keys())):
                item_path = f"{path}[{id_key}={key_val}]"
                if key_val not in old_by_id:
                    changes.append({
                        "path": item_path,
                        "type": "added",
                        "old": None,
                        "new": new_by_id[key_val],
                    })
                elif key_val not in new_by_id:
                    changes.append({
                        "path": item_path,
                        "type": "removed",
                        "old": old_by_id[key_val],
                        "new": None,
                    })
                else:
                    changes.extend(
                        diff_changes(old_by_id[key_val], new_by_id[key_val], item_path)
                    )
            return

    # Fallback: index-based comparison
    max_len = max(len(old_list), len(new_list))
    for i in range(max_len):
        item_path = f"{path}[{i}]"
        if i >= len(old_list):
            changes.append({"path": item_path, "type": "added", "old": None, "new": new_list[i]})
        elif i >= len(new_list):
            changes.append({"path": item_path, "type": "removed", "old": old_list[i], "new": None})
        elif old_list[i] != new_list[i]:
            if isinstance(old_list[i], dict) and isinstance(new_list[i], dict):
                changes.extend(diff_changes(old_list[i], new_list[i], item_path))
            else:
                changes.append({
                    "path": item_path,
                    "type": "modified",
                    "old": old_list[i],
                    "new": new_list[i],
                })


def append_changelog(
    data_dir: Path,
    scraper_name: str,
    source_url: str,
    old_data: dict | None,
    new_data: dict,
) -> Path:
    """Append a changelog entry to data/_changelog.jsonl.

    Args:
        data_dir: Path to the data/ directory.
        scraper_name: Name of the scraper (e.g. "epf_rates").
        source_url: Source URL that was scraped.
        old_data: Previous data dict (None if file didn't exist).
        new_data: New data dict.

    Returns:
        Path to the changelog file.
    """
    changelog_path = data_dir / "_changelog.jsonl"

    # Strip _metadata from both for diffing
    old_clean = {k: v for k, v in (old_data or {}).items() if k != "_metadata"}
    new_clean = {k: v for k, v in new_data.items() if k != "_metadata"}

    if old_data is None:
        changes = [{"path": "*", "type": "added", "old": None, "new": "(new file)"}]
    else:
        changes = diff_changes(old_clean, new_clean)

    # Compute content hashes for chaining
    import hashlib

    def _hash(data: dict) -> str:
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "scraper": scraper_name,
        "source": source_url,
        "changes": changes,
        "change_count": len(changes),
        "prev_hash": _hash(old_clean) if old_data else None,
        "new_hash": _hash(new_clean),
    }

    with open(changelog_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return changelog_path


def read_changelog(data_dir: Path, last_n: int | None = None) -> list[dict]:
    """Read changelog entries.

    Args:
        data_dir: Path to the data/ directory.
        last_n: If set, return only the last N entries.

    Returns:
        List of changelog entry dicts.
    """
    changelog_path = data_dir / "_changelog.jsonl"
    if not changelog_path.exists():
        return []

    entries = []
    with open(changelog_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    if last_n is not None:
        return entries[-last_n:]
    return entries
