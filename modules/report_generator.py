"""
VERIDEXA — report generation.
Exports any result table as CSV/Excel, and can assemble a combined
full-session HTML report from whatever's in session state.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from config.settings import APP_NAME


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return buf.getvalue()


def to_multi_sheet_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            if df is None or df.empty:
                continue
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


class PdfExportError(Exception):
    pass


def to_pdf_bytes(html: str) -> bytes:
    """Renders the same HTML used for `build_html_report` into a real,
    standalone PDF file (not "print via browser") using xhtml2pdf a
    pure-Python renderer with no system-level dependencies (no wkhtmltopdf
    binary, no headless Chrome needed)."""
    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise PdfExportError(
            "PDF export needs the 'xhtml2pdf' package. Install it with "
            "`pip install xhtml2pdf`."
        ) from e

    # The web-preview theme is dark (nice for the browser, wasteful ink on
    # paper and shakier support in xhtml2pdf's limited CSS engine), so we
    # override just the color rules for the PDF render — same structure
    # and content, print-friendly palette.
    print_overrides = """
    <style>
        body { background: #FFFFFF !important; color: #1A1A2E !important; }
        h1 { color: #6C5CE7 !important; -webkit-text-fill-color: #6C5CE7 !important; background: none !important; }
        h2 { border-bottom-color: #DDDDE8 !important; }
        th { background: #F1F1F8 !important; }
        th, td { border-color: #DDDDE8 !important; }
        .meta { color: #55586E !important; }
    </style>
    """
    pdf_html = html.replace("</head>", print_overrides + "</head>")

    buf = io.BytesIO()
    result = pisa.CreatePDF(src=pdf_html, dest=buf, encoding="utf-8")
    if result.err:
        raise PdfExportError("Could not render this report to PDF try the HTML version instead.")
    return buf.getvalue()


def build_html_report(title: str, sections: list[dict], username: str = "") -> str:
    """`sections` is a list of {"heading": str, "html": str} blocks —
    each `html` is pre-rendered (e.g. a df.to_html() or plotly fig.to_html())."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = "\n".join(
        f'<section><h2>{s["heading"]}</h2>{s["html"]}</section>' for s in sections
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title} — {APP_NAME}</title>
<style>
    body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#0F1117; color:#E8E8F0; margin:0; padding:2rem 3rem; }}
    h1 {{ background: linear-gradient(90deg,#8A7CFF,#6C5CE7,#34D6C4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    h2 {{ border-bottom: 1px solid #262A38; padding-bottom: .4rem; margin-top: 2.2rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #262A38; padding: 0.4rem 0.7rem; text-align: left; font-size: 0.9rem; }}
    th {{ background: #171A23; }}
    .meta {{ color:#8A8DA0; font-size:0.85rem; }}
</style>
</head>
<body>
<h1>{APP_NAME} — {title}</h1>
<p class="meta">Generated {generated}{f' for {username}' if username else ''}. All figures computed directly from your uploaded data.</p>
{body}
</body>
</html>"""
