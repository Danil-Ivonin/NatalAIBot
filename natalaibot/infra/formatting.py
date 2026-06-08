from html import escape

from natalaibot.models import ReportSection, StyledNatalReport

MAX_TELEGRAM_MESSAGE_LENGTH = 4096
SAFE_MESSAGE_LENGTH = 3900


def format_report_sections(report: StyledNatalReport) -> list[str]:
    sections = [
        report.intro,
        report.general,
        report.love_and_sex,
        report.career_and_money,
        report.demons,
        report.final_summary,
    ]
    return [_format_section(section) for section in sections]


def split_telegram_message(text: str, limit: int = SAFE_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


def _format_section(section: ReportSection) -> str:
    return f"<b>{escape(section.title)}</b>\n{escape(section.text)}"
