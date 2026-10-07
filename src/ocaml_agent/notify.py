import sqlite3

from ocaml_agent.telegram import send_long_message


DB_PATH = "data/agent.db"
TOP_N = 10
STRONG_THRESHOLD = 60


def clean_description(description, limit=350):
    if not description:
        return ""
    text = " ".join(description.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


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
        ) = row

        lines.append(f"{i}. {title}")

        if company:
            lines.append(f"🏢 {company}")

        if location:
            lines.append(f"📍 {location}")

        lines.append(
            f"⭐ Final: {final_score:.1f} | "
            f"OCaml: {score:.0f} | AI: {llm_score:.0f}"
        )

        description_text = clean_description(description)

        if description_text:
            lines.append(f"📝 {description_text}")

        if url:
            lines.append(f"🔗 {url}")

        lines.append("")

    lines.extend([
        "📊 OTHER DISCOVERED OPPORTUNITIES",
        "",
    ])

    if other_rows:
        for row in other_rows:
            title, company, final_score = row

            company_text = f" — {company}" if company else ""

            lines.append(
                f"• {title}{company_text} | Final: {final_score:.1f}"
            )
    else:
        lines.append("None")

    return "\n".join(lines)


def main():
    connection = sqlite3.connect(DB_PATH)

    strong_rows = connection.execute(
        """
        SELECT
            title,
            company,
            location,
            score,
            llm_score,
            final_score,
            description,
            canonical_url
        FROM seen_items
        WHERE final_score IS NOT NULL
          AND final_score >= ?
          AND COALESCE(emailed, 0) = 0
        ORDER BY final_score DESC, score DESC, id ASC
        LIMIT ?
        """,
        (STRONG_THRESHOLD, TOP_N),
    ).fetchall()

    other_rows = connection.execute(
        """
        SELECT
            title,
            company,
            final_score
        FROM seen_items
        WHERE final_score IS NOT NULL
          AND final_score < ?
        ORDER BY final_score DESC, score DESC, id ASC
        LIMIT 20
        """,
        (STRONG_THRESHOLD,),
    ).fetchall()

    if not strong_rows and not other_rows:
        connection.close()
        print("No ranked opportunities found.")
        return

    message = build_message(strong_rows, other_rows)

    # Only mark the strong opportunities as sent.
    # Lower-scoring discoveries remain available for future inspection.
    send_long_message(message)

    if strong_rows:
        connection.executemany(
            """
            UPDATE seen_items
            SET emailed = 1
            WHERE canonical_url = ?
            """,
            [(row[7],) for row in strong_rows],
        )

        connection.commit()

    connection.close()

    print(
        f"Sent report: {len(strong_rows)} top opportunities "
        f"+ {len(other_rows)} other discoveries."
    )


if __name__ == "__main__":
    main()
