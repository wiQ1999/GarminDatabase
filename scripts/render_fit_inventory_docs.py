"""Render local FIT metadata reports outside the tracked product documentation."""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'local-notes/fit-reports'
    output.mkdir(parents=True, exist_ok=True)
    report = json.loads((ROOT / 'data/fit_inventory.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT / 'data/collection.json').read_text(encoding='utf-8'))
    summary = report['summary']
    rows = report['fields']
    category_dates = defaultdict(list)
    for day, record in manifest['days'].items():
        for entry in record.get('files', []):
            category_dates[Path(entry['name']).stem.partition('_')[2]].append(day)
    catalog = [
        '# Katalog pól FIT z całej pobranej historii', '',
        'Wygenerowany przez `scripts/render_fit_inventory_docs.py` z lokalnego raportu '
        '`data/fit_inventory.json`. Nie zawiera wartości pomiarów. '
        'Nazwy i jednostki opisują pokrycie profilu, nie interpretację zdrowotną.', '',
        f"Zakres: {summary['archives']} archiwa, {summary['file_occurrences']} wystąpień FIT; "
        f"{summary['field_variants']} wariantów pól, w tym {summary['expanded_field_variants']} rozwinięć parsera.", '',
        'Wariant rozróżnia numer wiadomości, numer pola, przestrzeń deweloperską, nazwę i '
        'status rozwinięcia. To nie jest liczba niezależnych parametrów zdrowia. '
        'Kolumna „źródło” oznacza fizyczne pole, „rozwinięcie” — wynik reguły FIT. '
        'Liczby wystąpień obejmują również identyczne pliki obecne w kilku archiwach.', '',
        '„Nieznane” oznacza brak publicznej semantyki w użytym profilu. '
        'Nazwa z nowszego SDK jest osobną kolumną, nie potwierdzeniem dekodowania przez fitdecode.', '',
    ]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['message_num']].append(row)
    known_messages = []
    for number, fields in sorted(grouped.items()):
        parser_name = fields[0]['message_name']
        name = fields[0].get('sdk_message_name') or parser_name
        count = report['message_counts'][str(number)]
        catalog.extend([
            f'## {number}: {name}', '',
            f'Nazwa w parserze strukturalnym: `{parser_name}`.', '',
            f"Wiadomości: {count}. Kategorie: {', '.join(sorted(set(c for f in fields for c in f['categories'])))}.", '',
            '| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |',
            '| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |',
        ])
        for field in fields:
            arrays = ','.join(map(str, field['array_lengths'])) or '—'
            origin = 'rozwinięcie' if field['expanded'] else 'źródło'
            if field['developer_index'] is not None:
                origin += f"; developer {field['developer_index']}"
            sdk_units = field.get('sdk_units')
            unit = field['units'] or (','.join(map(str, sdk_units)) if isinstance(sdk_units, list) else sdk_units) or '—'
            catalog.append(f"| {field['field_num']} | {field['name']} | {field['sdk_name'] or '—'} | "
                f"{unit} | {','.join(field['base_types'])} | {arrays} | {origin} | "
                f"{field['count']} | {field['null_count']} |")
        catalog.append('')
        if not name.startswith('unknown_'):
            names = sorted(set(field['name'] if field['parser_named'] else field['sdk_name']
                               for field in fields if field['parser_named'] or field['sdk_name']))
            known_messages.append((number, name, count, names))
    (output / '09-fit-field-catalog.md').write_text('\n'.join(catalog), encoding='utf-8')
    lines = [
        '# Analiza pełnej pobranej historii FIT', '',
        'Raport lokalnego skanu. Analiza dotyczy plików uzyskanych z jednego endpointu dobrostanu, '
        'nie wszystkich informacji dostępnych na platformie Garmin Connect.', '',
        '## Metoda', '',
        'Każdy ZIP otwarto lokalnie, a FIT odczytywano pojedynczo. Nie rozpakowywano plików na dysk '
        'ani nie przekazywano pełnych pomiarów do kontekstu rozmowy. Raport przechowuje tylko '
        'metadane, liczby, typy, zakres czasu i katalog pól. Identyczne FIT deduplikowano '
        'po SHA-256 na czas dekodowania, zachowując liczbę ich wystąpień.', '',
        f"Parser: fitdecode {report['parser_versions']['fitdecode']}, CRC i błędy w trybie RAISE. "
        f"Kontrola uzupełniająca: oficjalne Garmin FIT SDK {report['parser_versions']['garmin-fit-sdk']}, "
        'bez skalowania, zamiany enumów, rozwijania komponentów ani łączenia tętna. SDK sprawdzono '
        'na jednym reprezentancie każdego wykrytego zestawu pól, nie na wszystkich plikach. '
        'Zgodność liczby wiadomości nie dowodzi zgodności każdej wartości.', '',
        'Źródła zasad formatu: [protokół FIT](https://developer.garmin.com/fit/protocol/) '
        'oraz [oficjalny SDK Python](https://github.com/garmin/fit-python-sdk). '
        'Opcje rozwijania subpól i komponentów są transformacjami profilu FIT, '
        'które trzeba odróżniać od fizycznych pól źródła.', '',
        '## Wyniki', '',
        '| Pozycja | Wynik |', '| --- | ---: |',
    ]
    metrics = [
        ('Archiwa ZIP', 'archives'), ('Rozmiar ZIP, bajty', 'archive_bytes'),
        ('Rozmiar FIT po rozpakowaniu, bajty', 'uncompressed_bytes'),
        ('Wystąpienia FIT', 'file_occurrences'), ('Unikatowe treści FIT', 'unique_file_hashes'),
        ('Wiadomości FIT, z powtórzeniami plików', 'messages'),
        ('Typy wiadomości', 'message_types'), ('Warianty pól', 'field_variants'),
        ('Warianty fizycznych pól', 'stored_field_variants'),
        ('Warianty rozwinięć parsera', 'expanded_field_variants'),
        ('Wystąpienia fizycznych pól', 'stored_field_occurrences'),
        ('Nazwane wystąpienia fizycznych pól, %', 'named_occurrence_percent'),
        ('Nieznane warianty fizycznych pól', 'unknown_stored_field_variants'),
        ('Warianty nazwane tylko w nowszym SDK', 'sdk_only_named_variants'),
        ('Nazwane wystąpienia po uzupełnieniu profilem SDK, %', 'public_profile_named_occurrence_percent'),
        ('Nieznane warianty po uzupełnieniu profilem SDK', 'public_profile_unknown_stored_variants'),
        ('Błędy dekodowania FIT', 'fit_decode_errors'),
        ('Ostrzeżenia parsera, z powtórzeniami', 'warning_occurrences'),
        ('Reprezentanci sprawdzeni SDK', 'sdk_signature_checks'),
        ('Próby SDK z błędem', 'sdk_checks_with_errors'),
        ('Próby SDK z inną liczbą wiadomości', 'sdk_message_count_mismatches'),
    ]
    lines.extend(f'| {label} | {summary[key]} |' for label, key in metrics)
    stored = [row for row in rows if not row['expanded']]
    lines.extend([
        f"| Warianty fizycznych pól z tablicami | {sum(bool(row['array_lengths']) for row in stored)} |",
        f"| Warianty z nieważnymi elementami tablic | {sum(row['contains_null_array'] for row in stored)} |",
        f"| Warianty z liczbami poza signed int64 | {sum(row['outside_signed_int64'] for row in stored)} |",
        f"| Warianty Developer Data | {sum(row['developer_index'] is not None for row in stored)} |",
    ])
    lines.extend([
        '', '## Dostępność historii', '',
        f"Pierwsze niepuste archiwum: **{summary['first_archive']}**, ostatnie: **{summary['last_archive']}**. "
        f"Ciągła sekwencja dostępnych archiwów zaczyna się **{summary['continuous_archive_history_from']}**. "
        f"Pozostaje **{summary['unresolved_days']}** dni z odpowiedzią 404 oznaczoną jako nierozstrzygnięta.", '',
        'Zakres archiwów opisuje dostępność tego zbioru, nie początek używania urządzenia. '
        'Brak ZIP na inne daty nie rozstrzyga, czy pomiary nigdy nie istniały, '
        'czy nie są udostępniane przez ten endpoint.', '',
        f"Zakres rozpoznanych pól czasu UTC, obejmujący również metadane plików: "
        f"`{summary['min_known_utc_time']}` – `{summary['max_known_utc_time']}`. "
        'Nie obejmuje czasu nierozpoznanych prywatnych pól i nie dowodzi kompletności pomiarów.', '',
        '| Kategoria plików | Liczba wystąpień | Pierwszy ZIP | Ostatni ZIP |',
        '| --- | ---: | --- | --- |',
    ])
    for category, days in sorted(category_dates.items()):
        lines.append(f'| {category} | {len(days)} | {min(days)} | {max(days)} |')
    lines.extend([
        '', '## Rozpoznany zakres parametrów', '',
        'Poniżej wszystkie nazwane rodziny wiadomości i ich rozpoznane pola. Obejmują zarówno '
        'pomiary, jak i metadane techniczne. Szczegółowy katalog zawiera również każdą '
        'nierozpoznaną wiadomość i pole, jednostki, tablice i liczbę wystąpień.', '',
        '| Nr | Wiadomość | Rozpoznane pola |', '| ---: | --- | --- |',
    ])
    for number, name, count, fields in known_messages:
        lines.append(f"| {number} | {name} | {', '.join(fields)} |")
    lines.extend([
        '', '## Ograniczenia i decyzje', '',
        'Pokrycie strukturalne (odczyt bajtów i wiadomości) i pokrycie semantyczne '
        '(znaczenie, jednostka, skala) to odrębne wyniki. Brak wyjątku parsera nie oznacza, '
        'że rozumiemy każdą metrykę. W szczególności wiele pól METRICS i niektóre serie '
        'WELLNESS pozostają identyfikatorami numerycznymi. Nie przypisujemy im nazw '
        'Body Battery, Training Readiness ani innych nazw na podstawie przypuszczeń.', '',
        'Pliki ACTIVITY obecne wewnątrz ZIP zachowujemy zgodnie z zasadą '
        'pełnego zachowania źródła. Ich obecność nie stanowi dowodu pełnej historii '
        'treningów; osobne pobieranie aktywności pozostaje poza zakresem.', '',
        'Tablice, nieważne wartości, subpola i komponenty wymagają reprezentacji bardziej '
        'ogólnej niż tabela z jednym zestawem kolumn zdrowotnych. Ustalony '
        '[schemat PostgreSQL](../../docs/10-postgresql-schema.md) zachowuje fizyczne pola oraz osobny katalog '
        'ich interpretacji. Reguły podsumowań opisuje dokumentacja aplikacji.', '',
        'Raport obejmuje rozmiary źródeł. Baza i JSON mają narzut struktury; nie można utożsamić go '
        'z rozmiarem ZIP ani obiecać zmieszczenia szczegółowych 90 dni w kontekście AI.', '',
        '## Odtworzenie analizy', '', '```powershell',
        r'.\.venv\Scripts\python.exe -m pip install -r requirements-analysis.txt',
        r'.\.venv\Scripts\python.exe scripts/analyze_fit_inventory.py',
        r'.\.venv\Scripts\python.exe scripts/render_fit_inventory_docs.py', '```', '',
        'Raport szczegółowy: `data/fit_inventory.json` (ignorowany przez Git). '
        'Przejściowy checkpoint zawiera tylko metadane i jest usuwany po udanej analizie. '
        'Wyniki dla ograniczenia `--limit` służą wyłącznie próbie skryptu i nie zastępują pełnego skanu. '
        'Pełny katalog tego skanu: [09-fit-field-catalog.md](09-fit-field-catalog.md).',
    ])
    (output / '08-fit-analysis.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Wrote local reports in local-notes/fit-reports')


if __name__ == '__main__':
    main()
