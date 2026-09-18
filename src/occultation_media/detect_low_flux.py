"""Heuristic visualization interval detection; not a formal D/R estimator."""
from datetime import datetime
import numpy as np
from .read_tangra_photometry import TangraRow

def detect_event(
    rows: list[TangraRow], target_id: int, predicted_midtime: datetime | None = None
) -> tuple[int, int]:
    """Detect the longest low run, optionally restricting it to a prediction.

    Parameters
    ----------
    rows : list[TangraRow]
        Full observation sequence.
    target_id : int
        One-based occulted-star identifier.
    predicted_midtime : datetime
        Optional predicted event midpoint in UTC. None searches the whole CSV.

    Returns
    -------
    start_index, end_index : tuple[int, int]
        Inclusive row indices of the detected low-flux state.

    Notes
    -----
    For sample ``i``, the diagnostic ratio is target net flux divided by the
    median net flux of non-target objects. A 15-sample moving mean is compared
    with 60% of its local median within ±20 s of prediction, or of the whole
    sequence when no prediction exists. At least 31 samples are required. This is a display
    heuristic, not a contact-time estimator.
    """

    if len(rows) < 31:
        raise ValueError("Automatic detection needs at least 31 samples; specify first/last low frames with --event-frames")
    comparison_ids = sorted(set(rows[0].signal_adu).difference({target_id}))
    ratios = []
    for row in rows:
        target = row.net_flux_adu(target_id)
        references = [row.net_flux_adu(identifier) for identifier in comparison_ids]
        reference = float(np.nanmedian(references)) if references else 1.0
        ratios.append(target / reference if reference > 0 else np.nan)
    ratio = np.asarray(ratios, dtype=float)
    finite = np.isfinite(ratio)
    if not finite.any():
        raise ValueError("No finite target/reference flux ratios; specify --event-frames")
    ratio[~finite] = np.interp(np.flatnonzero(~finite), np.flatnonzero(finite), ratio[finite])
    smooth = np.convolve(ratio, np.ones(15) / 15.0, mode="same")
    search = (np.ones(len(rows), dtype=bool) if predicted_midtime is None else
              np.asarray([abs((row.time_utc - predicted_midtime).total_seconds()) <= 20 for row in rows]))
    if not search.any():
        raise ValueError("Prediction lies outside the CSV; omit prediction or specify --event-frames")
    baseline = float(np.median(smooth[search]))
    candidate = search & (smooth < 0.60 * baseline)
    candidate[:15] = False
    candidate[-15:] = False

    runs: list[list[int]] = []
    for index in np.flatnonzero(candidate):
        if not runs or index != runs[-1][-1] + 1:
            runs.append([int(index)])
        else:
            runs[-1].append(int(index))
    if not runs:
        raise ValueError("No low-flux run detected; specify first/last low frames with --event-frames")
    best = max(runs, key=len)
    return best[0], best[-1]
