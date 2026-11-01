# Źródło danych i zasady weryfikacji

## Obsługiwane źródło

Aplikacja używa `Garmin.download_health_snapshot(requested_date)` z przypiętej biblioteki `garminconnect`. Metoda pobiera dzienny ZIP z `/download-service/files/wellness/{requested_date}`. Ręcznym odpowiednikiem jest Garmin Connect → Informacje o koncie → „Eksportuj dane dotyczące dobrostanu” dla wskazanej daty.

To nieoficjalny endpoint. Dostępność archiwum zależy od Garmin, konta i daty. Aplikacja nie zastępuje nieudanego pobrania danymi z innych endpointów i nie dodaje osobnego źródła treningów. Zgodność jednej próbki nie gwarantuje dostępności wszystkich dat ani wszystkich danych widocznych w Garmin Connect.

Wersje bibliotek są określone w `requirements-probe.txt`, `requirements-analysis.txt` i `pyproject.toml`; procedurę instalacji opisuje [uruchamianie](12-running-and-testing.md).

## Dzienne archiwum a pliki FIT

Żądanie dla wybranej daty zwraca jedno archiwum ZIP, które może zawierać wiele plików FIT różnych kategorii. Liczba i zawartość plików zależą od danych dostępnych na koncie Garmin. Data żądania jest metadanym archiwum: zawarte w nim pomiary nie muszą ograniczać się do tego dnia. Kolejność wpisów ZIP nie jest chronologiczną kolejnością pomiarów. Garmin opisuje dzienny eksport wellness jako ZIP z oryginalnymi plikami FIT w [instrukcji eksportu danych](https://support.garmin.com/de-DE/?faq=W1TvTPW8JZ6LfJSfK512Q8).

Synchronizacja urządzenia może udostępnić w Garmin Connect dane, których brakowało przy wcześniejszym eksporcie. Zaobserwowano, że późniejszy eksport tego samego dnia zawierał dodatkowy FIT, a wcześniej dostępne pliki pozostały identyczne. Jest to obserwacja, a nie gwarancja Garmin: nie ustalono, że pliki FIT nigdy się nie zmieniają, że każda synchronizacja tworzy jeden plik ani po jakim czasie dzień staje się kompletny. Przedział czasów w FIT nie określa częstotliwości jego publikacji.

Ponowne pobranie może zmienić hash całego ZIP-u nawet przy identycznej zawartości FIT. Zmian danych nie należy wnioskować z hasha kontenera: porównanie wymaga hashy rozpakowanych plików i ich pochodzenia. Deduplikacja identycznych FIT po SHA-256 nie dowodzi braku nakładających się pomiarów w różnych plikach. Aplikacja deduplikuje FIT w SQL niezależnie od kolejności wpisów ZIP. Pobierany ZIP pozostaje tylko w pamięci; ponowne pobranie może dodać nowe pochodzenia i pliki bez ponownego dekodowania kompletnych FIT.

## Oryginał i dekodowanie

ZIP pobrany z sieci jest walidowany i przetwarzany w pamięci, bez trwałego zapisu oryginału. Starsze lokalne ZIP pozostają dostępne dla poleceń CLI importu i ponownego dekodowania; aplikacja ich nie usuwa. FIT odczytuje się bez trwałego rozpakowywania całego archiwum. Strukturalny dekoder `fitdecode` dostarcza fizyczne definicje i wartości raw, a przypięty publiczny profil Garmin FIT SDK — nazwy, jednostki i reguły interpretacji.

Nazwy plików i wiadomości nie dowodzą dostępności konkretnej metryki. Brak nazwy w profilu nie powoduje odrzucenia pola; dane pozostają pod identyfikatorami źródłowymi. Pokrycie strukturalne i rozpoznanie semantyki są różnymi informacjami. Reguły zachowania danych opisują [architektura](03-architecture.md) i [schemat](10-postgresql-schema.md).

## Weryfikacja zgodności archiwów

Porównanie ręcznego i automatycznego eksportu obejmuje poprawność ZIP, listę wpisów, rozmiary i SHA-256 rozpakowanej zawartości. Należy porównać też multizbiór hashy niezależnie od nazw i kolejności. Różna kompresja lub metadane ZIP nie muszą oznaczać zmiany FIT.

Jeżeli FIT się różnią, sprawdza się definicje, typy, wartości, jednostki, czasy i liczbę rekordów. Sama zgodność liczby plików lub wiadomości nie dowodzi zgodności wartości. Brak danych i błędy sieciowe muszą zachować odrębne statusy zgodnie z [synchronizacją](04-synchronization.md).

Pomocniczy `scripts/probe_wellness.py` porównuje dwa lokalne ZIP (`--reference`, `--candidate`) albo pobiera jedną próbkę po lokalnym logowaniu. Nie zastępuje zwykłego procesu pobierania/importu w aplikacji. `scripts/analyze_fit_inventory.py` i `scripts/render_fit_inventory_docs.py` służą analizom metadanych; ich wyniki są lokalnymi raportami poza `docs/`, a nie kontraktem aplikacji.

Źródła formatu: [protokół FIT](https://developer.garmin.com/fit/protocol/) i [oficjalny SDK Python](https://github.com/garmin/fit-python-sdk). Implementacja klienta: [python-garminconnect](https://github.com/cyberjunky/python-garminconnect). Lokalne wyniki prób i skanów przechowuje się w ignorowanych folderach.

## Porównanie Garmin Connect, bazy, wykresu i MCP

Porównanie ma trzy niezależne poziomy:

1. Oryginalny FIT: identyfikuj go po SHA-256, odkoduj niezależnie oficjalnym SDK Garmin i porównaj multizbiór wartości oraz czasów z aktywnym dekodowaniem SQL. Nowy sieciowy ZIP pozostaje w pamięci. Różnica między dwoma dekoderami wymaga diagnozy przed zmianą interpretacji.
2. Kanały aplikacji: porównaj odczyt SQL z danymi przekazywanymi do wykresu oraz MCP, łącznie ze wszystkimi stronami, ważnością i nieznanym czasem. Nie zmieniaj globalnej polityki udostępniania na potrzeby testu; użyj tymczasowej konfiguracji kontrolowanego procesu MCP.
3. Garmin Connect: porównuj tę samą metrykę, zakres, strefę czasową i definicję statystyki. Źródłowa średnia nocna HRV nie jest średnią pięciominutowych próbek doby. Statystyki snu/czuwania nie są pełną dobą. Faza snu w pojedynczym rekordzie FIT nie jest czasem trwania fazy. Rozbieżności punktów prezentacji nie stanowią same w sobie dowodu uszkodzenia importu.

`scripts/verify_garmin_html.py` analizuje zapisane lokalnie HTML bez uruchamiania JavaScript. Obsługuje liczbowe etykiety punktów HRV, stresu i faz snu oraz wybrane źródłowe karty snu/HRV/tętna spoczynkowego. Raportuje dokładne dopasowania i diagnostykę przesunięcia czasu, bez automatycznej korekty. Kartę porównuje z ostatnią ważną obserwacją źródłową w danym dniu. Sama nazwa pliku nie dowodzi, jaki zakres pokazuje zapisany DOM; przed interpretacją wyniku sprawdź widok i wybraną datę.

```powershell
python scripts/verify_garmin_html.py --input verification --settings-file ŚCIEŻKA_DO_SETTINGS_JSON --report local-notes/garmin-verification.json
```

Geometria SVG, ogólne etykiety „Series” albo statystyka o innym znaczeniu nie wystarczają do dowodu dokładnej zgodności. Raport jawnie zachowuje takie ograniczenia i rozbieżności; nie traktuj pominiętego widoku jako testu zaliczonego. HTML, raporty i wyniki niezależnego SDK pozostają poza Git. Raport narzędzia zawiera liczniki i metadane, bez wartości pomiarów, sesji, DSN i treści wyjątków.

### Pełna analiza trzech wariantów wyjścia

`scripts/compare_garmin_sources.py` porównuje każdy lokalny HTML osobno z danymi przekazywanymi do wykresu (`Queries.chart` i przygotowanie serii), rzeczywistym procesem MCP stdio oraz ponownie odczytanymi plikami produkcyjnego eksportera. Kontrola obejmuje szczegóły, historię dzienną i miesięczną, wszystkie strony MCP, duplikaty, ważność, nieznany czas i pochodzenie. Zestawienie odnotowuje udokumentowane zaokrąglenie MCP, bez zaokrąglania danych źródłowych i eksportów. Nie jest testem zgodności pikseli renderera.

Zakres i rodzaj widoku pochodzą z zapisanego DOM, a nie z nazwy pliku. Odczyt obejmuje punkty, karty, liczbowe podsumowania dostępności i komórki tabel dziennych/tygodniowych. Każda komórka tabeli jest porównywana w zakresie jej wiersza, z zachowaniem jawnego roku i granic tygodnia. Karty i punkty bez jednoznacznego odpowiednika mają osobny status, także gdy przechowywana jest podobnie nazwana miara. Dopasowanie liczb po wyprowadzeniu statystyki z serii nie potwierdza równoważności algorytmów Garmin. Diagnostyka przesunięcia czasu oraz kontynuacji kategorii pomiędzy obserwacjami nie zmienia reguły ścisłego porównania.

Porównanie zachowuje kolejność agregacji: „Średnia wysokiego” jest średnią dziennych maksimów, a okresowe minimum/maksimum stresu dotyczy średnich dziennych. Średnia okresowych średnich dziennych jest nieważona; nie zastępuje jej średnia wszystkich próbek. Wykres dziennych średnich nie udostępnia dziennych maksimów — takie porównanie otrzymuje status braku wartości kanału. Reguły raportu nie zmieniają kontraktu agregacji aplikacji.

Jeżeli ten sam dzień zawiera różne ważne podsumowania źródłowe, raport zgłasza `ambiguous_source_observations`. Porównanie ostatniego kandydata pozostaje diagnostyką, także gdy liczba pasuje do HTML. Nie wybieraj arbitralnie pierwszego, ostatniego ani najbliższego karcie rekordu jako ostatecznego podsumowania Garmin Connect. Powtarzające się równe wartości nie są konfliktem.

```powershell
python scripts/compare_garmin_sources.py --input verification --settings-file ŚCIEŻKA_DO_SETTINGS_JSON --mcp-executable ŚCIEŻKA_DO_GarminDatabaseMCP.exe --output local-notes/garmin-comparison
```

Narzędzie tworzy prywatną konfigurację walidacji, nie zmieniając polityki udostępniania aplikacji. Odczytuje PostgreSQL bez modyfikacji danych i wyłącza publikację odtwarzalnego cache. Dla parametrów pustych w dniu kontrolnym szuka uzupełniającego dnia z obserwacjami; pusty wynik nie jest dowodem zgodności wartości. Raport obejmuje cały katalog i jawnie wskazuje parametry nieudostępniane przez MCP. Wymagane są zależności desktop/MCP i dostęp do istniejącej bazy, bez logowania Garmin i nowych pobrań.

Dla pięciu metryk średnich kontrola `raw_daily_summary` niezależnie przelicza z obserwacji SQL średnie (`math.fsum`), ekstrema, liczniki jakości i granice czasu. Nie używa reduktora aplikacji ani cache do wyznaczenia oczekiwanego wyniku. Sprawdza również brakujące, dodatkowe i powielone dni; zgodność kanałów korzystających ze wspólnego cache nie zastępuje tej kontroli. Tolerancja arytmetyki zmiennoprzecinkowej wynosi `abs_tol=1e-10`, `rel_tol=1e-12`, bez zaokrąglania pomiarów.

W katalogu wyniku powstają `comparison.html`, `comparison.json`, `differences.csv`, lokalizatory punktów w `point-differences.csv` oraz prywatne pliki eksportu w `exports/`. Lokalizatory odtwarza się z plików eksportu po ścisłym potwierdzeniu ich równoważności z wariantami i kontroli liczników dopasowania; indeks kanału dotyczy serii znormalizowanej. Raporty zawierają liczniki, nazwy parametrów i lokalizatory, a pomiary pozostają w źródłach i wygenerowanych eksportach. Nie dodawaj tego katalogu do Git. Materiał bez daty, wymaganych wartości lub odpowiedniego widoku jest wynikiem nieweryfikowalnym, nigdy zaliczonym.
