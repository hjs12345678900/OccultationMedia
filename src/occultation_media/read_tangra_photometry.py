"""Read Tangra target photometry and UTC labels without recalculating flux."""
from __future__ import annotations
import csv
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass(frozen=True)
class TangraRow:
    """One Tangra measurement sample.

    Attributes
    ----------
    frame : int
        Tangra frame number; dimensionless.
    time_utc : datetime
        Frame timestamp in UTC, with the CLI-supplied event date.
    signal_adu, background_adu : dict[int, float]
        Tangra aperture signal and scaled background in detector ADU, keyed by
        one-based object identifier.
    """

    frame: int
    time_utc: datetime
    signal_adu: dict[int, float]
    background_adu: dict[int, float]

    def net_flux_adu(self, object_id: int) -> float:
        """Return ``Signal(object_id) - Background(object_id)`` in ADU."""

        return self.signal_adu[object_id] - self.background_adu[object_id]

def parse_time(date_text: str, time_text: str) -> datetime:
    """Combine a calendar date and Tangra UTC clock label."""

    return datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S.%f")

def infer_event_date(folder: Path) -> str:
    """Infer ``YYYY-MM-DD`` from the event folder or contained filenames."""

    for text in [folder.name, *[path.name for path in folder.iterdir()]]:
        match = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", text)
        if match:
            return "-".join(match.groups())
    raise ValueError("Cannot infer event date; pass --event-date YYYY-MM-DD")

def parse_tangra_csv(path: Path, event_date: str) -> tuple[list[TangraRow], dict[int, str]]:
    """Read Tangra object metadata and frame photometry.

    Parameters
    ----------
    path : Path
        CSV export with an object table and ``FrameNo,Time (UT),...`` header.
    event_date : str
        UTC calendar date as ``YYYY-MM-DD``.

    Returns
    -------
    rows : list[TangraRow]
        Measurements in file order.
    object_types : dict[int, str]
        One-based object identifier to Tangra object type.

    Raises
    ------
    ValueError
        If the measurement header or signal/background columns are missing.
    """

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith("FrameNo,")), None)
    if header_index is None:
        raise ValueError("Tangra measurement header was not found")
    object_types: dict[int, str] = {}
    for line in lines[:header_index]:
        fields = next(csv.reader([line]))
        if len(fields) >= 2 and fields[0].isdigit() and fields[1] in {
            "OccultedStar", "ComparisonStar", "GuidingStar"
        }:
            object_types[int(fields[0])] = fields[1]

    reader = csv.DictReader(lines[header_index:])
    field_names = {name.strip() for name in (reader.fieldnames or [])}
    object_ids = sorted(
        int(match.group(1))
        for name in field_names
        if (match := re.fullmatch(r"Signal \((\d+)\)", name))
    )
    if not object_ids:
        raise ValueError("No Tangra Signal (n) columns were found")

    def optional_float(value: str | None) -> float:
        """Return a detector count or NaN for Tangra's blank measurements."""

        return float(value) if value is not None and value.strip() else float("nan")

    rows: list[TangraRow] = []
    for raw_row in reader:
        row = {key.strip(): value for key, value in raw_row.items()}
        if not row.get("FrameNo", "").strip():
            continue
        rows.append(
            TangraRow(
                frame=int(row["FrameNo"]),
                time_utc=parse_time(event_date, row["Time (UT)"].strip().strip("[]")),
                signal_adu={identifier: optional_float(row[f"Signal ({identifier})"]) for identifier in object_ids},
                background_adu={identifier: optional_float(row[f"Background ({identifier})"]) for identifier in object_ids},
            )
        )
    return rows, object_types


def read_target_position(path: Path, target_id: int) -> tuple[float, float] | None:
    """Read the selected object's fixed initial detector position from Tangra CSV.

    Return (x, y) in zero-based source pixels (upper-left origin), or None when
    the object table/coordinates are absent, ambiguous, negative or nonfinite.
    StartingX/StartingY describe the initial position, not per-frame tracking;
    the displayed source must have the same orientation and crop as the CSV.
    Column names, rather than column order, identify the metadata fields.
    """
    header = None
    positions = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for values in csv.reader(stream):
            fields = [value.strip() for value in values]
            if fields and fields[0] == "FrameNo":
                break
            if {"Object", "StartingX", "StartingY"}.issubset(fields):
                header = fields
                continue
            if header is None:
                continue
            record = dict(zip(header, fields))
            try:
                if int(record.get("Object", "")) != target_id:
                    continue
                x, y = float(record["StartingX"]), float(record["StartingY"])
            except (ValueError, KeyError):
                continue
            if math.isfinite(x) and math.isfinite(y) and x >= 0 and y >= 0:
                positions.append((x, y))
    return positions[0] if len(positions) == 1 else None
