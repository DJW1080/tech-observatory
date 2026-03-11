from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except Exception:
        PdfReader = None  # type: ignore


DEFAULT_SECTIONS = [
    {
        "folder": "research-reports",
        "title": "Research Reports",
        "subtitle": "Observing the systems that shape our digital life.",
        "description": "Independent research and investigations.",
        "icon": "🔬",
    },
    {
        "folder": "technical-documentation",
        "title": "Technical Documentation",
        "subtitle": "Observing the systems that shape our digital life.",
        "description": "Technical notes, guides, and reference material.",
        "icon": "🕹️",
    },
]

KNOWN_ACRONYMS = {
    "ai": "AI",
    "api": "API",
    "css": "CSS",
    "ci": "CI",
    "cd": "CD",
    "csv": "CSV",
    "dns": "DNS",
    "gpu": "GPU",
    "html": "HTML",
    "http": "HTTP",
    "https": "HTTPS",
    "idor": "IDOR",
    "ip": "IP",
    "it": "IT",
    "json": "JSON",
    "jwt": "JWT",
    "owasp": "OWASP",
    "pdf": "PDF",
    "rdp": "RDP",
    "seo": "SEO",
    "smb": "SMB",
    "sql": "SQL",
    "ssh": "SSH",
    "tls": "TLS",
    "ui": "UI",
    "url": "URL",
    "ux": "UX",
    "xml": "XML",
    "xss": "XSS",
    "yaml": "YAML",
}

VALID_SORT_MODES = {"date_desc", "date_asc", "alpha_asc", "alpha_desc"}


def parse_pdf_date(value: str | None) -> str | None:
    """
    Parse common PDF metadata date formats, such as:
    D:20260311
    D:20260311153000Z
    D:20260311153000+11'00'
    """
    if not value:
        return None

    candidate = value.strip()
    if candidate.startswith("D:"):
        candidate = candidate[2:]

    match = re.match(r"^(\d{4})(\d{2})(\d{2})", candidate)
    if not match:
        return None

    try:
        dt = datetime.strptime("".join(match.groups()), "%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def normalise_summary_text(value: str, max_length: int = 240) -> str:
    collapsed = re.sub(r"\s+", " ", value).strip()
    if len(collapsed) <= max_length:
        return collapsed

    shortened = collapsed[: max_length - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    if not shortened:
        shortened = collapsed[: max_length - 1].rstrip(" ,.;:-")
    return shortened + "…"


def extract_pdf_metadata(path: Path) -> dict:
    metadata = {
        "title": None,
        "subject": None,
        "author": None,
        "created_date": None,
        "modified_date": None,
    }

    if PdfReader is None:
        return metadata

    try:
        reader = PdfReader(str(path))
        raw_meta = reader.metadata or {}

        def meta_get(*keys: str) -> str | None:
            for key in keys:
                value = raw_meta.get(key)
                if value is not None:
                    text = str(value).strip()
                    if text:
                        return text
            return None

        metadata["title"] = meta_get("/Title", "Title")
        metadata["subject"] = meta_get("/Subject", "Subject")
        metadata["author"] = meta_get("/Author", "Author")
        metadata["created_date"] = parse_pdf_date(meta_get("/CreationDate", "CreationDate"))
        metadata["modified_date"] = parse_pdf_date(meta_get("/ModDate", "ModDate"))
    except Exception as exc:
        print(f"Warning: could not extract PDF metadata from '{path.name}': {exc}")

    return metadata


def smart_title_from_stem(stem: str) -> str:
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return stem

    words = re.split(r"\s+", cleaned)
    titled: list[str] = []

    for index, word in enumerate(words):
        lower = word.lower()

        if lower in KNOWN_ACRONYMS:
            titled.append(KNOWN_ACRONYMS[lower])
            continue

        if re.fullmatch(r"v\d+", lower):
            titled.append(lower.upper())
            continue

        if re.fullmatch(r"\d+d", lower):
            titled.append(lower[:-1] + "D")
            continue

        if re.fullmatch(r"[a-z]\d+", lower):
            titled.append(lower[0].upper() + lower[1:])
            continue

        if lower in {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to"} and 0 < index < len(words) - 1:
            titled.append(lower)
            continue

        titled.append(lower.capitalize())

    return " ".join(titled)


def display_name(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}[-_ ]*", "", stem)
    return smart_title_from_stem(stem) or filename


def choose_auto_title(path: Path, metadata: dict) -> str:
    for candidate in (metadata.get("title"),):
        if candidate:
            return str(candidate).strip()
    return display_name(path.name)


def choose_auto_abstract(path: Path, metadata: dict) -> str:
    abstract_path = path.with_suffix(".txt")
    if abstract_path.exists():
        try:
            return normalise_summary_text(abstract_path.read_text(encoding="utf-8").strip(), max_length=400)
        except Exception as exc:
            print(f"Warning: could not read abstract file '{abstract_path.name}': {exc}")

    for candidate in (metadata.get("subject"),):
        if candidate:
            return normalise_summary_text(str(candidate))

    return ""


def list_pdfs(folder: Path) -> list[Path]:
    if not folder.exists():
        return []

    return sorted(
        [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"],
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


def normalise_sort_mode(value: str | None) -> str:
    if not value:
        return "date_desc"

    candidate = str(value).strip().lower()
    if candidate not in VALID_SORT_MODES:
        print(f"Warning: unsupported sort mode '{value}'. Falling back to 'date_desc'.")
        return "date_desc"

    return candidate


def read_abstract(path: Path, entry: dict | None = None, metadata: dict | None = None) -> str:
    if entry and entry.get("abstract"):
        return str(entry["abstract"]).strip()

    return choose_auto_abstract(path, metadata or {})


def make_item(path: Path, entry: dict | None = None) -> dict:
    entry = entry or {}
    metadata = extract_pdf_metadata(path)
    date_value = (
        entry.get("date")
        or detect_date_from_filename(path.name)
        or metadata.get("modified_date")
        or metadata.get("created_date")
        or detect_date_from_file(path)
    )

    return {
        "file": path.name,
        "title": entry.get("title") or choose_auto_title(path, metadata),
        "date_iso": date_value,
        "date_display": format_date(date_value),
        "abstract": read_abstract(path, entry, metadata),
        "file_label": "PDF file",
    }


def sort_items(items: list[dict], sort_mode: str) -> list[dict]:
    if sort_mode == "alpha_asc":
        return sorted(items, key=lambda item: (item["title"].casefold(), item["file"].casefold()))

    if sort_mode == "alpha_desc":
        return sorted(items, key=lambda item: (item["title"].casefold(), item["file"].casefold()), reverse=True)

    if sort_mode == "date_asc":
        return sorted(
            items,
            key=lambda item: (item["date_iso"] is None, item["date_iso"] or "", item["title"].casefold()),
        )

    return sorted(
        items,
        key=lambda item: (item["date_iso"] or "", item["title"].casefold()),
        reverse=True,
    )


def load_site_config(data_dir: Path, fallback_title: str) -> dict:
    config_path = data_dir / "site.json"
    if not config_path.exists():
        print(f"Info: no site.json found at {config_path}. Using defaults.")
        return {
            "site_title": fallback_title,
            "site_icon": "🔭",
            "site_subtitle": "Observing the systems that shape our digital life.",
            "meta_description": "Observing the systems that shape our digital life.",
            "footer_text": "Technification · Tech Observatory",
            "latest_updates_count": 5,
            "sections": {},
        }

    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(f"Info: loaded config from {config_path}")

    site_subtitle = data.get("site_subtitle", "Observing the systems that shape our digital life.")
    return {
        "site_title": data.get("site_title", fallback_title),
        "site_icon": data.get("site_icon", "🔭"),
        "site_subtitle": site_subtitle,
        "meta_description": data.get("meta_description", site_subtitle),
        "footer_text": data.get("footer_text", "Technification · Tech Observatory"),
        "latest_updates_count": int(data.get("latest_updates_count", 5) or 5),
        "sections": data.get("sections", {}),
    }


def build_section(section_defaults: dict, config_sections: dict, data_dir: Path) -> dict:
    folder = section_defaults["folder"]
    config = config_sections.get(folder, {})
    folder_path = data_dir / folder
    folder_path.mkdir(parents=True, exist_ok=True)

    listed_files = config.get("documents", [])
    sort_mode = normalise_sort_mode(config.get("sort"))
    actual_paths = list_pdfs(folder_path)
    actual_files_by_lower = {path.name.lower(): path for path in actual_paths}

    items: list[dict] = []
    seen: set[str] = set()

    if listed_files:
        print(f"Info: applying manual order for section '{folder}'")

    for entry in listed_files:
        raw_filename = entry.get("file", "").strip()
        if not raw_filename:
            continue

        matched_path = actual_files_by_lower.get(raw_filename.lower())
        if not matched_path:
            print(f"Warning: site.json entry '{raw_filename}' not found in '{folder_path}'.")
            continue

        seen.add(matched_path.name.lower())
        items.append(make_item(matched_path, entry))

    remaining = [make_item(path) for path in actual_paths if path.name.lower() not in seen]
    items.extend(sort_items(remaining, sort_mode))

    return {
        "folder": folder,
        "title": config.get("title", section_defaults["title"]),
        "subtitle": config.get("subtitle", section_defaults.get("subtitle", "")),
        "icon": config.get("icon", section_defaults.get("icon", "")),
        "description": config.get("description", section_defaults["description"]),
        "meta_description": config.get(
            "meta_description",
            f"{config.get('description', section_defaults['description'])} — {config.get('title', section_defaults['title'])}.",
        ),
        "sort": sort_mode,
        "path": folder_path,
        "items": items,
    }


def heading_with_icon(title: str, icon: str | None = None) -> str:
    escaped_title = html.escape(title)
    if icon and icon not in title:
        return f'{escaped_title} <span class="section-icon" aria-hidden="true">{html.escape(icon)}</span>'
    return escaped_title


def render_nav(sections: list[dict], relative_prefix: str, current_page: str) -> str:
    parts: list[str] = []

    if current_page == "home":
        parts.append('<span class="current" aria-current="page">Home</span>')
    else:
        parts.append(f'<a href="{relative_prefix}index.html">Home</a>')

    for section in sections:
        label = html.escape(section["title"])
        href = f'{relative_prefix}{section["folder"]}/index.html'
        if current_page == section["folder"]:
            parts.append(f'<span class="current" aria-current="page">{label}</span>')
        else:
            parts.append(f'<a href="{href}">{label}</a>')

    separator = '<span class="nav-sep" aria-hidden="true">|</span>'
    return f'      <nav class="site-nav" aria-label="Site">{separator.join(parts)}</nav>'


def render_doc_list(items: list[dict], base_href: str) -> str:
    if not items:
        return '        <li class="empty">No documents found in this section yet.</li>'

    rows: list[str] = []
    for item in items:
        href = make_href(base_href, item["file"])
        title = html.escape(item["title"])
        filename = html.escape(item["file"])
        file_label = html.escape(item.get("file_label", "PDF file"))

        meta_line = ""
        if item["date_display"]:
            meta_line = f'\n          <div class="doc-meta">{html.escape(item["date_display"])}</div>'

        abstract_html = ""
        if item.get("abstract"):
            abstract_html = f'\n          <div class="doc-abstract">{html.escape(item["abstract"])}</div>'

        rows.append(
            "        <li class=\"document-item\">\n"
            f'          <div class="doc-title"><a href="{href}" class="doc-title-link">{title}</a><span class="file-badge">PDF</span></div>'
            f"{meta_line}"
            f"{abstract_html}\n"
            f'          <div class="doc-fileline">{file_label} · <span class="doc-filename">{filename}</span></div>\n'
            "        </li>"
        )

    return "\n".join(rows)


def render_home_page(
    site_title: str,
    site_icon: str,
    site_subtitle: str,
    meta_description: str,
    footer_text: str,
    sections: list[dict],
    latest_updates_count: int,
) -> str:
    all_docs: list[tuple[str, dict, dict]] = []
    for section in sections:
        for item in section["items"]:
            if item.get("date_iso"):
                all_docs.append((item["date_iso"], section, item))

    all_docs.sort(reverse=True, key=lambda x: (x[0], x[2]["title"].casefold()))
    latest_items = all_docs[: max(latest_updates_count, 1)]

    latest_html: list[str] = []
    for _, section, item in latest_items:
        href = f'./{section["folder"]}/{quote(item["file"])}'
        title = html.escape(item["title"])
        date_display = html.escape(item["date_display"])
        section_label = html.escape(section["title"])
        latest_html.append(
            f'<li><a href="{href}">{title}</a> <span class="latest-meta">— {date_display} · {section_label}</span></li>'
        )

    latest_updates_block = "\n        ".join(latest_html) if latest_html else "<li>No recent updates.</li>"

    last_updated_html = ""
    if all_docs:
        last_updated_display = all_docs[0][2].get("date_display") or all_docs[0][0]
        last_updated_html = f'\n      <p class="last-updated">Last updated: {html.escape(last_updated_display)}</p>'

    section_html: list[str] = []
    for section in sections:
        count = len(section["items"])
        count_label = "document" if count == 1 else "documents"

        section_html.append(
            f"""    <section class="card">
      <div class="section-heading">
        <div>
          <h2>{heading_with_icon(section["title"], section.get("icon", ""))}</h2>
          <p class="section-text">{html.escape(section["description"])}</p>
        </div>
        <span class="count-badge">{count} {count_label}</span>
      </div>
      <ul class="document-list">
{render_doc_list(section["items"], f'./{section["folder"]}')}
      </ul>
      <p class="browse-link">
        <a href="./{section['folder']}/index.html">Browse full section</a>
      </p>
    </section>"""
        )

    joined_sections = "\n\n".join(section_html)
    site_heading = heading_with_icon(site_title, site_icon)
    nav_html = render_nav(sections, "./", "home")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(site_title)}</title>
  <meta name="description" content="{html.escape(meta_description)}">
  <link rel="icon" href="./assets/icons/favicon.ico" sizes="any">
  <link rel="icon" type="image/png" sizes="32x32" href="./assets/icons/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="./assets/icons/favicon-16x16.png">
  <link rel="apple-touch-icon" href="./assets/icons/apple-touch-icon.png">
  <link rel="stylesheet" href="./assets/css/style.css">
</head>
<body>
  <header class="site-header">
    <div class="container">
      <h1>{site_heading}</h1>
      <p class="site-subtitle">{html.escape(site_subtitle)}</p>
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
      <ul class="document-list latest-list">
        {latest_updates_block}
      </ul>{last_updated_html}
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


def render_section_page(
    site_title: str,
    site_subtitle: str,
    footer_text: str,
    sections: list[dict],
    section: dict,
) -> str:
    count = len(section["items"])
    count_label = "document" if count == 1 else "documents"

    page_title = f"{section['title']} · {site_title}"
    nav_html = render_nav(sections, "../", section["folder"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(section['meta_description'])}">
  <link rel="icon" href="../assets/icons/favicon.ico" sizes="any">
  <link rel="icon" type="image/png" sizes="32x32" href="../assets/icons/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="../assets/icons/favicon-16x16.png">
  <link rel="apple-touch-icon" href="../assets/icons/apple-touch-icon.png">
  <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>
  <header class="site-header">
    <div class="container">
      <h1>{heading_with_icon(section['title'], section.get('icon', ''))}</h1>
      <p class="site-subtitle">{html.escape(site_subtitle)}</p>
{nav_html}
    </div>
  </header>

  <main class="container">
    <section class="card">
      <div class="section-heading">
        <div>
          <h2>{heading_with_icon(section['title'], section.get('icon', ''))}</h2>
          <p class="section-text">{html.escape(section['description'])}</p>
        </div>
        <span class="count-badge">{count} {count_label}</span>
      </div>
      <ul class="document-list">
{render_doc_list(section['items'], '.')}
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

    config = load_site_config(data_dir, fallback_title)

    site_title = config["site_title"]
    site_icon = config["site_icon"]
    site_subtitle = config["site_subtitle"]
    meta_description = config["meta_description"]
    footer_text = config["footer_text"]
    latest_updates_count = config["latest_updates_count"]

    sections = [build_section(default, config["sections"], data_dir) for default in DEFAULT_SECTIONS]

    write_text(
        data_dir / "index.html",
        render_home_page(
            site_title,
            site_icon,
            site_subtitle,
            meta_description,
            footer_text,
            sections,
            latest_updates_count,
        ),
    )

    for section in sections:
        write_text(
            section["path"] / "index.html",
            render_section_page(site_title, site_subtitle, footer_text, sections, section),
        )

    write_text(data_dir / ".nojekyll", "")

    print("Info: site build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
