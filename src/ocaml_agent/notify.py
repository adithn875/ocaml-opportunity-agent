import argparse
import sqlite3
from html import unescape
from html.parser import HTMLParser

from ocaml_agent.jane_street_collector import is_ocaml_job
from ocaml_agent.telegram import send_long_message


DB_PATH = "data/agent.db"
TOP_N = 10
STRONG_THRESHOLD = 60


class _DescriptionHTMLParser(HTMLParser):
    """Extract readable text while preserving non-HTML angle-bracket text."""

    _BLOCK_TAGS = {
        "article",
        "blockquote",
        "div",
        "dl",
        "dt",
        "dd",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
    _INLINE_TAGS = {
        "a",
        "b",
        "br",
        "code",
        "em",
        "i",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
    }
    _IGNORED_TAGS = {"script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._ignored_depth = 0

    def _separator(self):
        if self.parts and not self.parts[-1].endswith(" "):
            self.parts.append(" ")

    def handle_starttag(self, tag, attrs):
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "li":
            self._separator()
            self.parts.append("• ")
        elif tag == "br" or tag in self._BLOCK_TAGS:
            self._separator()
        elif tag not in self._INLINE_TAGS:
            self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in self._IGNORED_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self._IGNORED_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif not self._ignored_depth and tag in self._BLOCK_TAGS:
            self._separator()
        elif not self._ignored_depth and tag not in self._INLINE_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._ignored_depth:
            self.parts.append(data)


def clean_description(description, limit=350):
    """Convert an optional HTML description into compact notification text."""

    if not isinstance(description, str) or not description:
        return ""

    parser = _DescriptionHTMLParser()
    parser.feed(description)
    parser.close()
    text = " ".join(unescape("".join(parser.parts)).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."



def format_score(value, precision=1):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{precision}f}"
    except (TypeError, ValueError):
        return "N/A"


def format_date(value):
    """Display source-provided date information without inferring freshness."""

    if not isinstance(value, str) or not value.strip():
        return "unknown"
    return value.strip()


def is_notification_eligible(title, source, description):
    """Keep legacy Jane Street rows aligned with the collector's filter."""

    if source != "Jane Street":
        return True

    return is_ocaml_job(
        {
            "position": title,
            "overview": description,
        }
    )


def get_notification_rows(connection):
    """Return eligible ranked rows formatted for the notification message."""

    strong_candidates = connection.execute(
        """
        SELECT
            title,
            company,
            location,
            score,
            llm_score,
            final_score,
            description,
            canonical_url,
            source
            , posted_date,
            deadline
        FROM seen_items
        WHERE final_score IS NOT NULL
          AND final_score >= ?
          AND COALESCE(emailed, 0) = 0
        ORDER BY final_score DESC, score DESC, id ASC
        """,
        (STRONG_THRESHOLD,),
    ).fetchall()

    strong_rows = [
        row[:8] + row[9:]
        for row in strong_candidates
        if is_notification_eligible(
            title=row[0],
            source=row[8],
            description=row[6],
        )
    ][:TOP_N]

    other_candidates = connection.execute(
        """
        SELECT title, company, final_score, canonical_url, source, description
        FROM seen_items
        WHERE final_score IS NOT NULL
          AND final_score < ?
          AND COALESCE(emailed, 0) = 0
        ORDER BY final_score DESC, score DESC, id ASC
        """,
        (STRONG_THRESHOLD,),
    ).fetchall()

    other_rows = [
        row[:4]
        for row in other_candidates
        if is_notification_eligible(
            title=row[0],
            source=row[4],
            description=row[5],
        )
    ][:20]

    return strong_rows, other_rows


def build_message(strong_rows, other_rows):
    lines = [
        "🚀 OCaml Opportunity Agent",
        "",
        "🔥 TOP OPPORTUNITIES",
        "",
    ]

    for i, row in enumerate(strong_rows, 1):
        (
            title,
            company,
            location,
            score,
            llm_score,
            final_score,
            description,
            url,
            *freshness,
        ) = row

        lines.append(f"{i}. {title}")

        if company:
            lines.append(f"🏢 {company}")

        if location:
            lines.append(f"📍 {location}")

        lines.append(
            f"⭐ Final: {format_score(final_score)} | "
            f"OCaml: {format_score(score, 0)} | AI: {format_score(llm_score, 0)}"
        )

        description_text = clean_description(description)

        if description_text:
            lines.append(f"📝 {description_text}")

        posted_date = freshness[0] if freshness else None
        deadline = freshness[1] if len(freshness) > 1 else None
        lines.append(
            f"🗓️ Posted: {format_date(posted_date)} | "
            f"Deadline: {format_date(deadline)}"
        )

        if url:
            lines.append(f"🔗 Listing: {url}")

        lines.append("")

    lines.extend([
        "📊 OTHER DISCOVERED OPPORTUNITIES",
        "",
    ])

    if other_rows:
        for row in other_rows:
            title, company, final_score, *_ = row

            company_text = f" — {company}" if company else ""

            lines.append(
                f"• {title}{company_text} | Final: {format_score(final_score)}"
            )
    else:
        lines.append("None")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Send or preview ranked opportunity notifications."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the notification without sending it or updating delivery state.",
    )
    args = parser.parse_args()

    connection = sqlite3.connect(DB_PATH)

    strong_rows, other_rows = get_notification_rows(connection)

    if not strong_rows and not other_rows:
        connection.close()
        print("No ranked opportunities found.")
        return

    message = build_message(strong_rows, other_rows)

    if args.dry_run:
        print(message)
        connection.close()
        print("Dry run complete; no notification sent or records marked.")
        return

    try:
        send_long_message(message)
    except Exception:
        connection.close()
        raise

    delivered_urls = list(
        dict.fromkeys(
            [row[7] for row in strong_rows]
            + [row[3] for row in other_rows]
        )
    )

    # Delivery state changes only after every message chunk has been sent.
    if delivered_urls:
        connection.executemany(
            """
            UPDATE seen_items
            SET emailed = 1
            WHERE canonical_url = ?
            """,
            [(url,) for url in delivered_urls],
        )

        connection.commit()

    connection.close()

    print(
        f"Sent report: {len(strong_rows)} top opportunities "
        f"+ {len(other_rows)} other discoveries."
    )


if __name__ == "__main__":
    main()
