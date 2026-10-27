"""
report_exporter.py
==================
CrowdSense — Event Safety & Stampede Prevention PDF Report Generator
Audience: Event Organisers
Purpose:  Produce an accurate, data-driven, actionable PDF that helps
          organisers plan safer events and prevent stampedes in the future.
"""

import csv
import io
import math
import os
import shutil
import tempfile
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib.units import mm, cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
        PageBreak,
        HRFlowable,
        KeepTogether,
    )
    from reportlab.lib.colors import HexColor, Color
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    # Fallback stubs so module-level constants don't raise NameError
    mm = 2.8346456692913385
    cm = 28.346456692913385
    A4 = (595.2755905511812, 841.8897637795277)

    class _FakeColors:
        white = None
        black = None
    colors = _FakeColors()

    def HexColor(h): return None
    def Color(*a, **kw): return None
    class ParagraphStyle: pass
    def getSampleStyleSheet(): return {}
    TA_CENTER = TA_LEFT = TA_RIGHT = TA_JUSTIFY = 0
    SimpleDocTemplate = Paragraph = Spacer = Table = TableStyle = None
    Image = PageBreak = HRFlowable = KeepTogether = None

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
C_SAFE      = HexColor("#27AE60") if REPORTLAB_AVAILABLE else None   # green
C_WARNING   = HexColor("#F39C12") if REPORTLAB_AVAILABLE else None   # amber
C_CRITICAL  = HexColor("#E74C3C") if REPORTLAB_AVAILABLE else None   # red
C_PRIMARY   = HexColor("#1A2B4A") if REPORTLAB_AVAILABLE else None   # deep navy
C_ACCENT    = HexColor("#2980B9") if REPORTLAB_AVAILABLE else None   # blue
C_LIGHT_BG  = HexColor("#F4F6F9") if REPORTLAB_AVAILABLE else None   # very light grey
C_MID_BG    = HexColor("#DDE3EC") if REPORTLAB_AVAILABLE else None   # light blue-grey
C_WHITE     = colors.white        if REPORTLAB_AVAILABLE else None
C_BLACK     = colors.black        if REPORTLAB_AVAILABLE else None

# Matplotlib hex strings
MPL_SAFE     = "#27AE60"
MPL_WARNING  = "#F39C12"
MPL_CRITICAL = "#E74C3C"
MPL_PRIMARY  = "#1A2B4A"
MPL_ACCENT   = "#2980B9"
MPL_BG       = "#F4F6F9"

PAGE_W, PAGE_H = A4 if REPORTLAB_AVAILABLE else (595, 842)
MARGIN = 20 * mm
INNER_W = PAGE_W - 2 * MARGIN

# Density thresholds (Fruin Level of Service)
DENSITY_WARNING   = 1.0   # p/m²  — crowded, restricted movement
DENSITY_STAMPEDE  = 3.0   # p/m²  — Fruin LoS F, stampede risk
OCCUPANCY_WARNING  = 0.70  # 70 %
OCCUPANCY_CRITICAL = 0.90  # 90 %


# ===========================================================================
# ReportExporter
# ===========================================================================

class ReportExporter:
    """Generates a comprehensive PDF safety report for event organisers."""

    def __init__(
        self,
        report_manager=None,
        graph_manager=None,
        output_folder="data/reports",
    ):
        self.report_manager   = report_manager
        self.graph_manager    = graph_manager
        self.output_folder    = output_folder
        os.makedirs(self.output_folder, exist_ok=True)

    # =========================================================================
    # PUBLIC HELPERS (kept for API compatibility)
    # =========================================================================

    def safe(self, value, default="—"):
        """Return value if truthy else default."""
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return value

    def get_value(self, d, *keys, default="—"):
        """Safely drill into nested dict."""
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k, None)
            if cur is None:
                return default
        return cur

    def get_report_rows(self):
        """Return a list of basic row dicts for the current report (legacy helper)."""
        if not self.report_manager:
            return []
        try:
            report = self.report_manager.generate_report()
            rows = []
            for alert in report.get("alerts", []):
                rows.append({
                    "type":      "alert",
                    "timestamp": alert.get("timestamp", ""),
                    "zone_id":   alert.get("zone_id", ""),
                    "severity":  alert.get("severity", ""),
                    "message":   alert.get("message", ""),
                })
            for incident in report.get("incidents", []):
                rows.append({
                    "type":        "incident",
                    "timestamp":   incident.get("timestamp", ""),
                    "zone_id":     incident.get("zone_id", ""),
                    "description": incident.get("description", ""),
                    "status":      incident.get("status", ""),
                })
            return rows
        except Exception:
            return []

    def get_analytics_data(self):
        """Return analytics dict from the report_manager (legacy helper)."""
        if not self.report_manager:
            return {}
        try:
            report = self.report_manager.generate_report()
            return report.get("analytics", {})
        except Exception:
            return {}

    # =========================================================================
    # STYLE HELPERS
    # =========================================================================

    def _build_styles(self):
        """Return a dict of ParagraphStyles."""
        base = getSampleStyleSheet()

        def ps(name, **kw):
            return ParagraphStyle(name, parent=base["Normal"], **kw)

        styles = {
            "cover_title": ParagraphStyle(
                "cover_title",
                fontSize=32, leading=38, textColor=C_WHITE,
                fontName="Helvetica-Bold", alignment=TA_CENTER,
                spaceAfter=8,
            ),
            "cover_subtitle": ParagraphStyle(
                "cover_subtitle",
                fontSize=14, leading=18, textColor=HexColor("#BDC3C7"),
                fontName="Helvetica", alignment=TA_CENTER, spaceAfter=4,
            ),
            "cover_meta": ParagraphStyle(
                "cover_meta",
                fontSize=11, leading=15, textColor=HexColor("#ECF0F1"),
                fontName="Helvetica", alignment=TA_CENTER,
            ),
            "section_head": ps(
                "section_head",
                fontSize=15, leading=20, fontName="Helvetica-Bold",
                textColor=C_PRIMARY, spaceBefore=14, spaceAfter=6,
                borderPad=4,
            ),
            "sub_head": ps(
                "sub_head",
                fontSize=11, leading=15, fontName="Helvetica-Bold",
                textColor=C_ACCENT, spaceBefore=8, spaceAfter=4,
            ),
            "body": ps(
                "body",
                fontSize=9.5, leading=14, fontName="Helvetica",
                textColor=C_BLACK, spaceAfter=4,
            ),
            "body_j": ps(
                "body_j",
                fontSize=9.5, leading=14, fontName="Helvetica",
                textColor=C_BLACK, spaceAfter=4, alignment=TA_JUSTIFY,
            ),
            "bullet": ps(
                "bullet",
                fontSize=9.5, leading=14, fontName="Helvetica",
                textColor=C_BLACK, spaceAfter=3,
                leftIndent=16, firstLineIndent=-10,
            ),
            "caption": ps(
                "caption",
                fontSize=8.5, leading=12, fontName="Helvetica-Oblique",
                textColor=HexColor("#7F8C8D"), alignment=TA_CENTER,
                spaceAfter=6,
            ),
            "table_header": ps(
                "table_header",
                fontSize=9, leading=12, fontName="Helvetica-Bold",
                textColor=C_WHITE,
            ),
            "table_cell": ps(
                "table_cell",
                fontSize=8.5, leading=12, fontName="Helvetica",
                textColor=C_BLACK,
            ),
            "table_cell_sm": ps(
                "table_cell_sm",
                fontSize=7.5, leading=11, fontName="Helvetica",
                textColor=C_BLACK,
            ),
            "label_key": ps(
                "label_key",
                fontSize=9.5, leading=13, fontName="Helvetica-Bold",
                textColor=C_PRIMARY,
            ),
            "label_val": ps(
                "label_val",
                fontSize=9.5, leading=13, fontName="Helvetica",
                textColor=C_BLACK,
            ),
            "callout_text": ps(
                "callout_text",
                fontSize=10, leading=14, fontName="Helvetica-Bold",
                textColor=C_WHITE, alignment=TA_CENTER,
            ),
            "note": ps(
                "note",
                fontSize=8.5, leading=12, fontName="Helvetica-Oblique",
                textColor=HexColor("#5D6D7E"),
            ),
        }
        return styles

    # =========================================================================
    # MAKE TABLE (legacy API)
    # =========================================================================

    def make_table(self, headers, rows, col_widths=None):
        """Create a plain ReportLab Table with standard styling."""
        S = self._build_styles()
        header_row = [Paragraph(str(h), S["table_header"]) for h in headers]
        data = [header_row]
        for row in rows:
            data.append([Paragraph(str(c), S["table_cell"]) for c in row])
        if col_widths is None:
            col_widths = [INNER_W / len(headers)] * len(headers)
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHT_BG]),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#C0C8D4")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
        tbl.setStyle(style)
        return tbl

    # =========================================================================
    # HEADER / FOOTER
    # =========================================================================

    def _header_footer(self, canvas, doc):
        """Draw page header and footer on every page after the cover page."""
        canvas.saveState()
        page_num  = doc.page
        page_total = getattr(doc, "_total_pages", "?")
        venue_name = getattr(doc, "_venue_name", "CrowdSense")

        if page_num > 1:
            # --- Header bar ---
            canvas.setFillColor(C_PRIMARY)
            canvas.rect(MARGIN, PAGE_H - 18 * mm, INNER_W, 10 * mm, fill=1, stroke=0)
            canvas.setFillColor(C_WHITE)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawString(MARGIN + 4, PAGE_H - 13 * mm,
                              f"CrowdSense Event Safety Report  |  {venue_name}")
            canvas.setFont("Helvetica", 8)
            canvas.drawRightString(PAGE_W - MARGIN - 4, PAGE_H - 13 * mm,
                                   "CONFIDENTIAL")

            # --- Footer bar ---
            canvas.setFillColor(C_MID_BG)
            canvas.rect(MARGIN, 10 * mm, INNER_W, 7 * mm, fill=1, stroke=0)
            canvas.setFillColor(C_PRIMARY)
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(MARGIN + 4, 13 * mm,
                              "Generated by CrowdSense  |  For internal event planning use only")
            canvas.setFont("Helvetica-Bold", 7.5)
            canvas.drawRightString(PAGE_W - MARGIN - 4, 13 * mm,
                                   f"Page {page_num} of {page_total}")

        canvas.restoreState()

    # =========================================================================
    # SECTION HELPERS
    # =========================================================================

    def _divider(self):
        return HRFlowable(width="100%", thickness=0.5,
                          color=C_MID_BG, spaceAfter=6, spaceBefore=2)

    def _section_title(self, text, S):
        return [
            Paragraph(text, S["section_head"]),
            self._divider(),
        ]

    def _kv_table(self, pairs, S, col_ratio=(0.38, 0.62)):
        """Two-column key-value table."""
        w0 = INNER_W * col_ratio[0]
        w1 = INNER_W * col_ratio[1]
        data = [
            [Paragraph(k, S["label_key"]), Paragraph(str(v), S["label_val"])]
            for k, v in pairs
        ]
        tbl = Table(data, colWidths=[w0, w1])
        tbl.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_WHITE, C_LIGHT_BG]),
            ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#D5DCE8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return tbl

    def _risk_color(self, risk_str):
        r = str(risk_str).upper()
        if r == "CRITICAL":
            return C_CRITICAL
        if r == "WARNING":
            return C_WARNING
        return C_SAFE

    def _format_duration(self, session):
        """Format session duration gracefully from duration, duration_seconds, or timestamps."""
        if not session or not isinstance(session, dict):
            return "Not recorded"
        dur = session.get("duration")
        if dur and str(dur).strip() and str(dur).strip() != "—":
            return str(dur).strip()
        secs = session.get("duration_seconds")
        if secs is not None:
            try:
                secs = int(float(secs))
                h = secs // 3600
                m = (secs % 3600) // 60
                s = secs % 60
                if h > 0:
                    return f"{h}h {m:02d}m {s:02d}s"
                elif m > 0:
                    return f"{m}m {s:02d}s"
                else:
                    return f"{s}s"
            except Exception:
                pass
        st_str = session.get("start_time")
        et_str = session.get("end_time")
        if st_str and et_str:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    st = datetime.strptime(str(st_str).strip(), fmt)
                    et = datetime.strptime(str(et_str).strip(), fmt)
                    diff = int((et - st).total_seconds())
                    if diff >= 0:
                        m = (diff % 3600) // 60
                        s = diff % 60
                        h = diff // 3600
                        return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"
                except Exception:
                    continue
        return "Not recorded"

    def _normalize_occupancy(self, value):
        """
        Normalize occupancy value to percentage (0.0 to 100.0+).
        If value is a fraction <= 1.0 (e.g. 0.85), returns 85.0.
        If value is already a percentage (e.g. 85.0 or 333.3), returns 85.0.
        """
        try:
            val = float(value)
            if 0 < val <= 1.0:
                return val * 100.0
            return val
        except Exception:
            return 0.0

    def _fmt_pct(self, value, decimals=1):
        try:
            val = self._normalize_occupancy(value)
            return f"{val:.{decimals}f}%"
        except Exception:
            return str(value)

    def _fmt_f(self, value, decimals=2, suffix=""):
        try:
            return f"{float(value):.{decimals}f}{suffix}"
        except Exception:
            return str(value)

    # =========================================================================
    # COVER PAGE
    # =========================================================================

    def add_cover_page(self, story, report, rating_label, rating_color_hex):
        """Single-table cover page — no negative spacers, no overlapping."""

        venue        = (report.get("venue") or {}) if isinstance(report, dict) else {}
        if not isinstance(venue, dict): venue = {}
        session      = (report.get("session") or {}) if isinstance(report, dict) else {}
        if not isinstance(session, dict): session = {}
        generated_at = report.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")) if isinstance(report, dict) else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        venue_name   = venue.get("name") or "Event Venue"
        session_id   = session.get("session_id") or "Not recorded"
        badge_color  = HexColor(rating_color_hex)

        # ── shared inline styles ──────────────────────────────────────────
        def _ps(name, **kw):
            return ParagraphStyle(name, **kw)

        st_app = _ps("cv_app", fontSize=10, fontName="Helvetica-Bold",
                     textColor=HexColor("#BDC3C7"), alignment=TA_CENTER,
                     leading=14)
        st_title = _ps("cv_title", fontSize=28, fontName="Helvetica-Bold",
                       textColor=C_WHITE, alignment=TA_CENTER,
                       leading=34, spaceAfter=0)
        st_venue = _ps("cv_venue", fontSize=13, fontName="Helvetica",
                       textColor=HexColor("#BDC3C7"), alignment=TA_CENTER,
                       leading=18)
        st_meta = _ps("cv_meta", fontSize=10, fontName="Helvetica",
                      textColor=HexColor("#ECF0F1"), alignment=TA_CENTER,
                      leading=15)
        st_badge = _ps("cv_badge", fontSize=14, fontName="Helvetica-Bold",
                       textColor=C_WHITE, alignment=TA_CENTER, leading=20)
        st_intro = _ps("cv_intro", fontSize=10, fontName="Helvetica",
                       textColor=HexColor("#2C3E50"), alignment=TA_JUSTIFY,
                       leading=15)
        st_conf = _ps("cv_conf", fontSize=9, fontName="Helvetica-Oblique",
                      textColor=HexColor("#7F8C8D"), alignment=TA_CENTER,
                      leading=13)

        # ── build every row of the cover as a nested sub-table ───────────
        # Row 0: dark-navy header block
        header_rows = [
            [Paragraph("CrowdSense", st_app)],
            [Spacer(1, 6)],
            [Paragraph("Event Safety &amp; Stampede Prevention Report", st_title)],
            [Spacer(1, 4)],
            [Paragraph(venue_name, st_venue)],
            [Spacer(1, 8)],
            [Paragraph(f"Session: {session_id}", st_meta)],
            [Paragraph(f"Generated: {generated_at}", st_meta)],
            [Spacer(1, 10)],
        ]
        header_tbl = Table(header_rows, colWidths=[INNER_W])
        header_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_PRIMARY),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ]))

        # Row 1: rating badge
        badge_rows = [
            [Paragraph(f"Overall Safety Rating: {rating_label}", st_badge)],
        ]
        badge_tbl = Table(badge_rows, colWidths=[INNER_W], rowHeights=[38])
        badge_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), badge_color),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ]))

        # Row 2: intro text block
        intro_rows = [
            [Spacer(1, 10)],
            [Paragraph(
                "This report is intended for event organisers and safety teams. "
                "It provides a data-driven analysis of crowd density, occupancy, "
                "risk events, and alerts recorded during the monitoring session. "
                "Use the findings and recommendations herein to improve crowd "
                "management and prevent stampede incidents at future events.",
                st_intro,
            )],
            [Spacer(1, 8)],
            [Paragraph(
                "<b>CONFIDENTIAL — For internal event planning use only.</b>",
                st_conf,
            )],
            [Spacer(1, 8)],
        ]
        intro_tbl = Table(intro_rows, colWidths=[INNER_W])
        intro_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_WHITE),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Outer wrapper — all three blocks stacked cleanly
        outer = Table(
            [[header_tbl], [badge_tbl], [intro_tbl]],
            colWidths=[INNER_W],
        )
        outer.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        story.append(outer)
        story.append(PageBreak())

    # =========================================================================
    # EXECUTIVE SUMMARY
    # =========================================================================

    def add_executive_summary(self, story, report, rating_label, rating_color_hex,
                               stampede_risk_label, stampede_risk_hex):
        S = self._build_styles()
        story += self._section_title("1. Executive Summary", S)

        analytics = report.get("analytics", {})
        people    = analytics.get("people", {})
        occupancy = analytics.get("occupancy", {})
        density   = analytics.get("density", {})
        risk      = analytics.get("risk", {})
        alerts_a  = analytics.get("alerts", {})
        venue     = (report.get("venue") or {}) if isinstance(report, dict) else {}
        if not isinstance(venue, dict): venue = {}
        session   = (report.get("session") or {}) if isinstance(report, dict) else {}
        if not isinstance(session, dict): session = {}

        peak_people  = people.get("peak_people", 0)
        peak_occ     = self._normalize_occupancy(occupancy.get("peak_occupancy") or occupancy.get("maximum_occupancy") or 0)
        avg_density  = float(density.get("average_density", 0))
        max_density  = float(density.get("peak_density") or density.get("maximum_density") or 0)
        total_alerts = alerts_a.get("total", 0)
        crit_alerts  = alerts_a.get("critical", 0)
        safe_r       = risk.get("safe_records", 0)
        warn_r       = risk.get("warning_records", 0)
        crit_r       = risk.get("critical_records", 0)
        total_r      = max(safe_r + warn_r + crit_r, 1)
        capacity     = venue.get("capacity", 0)
        duration     = self._format_duration(session)

        pct_crit     = crit_r / total_r * 100
        pct_warn     = warn_r / total_r * 100

        summary_text = (
            f"During this monitoring session (duration: <b>{duration}</b>), "
            f"CrowdSense tracked crowd conditions across all configured zones. "
            f"Peak attendance reached <b>{peak_people:,} people</b> against a venue "
            f"capacity of <b>{capacity:,}</b>, representing a maximum occupancy of "
            f"<b>{self._fmt_pct(peak_occ)}</b>. "
            f"The average crowd density was <b>{self._fmt_f(avg_density)} p/m²</b> "
            f"with a peak of <b>{self._fmt_f(max_density)} p/m²</b>. "
            f"A total of <b>{total_alerts} alerts</b> were triggered "
            f"({crit_alerts} critical). "
            f"Across all recorded samples, <b>{pct_crit:.1f}% were in a CRITICAL state</b> "
            f"and {pct_warn:.1f}% in a WARNING state. "
            f"Based on this data, the overall session safety rating is assessed as "
            f"<b>{rating_label}</b> and the stampede risk score is "
            f"<b>{stampede_risk_label}</b>."
        )
        story.append(Paragraph(summary_text, S["body_j"]))
        story.append(Spacer(1, 8))

        # KPI row
        kpi_items = [
            ("Peak Attendance",    f"{peak_people:,} people"),
            ("Venue Capacity",     f"{capacity:,} people"),
            ("Peak Occupancy",     self._fmt_pct(peak_occ)),
            ("Peak Density",       f"{self._fmt_f(max_density)} p/m²"),
            ("Total Alerts",       str(total_alerts)),
            ("Critical Alerts",    str(crit_alerts)),
            ("Safety Rating",      rating_label),
            ("Stampede Risk",      stampede_risk_label),
        ]
        kpi_data = [[
            Paragraph(k, ParagraphStyle("kpi_k", fontSize=8,
                                         fontName="Helvetica-Bold",
                                         textColor=C_PRIMARY, alignment=TA_CENTER)),
            Paragraph(str(v), ParagraphStyle("kpi_v", fontSize=10,
                                              fontName="Helvetica-Bold",
                                              textColor=C_ACCENT, alignment=TA_CENTER)),
        ] for k, v in kpi_items]

        # 4-column layout
        rows_4 = []
        for i in range(0, len(kpi_data), 4):
            chunk = kpi_data[i:i+4]
            while len(chunk) < 4:
                chunk.append([Paragraph("", S["body"]), Paragraph("", S["body"])])
            flat_k = [chunk[j][0] for j in range(4)]
            flat_v = [chunk[j][1] for j in range(4)]
            rows_4.append(flat_k)
            rows_4.append(flat_v)

        col_w = INNER_W / 4
        kpi_tbl = Table(rows_4, colWidths=[col_w] * 4)
        kpi_style = [
            ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, C_MID_BG),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, C_MID_BG),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        for row_idx in range(0, len(rows_4), 2):
            kpi_style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), C_MID_BG))
        kpi_tbl.setStyle(TableStyle(kpi_style))
        story.append(kpi_tbl)
        story.append(Spacer(1, 6))

    # =========================================================================
    # SESSION SECTION
    # =========================================================================

    def add_session_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("2. Session Overview", S)
        session = (report.get("session") or {}) if isinstance(report, dict) else {}
        if not isinstance(session, dict): session = {}

        pairs = [
            ("Session ID",       self.safe(session.get("session_id"), "Not recorded")),
            ("Start Time",       self.safe(session.get("start_time"), "Not recorded")),
            ("End Time",         self.safe(session.get("end_time"), "Not recorded")),
            ("Duration",         self._format_duration(session)),
            ("Status",           self.safe(session.get("status"), "Unknown").capitalize()),
            ("Log Records",      str(session.get("report_log_records", 0))),
            ("Alerts Logged",    str(session.get("report_alerts", 0))),
            ("Incidents Logged", str(session.get("report_incidents", 0))),
        ]
        story.append(self._kv_table(pairs, S))
        story.append(Spacer(1, 8))

    # =========================================================================
    # VENUE SECTION
    # =========================================================================

    def add_venue_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("3. Venue Configuration", S)
        venue = (report.get("venue") or {}) if isinstance(report, dict) else {}
        if not isinstance(venue, dict): venue = {}

        shape    = venue.get("shape", "rectangle")
        capacity = int(venue.get("capacity", 0) or 0)
        length   = float(venue.get("length", 0) or 0)
        width    = float(venue.get("width", 0) or 0)
        diameter = float(venue.get("diameter", 0) or 0)

        warn_pct = float(venue.get("warning_threshold", 70) or 70)
        crit_pct = float(venue.get("critical_threshold", 90) or 90)
        warn_cap = int(capacity * (warn_pct / 100.0))
        crit_cap = int(capacity * (crit_pct / 100.0))

        zone_thresholds = venue.get("zone_thresholds", {})
        if not isinstance(zone_thresholds, dict): zone_thresholds = {}
        custom_count = len(zone_thresholds)

        if shape == "circle" and diameter > 0:
            floor_area = math.pi * (diameter / 2) ** 2
            dims_str = f"Diameter: {diameter:.1f} m"
        elif length > 0 and width > 0:
            floor_area = length * width
            dims_str = f"Length: {length:.1f} m x Width: {width:.1f} m"
        else:
            floor_area = 0
            dims_str = "Not configured"

        density_at_capacity = (capacity / floor_area) if floor_area > 0 else 0

        pairs = [
            ("Venue Name",                    venue.get("name") or "Not set"),
            ("Shape",                         shape.capitalize()),
            ("Dimensions",                    dims_str),
            ("Floor Area",                    f"{floor_area:.1f} m2" if floor_area else "Not configured"),
            ("Total Capacity",                f"{capacity:,} people" if capacity else "Not set"),
            (f"Warning Threshold ({warn_pct:.0f}%)",       f"{warn_cap:,} people" if capacity else f"{warn_pct:.0f}%"),
            (f"Critical Threshold ({crit_pct:.0f}%)",      f"{crit_cap:,} people" if capacity else f"{crit_pct:.0f}%"),
            ("Custom Zone Thresholds",        f"{custom_count} zone(s) customized" if custom_count > 0 else "None (venue defaults)"),
            ("Density at Capacity",           f"{density_at_capacity:.2f} p/m2" if density_at_capacity else "Unable to calculate"),
        ]
        story.append(self._kv_table(pairs, S))

        if density_at_capacity > 0:
            within_or_above = "<b>within</b>" if density_at_capacity < DENSITY_STAMPEDE else "<b>above</b>"
            note = (
                f"<b>Note:</b> A density of <b>{density_at_capacity:.2f} p/m\xb2</b> at full "
                f"capacity is {within_or_above} "
                f"the Fruin Level of Service F threshold of {DENSITY_STAMPEDE:.1f} p/m\xb2. "
                f"Maintaining a maximum density below {DENSITY_WARNING:.1f} p/m\xb2 is recommended "
                f"for comfortable crowd flow."
            )
            story.append(Spacer(1, 6))
            story.append(Paragraph(note, S["note"]))
        story.append(Spacer(1, 8))

    # =========================================================================
    # CROWD STATISTICS
    # =========================================================================

    def add_people_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("4. Crowd Statistics", S)
        p = report.get("analytics", {}).get("people", {})

        pairs = [
            ("Peak Attendance",     f"{int(p.get('peak_people', 0)):,} people"),
            ("Minimum Attendance",  f"{int(p.get('minimum_people', 0)):,} people"),
            ("Average Attendance",  f"{float(p.get('average_people', 0)):,.1f} people"),
            ("Total Data Samples",  str(p.get("total_records", 0))),
        ]
        story.append(self._kv_table(pairs, S))
        story.append(Spacer(1, 8))

    # =========================================================================
    # OCCUPANCY SECTION
    # =========================================================================

    def add_occupancy_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("5. Occupancy Analysis", S)
        occ  = report.get("analytics", {}).get("occupancy", {})
        risk = report.get("analytics", {}).get("risk", {})

        max_occ  = self._normalize_occupancy(occ.get("peak_occupancy") or occ.get("maximum_occupancy") or 0)
        min_occ  = self._normalize_occupancy(occ.get("minimum_occupancy", 0))
        avg_occ  = self._normalize_occupancy(occ.get("average_occupancy", 0))
        safe_r   = int(risk.get("safe_records", 0))
        warn_r   = int(risk.get("warning_records", 0))
        crit_r   = int(risk.get("critical_records", 0))
        total_r  = max(safe_r + warn_r + crit_r, 1)

        pct_warn = (warn_r + crit_r) / total_r * 100
        pct_crit = crit_r / total_r * 100

        pairs = [
            ("Peak Occupancy",                    self._fmt_pct(max_occ)),
            ("Minimum Occupancy",                 self._fmt_pct(min_occ)),
            ("Average Occupancy",                 self._fmt_pct(avg_occ)),
            ("Time above Warning (70%)",          f"{pct_warn:.1f}% of samples"),
            ("Time in Critical Zone (90%+)",      f"{pct_crit:.1f}% of samples"),
            ("Warning Threshold",                 f"{OCCUPANCY_WARNING*100:.0f}% occupancy"),
            ("Critical Threshold",                f"{OCCUPANCY_CRITICAL*100:.0f}% occupancy"),
        ]
        story.append(self._kv_table(pairs, S))

        if max_occ > (OCCUPANCY_CRITICAL * 100):
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"Peak occupancy of {self._fmt_pct(max_occ)} exceeded the critical "
                f"threshold ({OCCUPANCY_CRITICAL*100:.0f}%). Immediate action was required to prevent dangerous overcrowding.",
                ParagraphStyle("warn_note", fontSize=9, fontName="Helvetica-BoldOblique",
                               textColor=C_CRITICAL, spaceAfter=4)
            ))
        story.append(Spacer(1, 8))

    # =========================================================================
    # DENSITY SECTION
    # =========================================================================

    def add_density_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("6. Crowd Density Analysis", S)
        density = report.get("analytics", {}).get("density", {})
        risk    = report.get("analytics", {}).get("risk", {})

        max_d   = float(density.get("peak_density") or density.get("maximum_density") or 0)
        min_d   = float(density.get("minimum_density", 0))
        avg_d   = float(density.get("average_density", 0))
        warn_r  = int(risk.get("warning_records", 0))
        crit_r  = int(risk.get("critical_records", 0))
        total_r = max(int(risk.get("safe_records", 0)) + warn_r + crit_r, 1)

        pct_above_1 = (warn_r + crit_r) / total_r * 100
        pct_above_3 = crit_r / total_r * 100

        pairs = [
            ("Peak Density",               f"{max_d:.3f} p/m\xb2"),
            ("Minimum Density",            f"{min_d:.3f} p/m\xb2"),
            ("Average Density",            f"{avg_d:.3f} p/m\xb2"),
            ("Time above 1.0 p/m\xb2",     f"{pct_above_1:.1f}% of samples"),
            ("Time above 3.0 p/m\xb2 (LoS F)", f"{pct_above_3:.1f}% of samples"),
            ("Fruin LoS F Threshold",      "3.0 p/m\xb2 — stampede risk zone"),
        ]
        story.append(self._kv_table(pairs, S))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "The <b>Fruin Level of Service (LoS) F</b> threshold of <b>3.0 p/m\xb2</b> "
            "represents the density at which crowd movement becomes impossible, "
            "physical contact is unavoidable, and stampede conditions can develop. "
            "Keeping density below 1.0 p/m\xb2 ensures comfortable flow and evacuation capability.",
            S["note"]
        ))
        story.append(Spacer(1, 8))

    # =========================================================================
    # RISK BREAKDOWN
    # =========================================================================

    def add_risk_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("7. Risk Distribution", S)
        risk    = report.get("analytics", {}).get("risk", {})

        safe_r  = int(risk.get("safe_records", 0))
        warn_r  = int(risk.get("warning_records", 0))
        crit_r  = int(risk.get("critical_records", 0))
        total_r = max(safe_r + warn_r + crit_r, 1)

        headers = ["Risk Level", "Sample Count", "Percentage", "Implication"]
        rows = [
            ["SAFE",     f"{safe_r:,}",  f"{safe_r/total_r*100:.1f}%",  "Crowd within safe limits"],
            ["WARNING",  f"{warn_r:,}",  f"{warn_r/total_r*100:.1f}%",  "Elevated density — monitor closely"],
            ["CRITICAL", f"{crit_r:,}",  f"{crit_r/total_r*100:.1f}%",  "Dangerous — intervention required"],
            ["TOTAL",    f"{total_r:,}", "100%",                          "All recorded samples"],
        ]
        col_widths = [INNER_W * x for x in [0.16, 0.18, 0.16, 0.50]]
        header_row = [Paragraph(str(h), S["table_header"]) for h in headers]
        data = [header_row]
        for row in rows:
            data.append([Paragraph(str(c), S["table_cell"]) for c in row])
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        ts = [
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#C0C8D4")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 1), (-1, 1), HexColor("#D5F5E3")),   # safe green
            ("BACKGROUND", (0, 2), (-1, 2), HexColor("#FDEBD0")),   # warning amber
            ("BACKGROUND", (0, 3), (-1, 3), HexColor("#FADBD8")),   # critical red
            ("BACKGROUND", (0, 4), (-1, 4), C_LIGHT_BG),            # total
            ("FONTNAME",   (0, 4), (-1, 4), "Helvetica-Bold"),
        ]
        tbl.setStyle(TableStyle(ts))
        story.append(tbl)
        story.append(Spacer(1, 8))

    # =========================================================================
    # ALERTS LOG
    # =========================================================================

    def add_alert_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("8. Alerts Log", S)
        alerts    = report.get("alerts", [])
        analytics = report.get("analytics", {}).get("alerts", {})

        story.append(Paragraph(
            f"Total alerts generated: <b>{analytics.get('total', len(alerts))}</b>  |  "
            f"Warning: <b>{analytics.get('warning', 0)}</b>  |  "
            f"Critical: <b>{analytics.get('critical', 0)}</b>",
            S["body"]
        ))
        story.append(Spacer(1, 4))

        if not alerts:
            story.append(Paragraph("No alerts were recorded during this session.", S["body"]))
            story.append(Spacer(1, 8))
            return

        headers = ["Alert ID", "Time", "Zone", "Severity", "People", "Occ%", "Density", "Message"]
        col_widths = [INNER_W * x for x in [0.10, 0.12, 0.07, 0.09, 0.07, 0.07, 0.08, 0.40]]
        header_row = [Paragraph(h, S["table_header"]) for h in headers]
        data = [header_row]

        for a in alerts:
            sev = str(a.get("severity", "")).upper()
            occ_raw = a.get("occupancy", 0)
            occ_str = self._fmt_pct(occ_raw)
            data.append([
                Paragraph(str(a.get("alert_id", ""))[:12], S["table_cell_sm"]),
                Paragraph(str(a.get("timestamp", ""))[:19], S["table_cell_sm"]),
                Paragraph(str(a.get("zone_id", "")), S["table_cell_sm"]),
                Paragraph(sev, S["table_cell_sm"]),
                Paragraph(str(a.get("people", "")), S["table_cell_sm"]),
                Paragraph(occ_str, S["table_cell_sm"]),
                Paragraph(self._fmt_f(a.get("density", ""), 2), S["table_cell_sm"]),
                Paragraph(str(a.get("message", ""))[:120], S["table_cell_sm"]),
            ])

        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        ts = [
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#C0C8D4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        for i, a in enumerate(alerts, start=1):
            sev = str(a.get("severity", "")).upper()
            if sev == "CRITICAL":
                ts.append(("BACKGROUND", (3, i), (3, i), HexColor("#FADBD8")))
            elif sev == "WARNING":
                ts.append(("BACKGROUND", (3, i), (3, i), HexColor("#FDEBD0")))
        tbl.setStyle(TableStyle(ts))
        story.append(tbl)
        story.append(Spacer(1, 8))

    # =========================================================================
    # INCIDENTS LOG
    # =========================================================================

    def add_incident_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("9. Incidents Log", S)
        incidents  = report.get("incidents", [])
        inc_stats  = report.get("analytics", {}).get("incidents", {})

        story.append(Paragraph(
            f"Total incidents recorded: <b>{inc_stats.get('total', len(incidents))}</b>",
            S["body"]
        ))
        story.append(Spacer(1, 4))

        if not incidents:
            story.append(Paragraph("No incidents were recorded during this session.", S["body"]))
            story.append(Spacer(1, 8))
            return

        headers = ["Incident ID", "Timestamp", "Zone", "Description", "Status"]
        col_widths = [INNER_W * x for x in [0.14, 0.14, 0.08, 0.46, 0.18]]
        header_row = [Paragraph(h, S["table_header"]) for h in headers]
        data = [header_row]
        for idx, inc in enumerate(incidents):
            status = str(inc.get("status", "")).upper()
            data.append([
                Paragraph(str(inc.get("incident_id", ""))[:16], S["table_cell_sm"]),
                Paragraph(str(inc.get("timestamp", ""))[:19], S["table_cell_sm"]),
                Paragraph(str(inc.get("zone_id", "")), S["table_cell_sm"]),
                Paragraph(str(inc.get("description", ""))[:200], S["table_cell_sm"]),
                Paragraph(status, S["table_cell_sm"]),
            ])

        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        ts = [
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHT_BG]),
            ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#C0C8D4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
        tbl.setStyle(TableStyle(ts))
        story.append(tbl)
        story.append(Spacer(1, 8))

    # =========================================================================
    # MOST CROWDED ZONE
    # =========================================================================

    def add_most_crowded_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("10. Most Crowded Zone", S)
        mcz = report.get("analytics", {}).get("most_crowded_zone", {})

        if not mcz:
            story.append(Paragraph(
                "No zone data was recorded during this session. "
                "Ensure cameras are configured and a session is active before generating a report.",
                S["body"]
            ))
            story.append(Spacer(1, 8))
            return

        # analytics_manager uses 'zone_id', 'peak_people', 'peak_density'
        # with 'people' and 'density' as latest-frame compatibility fields
        zone_id     = mcz.get("zone_id") or mcz.get("id") or "Unknown"
        peak_people = int(mcz.get("peak_people") or mcz.get("people") or 0)
        peak_density= float(mcz.get("peak_density") or mcz.get("density") or 0)
        avg_people  = float(mcz.get("average_people") or 0)
        risk        = str(mcz.get("risk", "SAFE")).upper()
        rc          = self._risk_color(risk)

        pairs = [
            ("Zone ID",          zone_id),
            ("Peak People",      f"{peak_people:,} people"),
            ("Average People",   f"{avg_people:.1f} people"),
            ("Peak Density",     f"{peak_density:.3f} p/m\xb2"),
            ("Risk Level",       risk),
        ]
        story.append(self._kv_table(pairs, S))

        # Highlight callout
        hl_data = [[Paragraph(
            f"Zone <b>{zone_id}</b> was the most densely crowded zone during this session "
            f"with a peak of {peak_people:,} people at a peak density of {peak_density:.3f} p/m\xb2. "
            f"This zone should receive priority attention in future event planning.",
            ParagraphStyle("hl", fontSize=9.5, fontName="Helvetica",
                           textColor=C_WHITE, leading=14)
        )]]
        hl_tbl = Table(hl_data, colWidths=[INNER_W])
        hl_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), rc),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(Spacer(1, 4))
        story.append(hl_tbl)
        story.append(Spacer(1, 8))

    # =========================================================================
    # ZONE STATISTICS
    # =========================================================================

    def add_zone_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("11. Zone-by-Zone Analysis", S)
        analytics = (report.get("analytics") or {}) if isinstance(report, dict) else {}
        if not isinstance(analytics, dict): analytics = {}
        zones = analytics.get("zones", {})
        venue = (report.get("venue") or {}) if isinstance(report, dict) else {}
        if not isinstance(venue, dict): venue = {}

        if not zones:
            story.append(Paragraph("No zone data available.", S["body"]))
            story.append(Spacer(1, 8))
            return

        def_warn = float(venue.get("warning_threshold", 70) or 70)
        def_crit = float(venue.get("critical_threshold", 90) or 90)
        venue_zt = venue.get("zone_thresholds", {})
        if not isinstance(venue_zt, dict): venue_zt = {}

        headers = ["Zone ID", "Peak People", "Peak Density (p/m\xb2)", "Thresholds (Warn/Crit)", "Risk Level", "Status"]
        col_widths = [INNER_W * x for x in [0.15, 0.15, 0.18, 0.22, 0.15, 0.15]]
        header_row = [Paragraph(h, S["table_header"]) for h in headers]
        data = [header_row]
        row_colors = []
        has_any_custom = False

        for zid, zdata in sorted(zones.items()):
            risk        = str(zdata.get("risk", "SAFE")).upper()
            peak_people = int(zdata.get("peak_people") or zdata.get("people") or 0)
            peak_density= float(zdata.get("peak_density") or zdata.get("density") or 0)

            zw = zdata.get("warning_threshold")
            zc = zdata.get("critical_threshold")
            is_cust = bool(zdata.get("has_custom_threshold"))
            if zw is None or zc is None:
                zt = venue_zt.get(str(zid))
                if zt:
                    zw = zt.get("warning_threshold", def_warn)
                    zc = zt.get("critical_threshold", def_crit)
                    is_cust = True
                else:
                    zw = def_warn
                    zc = def_crit

            if is_cust:
                has_any_custom = True
                th_text = f"<b>{float(zw):.0f}% / {float(zc):.0f}%*</b>"
            else:
                th_text = f"{float(zw):.0f}% / {float(zc):.0f}%"

            if risk == "CRITICAL":
                status = "Intervention required"
                bg     = HexColor("#FADBD8")
            elif risk == "WARNING":
                status = "Monitor closely"
                bg     = HexColor("#FDEBD0")
            else:
                status = "Within safe limits"
                bg     = HexColor("#D5F5E3")
            row_colors.append(bg)
            data.append([
                Paragraph(str(zid), S["table_cell"]),
                Paragraph(f"{peak_people:,}", S["table_cell"]),
                Paragraph(f"{peak_density:.3f}", S["table_cell"]),
                Paragraph(th_text, S["table_cell"]),
                Paragraph(risk, S["table_cell"]),
                Paragraph(status, S["table_cell"]),
            ])

        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        ts = [
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#C0C8D4")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
        for i, bg in enumerate(row_colors, start=1):
            ts.append(("BACKGROUND", (0, i), (-1, i), bg))
        tbl.setStyle(TableStyle(ts))
        story.append(tbl)
        if has_any_custom or len(venue_zt) > 0:
            story.append(Spacer(1, 4))
            story.append(Paragraph("<i>* Indicates custom zone thresholds configured via Zone Settings.</i>", S["caption"]))
        story.append(Spacer(1, 8))

    # =========================================================================
    # STAMPEDE RISK ASSESSMENT
    # =========================================================================

    def add_stampede_risk_section(self, story, report, stampede_risk_label, stampede_risk_hex):
        S = self._build_styles()
        story += self._section_title("12. Stampede Risk Assessment", S)

        risk      = report.get("analytics", {}).get("risk", {})
        density   = report.get("analytics", {}).get("density", {})
        analytics = report.get("analytics", {})
        mcz       = analytics.get("most_crowded_zone", {})

        safe_r  = int(risk.get("safe_records", 0))
        warn_r  = int(risk.get("warning_records", 0))
        crit_r  = int(risk.get("critical_records", 0))
        total_r = max(safe_r + warn_r + crit_r, 1)

        max_d   = float(density.get("peak_density") or density.get("maximum_density") or 0)
        avg_d   = float(density.get("average_density", 0))
        pct_los_f = crit_r / total_r * 100
        pct_crowded = (warn_r + crit_r) / total_r * 100

        # Callout badge
        badge_data = [[Paragraph(
            f"Stampede Risk Score: <b>{stampede_risk_label}</b>",
            ParagraphStyle("sr_badge", fontSize=14, fontName="Helvetica-Bold",
                           textColor=C_WHITE, alignment=TA_CENTER)
        )]]
        badge_tbl = Table(badge_data, colWidths=[INNER_W], rowHeights=[30])
        badge_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor(stampede_risk_hex)),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(badge_tbl)
        story.append(Spacer(1, 8))

        # Narrative
        narrative_map = {
            "LOW":     (
                "Crowd conditions during this session remained predominantly within safe parameters. "
                "Density levels were generally below the Fruin LoS F threshold of 3.0 p/m². "
                "While continued vigilance is required, the risk of stampede-type incidents "
                "during this session was low."
            ),
            "MEDIUM":  (
                "Crowd conditions reached elevated density levels on multiple occasions. "
                "The proportion of time spent in WARNING or CRITICAL states is significant. "
                "Without active crowd management intervention, these conditions could escalate "
                "to dangerous levels at future events of similar scale."
            ),
            "HIGH":    (
                "Crowd conditions frequently exceeded safe density thresholds during this session. "
                "Significant time was recorded at or near Fruin Level of Service F (3.0 p/m²). "
                "These conditions represent a serious stampede risk. Immediate structural and "
                "operational changes to crowd management are strongly recommended."
            ),
            "EXTREME": (
                "CRITICAL: Crowd conditions during this session reached extreme density levels "
                "that are directly associated with historical stampede events. The Fruin LoS F "
                "threshold was exceeded for a substantial period. This venue/event configuration "
                "poses an unacceptable risk of crowd crush or stampede. Major operational changes "
                "must be implemented before hosting future events of this scale."
            ),
        }
        narrative = narrative_map.get(stampede_risk_label, narrative_map["MEDIUM"])
        story.append(Paragraph(narrative, S["body_j"]))
        story.append(Spacer(1, 6))

        # Risk factors table
        story.append(Paragraph("Key Risk Factors Identified:", S["sub_head"]))
        factors = [
            ["Risk Factor", "Observed Value", "Safe Threshold", "Status"],
        ]
        def _status_cell(val, threshold, lower_is_worse=True):
            if lower_is_worse:
                bad = val > threshold
            else:
                bad = val < threshold
            return "[!] EXCEEDS SAFE LIMIT" if bad else "[OK] Within limit"

        factors += [
            [
                "Maximum Density",
                f"{max_d:.3f} p/m\xb2",
                f"< {DENSITY_STAMPEDE:.1f} p/m\xb2 (Fruin LoS F)",
                _status_cell(max_d, DENSITY_STAMPEDE),
            ],
            [
                "Average Density",
                f"{avg_d:.3f} p/m\xb2",
                f"< {DENSITY_WARNING:.1f} p/m\xb2",
                _status_cell(avg_d, DENSITY_WARNING),
            ],
            [
                "Time at Critical Density",
                f"{pct_los_f:.1f}% of session",
                "< 5% of session",
                _status_cell(pct_los_f, 5),
            ],
            [
                "Time in Crowded State",
                f"{pct_crowded:.1f}% of session",
                "< 20% of session",
                _status_cell(pct_crowded, 20),
            ],
            [
                "Most Crowded Zone",
                str(mcz.get("zone_id") or mcz.get("id") or "No data"),
                "All zones SAFE",
                "Review this zone" if str(mcz.get("risk","")).upper() != "SAFE" else "OK",
            ],
        ]
        col_widths = [INNER_W * x for x in [0.30, 0.22, 0.28, 0.20]]
        data = []
        for i, row in enumerate(factors):
            if i == 0:
                data.append([Paragraph(c, S["table_header"]) for c in row])
            else:
                data.append([Paragraph(str(c), S["table_cell"]) for c in row])

        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        ts = [
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHT_BG]),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#C0C8D4")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
        # Colour status column
        for i, row in enumerate(factors[1:], start=1):
            status_str = str(row[-1])
            if "EXCEEDS" in status_str:
                ts.append(("BACKGROUND", (3, i), (3, i), HexColor("#FADBD8")))
                ts.append(("TEXTCOLOR", (3, i), (3, i), C_CRITICAL))
                ts.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
            elif "Review" in status_str:
                ts.append(("BACKGROUND", (3, i), (3, i), HexColor("#FDEBD0")))
                ts.append(("TEXTCOLOR", (3, i), (3, i), C_WARNING))
        tbl.setStyle(TableStyle(ts))
        story.append(tbl)
        story.append(Spacer(1, 8))

    # =========================================================================
    # RECOMMENDATIONS
    # =========================================================================

    def add_recommendations_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("13. Event Planning Recommendations", S)

        analytics = report.get("analytics", {})
        people    = analytics.get("people", {})
        occupancy = analytics.get("occupancy", {})
        density   = analytics.get("density", {})
        risk      = analytics.get("risk", {})
        mcz       = analytics.get("most_crowded_zone", {})
        venue     = report.get("venue", {})

        peak_occ  = self._normalize_occupancy(occupancy.get("peak_occupancy") or occupancy.get("maximum_occupancy") or 0)
        avg_occ   = self._normalize_occupancy(occupancy.get("average_occupancy", 0))
        max_d     = float(density.get("peak_density") or density.get("maximum_density") or 0)
        avg_d     = float(density.get("average_density", 0))
        safe_r    = int(risk.get("safe_records", 0))
        warn_r    = int(risk.get("warning_records", 0))
        crit_r    = int(risk.get("critical_records", 0))
        total_r   = max(safe_r + warn_r + crit_r, 1)
        capacity  = int(venue.get("capacity", 0))
        mcz_id    = mcz.get("zone_id") or mcz.get("id") or "the most crowded zone"

        pct_crit  = crit_r / total_r
        pct_warn  = (warn_r + crit_r) / total_r

        story.append(Paragraph(
            "The following recommendations are automatically generated from the data "
            "collected during this monitoring session. Each recommendation is tied to a "
            "specific observed metric. Implementing these measures will reduce the risk of "
            "crowd-related incidents at future events.",
            S["body_j"]
        ))
        story.append(Spacer(1, 8))

        # --- Data-Driven Recommendations ---
        story.append(Paragraph("Data-Driven Recommendations", S["sub_head"]))

        recs = []

        if peak_occ > 85.0:
            reduced_cap = int(capacity * 0.85) if capacity > 0 else 0
            recs.append((
                "Reduce Advertised Capacity",
                f"Peak occupancy reached {self._fmt_pct(peak_occ)}, exceeding the 85% "
                f"planning threshold. Reduce the maximum ticket/admission count to "
                f"{reduced_cap:,} people (85% of stated capacity) to maintain a buffer "
                f"for emergency egress.",
                C_CRITICAL,
            ))

        if crit_r > 0:
            recs.append((
                f"Deploy Additional Stewards at Zone {mcz_id}",
                f"Critical-density events were recorded {crit_r:,} times ({pct_crit*100:.1f}% "
                f"of samples). Zone '{mcz_id}' was the most affected area. Deploy trained "
                f"crowd management stewards at this zone with authority to implement one-way "
                f"flow and temporary entry holds.",
                C_CRITICAL,
            ))

        if max_d > DENSITY_STAMPEDE:
            recs.append((
                "Install Physical Crowd Flow Barriers",
                f"Density exceeded {DENSITY_STAMPEDE:.1f} p/m² (Fruin Level of Service F). "
                f"Install physical barriers (crowd pens, chicane entry systems, or queue "
                f"management fencing) to limit the rate of crowd accumulation in high-risk zones. "
                f"Barriers should be designed to be rapidly removable in an emergency.",
                C_CRITICAL,
            ))

        if pct_warn > 0.20:
            recs.append((
                "Lower Crowd Warning Threshold",
                f"{pct_warn*100:.1f}% of recorded samples were in WARNING or CRITICAL state. "
                f"The current warning threshold may be too permissive. Reduce the warning "
                f"trigger density to allow earlier intervention before critical conditions develop.",
                C_WARNING,
            ))

        if avg_d > DENSITY_WARNING:
            recs.append((
                "Improve Crowd Distribution",
                f"Average density across the session was {avg_d:.2f} p/m², above the "
                f"comfortable-flow threshold of {DENSITY_WARNING:.1f} p/m². Review venue layout "
                f"to ensure attractions, stages, or focal points are distributed to prevent "
                f"congregation hot-spots.",
                C_WARNING,
            ))

        if avg_occ > 75.0:
            recs.append((
                "Implement Timed Entry System",
                f"Average occupancy was {self._fmt_pct(avg_occ)}, indicating the venue was "
                f"consistently heavily used. Consider a staggered/timed entry system to spread "
                f"arrival over a longer period and prevent entry surge.",
                C_WARNING,
            ))

        if not recs:
            recs.append((
                "Maintain Current Practices",
                "Crowd conditions were within safe parameters during this session. Continue "
                "current monitoring and crowd management protocols. Review this report at each "
                "event to track trends over time.",
                C_SAFE,
            ))

        for i, (title, body, color) in enumerate(recs):
            rec_data = [[
                Paragraph(f"R{i+1}. {title}", ParagraphStyle(
                    f"rt{i}", fontSize=9.5, fontName="Helvetica-Bold",
                    textColor=C_PRIMARY
                )),
            ], [
                Paragraph(body, S["body_j"]),
            ]]
            rt = Table(rec_data, colWidths=[INNER_W - 16])
            rt.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            outer = Table([[rt]], colWidths=[INNER_W])
            outer.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("BOX", (0, 0), (-1, -1), 1, color),
                ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT_BG),
                ("LINEABOVE", (0, 0), (-1, 0), 3, color),
            ]))
            story.append(outer)
            story.append(Spacer(1, 6))

        # --- General Stampede Prevention Checklist ---
        story.append(Spacer(1, 4))
        story.append(Paragraph("General Stampede Prevention Checklist", S["sub_head"]))
        checklist = [
            "Conduct a pre-event crowd risk assessment and define density limits per zone before gates open.",
            "Establish a dedicated crowd management communications channel between all stewards, "
            "security, and the control room.",
            "Train all front-line staff in recognising early signs of crowd distress: "
            "people facing backward, being lifted off their feet, pushing, or shouting.",
            "Ensure all emergency exits are clearly signed, unobstructed, and staffed at all "
            "times during peak occupancy periods.",
            "Develop and rehearse a crowd emergency response plan including PA announcements, "
            "orderly dispersal routes, and medical triage staging areas.",
        ]
        for item in checklist:
            story.append(Paragraph(f"[x]  {item}", S["bullet"]))
        story.append(Spacer(1, 8))

    # =========================================================================
    # DATA QUALITY
    # =========================================================================

    def add_data_quality_section(self, story, report):
        S = self._build_styles()
        story += self._section_title("14. Data Quality & Monitoring Notes", S)

        analytics = report.get("analytics", {})
        people    = analytics.get("people", {})
        session   = report.get("session", {})

        total_samples = int(people.get("total_records", 0))
        duration      = self._format_duration(session)

        pairs = [
            ("Total Log Records",         str(total_samples) if total_samples else "No records"),
            ("Session Duration",          duration),
            ("Detection Method",          "Computer Vision (OpenCV YOLO)"),
            ("Coverage",                  "All configured camera zones"),
            ("Data Completeness",         "Based on logged frames — gaps may exist during disconnections"),
        ]
        story.append(self._kv_table(pairs, S))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "<b>Note:</b> Crowd counts are estimated from video analysis and may have "
            "a margin of error, particularly in zones with partial camera coverage, "
            "occlusion, or lighting variation. This report should be used as a planning "
            "guide in conjunction with manual observation records.",
            S["note"]
        ))
        story.append(Spacer(1, 8))

    # =========================================================================
    # CHART GENERATION
    # =========================================================================

    def _load_log_data(self):
        """Load crowd log CSV and return list of row dicts."""
        log_path = os.path.join("data", "logs", "crowd_log.csv")
        rows = []
        if not os.path.exists(log_path):
            return rows
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
        except Exception:
            pass
        return rows

    def generate_report_graphs(self, report=None):
        """Generate 5 professional matplotlib charts. Returns list of (path, caption)."""
        tmpdir = tempfile.mkdtemp(prefix="crowdsense_charts_")
        charts = []

        rows = self._load_log_data()
        if report and self.report_manager:
            session = report.get("session")
            if session:
                try:
                    filtered = self.report_manager.filter_rows_by_session(rows, session)
                    if filtered:
                        rows = filtered
                except Exception:
                    pass

        if len(rows) > 500:
            step = max(1, len(rows) // 500)
            rows = rows[::step]

        # ------------------------------------------------------------------
        # Shared data extraction
        # ------------------------------------------------------------------
        timestamps   = []
        total_people = []
        densities    = []
        risks        = []

        for row in rows:
            ts = row.get("timestamp", "")
            tp = row.get("total_people", "0")
            d  = row.get("density", "0")
            r  = str(row.get("risk", "SAFE")).upper()
            try:
                tp_val = float(tp)
                d_val  = float(d)
            except ValueError:
                continue
            timestamps.append(ts)
            total_people.append(tp_val)
            densities.append(d_val)
            risks.append(r)

        # ------------------------------------------------------------------
        # Chart 1: People Over Time (with risk-coloured background bands)
        # ------------------------------------------------------------------
        try:
            fig, ax = plt.subplots(figsize=(9, 3.8))
            fig.patch.set_facecolor(MPL_BG)
            ax.set_facecolor("#FFFFFF")

            if total_people:
                x = list(range(len(total_people)))

                # Group contiguous intervals of WARNING and CRITICAL
                i = 0
                n = len(risks)
                while i < n:
                    r = risks[i]
                    if r in ("CRITICAL", "WARNING"):
                        start = i
                        while i < n and risks[i] == r:
                            i += 1
                        end = i - 1
                        color = MPL_CRITICAL if r == "CRITICAL" else MPL_WARNING
                        alpha = 0.18 if r == "CRITICAL" else 0.12
                        ax.axvspan(start - 0.5, end + 0.5, alpha=alpha, color=color, linewidth=0)
                    else:
                        i += 1

                ax.plot(x, total_people, color=MPL_PRIMARY, linewidth=1.6,
                        label="Total People", zorder=3)
                ax.fill_between(x, total_people, alpha=0.08, color=MPL_ACCENT)

                # Peak marker
                peak_idx = int(np.argmax(total_people))
                ax.plot(peak_idx, total_people[peak_idx], "v", color=MPL_CRITICAL,
                        markersize=7, zorder=4, label=f"Peak: {int(total_people[peak_idx])}")

                ax.set_xlabel("Sample Index", fontsize=8)
                ax.set_ylabel("People Count", fontsize=8)

            ax.set_title("Crowd Size Over Time", fontsize=11, fontweight="bold",
                          color=MPL_PRIMARY, pad=10)

            safe_patch    = mpatches.Patch(color=MPL_SAFE,     alpha=0.5, label="SAFE")
            warning_patch = mpatches.Patch(color=MPL_WARNING,  alpha=0.5, label="WARNING")
            critical_patch= mpatches.Patch(color=MPL_CRITICAL, alpha=0.5, label="CRITICAL")
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(handles=handles + [safe_patch, warning_patch, critical_patch],
                      fontsize=7, loc="upper left", framealpha=0.8)

            ax.tick_params(axis="both", labelsize=7)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            plt.tight_layout()
            p1 = os.path.join(tmpdir, "people_over_time.png")
            fig.savefig(p1, dpi=130, bbox_inches="tight")
            plt.close(fig)
            charts.append((p1, "Figure 1: Crowd size over time. Coloured bands indicate risk state "
                                "(green=SAFE, amber=WARNING, red=CRITICAL). Peak attendance highlighted."))
        except Exception as e:
            print(f"[ReportExporter] Chart 1 error: {e}")

        # ------------------------------------------------------------------
        # Chart 2: Density Over Time (with stampede threshold lines)
        # ------------------------------------------------------------------
        try:
            fig, ax = plt.subplots(figsize=(9, 3.8))
            fig.patch.set_facecolor(MPL_BG)
            ax.set_facecolor("#FFFFFF")

            if densities:
                x = list(range(len(densities)))
                ax.plot(x, densities, color=MPL_ACCENT, linewidth=1.6,
                        label="Density", zorder=3)
                ax.fill_between(x, densities, alpha=0.08, color=MPL_ACCENT)

                # Ensure warning line (1.0 p/m2) is always in view for context
                max_obs = max(densities) if densities else 0.0
                max_y = max(DENSITY_WARNING * 1.3, max_obs * 1.15)
                # Threshold lines
                ax.axhline(DENSITY_WARNING, color=MPL_WARNING, linestyle="--",
                            linewidth=1.2, label=f"Warning threshold ({DENSITY_WARNING:.1f} p/m\xb2)")
                if max_y >= DENSITY_STAMPEDE:
                    ax.axhline(DENSITY_STAMPEDE, color=MPL_CRITICAL, linestyle="--",
                                linewidth=1.4, label=f"Stampede threshold - Fruin LoS F ({DENSITY_STAMPEDE:.1f} p/m\xb2)")

                # Fill danger zone
                if max_y > DENSITY_STAMPEDE:
                    ax.fill_between(x, DENSITY_STAMPEDE, [min(d, max_y) for d in densities],
                                    where=[d >= DENSITY_STAMPEDE for d in densities],
                                    alpha=0.25, color=MPL_CRITICAL, label="Stampede zone")

                ax.set_ylim(0, max_y)
                ax.set_xlabel("Sample Index", fontsize=8)
                ax.set_ylabel("Density (p/m\xb2)", fontsize=8)

            ax.set_title("Crowd Density Over Time", fontsize=11, fontweight="bold",
                          color=MPL_PRIMARY, pad=10)
            ax.legend(fontsize=7, loc="upper left", framealpha=0.8)
            ax.tick_params(axis="both", labelsize=7)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            plt.tight_layout()
            p2 = os.path.join(tmpdir, "density_over_time.png")
            fig.savefig(p2, dpi=130, bbox_inches="tight")
            plt.close(fig)
            charts.append((p2, "Figure 2: Crowd density over time. The amber dashed line marks the "
                                "comfortable-flow threshold (1.0 p/m²). The red dashed line marks "
                                "Fruin Level of Service F — the stampede danger zone (3.0 p/m²)."))
        except Exception as e:
            print(f"[ReportExporter] Chart 2 error: {e}")

        # ------------------------------------------------------------------
        # Chart 3: Zone Peak People (horizontal bar)
        # ------------------------------------------------------------------
        try:
            zones_data = {}
            if report:
                zones_data = report.get("analytics", {}).get("zones", {})

            if zones_data:
                zone_ids    = sorted(zones_data.keys())
                # Use peak_people if available; fall back to people (latest-frame compat field)
                zone_people = [int(zones_data[z].get("peak_people") or zones_data[z].get("people") or 0) for z in zone_ids]
                zone_risks  = [str(zones_data[z].get("risk", "SAFE")).upper() for z in zone_ids]
                bar_colors  = []
                for r in zone_risks:
                    if r == "CRITICAL":
                        bar_colors.append(MPL_CRITICAL)
                    elif r == "WARNING":
                        bar_colors.append(MPL_WARNING)
                    else:
                        bar_colors.append(MPL_SAFE)

                fig, ax = plt.subplots(figsize=(9, max(3.2, len(zone_ids) * 0.6 + 1.0)))
                fig.patch.set_facecolor(MPL_BG)
                ax.set_facecolor("#FFFFFF")

                y_pos = list(range(len(zone_ids)))
                bars = ax.barh(y_pos, zone_people, color=bar_colors,
                               edgecolor="#CCCCCC", linewidth=0.5, height=0.6)
                for bar, val in zip(bars, zone_people):
                    ax.text(bar.get_width() + max(zone_people, default=1) * 0.01,
                            bar.get_y() + bar.get_height() / 2,
                            f"{val:,}", va="center", ha="left", fontsize=7.5)
                ax.set_yticks(y_pos)
                ax.set_yticklabels(zone_ids, fontsize=8)
                ax.set_xlabel("People Count", fontsize=8)
                ax.set_title("Peak People per Zone", fontsize=11, fontweight="bold",
                              color=MPL_PRIMARY, pad=10)
                ax.tick_params(axis="x", labelsize=7)
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                legend_patches = [
                    mpatches.Patch(color=MPL_SAFE,     label="SAFE"),
                    mpatches.Patch(color=MPL_WARNING,  label="WARNING"),
                    mpatches.Patch(color=MPL_CRITICAL, label="CRITICAL"),
                ]
                ax.legend(handles=legend_patches, fontsize=7, loc="lower right")
                plt.tight_layout()
                p3 = os.path.join(tmpdir, "zone_peak_people.png")
                fig.savefig(p3, dpi=130, bbox_inches="tight")
                plt.close(fig)
                charts.append((p3, "Figure 3: Peak people count per zone. Bars are colour-coded by "
                                    "risk level (green=SAFE, amber=WARNING, red=CRITICAL)."))
            else:
                # Fallback: zone bar from log rows
                zone_agg = {}
                for row in rows:
                    zid = row.get("zone_id", "zone_1")
                    try:
                        zp = float(row.get("zone_people", 0))
                    except Exception:
                        zp = 0
                    zone_agg[zid] = max(zone_agg.get(zid, 0), zp)

                if zone_agg:
                    zone_ids    = sorted(zone_agg.keys())
                    zone_people = [zone_agg[z] for z in zone_ids]
                    fig, ax = plt.subplots(figsize=(9, 3.5))
                    fig.patch.set_facecolor(MPL_BG)
                    ax.set_facecolor("#FFFFFF")
                    ax.barh(zone_ids, zone_people, color=MPL_ACCENT, edgecolor="#CCCCCC", height=0.5)
                    ax.set_xlabel("Peak People", fontsize=8)
                    ax.set_title("Peak People per Zone", fontsize=11, fontweight="bold",
                                  color=MPL_PRIMARY, pad=10)
                    ax.tick_params(labelsize=7)
                    ax.spines["top"].set_visible(False)
                    ax.spines["right"].set_visible(False)
                    plt.tight_layout()
                    p3 = os.path.join(tmpdir, "zone_peak_people.png")
                    fig.savefig(p3, dpi=130, bbox_inches="tight")
                    plt.close(fig)
                    charts.append((p3, "Figure 3: Peak people count per zone."))
        except Exception as e:
            print(f"[ReportExporter] Chart 3 error: {e}")

        # ------------------------------------------------------------------
        # Chart 4: Risk Distribution Pie Chart
        # ------------------------------------------------------------------
        try:
            if report:
                risk_data = report.get("analytics", {}).get("risk", {})
                safe_r  = int(risk_data.get("safe_records", 0))
                warn_r  = int(risk_data.get("warning_records", 0))
                crit_r  = int(risk_data.get("critical_records", 0))
            else:
                safe_r = risks.count("SAFE")
                warn_r = risks.count("WARNING")
                crit_r = risks.count("CRITICAL")

            total_r = safe_r + warn_r + crit_r
            if total_r > 0:
                sizes  = []
                labels = []
                colors_pie = []
                explode = []
                for val, label, color, exp in [
                    (safe_r,  "SAFE",     MPL_SAFE,     0.02),
                    (warn_r,  "WARNING",  MPL_WARNING,  0.04),
                    (crit_r,  "CRITICAL", MPL_CRITICAL, 0.06),
                ]:
                    if val > 0:
                        sizes.append(val)
                        labels.append(f"{label}\n{val/total_r*100:.1f}%")
                        colors_pie.append(color)
                        explode.append(exp)

                fig, ax = plt.subplots(figsize=(6, 4.5))
                fig.patch.set_facecolor(MPL_BG)
                wedges, texts, autotexts = ax.pie(
                    sizes, labels=labels, colors=colors_pie,
                    autopct="%1.0f%%", startangle=140,
                    explode=explode,
                    wedgeprops={"edgecolor": "white", "linewidth": 1.5},
                    textprops={"fontsize": 8},
                )
                for at in autotexts:
                    at.set_fontsize(8)
                    at.set_color("white")
                    at.set_fontweight("bold")
                ax.set_title("Risk Distribution\n(all recorded samples)",
                              fontsize=11, fontweight="bold", color=MPL_PRIMARY, pad=10)
                plt.tight_layout()
                p4 = os.path.join(tmpdir, "risk_distribution.png")
                fig.savefig(p4, dpi=130, bbox_inches="tight")
                plt.close(fig)
                charts.append((p4, "Figure 4: Distribution of all monitoring samples by risk level. "
                                    "A large CRITICAL or WARNING slice indicates persistent unsafe conditions."))
        except Exception as e:
            print(f"[ReportExporter] Chart 4 error: {e}")

        # ------------------------------------------------------------------
        # Chart 5: Occupancy Over Time
        # ------------------------------------------------------------------
        try:
            venue_cap = 0
            if report:
                venue_cap = int(report.get("venue", {}).get("capacity", 0))

            if total_people and venue_cap > 0:
                occupancy_series = [p / venue_cap for p in total_people]

                fig, ax = plt.subplots(figsize=(9, 3.8))
                fig.patch.set_facecolor(MPL_BG)
                ax.set_facecolor("#FFFFFF")

                x = list(range(len(occupancy_series)))
                ax.plot(x, [v * 100 for v in occupancy_series], color=MPL_PRIMARY,
                        linewidth=1.6, label="Occupancy %")
                ax.fill_between(x, [v * 100 for v in occupancy_series],
                                alpha=0.08, color=MPL_PRIMARY)

                v_dict = (report.get("venue") or {}) if isinstance(report, dict) else {}
                warn_pct = float(v_dict.get("warning_threshold", 70) or 70)
                crit_pct = float(v_dict.get("critical_threshold", 90) or 90)
                ax.axhline(warn_pct, color=MPL_WARNING, linestyle="--",
                            linewidth=1.2, label=f"Warning {warn_pct:.0f}%")
                ax.axhline(crit_pct, color=MPL_CRITICAL, linestyle="--",
                            linewidth=1.4, label=f"Critical {crit_pct:.0f}%")

                max_occ_val = max([v * 100 for v in occupancy_series]) if occupancy_series else 100.0
                ax.set_ylim(0, max(120.0, max_occ_val * 1.15))
                ax.set_xlabel("Sample Index", fontsize=8)
                ax.set_ylabel("Occupancy (%)", fontsize=8)
                ax.set_title("Venue Occupancy Over Time", fontsize=11, fontweight="bold",
                              color=MPL_PRIMARY, pad=10)
                ax.legend(fontsize=7, loc="upper left", framealpha=0.8)
                ax.tick_params(axis="both", labelsize=7)
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                plt.tight_layout()
                p5 = os.path.join(tmpdir, "occupancy_over_time.png")
                fig.savefig(p5, dpi=130, bbox_inches="tight")
                plt.close(fig)
                charts.append((p5, "Figure 5: Venue occupancy percentage over time. "
                                    "Amber dashed = 70% warning threshold, Red dashed = 90% critical threshold."))
        except Exception as e:
            print(f"[ReportExporter] Chart 5 error: {e}")

        return charts, tmpdir

    # =========================================================================
    # ADD GRAPHS SECTION TO STORY
    # =========================================================================

    def add_graphs_to_report(self, story, charts):
        """Embed chart images into the PDF story with captions."""
        S = self._build_styles()
        story += self._section_title("15. Crowd Analytics Charts", S)
        story.append(Paragraph(
            "The following charts are generated from the raw monitoring data collected "
            "during this session. They provide a visual overview of crowd dynamics and "
            "support the findings described in the sections above.",
            S["body_j"]
        ))
        story.append(Spacer(1, 8))

        max_img_w = INNER_W
        max_img_h = 200

        for path, caption in charts:
            if not os.path.exists(path):
                continue
            try:
                img = Image(path, width=max_img_w, height=max_img_h,
                            kind="proportional")
                story.append(KeepTogether([
                    img,
                    Paragraph(caption, S["caption"]),
                    Spacer(1, 10),
                ]))
            except Exception as e:
                print(f"[ReportExporter] Image embed error: {e}")

    # =========================================================================
    # SCORING HELPERS
    # =========================================================================

    def _compute_safety_rating(self, report):
        """Return (label, hex_color) for the overall safety rating."""
        analytics = (report.get("analytics") or {}) if isinstance(report, dict) else {}
        risk    = analytics.get("risk") or {}
        safe_r  = int(risk.get("safe_records", 0))
        warn_r  = int(risk.get("warning_records", 0))
        crit_r  = int(risk.get("critical_records", 0))
        total_r = max(safe_r + warn_r + crit_r, 1)
        pct_crit = crit_r / total_r

        if pct_crit < 0.05:
            return "SAFE", "#27AE60"
        elif pct_crit < 0.20:
            return "CAUTION", "#F39C12"
        else:
            return "HIGH RISK", "#E74C3C"

    def _compute_stampede_risk(self, report):
        """Return (label, hex_color) for the stampede risk score."""
        analytics = (report.get("analytics") or {}) if isinstance(report, dict) else {}
        risk    = analytics.get("risk") or {}
        safe_r  = int(risk.get("safe_records", 0))
        warn_r  = int(risk.get("warning_records", 0))
        crit_r  = int(risk.get("critical_records", 0))
        total_r = max(safe_r + warn_r + crit_r, 1)
        density = analytics.get("density") or {}
        max_d   = float(density.get("peak_density") or density.get("maximum_density") or 0)
        pct_los_f = crit_r / total_r

        if max_d < DENSITY_WARNING and pct_los_f < 0.02:
            return "LOW", "#27AE60"
        elif max_d < DENSITY_STAMPEDE and pct_los_f < 0.10:
            return "MEDIUM", "#F39C12"
        elif max_d < DENSITY_STAMPEDE * 1.5 and pct_los_f < 0.30:
            return "HIGH", "#E67E22"
        else:
            return "EXTREME", "#E74C3C"

    # =========================================================================
    # EXPORT PDF (main entry point — API calls this)
    # =========================================================================

    def export_pdf(self, report=None):
        """
        Generate the full PDF report.

        Parameters
        ----------
        report : dict, optional
            Pre-built report dict. If None, attempts to generate via report_manager.

        Returns
        -------
        str
            Absolute path to the generated PDF file.

        Raises
        ------
        RuntimeError
            If ReportLab is not available.
        """
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "ReportLab is not installed. "
                "Install it with: pip install reportlab"
            )

        # --- Fetch or use supplied report ---
        if report is None:
            if self.report_manager:
                try:
                    report = self.report_manager.generate_report()
                except Exception as e:
                    report = {}
                    print(f"[ReportExporter] Warning: could not generate report — {e}")
            else:
                report = {}

        # --- Compute scores ---
        rating_label,        rating_hex        = self._compute_safety_rating(report)
        stampede_risk_label, stampede_risk_hex  = self._compute_stampede_risk(report)

        # --- Output path ---
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"event_safety_report_{ts}.pdf"
        out_path = os.path.join(self.output_folder, filename)
        os.makedirs(self.output_folder, exist_ok=True)

        # --- Build story ---
        story = []

        # Cover page
        self.add_cover_page(story, report, rating_label, rating_hex)

        # Section 1: Executive Summary
        self.add_executive_summary(story, report, rating_label, rating_hex,
                                   stampede_risk_label, stampede_risk_hex)

        # Section 2: Session Overview
        self.add_session_section(story, report)

        # Section 3: Venue Configuration
        self.add_venue_section(story, report)

        # Section 4: Crowd Statistics
        self.add_people_section(story, report)

        # Section 5: Occupancy Analysis
        self.add_occupancy_section(story, report)

        # Section 6: Density Analysis
        self.add_density_section(story, report)

        # Section 7: Risk Distribution
        self.add_risk_section(story, report)

        # Section 8: Alerts Log
        self.add_alert_section(story, report)

        # Section 9: Incidents Log
        self.add_incident_section(story, report)

        # Section 10: Most Crowded Zone
        self.add_most_crowded_section(story, report)

        # Section 11: Zone-by-Zone Analysis
        self.add_zone_section(story, report)

        # Section 12: Stampede Risk Assessment
        story.append(PageBreak())
        self.add_stampede_risk_section(story, report, stampede_risk_label, stampede_risk_hex)

        # Section 13: Recommendations
        self.add_recommendations_section(story, report)

        # Section 14: Data Quality
        self.add_data_quality_section(story, report)

        # Section 15: Charts — generate then embed
        charts, tmpdir = self.generate_report_graphs(report=report)
        if charts:
            story.append(PageBreak())
            self.add_graphs_to_report(story, charts)

        # --- Build PDF ---
        venue_name = report.get("venue", {}).get("name", "CrowdSense")

        # Two-pass: first pass to count total pages
        # We use a BytesIO to pre-build and count pages
        buf = io.BytesIO()
        doc_count = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=22 * mm, bottomMargin=22 * mm,
        )
        doc_count._venue_name  = venue_name
        doc_count._total_pages = "?"

        # Build to count pages — use a minimal canvas callback
        _page_count = [0]

        def _count_page(canvas, doc):
            _page_count[0] += 1

        doc_count.build(story, onFirstPage=_count_page, onLaterPages=_count_page)
        total_pages = _page_count[0]

        # Rebuild story (ReportLab consumes flowables in place)
        story = []
        self.add_cover_page(story, report, rating_label, rating_hex)
        self.add_executive_summary(story, report, rating_label, rating_hex,
                                   stampede_risk_label, stampede_risk_hex)
        self.add_session_section(story, report)
        self.add_venue_section(story, report)
        self.add_people_section(story, report)
        self.add_occupancy_section(story, report)
        self.add_density_section(story, report)
        self.add_risk_section(story, report)
        self.add_alert_section(story, report)
        self.add_incident_section(story, report)
        self.add_most_crowded_section(story, report)
        self.add_zone_section(story, report)
        story.append(PageBreak())
        self.add_stampede_risk_section(story, report, stampede_risk_label, stampede_risk_hex)
        self.add_recommendations_section(story, report)
        self.add_data_quality_section(story, report)
        if charts:
            story.append(PageBreak())
            self.add_graphs_to_report(story, charts)

        # Final build with correct page count
        doc = SimpleDocTemplate(
            out_path,
            pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=22 * mm, bottomMargin=22 * mm,
            title=f"CrowdSense Event Safety Report — {venue_name}",
            author="CrowdSense Monitoring System",
            subject="Crowd Safety & Stampede Prevention Report",
            creator="CrowdSense v1.0",
        )
        doc._venue_name  = venue_name
        doc._total_pages = total_pages

        doc.build(
            story,
            onFirstPage=self._header_footer,
            onLaterPages=self._header_footer,
        )

        # Cleanup temp charts
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

        print(f"[ReportExporter] PDF saved -> {out_path}")
        return out_path
