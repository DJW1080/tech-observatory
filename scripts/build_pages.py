from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

DEFAULT_SECTIONS = [
    {
        "folder": "research-reports",
        "title": "Research Reports 🔬",
        "subtitle": "Independent research and investigations",
        "description": "In-depth research reports, investigations, and analyses.",
        "icon": "🔬",
    },
    {
        "folder": "technical-documentation",
        "title": "Technical Documentation 🕹️",
        "subtitle": "Technical notes and documentation",
        "description": "Technical documentation, instruction manuals, and specifications.",
        "icon": "🕹️",
    },
]

def display_name(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}[-_ ]*", "", stem)
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    return cleaned.title() if cleaned else filename


def list_docx(folder: Path) -> list[Path]:
    if not folder.exists():
        return []

    return sorted(
        [
            path for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() == ".docx"
        ],
        key=lambda p: p.name.lower(),
    )


def detect_date_from_filename(filename: str) -> str | None:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", filename)
    if not match:
        return None

    value = match.group(1)
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        return None


def detect_date_from_file(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def format_date(date_value: str | None) -> str:
    if not date_value:
        return ""

    try:
        dt = datetime.strptime(date_value, "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%b %Y')}"
    except ValueError:
        print(f"Warning: invalid date format '{date_value}'. Expected YYYY-MM-DD.")
        return date_value


def make_href(base_href: str, filename: str) -> str:
    return f"{base_href}/{quote(filename)}"


def load_site_config(data_dir: Path, fallback_title: str) -> dict:
    config_path = data_dir / "site.json"
    if not config_path.exists():
        print(f"Info: no site.json found at {config_path}. Using defaults.")
        return {
            "site_title": fallback_title,
            "site_subtitle": "Research reports and technical documentation.",
            "footer_text": "Published with GitHub Pages.",
            "sections": {},
        }

    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(f"Info: loaded config from {config_path}")

    return {
        "site_title": data.get("site_title", fallback_title),
        "site_subtitle": data.get("site_subtitle", "Research reports and technical documentation."),
        "footer_text": data.get("footer_text", "Published with GitHub Pages."),
        "sections": data.get("sections", {}),
    }


def build_section(section_defaults: dict, config_sections: dict, data_dir: Path) -> dict:
    folder = section_defaults["folder"]
    config = config_sections.get(folder, {})
    folder_path = data_dir / folder
    folder_path.mkdir(parents=True, exist_ok=True)

    listed_files = config.get("documents", [])
    actual_paths = list_docx(folder_path)
    actual_files_by_lower = {path.name.lower(): path for path in actual_paths}

    items: list[dict] = []
    seen: set[str] = set()

    if listed_files:
        print(f"Info: applying manual order for section '{folder}'")

    # Manually ordered items from site.json
    for entry in listed_files:
        raw_filename = entry.get("file", "").strip()
        if not raw_filename:
            continue

        matched_path = actual_files_by_lower.get(raw_filename.lower())
        if not matched_path:
            print(f"Warning: site.json entry '{raw_filename}' not found in '{folder_path}'.")
            continue

        seen.add(matched_path.name.lower())

        date_value = (
            entry.get("date")
            or detect_date_from_filename(matched_path.name)
            or detect_date_from_file(matched_path)
        )

        # Optional abstract support
        abstract_path = matched_path.with_suffix(".txt")
        abstract_text = ""
        if abstract_path.exists():
            abstract_text = abstract_path.read_text(encoding="utf-8").strip()

        items.append(
            {
                "file": matched_path.name,
                "title": entry.get("title", display_name(matched_path.name)),
                "date_iso": date_value,
                "date_display": format_date(date_value),
                "abstract": abstract_text,
            }
        )

    # Automatically discovered items
    remaining = [path for path in actual_paths if path.name.lower() not in seen]

    for path in remaining:
        date_value = (
            detect_date_from_filename(path.name)
            or detect_date_from_file(path)
        )

        # Optional abstract support
        abstract_path = path.with_suffix(".txt")
        abstract_text = ""
        if abstract_path.exists():
            abstract_text = abstract_path.read_text(encoding="utf-8").strip()

        items.append(
            {
                "file": path.name,
                "title": display_name(path.name),
                "date_iso": date_value,
                "date_display": format_date(date_value),
                "abstract": abstract_text,
            }
        )

    return {
       "folder": folder,
       "title": config.get("title", section_defaults["title"]),
       "subtitle": config.get("subtitle", section_defaults.get("subtitle", "")),
       "icon": config.get("icon", section_defaults.get("icon", "")),
       "description": config.get("description", section_defaults["description"]),
       "path": folder_path,
       "items": items,
   }


def render_doc_list(items: list[dict], base_href: str) -> str:
    if not items:
        return '        <li class="empty">No documents found in this section yet.</li>'

    rows: list[str] = []
    for item in items:
        href = make_href(base_href, item["file"])
        title = html.escape(item["title"])
        filename = html.escape(item["file"])

        meta_line = ""
        if item["date_display"]:
            meta_line = f'\n          <div class="doc-meta">{html.escape(item["date_display"])}</div>'

        abstract_html = ""
        if item.get("abstract"):
            abstract_html = f'\n          <div class="doc-abstract">{html.escape(item["abstract"])}</div>'

        rows.append(
            "        <li>\n"
            f'          <div class="doc-title">{title}</div>'
            f"{meta_line}"
            f"{abstract_html}\n"
            f'          <a href="{href}" class="filename">{filename}</a>\n'
            "        </li>"
        )

    return "\n".join(rows)


def render_home_page(site_title: str, site_subtitle: str, footer_text: str, sections: list[dict]) -> str:
    # Collect all docs for latest updates and last-updated line
    all_docs = []
    for section in sections:
        for item in section["items"]:
            if item.get("date_iso"):
                all_docs.append((item["date_iso"], section["folder"], item))

    all_docs.sort(reverse=True, key=lambda x: x[0])
    latest_items = all_docs[:5]

    latest_html = []
    for date_iso, folder, item in latest_items:
        href = f"./{folder}/{quote(item['file'])}"
        title = html.escape(item["title"])
        date_display = html.escape(item["date_display"])
        latest_html.append(f'<li><a href="{href}">{title}</a> — {date_display}</li>')

    latest_updates_block = "\n".join(latest_html) if latest_html else "<li>No recent updates.</li>"

    last_updated_display = ""
    if all_docs:
        # Use the newest item's display date
        last_updated_display = all_docs[0][2].get("date_display") or all_docs[0][0]

    last_updated_html = ""
    if last_updated_display:
        last_updated_html = f'<li class="last-updated">Last updated: {html.escape(last_updated_display)}</li>'

    # Section cards (unchanged layout)
    section_html: list[str] = []
    for section in sections:
        count = len(section["items"])
        count_label = "document" if count == 1 else "documents"

        section_html.append(
            f"""    <section class="card">
      <div class="section-heading">
        <div>
          <h2>{html.escape(section["title"])} {section.get("icon", "")}</h2>
          <p class="section-text">{html.escape(section["subtitle"])}</p>
        </div>
        <span class="count-badge">{count} {count_label}</span>
      </div>
      <ul class="document-list">
{render_doc_list(section["items"], f"./{section['folder']}")}
      </ul>
      <p class="browse-link">
        <a href="./{section['folder']}/index.html">Browse full section</a>
      </p>
    </section>"""
        )

    joined_sections = "\n\n".join(section_html)

    # Simple text nav for home
    nav_html = """
      <p class="site-nav">
        <a href="./index.html">Home</a> |
        <a href="./research-reports/index.html">Research Reports</a> |
        <a href="./technical-documentation/index.html">Technical Documentation</a>
      </p>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(site_title)}</title>
  <meta name="description" content="Tech Observatory documents the hidden systems shaping our digital life, through independent research, technical analysis, and public‑interest reporting.">
  <link rel="stylesheet" href="./assets/css/style.css">
</head>
<body>
  <header class="site-header">
  <div class="container">
    <h1>{html.escape(site_title)} 🔭</h1>
    <p class="site-subtitle">{site_subtitle}</p>
    {nav_html}
   </div>
</header>

  <main class="container">
    <section class="card">
      <div class="section-heading">
        <div>
          <h2>Latest Updates</h2>
        </div>
      </div>
      <ul class="document-list">
        {latest_updates_block}
        {last_updated_html}
      </ul>
    </section>

{joined_sections}

  </main>

  <footer class="site-footer">
    <div class="container">
      <p class="footer-text">{html.escape(footer_text)} developed by <a href="https://github.com/DJW1080" class="stealth-link">DeanTech1980</a>.</p>
    </div>
  </footer>
</body>
</html>
"""


def render_section_page(site_title: str, site_subtitle: str, footer_text: str, section: dict) -> str:
    count = len(section["items"])
    count_label = "document" if count == 1 else "documents"

    section_title = html.escape(section["title"])
    page_title = f"{section['title']} · {site_title}"
    meta_description = f"{section['title']} in {site_title}."

    # Simple text nav for section pages
    nav_html = """
      <p class="site-nav">
        <a href="../index.html">Home</a> |
        <a href="../research-reports/index.html">Research Reports</a> |
        <a href="../technical-documentation/index.html">Technical Documentation</a>
      </p>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(meta_description)}">
  <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>
  <header class="site-header">
    <div class="container">
      <h1>{section_title} {section.get("icon", "")}</h1>
      <p class="site-subtitle">{html.escape(section.get("subtitle", site_subtitle))}</p>
{nav_html}
    </div>
  </header>

  <main class="container">
    <section class="card">
      <div class="section-heading">
        <div>
          <h2>{section_title} {section.get("icon", "")}</h2>
          <p class="section-text">{html.escape(section["description"])}</p>
        </div>
        <span class="count-badge">{count} {count_label}</span>
      </div>
      <ul class="document-list">
{render_doc_list(section["items"], ".")}
      </ul>
    </section>
  </main>

  <footer class="site-footer">
    <div class="container">
      <p class="footer-text">{html.escape(footer_text)} developed by <a href="https://github.com/DJW1080" class="stealth-link">DeanTech1980</a>.</p>
    </div>
  </footer>
</body>
</html>
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    data_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
    fallback_title = sys.argv[2] if len(sys.argv) > 2 else "Tech Observatory"

    assets_dir = data_dir / "assets" / "css"
    assets_dir.mkdir(parents=True, exist_ok=True)

    config = load_site_config(data_dir, fallback_title)

    site_title = config["site_title"]
    site_subtitle = config["site_subtitle"]
    footer_text = config["footer_text"]

    sections = [
        build_section(default, config["sections"], data_dir)
        for default in DEFAULT_SECTIONS
    ]

    write_text(
        data_dir / "index.html",
        render_home_page(site_title, site_subtitle, footer_text, sections),
    )

    for section in sections:
        write_text(
            section["path"] / "index.html",
            render_section_page(site_title, site_subtitle, footer_text, section),
        )

    write_text(data_dir / ".nojekyll", "")

    print("Info: site build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    