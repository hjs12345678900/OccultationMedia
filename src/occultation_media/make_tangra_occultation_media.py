#!/usr/bin/env python3
"""Create synchronized media from Tangra CSV and ADV/SER/FITS/RAVF or LC.

Full sources retain their complete field; LC mode uses recorded target stamps.
CSV UTC controls display timing. This tool does not fit formal contact times.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from datetime import timedelta
import numpy as np
from .read_tangra_photometry import TangraRow, parse_time, infer_event_date, parse_tangra_csv, read_target_position
from .read_tangra_stamps import extract_target_stamps
from .detect_low_flux import detect_event
from .render_occultation_media import load_font, render_language, make_mp4
from .render_detector_field import frame_durations
from .prepare_source_frames import add_source_arguments, unique_file, validate_rows, load_source_frames

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--event-date")
    parser.add_argument("--asteroid", required=True)
    parser.add_argument("--star", required=True)
    parser.add_argument("--predicted-time", help="Optional predicted UTC midpoint, HH:MM:SS[.sss]; omit to hide prediction")
    parser.add_argument("--prediction-error-sec", type=float, help="Optional uncertainty in seconds; omitted means no blue band")
    parser.add_argument("--predicted-max-duration-sec", type=float)
    parser.add_argument("--exposure-ms", type=float, required=True)
    parser.add_argument("--display-margin-sec", type=float, default=5.0)
    parser.add_argument("--language", choices=("en", "zh", "both"), default="both")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--basename")
    add_source_arguments(parser)
    return parser.parse_args(argv)

def main(argv=None) -> None:
    args = parse_args(argv)
    event_date = args.event_date or infer_event_date(args.folder)
    predicted_midtime = None
    if args.predicted_time:
        time_text = args.predicted_time if "." in args.predicted_time else args.predicted_time + ".000"
        predicted_midtime = parse_time(event_date, time_text)
    else:
        # Missing prediction stays missing; never use the measured event midpoint.
        args.prediction_error_sec = None
        args.predicted_max_duration_sec = None
    csv_path = unique_file(args.folder, args.csv, ".csv")
    if args.stride < 1 or args.exposure_ms <= 0 or (args.prediction_error_sec is not None and (not np.isfinite(args.prediction_error_sec) or args.prediction_error_sec < 0)) or args.display_margin_sec < 0:
        raise ValueError("Invalid stride, exposure, uncertainty or display margin")
    rows, object_types = parse_tangra_csv(csv_path, event_date)
    target_id = next((identifier for identifier, kind in object_types.items() if kind == "OccultedStar"), 1)
    marker_source = "manual" if args.target_xy is not None else None
    if args.source and args.target_xy is None:
        args.target_xy = read_target_position(csv_path, target_id)
        if args.target_xy is not None:
            marker_source = "csv_starting_position"
    validate_rows(rows, target_id)
    if args.event_frames:
        lookup = {r.frame:i for i,r in enumerate(rows)}
        if any(f not in lookup for f in args.event_frames):
            raise ValueError("--event-frames values must occur in CSV")
        event_bounds = tuple(lookup[f] for f in args.event_frames)
    else:
        event_bounds = detect_event(rows, target_id, predicted_midtime)
    if not (0 < event_bounds[0] <= event_bounds[1] < len(rows)-1):
        raise ValueError("Low interval requires baseline samples before and after")
    event_start, event_end = event_bounds
    display_start = rows[event_start].time_utc - timedelta(seconds=args.display_margin_sec)
    display_end = rows[event_end].time_utc + timedelta(seconds=args.display_margin_sec)
    cadence = float(np.median(np.diff([row.time_utc.timestamp() for row in rows])))
    stride = args.stride
    all_indices = [index for index, row in enumerate(rows) if display_start <= row.time_utc <= display_end]
    selected_indices = all_indices[::stride]
    wanted_frames = {rows[index].frame for index in selected_indices}
    selected_rows = [rows[i] for i in selected_indices]
    frame_durations(selected_rows)
    if args.source:
        stamps, source_info = load_source_frames(args, selected_rows)
    else:
        lc_path = unique_file(args.folder, args.lc, ".lc")
        stamps = extract_target_stamps(lc_path, wanted_frames, target_id)
        source_info = {"source":str(lc_path.resolve()),"format":"LC", "display_timestamp_convention":"Tangra CSV UTC"}
    output_dir = args.output_dir or args.folder
    basename = args.basename or re.sub(r"[^A-Za-z0-9_-]+", "_", f"{args.asteroid}_{args.star}").strip("_")
    languages = ("en", "zh") if args.language == "both" else (args.language,)
    summary: dict[str, object] = {}
    for language in languages:
        gif_path = output_dir / f"{basename}_occultation_{language}.gif"
        metadata = render_language(
            rows, selected_indices, stamps, target_id, event_bounds, predicted_midtime,
            args.prediction_error_sec, args.asteroid, args.star, args.exposure_ms,
            args.predicted_max_duration_sec, language, gif_path,
            full_field=bool(args.source), target_xy=args.target_xy,
        )
        if not args.no_mp4:
            metadata["mp4"] = str(make_mp4(gif_path))
        summary[language] = metadata
    manifest = {"csv":str(csv_path.resolve()), "source":source_info, "outputs":summary,
                "stretch":{"reference":"first displayed frame", "percentiles":[0.5,99.95],"asinh_factor":8},
                "stride":args.stride, "target_xy":args.target_xy,
                "target_position_source":marker_source,
                "prediction": None if predicted_midtime is None else {
                    "midtime_utc":predicted_midtime.isoformat(),
                    "uncertainty_sec":args.prediction_error_sec,
                    "max_duration_sec":args.predicted_max_duration_sec},
                "event_selection":"manual" if args.event_frames else ("near_prediction" if predicted_midtime else "whole_csv")}
    (output_dir / f"{basename}_metadata.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
