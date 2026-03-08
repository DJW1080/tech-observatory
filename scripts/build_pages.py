from __future__ import annotations

import html
import sys
from pathlib import Path
from urllib.parse import quote


SECTION_CONFIG = [
    {
        "folder": "research-reports",
        "title": "Research Reports",
        "description": "Reports, investigations, and longer-form research material.",
    },
    {
        "folder": "technical-documentation",
        "title": "Technical Documentation",
        "description": "Technical notes, reference material, and implementation documentation.",
    },
]


def display_name(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    return cleaned if cleaned else filename


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


def make_href(base_href: str, filename: str) -> str:
    return f"{base_href}/{quote(filename)}"


def render_doc_list(items: list[Path], base_href: str) -> str:
    if not items:
        return '<li class="empty">No documents found in this section yet.</li>'

    rows: list[str] = []
    for item in items:
        href = make_href(base_href, item.name)
        text = html.escape(display_name(item.name))
        filename = html.escape(item.name)
        rows.append(
            "        <li>\n"
            f'          <a href="{href}">{text}</a>\n'
            f'          <span class="filename">{filename}</span>\n'
            "        </li>"
        )

    return "\n".join(rows)


def render_home_page(site_title: str, sections: list[dict]) -> str:
    section_html: list[str] = []

    for section in sections:
        count = len(section["items"])
        count_label = "document" if count == 1 else "documents"

        section_html.append(
            f"""    <section class="card">
      <div class="section-heading">
        <div>
          <h2>{html.escape(section["title"])}</h2>
          <p class="section-text">{html.escape(section["description"])}</p>
        </div>
        <span class="count-badge">{count} {count_label}</span>
      </div>
      <ul class="document-list">
{render_doc_list(section["items"], f"./{section['folder']}")}
      </ul>
      <p class="browse-link">
        <a href="./{section['folder']}/">Browse full section</a>
      </p>
    </section>"""
        )

    joined_sections = "\n\n".join(section_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(site_title)}</title>
  <meta name="description" content="{html.escape(site_title)} document archive for research reports and technical documentation.">
  <link rel="stylesheet" href="./assets/css/style.css">
</head>
<body>
  <header class="site-header">
    <div class="container">
      <h1>{html.escape(site_title)}</h1>
      <p class="intro">
        A document archive for research reports and technical documentation.
      </p>
    </div>
  </header>

  <main class="container">
{joined_sections}
  </main>

  <footer class="site-footer">
    <div class="container">
      <p>Published with GitHub Pages.</p>
    </div>
  </footer>
</body>
</html>
"""


def render_section_page(site_title: str, section: dict) -> str:
    count = len(section["items"])
    count_label = "document" if count == 1 else "documents"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(section["title"])} · {html.escape(site_title)}</title>
  <meta name="description" content="{html.escape(section["title"])} in {html.escape(site_title)}.">
  <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>
  <header class="site-header">
    <div class="container">
      <h1>{html.escape(section["title"])}</h1>
      <p class="intro">
        <a class="header-link" href="../index.html">Back to home</a>
      </p>
    </div>
  </header>

  <main class="container">
    <section class="card">
      <div class="section-heading">
        <div>
          <h2>{html.escape(section["title"])}</h2>
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
      <p><a href="../index.html">Return to {html.escape(site_title)}</a></p>
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
    site_title = sys.argv[2] if len(sys.argv) > 2 else "Tech Observatory"

    assets_dir = data_dir / "assets" / "css"
    assets_dir.mkdir(parents=True, exist_ok=True)

    sections: list[dict] = []
    for item in SECTION_CONFIG:
        folder_path = data_dir / item["folder"]
        folder_path.mkdir(parents=True, exist_ok=True)

        section = {
            "folder": item["folder"],
            "title": item["title"],
            "description": item["description"],
            "path": folder_path,
            "items": list_docx(folder_path),
        }
        sections.append(section)

    write_text(data_dir / "index.html", render_home_page(site_title, sections))

    for section in sections:
        write_text(section["path"] / "index.html", render_section_page(site_title, section))

    write_text(data_dir / ".nojekyll", "")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())