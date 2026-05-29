"""Tests for PCB data."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def test_pcb_file_exists():
    assert (DATA_DIR / "pcb_table.json").exists()


def test_pcb_schema():
    data = json.loads((DATA_DIR / "pcb_table.json").read_text())
    assert "tax_brackets" in data
    assert "tax_reliefs" in data
    assert "pcb_method" in data
    assert "_metadata" in data


def test_pcb_brackets_count():
    data = json.loads((DATA_DIR / "pcb_table.json").read_text())
    brackets = data["tax_brackets"]["brackets"]
    assert len(brackets) == 11  # 11 tax brackets


def test_pcb_brackets_structure():
    data = json.loads((DATA_DIR / "pcb_table.json").read_text())
    brackets = data["tax_brackets"]["brackets"]
    for b in brackets:
        assert "min" in b
        assert "rate" in b
        assert "base_tax" in b


def test_pcb_first_bracket():
    data = json.loads((DATA_DIR / "pcb_table.json").read_text())
    first = data["tax_brackets"]["brackets"][0]
    assert first["min"] == 0
    assert first["max"] == 5000
    assert first["rate"] == 0.0


def test_pcb_top_bracket():
    data = json.loads((DATA_DIR / "pcb_table.json").read_text())
    top = data["tax_brackets"]["brackets"][-1]
    assert top["rate"] == 0.30
    assert top["max"] is None


def test_pcb_reliefs():
    data = json.loads((DATA_DIR / "pcb_table.json").read_text())
    reliefs = data["tax_reliefs"]["reliefs"]
    assert len(reliefs) >= 10
    codes = {r["code"] for r in reliefs}
    assert "self" in codes
    assert "spouse" in codes
    assert "child" in codes
