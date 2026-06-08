from natalaibot.infra.formatting import format_report_sections
from natalaibot.models import ReportSection, StyledNatalReport


def test_format_report_sections_renders_each_section_as_separate_message() -> None:
    report = StyledNatalReport(
        title="Natal report",
        intro=ReportSection(title="Intro", text="Intro text."),
        general=ReportSection(title="General", text="General text."),
        love_and_sex=ReportSection(title="Love", text="Love text."),
        career_and_money=ReportSection(title="Career", text="Career text."),
        demons=ReportSection(title="Demons", text="Demons text."),
        final_summary=ReportSection(title="Final", text="Final text."),
    )

    result = format_report_sections(report=report)

    assert result == [
        "<b>Intro</b>\nIntro text.",
        "<b>General</b>\nGeneral text.",
        "<b>Love</b>\nLove text.",
        "<b>Career</b>\nCareer text.",
        "<b>Demons</b>\nDemons text.",
        "<b>Final</b>\nFinal text.",
    ]


def test_format_report_sections_escapes_html() -> None:
    report = StyledNatalReport(
        title="<Chart>",
        intro=ReportSection(title="Intro & start", text="A < B"),
        general=ReportSection(title="General", text="Text"),
        love_and_sex=ReportSection(title="Love", text="Text"),
        career_and_money=ReportSection(title="Career", text="Text"),
        demons=ReportSection(title="Demons", text="Text"),
        final_summary=ReportSection(title="Final", text="Text"),
    )

    result = format_report_sections(report=report)

    assert result[0] == "<b>Intro &amp; start</b>\nA &lt; B"
