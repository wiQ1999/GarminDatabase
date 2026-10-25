"""Render trusted, local parameter metadata; selecting a metric needs no I/O."""

from html import escape

from garmin_database.application.parameter_descriptions import parameter_description


def parameter_help(parameter):
    if not parameter:
        return "Wybierz parametr, aby zobaczyć jego znaczenie i opis sposobu pomiaru."
    description = parameter_description(parameter)
    paragraphs = [f"<b>{escape(description['meaning'])}</b>"]
    for label, field in (
        ("Sposób pomiaru", "measurement"),
        ("Interpretacja", "limitations"),
        ("W aplikacji", "presentation"),
    ):
        paragraphs.append(f"<b>{label}:</b> {escape(description[field])}")
    sources = " · ".join(
        f'<a href="{escape(source["url"], quote=True)}">{escape(source["title"])}</a>'
        for source in description["sources"]
    )
    paragraphs.append(
        f"Źródła Garmin: {sources}. Weryfikacja: {description['reviewed_on']}."
    )
    return "<br>".join(paragraphs)
