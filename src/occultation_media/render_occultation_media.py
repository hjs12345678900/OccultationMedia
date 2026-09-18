"""Render synchronized curves and real detector frames to GIF, PNG and MP4."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .read_tangra_photometry import TangraRow
from .render_detector_field import first_frame_limits, paste_full_field, frame_durations
STAMP_SIZE = 35
CANVAS_SIZE = (2100, 900)
EXPORT_SIZE = (1260, 540)
PANEL_SIZE = (980, 760)
LEFT_ORIGIN = (70, 70)
RIGHT_ORIGIN = (1080, 70)

from .platform_runtime import load_font, ffmpeg_executable, hidden_process_options

def format_adu(value: float) -> str:
    """Format an ADU axis value using compact K/M suffixes."""

    if value >= 1_000_000: return f"{value / 1_000_000:.1f}M"
    if value >= 1_000: return f"{value / 1_000:.0f}K"
    return f"{value:.0f}"

def render_language(
    rows: list[TangraRow],
    selected_indices: list[int],
    stamps: dict[int, np.ndarray],
    target_id: int,
    event_bounds: tuple[int, int],
    predicted_midtime: datetime | None,
    prediction_error_sec: float | None,
    asteroid: str,
    star: str,
    exposure_ms: float,
    predicted_max_duration_sec: float | None,
    language: str,
    output_gif: Path,
    full_field: bool = False,
    target_xy: tuple[float, float] | None = None,
) -> dict[str, object]:
    """Render one localized GIF in the established 1260 × 540 layout.

    The light curve is target-only net flux in ADU. Pixel intensities use one
    fixed percentile/asinh stretch across the complete animation so changes in
    apparent target brightness remain comparable between frames.
    """

    selected_rows = [rows[index] for index in selected_indices]
    selected_frames = [row.frame for row in selected_rows]
    black_adu, white_adu = first_frame_limits(stamps[selected_frames[0]])

    start_index, end_index = event_bounds
    disappearance = rows[start_index - 1].time_utc + (rows[start_index].time_utc - rows[start_index - 1].time_utc) / 2
    reappearance = rows[end_index].time_utc + (rows[end_index + 1].time_utc - rows[end_index].time_utc) / 2
    event_frames = {row.frame for row in rows[start_index : end_index + 1]}
    axis_start, axis_end = selected_rows[0].time_utc, selected_rows[-1].time_utc
    axis_span = (axis_end - axis_start).total_seconds()
    fluxes = np.asarray([row.net_flux_adu(target_id) for row in selected_rows])
    cadence = float(np.median(np.diff([sample.time_utc.timestamp() for sample in rows])))
    y_min = 0.0
    y_max = float(np.ceil(max(100_000.0, fluxes.max() * 1.08) / 50_000.0) * 50_000.0)

    title_font = load_font(38, language, True)
    label_font = load_font(25, language, True)
    text_font = load_font(23, language)
    small_font = load_font(20, language)
    mono_font = load_font(22, language)
    target_color, event_color = (92, 170, 255), (255, 73, 98)
    current_color = (250, 236, 181)
    strings = {
        "en": {
            "curve_title": "Target light curve", "curve_sub": f"Object {target_id} • Signal − Background",
            "y": "net flux (ADU)", "dip": "DIP", "legend": f"Object {target_id} (occulted star)",
            "prediction": "prediction", "cutout": "target cutout", "frame": "frame",
            "low": "LOW-FLUX FRAME", "exposure": "ms exposure", "fps": "fps", "predicted": "predicted",
        },
        "zh": {
            "curve_title": "目标星光变曲线", "curve_sub": f"目标 {target_id} · 信号 − 背景",
            "y": "净光通量（ADU）", "dip": "实测变暗", "legend": f"目标 {target_id}（被掩星）",
            "prediction": "预报", "cutout": "目标星切片", "frame": "帧",
            "low": "低光通量帧", "exposure": "毫秒曝光", "fps": "帧/秒", "predicted": "预报",
        },
    }[language]

    if full_field:
        strings["cutout"] = "full recorded field" if language == "en" else "完整记录星场"

    def sx(time_utc: datetime) -> float:
        return 98 + (time_utc - axis_start).total_seconds() / axis_span * (922 - 98)

    def sy(flux_adu: float) -> float:
        return 628 - (flux_adu - y_min) / (y_max - y_min) * (628 - 124)

    def base_canvas() -> Image.Image:
        image = Image.new("RGB", CANVAS_SIZE, (9, 13, 22))
        draw = ImageDraw.Draw(image)
        for y in range(CANVAS_SIZE[1]):
            blend = y / CANVAS_SIZE[1]
            draw.line((0, y, CANVAS_SIZE[0], y), fill=(int(9 + 12 * blend), int(13 + 17 * blend), int(22 + 26 * blend)))
        for origin in (LEFT_ORIGIN, RIGHT_ORIGIN):
            x, y = origin
            draw.rounded_rectangle((x, y, x + PANEL_SIZE[0], y + PANEL_SIZE[1]), radius=18, fill=(10, 17, 29), outline=(42, 57, 84), width=2)
        return image

    def curve_panel(current_index: int) -> Image.Image:
        panel = Image.new("RGB", PANEL_SIZE, (10, 17, 29))
        draw = ImageDraw.Draw(panel, "RGBA")
        draw.text((42, 25), strings["curve_title"], font=title_font, fill=(242, 247, 255))
        draw.text((42, 73), strings["curve_sub"], font=small_font, fill=(182, 198, 220))
        x0, y0, x1, y1 = 98, 124, 922, 628
        if predicted_midtime is not None and prediction_error_sec is not None:
            predicted_start = predicted_midtime - timedelta(seconds=prediction_error_sec)
            predicted_end = predicted_midtime + timedelta(seconds=prediction_error_sec)
            band_left, band_right = max(x0, sx(predicted_start)), min(x1, sx(predicted_end))
            if band_left < band_right:
                draw.rectangle((band_left, y0, band_right, y1), fill=(65, 116, 166, 42))
        current_time = selected_rows[current_index].time_utc
        # Reveal the observed interval causally: no red fill before disappearance,
        # then extend it to the current sample until the full dip is visible.
        if current_time > disappearance:
            progressive_end = min(current_time, reappearance)
            draw.rectangle((sx(disappearance), y0, sx(progressive_end), y1), fill=(255, 73, 98, 38))
        for i in range(1, 5):
            y, x = y0 + i * (y1 - y0) / 5, x0 + i * (x1 - x0) / 5
            draw.line((x0, y, x1, y), fill=(31, 45, 68), width=1)
            draw.line((x, y0, x, y1), fill=(31, 45, 68), width=1)
        draw.rectangle((x0, y0, x1, y1), outline=(64, 78, 104), width=2)
        if predicted_midtime is not None and axis_start <= predicted_midtime <= axis_end:
            draw.line((sx(predicted_midtime), y0, sx(predicted_midtime), y1), fill=(120, 177, 230), width=2)
        if current_time >= disappearance:
            draw.line((sx(disappearance), y0, sx(disappearance), y1), fill=event_color, width=2)
            if current_time >= reappearance:
                draw.line((sx(reappearance), y0, sx(reappearance), y1), fill=event_color, width=2)
                dip_text = f"{strings['dip']} ≈ {disappearance.strftime('%H:%M:%S.%f')[:-3]}–{reappearance.strftime('%H:%M:%S.%f')[:-3]} UTC"
            elif language == "en":
                dip_text = f"DIP IN PROGRESS • from {disappearance.strftime('%H:%M:%S.%f')[:-3]} UTC"
            else:
                dip_text = f"正在变暗 • 始于 {disappearance.strftime('%H:%M:%S.%f')[:-3]} UTC"
            draw.text((x1 - 12, y0 + 12), dip_text, font=small_font, fill=event_color, anchor="ra")
        for value in np.linspace(y_min, y_max, 5):
            draw.text((x0 - 12, sy(float(value))), format_adu(value), font=small_font, fill=(196, 204, 218), anchor="ra")
        # Rotate the y label so it remains fully inside the panel in both Latin
        # and CJK layouts without competing with numerical tick labels.
        label_box = draw.textbbox((0, 0), strings["y"], font=small_font)
        label_layer = Image.new("RGBA", (label_box[2] + 8, label_box[3] + 8), (0, 0, 0, 0))
        ImageDraw.Draw(label_layer).text((4, 4), strings["y"], font=small_font, fill=(196, 204, 218, 255))
        label_layer = label_layer.rotate(90, expand=True)
        panel.paste(label_layer, (18, int((y0 + y1 - label_layer.height) / 2)), label_layer)
        draw.text(((x0 + x1) / 2, 706), "UTC", font=small_font, fill=(196, 204, 218), anchor="mm")
        for timestamp, x in ((axis_start, x0), (axis_start + (axis_end - axis_start) / 2, (x0 + x1) / 2), (axis_end, x1)):
            draw.text((x, y1 + 18), timestamp.strftime("%H:%M:%S.%f")[:-4], font=small_font, fill=(196, 204, 218), anchor="mt")
        points = [(sx(row.time_utc), sy(row.net_flux_adu(target_id))) for row in selected_rows[: current_index + 1]]
        if len(points) > 1: draw.line(points, fill=target_color + (230,), width=5, joint="curve")
        for point_index, (point, row) in enumerate(zip(points, selected_rows)):
            current = point_index == len(points) - 1
            radius = 9 if current else 4
            fill = current_color if current else (event_color if row.frame in event_frames else target_color)
            outline = (255, 255, 255) if current else (10, 17, 29)
            x, y = point
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=outline, width=2)
        draw.line((48, 706, 92, 706), fill=target_color, width=5)
        draw.ellipse((66, 700, 78, 712), fill=target_color)
        draw.text((106, 692), strings["legend"], font=text_font, fill=(232, 238, 248))
        if predicted_midtime is not None:
            draw.line((650, 706, 678, 706), fill=(120, 177, 230), width=2)
            legend = strings['prediction']
            if prediction_error_sec is not None:
                draw.rectangle((650, 697, 678, 715), fill=(65, 116, 166, 90))
                legend += f" ±{prediction_error_sec:g} s"
            draw.text((690, 692), legend, font=text_font, fill=(182, 198, 220))
        return panel

    def stamp_panel(row: TangraRow, stamp: np.ndarray) -> Image.Image:
        panel = Image.new("RGB", PANEL_SIZE, (10, 17, 29))
        draw = ImageDraw.Draw(panel, "RGBA")
        heading = f"{asteroid} {strings['cutout']}"
        heading_font = title_font
        for size in range(38, 17, -1):
            heading_font = load_font(size, language, True)
            if draw.textlength(heading, font=heading_font) <= 610:
                break
        while draw.textlength(heading, font=heading_font) > 610:
            heading = heading[:-2] + "…"
        draw.text((42, 25), heading, font=heading_font, fill=(236, 244, 255))
        time_text = row.time_utc.strftime("%H:%M:%S.%f")[:-3]
        draw.text((42, 76), f"{star} • {strings['frame']} {row.frame} • {time_text} UTC", font=mono_font, fill=(182, 198, 220))
        video_box = (54, 124, 926, 704)
        outline = event_color if row.frame in event_frames else (55, 69, 96)
        draw.rounded_rectangle(video_box, radius=14, fill=(4, 7, 12), outline=outline, width=3)
        if full_field:
            paste_full_field(panel, stamp, black_adu, white_adu, target_xy)
        else:
            linear = np.clip((stamp.astype(float) - black_adu) / (white_adu - black_adu), 0.0, 1.0)
            display = np.asarray(np.round(255 * np.arcsinh(8 * linear) / np.arcsinh(8)), dtype=np.uint8)
            image = Image.fromarray(display, mode="L").convert("RGB").resize((520, 520), Image.Resampling.NEAREST)
            image_x, image_y = 230, 154
            panel.paste(image, (image_x, image_y))
            center_x = image_x + image.width // 2
            center_y = image_y + image.height // 2
            radius = int(round(4.61 * image.width / STAMP_SIZE))
            marker_color = (255, 242, 88)
            draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), outline=marker_color, width=4)
            gap, tick = 8, 20
            draw.line((center_x, center_y - radius - gap - tick, center_x, center_y - radius - gap), fill=marker_color, width=4)
            draw.line((center_x, center_y + radius + gap, center_x, center_y + radius + gap + tick), fill=marker_color, width=4)
            draw.line((center_x - radius - gap - tick, center_y, center_x - radius - gap, center_y), fill=marker_color, width=4)
            draw.line((center_x + radius + gap, center_y, center_x + radius + gap + tick, center_y), fill=marker_color, width=4)
        draw.text((42, 716), f"{exposure_ms:g} {strings['exposure']} • {1 / cadence:.1f} {strings['fps']}", font=small_font, fill=(196, 204, 218))
        if predicted_midtime is not None:
            prediction_text = f"{strings['predicted']} {predicted_midtime.strftime('%H:%M:%S')} UTC"
            if prediction_error_sec is not None:
                prediction_text += f" ±{prediction_error_sec:g} s"
            if predicted_max_duration_sec is not None:
                prediction_text += f" • max {predicted_max_duration_sec:g} s" if language == "en" else f" • 最长 {predicted_max_duration_sec:g} 秒"
            draw.text((938, 716), prediction_text, font=small_font, fill=(196, 204, 218), anchor="ra")
        if row.frame in event_frames:
            draw.text((900, 31), strings["low"], font=label_font, fill=event_color, anchor="ra")
        return panel

    gif_frames: list[Image.Image] = []
    for current_index, row in enumerate(selected_rows):
        canvas = base_canvas()
        canvas.paste(curve_panel(current_index), LEFT_ORIGIN)
        canvas.paste(stamp_panel(row, stamps[row.frame]), RIGHT_ORIGIN)
        gif_frames.append(canvas.resize(EXPORT_SIZE, Image.Resampling.LANCZOS))
    output_gif.parent.mkdir(parents=True, exist_ok=True)
    # Preserve sparse colored pointers and plot lines against grayscale detector noise.
    encoded_frames = [frame.quantize(colors=256, method=Image.Quantize.MAXCOVERAGE) for frame in gif_frames]
    encoded_frames[0].save(output_gif, save_all=True, append_images=encoded_frames[1:], duration=frame_durations(selected_rows), loop=0, disposal=2, optimize=True)
    preview = output_gif.with_name(f"{output_gif.stem}_preview.png")
    gif_frames[len(gif_frames) // 2].save(preview)
    return {
        "gif": str(output_gif), "preview": str(preview), "frames": len(gif_frames),
        "disappearance_utc": disappearance.isoformat(), "reappearance_utc": reappearance.isoformat(),
        "black_adu": black_adu, "white_adu": white_adu,
    }

def make_mp4(gif_path: Path) -> Path:
    """Convert a 1260 × 540 GIF to silent H.264/yuv420p at 25 fps."""

    output = gif_path.with_suffix(".mp4")
    subprocess.run([
        ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(gif_path),
        "-vf", "fps=25,scale=1260:540:flags=lanczos,format=yuv420p", "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-movflags", "+faststart", "-an", str(output),
    ], check=True, **hidden_process_options())
    return output
