"""
Printable training reports.

Rendered server-side rather than in the browser so the same file comes out of
the web app, the phone and a scheduled job, and so it survives being emailed to
someone who has no account here. ReportLab draws it: it is pure Python with no
system libraries behind it, which matters for a container that has to rebuild
cleanly on someone else's server.

The layout is deliberately plain. A recap that will be printed, filed or shown
to a coach should read like a document, not like a screenshot of a dashboard.
"""
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Line
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

INK = colors.HexColor("#1a1d24")
MUTED = colors.HexColor("#6b7280")
LINE = colors.HexColor("#e5e7eb")
ACCENT = colors.HexColor("#e0553a")
POSITIVE = colors.HexColor("#15803d")
NEGATIVE = colors.HexColor("#b45309")

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_styles["Title"], fontName="Helvetica-Bold",
                    fontSize=22, leading=26, textColor=INK, alignment=0, spaceAfter=2)
SUB = ParagraphStyle("SUB", parent=_styles["Normal"], fontName="Helvetica",
                     fontSize=10.5, leading=14, textColor=MUTED, spaceAfter=14)
H2 = ParagraphStyle("H2", parent=_styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=12, leading=15, textColor=INK, spaceBefore=16, spaceAfter=7)
BODY = ParagraphStyle("BODY", parent=_styles["Normal"], fontName="Helvetica",
                      fontSize=9.5, leading=14, textColor=INK)
NOTE = ParagraphStyle("NOTE", parent=BODY, fontSize=8.5, leading=12, textColor=MUTED)


# ------------------------------------------------------------ formatting ---
def _pace(seconds: Optional[float]) -> str:
    if not seconds or seconds <= 0:
        return "--"
    return f"{int(seconds // 60)}:{int(round(seconds % 60)):02d}"


def _hms(seconds: Optional[float]) -> str:
    if not seconds or seconds <= 0:
        return "--"
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m {secs:02d}s"


def _clock(seconds: Optional[float]) -> str:
    if not seconds or seconds <= 0:
        return "--"
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _num(value: Optional[float], digits: int = 0, unit: str = "") -> str:
    if value is None:
        return "--"
    return f"{value:,.{digits}f}{unit}"


def _signed(value: float, rendered: str) -> str:
    return f"{'+' if value > 0 else '-'}{rendered}"


def _pct(delta: Dict[str, Any]) -> str:
    pct = delta.get("pct")
    return f"  ({abs(pct):.0f}%)" if pct is not None and abs(pct) >= 1 else ""


def _change_num(delta: Optional[Dict[str, Any]], unit: str = "", digits: int = 1) -> str:
    if not delta or delta.get("change") is None:
        return "--"
    change = delta["change"]
    if abs(change) < 0.05:
        return "no change"
    size = f"{abs(change):,.{digits}f}".rstrip("0").rstrip(".") if digits else f"{abs(change):,.0f}"
    return _signed(change, f"{size}{unit}") + _pct(delta)


def _change_time(delta: Optional[Dict[str, Any]]) -> str:
    """
    A change in duration, read as a duration.

    Seconds are not a unit anyone compares weeks in -- "+38403" is not a
    figure, and neither really is "+35m 00s" -- so this rounds to minutes.
    """
    if not delta or delta.get("change") is None:
        return "--"
    change = delta["change"]
    if abs(change) < 60:
        return "no change"
    minutes = int(round(abs(change) / 60))
    hours, minutes = divmod(minutes, 60)
    size = f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
    return _signed(change, size) + _pct(delta)


def _change_pace(delta: Optional[Dict[str, Any]]) -> str:
    """
    A change in pace, said out loud.

    A signed number is genuinely ambiguous here -- "-12.6" is an improvement,
    and reads like a loss -- so the direction is a word and the size is in
    seconds per kilometre. The percentage is dropped: nobody thinks about pace
    in percentages.
    """
    if not delta or delta.get("change") is None:
        return "--"
    change = delta["change"]
    if abs(change) < 1:
        return "no change"
    return f"{abs(change):.0f} s/km {'quicker' if change < 0 else 'slower'}"


# How to colour a change. Some figures have no better direction at all: a lower
# average heart rate can mean easier running or a quicker athlete, and guessing
# which would be inventing a verdict the data does not support.
BETTER_UP, BETTER_DOWN, NEUTRAL = "up", "down", "flat"


def _tone(delta: Optional[Dict[str, Any]], direction: str = BETTER_UP):
    if (not delta or delta.get("change") is None or abs(delta["change"]) < 0.05
            or direction == NEUTRAL):
        return MUTED
    better = delta["change"] < 0 if direction == BETTER_DOWN else delta["change"] > 0
    return POSITIVE if better else NEGATIVE


# ---------------------------------------------------------------- blocks ---
def _rule() -> Drawing:
    d = Drawing(170 * mm, 1)
    d.add(Line(0, 0, 170 * mm, 0, strokeColor=LINE, strokeWidth=0.6))
    return d


def _headline(totals: Dict[str, Any]) -> Table:
    """The four figures that describe a training period."""
    cells = [
        ("Distance", _num(totals.get("km"), 1, " km")),
        ("Time", _hms(totals.get("moving_sec"))),
        ("Runs", _num(totals.get("runs"))),
        ("Training load", _num(totals.get("load"))),
    ]
    table = Table(
        [[c[0] for c in cells], [c[1] for c in cells]],
        colWidths=[42.5 * mm] * 4,
    )
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, 1), "Helvetica-Bold", 17),
        ("TEXTCOLOR", (0, 1), (-1, 1), INK),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 1), (-1, 1), 0.6, LINE),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
    ]))
    return table


def _comparison(report: Dict[str, Any]) -> List[Any]:
    """Every headline figure against the same figure last time."""
    totals, deltas = report.get("totals") or {}, report.get("deltas") or {}
    previous = (report.get("previous") or {}).get("totals") or {}
    noun = report.get("kind", "period")

    # Against an empty period every figure is up by its own value, which looks
    # like a table of achievements and is really a table of nothing to compare.
    if not previous.get("sessions"):
        label = (report.get("previous") or {}).get("label", f"the previous {noun}")
        return [Paragraph(f"There is no training recorded in {label} to compare against.", BODY)]

    rows = [["", f"This {noun}", f"Previous {noun}", "Change"]]
    tones = []
    spec = [
        ("Distance", "km", lambda v: _num(v, 1, " km"),
         lambda d: _change_num(d, " km"), BETTER_UP),
        ("Moving time", "moving_sec", _hms, _change_time, BETTER_UP),
        ("Runs", "runs", lambda v: _num(v), lambda d: _change_num(d, "", 0), BETTER_UP),
        ("Sessions", "sessions", lambda v: _num(v), lambda d: _change_num(d, "", 0), BETTER_UP),
        ("Days trained", "days_trained", lambda v: _num(v),
         lambda d: _change_num(d, "", 0), BETTER_UP),
        ("Training load", "load", lambda v: _num(v), lambda d: _change_num(d, "", 0), BETTER_UP),
        ("Elevation", "elevation_gain_m", lambda v: _num(v, 0, " m"),
         lambda d: _change_num(d, " m", 0), BETTER_UP),
        ("Average pace", "avg_pace_sec_km", lambda v: _pace(v) + " /km",
         _change_pace, BETTER_DOWN),
        ("Average heart rate", "avg_hr", lambda v: _num(v, 0, " bpm"),
         lambda d: _change_num(d, " bpm", 0), NEUTRAL),
    ]
    for label, key, render, render_change, direction in spec:
        if totals.get(key) is None and previous.get(key) is None:
            continue
        delta = deltas.get(key)
        rows.append([label, render(totals.get(key)), render(previous.get(key)),
                     render_change(delta)])
        tones.append(_tone(delta, direction))

    table = Table(rows, colWidths=[52 * mm, 40 * mm, 40 * mm, 38 * mm])
    style = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9.5),
        ("FONT", (1, 1), (1, -1), "Helvetica-Bold", 9.5),
        ("TEXTCOLOR", (2, 1), (2, -1), MUTED),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.HexColor("#f3f4f6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for index, tone in enumerate(tones, start=1):
        style.append(("TEXTCOLOR", (3, index), (3, index), tone))
    table.setStyle(TableStyle(style))
    return [table]


def _chart(report: Dict[str, Any]) -> Optional[Drawing]:
    """Distance over the period. Empty buckets stay, because gaps are data."""
    rows = (report.get("breakdown") or {}).get("rows") or []
    values = [r.get("km") or 0.0 for r in rows]
    if not rows or not any(values):
        return None

    drawing = Drawing(170 * mm, 46 * mm)
    chart = VerticalBarChart()
    chart.x, chart.y = 14 * mm, 10 * mm
    chart.width, chart.height = 152 * mm, 32 * mm
    chart.data = [values]
    chart.bars[0].fillColor = ACCENT
    chart.bars[0].strokeColor = None
    chart.barSpacing = 1.5
    chart.groupSpacing = 3
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.15 or 1
    chart.valueAxis.valueStep = max(1, round((max(values) * 1.15) / 3))
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.fillColor = MUTED
    chart.valueAxis.strokeColor = LINE
    chart.categoryAxis.categoryNames = [r.get("label", "") for r in rows]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.fillColor = MUTED
    chart.categoryAxis.labels.dy = -2
    chart.categoryAxis.strokeColor = LINE
    # A month of daily bars cannot carry a label on every one of them.
    if len(rows) > 16:
        step = 5 if len(rows) > 20 else 2
        chart.categoryAxis.categoryNames = [
            name if index % step == 0 else "" for index, name in
            enumerate(chart.categoryAxis.categoryNames)
        ]
    drawing.add(chart)
    return drawing


def _sessions(report: Dict[str, Any], limit: int = 40) -> List[Any]:
    sessions = [s for s in (report.get("sessions") or []) if s.get("is_run")]
    if not sessions:
        return []
    rows = [["Date", "Session", "Distance", "Time", "Pace", "HR", "Load"]]
    for s in sessions[:limit]:
        when = datetime.fromisoformat(s["start_time"])
        name = (s.get("name") or "")[:30]
        rows.append([
            when.strftime("%a %d %b"), name,
            _num(s.get("km"), 2, " km"), _clock(s.get("moving_sec")),
            _pace(s.get("pace_sec_km")), _num(s.get("avg_hr")), _num(s.get("load")),
        ])

    table = Table(rows, colWidths=[24 * mm, 52 * mm, 22 * mm, 20 * mm, 20 * mm, 15 * mm, 17 * mm],
                  repeatRows=1)
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.HexColor("#f3f4f6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    out: List[Any] = [table]
    if len(sessions) > limit:
        out += [Spacer(1, 4), Paragraph(
            f"{len(sessions) - limit} further runs are not listed.", NOTE)]
    return out


def _records(report: Dict[str, Any]) -> List[Any]:
    records = report.get("records") or []
    if not records:
        return []
    rows = [["Distance", "Time", "Pace", ""]]
    for r in records:
        rows.append([
            r["label"], _clock(r.get("time_seconds")),
            _pace(r.get("pace_sec_km")) + " /km",
            "personal record" if r.get("is_personal_record") else "",
        ])
    table = Table(rows, colWidths=[30 * mm, 30 * mm, 30 * mm, 80 * mm])
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("FONT", (3, 1), (3, -1), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (3, 1), (3, -1), ACCENT),
        ("ALIGN", (1, 0), (2, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [table]


def _other_sports(report: Dict[str, Any]) -> List[Any]:
    other = report.get("other_sports") or {}
    if not other:
        return []
    rows = [["Sport", "Sessions", "Distance", "Time"]]
    for sport, v in sorted(other.items(), key=lambda kv: -kv[1]["count"]):
        rows.append([sport.capitalize(), str(v["count"]),
                     _num(v.get("km"), 1, " km") if v.get("km") else "--",
                     _hms(v.get("moving_sec"))])
    table = Table(rows, colWidths=[50 * mm, 30 * mm, 30 * mm, 60 * mm])
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [Paragraph("Everything else", H2), table,
            Spacer(1, 4),
            Paragraph("Counted separately. None of it is in the running figures above.", NOTE)]


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, doc.report_footer)
    canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render(report: Dict[str, Any], athlete: Optional[str] = None,
           note: Optional[str] = None, note_model: Optional[str] = None) -> bytes:
    """Build the PDF and hand back its bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=f"{report.get('label')} - training report",
        author="Performance",
    )
    generated = datetime.now().strftime("%d %B %Y")
    doc.report_footer = f"Performance - generated {generated}"

    totals = report.get("totals") or {}
    kind = report.get("kind", "period")
    story: List[Any] = [
        Paragraph(str(report.get("label")), H1),
        Paragraph(
            f"{kind.capitalize()} training report"
            + (f" for {athlete}" if athlete else "")
            + ("" if report.get("complete") else "  ·  this period has not finished yet"),
            SUB,
        ),
    ]

    if report.get("empty"):
        story.append(Paragraph("No activity was recorded in this period.", BODY))
        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        return buffer.getvalue()

    story += [_headline(totals), Spacer(1, 6)]

    chart = _chart(report)
    if chart is not None:
        unit = (report.get("breakdown") or {}).get("unit", "day")
        story += [Paragraph(f"Distance by {unit}", H2), chart]

    story += [Paragraph(f"Compared with the previous {kind}", H2)]
    story += _comparison(report)

    detail = [
        ("Longest run", _num(totals.get("longest_km"), 2, " km")),
        ("Quickest average pace", _pace(totals.get("fastest_pace_sec_km")) + " /km"
         if totals.get("fastest_pace_sec_km") else "--"),
        ("Grade-adjusted pace", _pace(totals.get("avg_gap_sec_km")) + " /km"
         if totals.get("avg_gap_sec_km") else "--"),
        ("Average cadence", _num(totals.get("avg_cadence"), 0, " spm")),
        ("Average stride", _num(totals.get("avg_stride_m"), 2, " m")),
        ("Aerobic decoupling", _num(totals.get("avg_decoupling_pct"), 1, "%")),
        ("Calories", _num(totals.get("calories"), 0, " kcal")),
        ("Fitness at the end", _num((report.get("form") or {}).get("ctl_end"), 0)),
    ]
    detail = [d for d in detail if d[1] != "--"]
    if detail:
        pairs = [[a[0], a[1], b[0] if b else "", b[1] if b else ""]
                 for a, b in zip(detail[::2], list(detail[1::2]) + [None])]
        table = Table(pairs, colWidths=[45 * mm, 40 * mm, 45 * mm, 40 * mm])
        table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("FONT", (1, 0), (1, -1), "Helvetica-Bold", 9),
            ("FONT", (3, 0), (3, -1), "Helvetica-Bold", 9),
            ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
            ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story += [Paragraph("The detail", H2), table]

    records = _records(report)
    if records:
        # Kept whole: a heading stranded at the foot of a page with one row of
        # its table overleaf is the classic way a generated PDF looks broken.
        story.append(KeepTogether([Paragraph("Best efforts", H2)] + records))

    if note:
        story += [Paragraph("Coach's note", H2), Paragraph(note, BODY), Spacer(1, 5),
                  Paragraph(
                      f"Written by {note_model or 'a language model'} running on this server, "
                      "from the figures in this report. It phrases them; it does not measure "
                      "anything.", NOTE)]

    other = _other_sports(report)
    if other:
        story.append(KeepTogether(other))

    sessions = _sessions(report)
    if sessions:
        story += [PageBreak(), Paragraph("Every run", H2)] + sessions

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
