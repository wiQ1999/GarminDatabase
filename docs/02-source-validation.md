# Źródło danych i zasady weryfikacji

## Obsługiwane źródło

Aplikacja używa `Garmin.download_health_snapshot(requested_date)` z przypiętej biblioteki `garminconnect`. Metoda pobiera dzienny ZIP z `/download-service/files/wellness/{requested_date}`. Ręcznym odpowiednikiem jest Garmin Connect → Informacje o koncie → „Eksportuj dane dotyczące dobrostanu” dla wskazanej daty.

To nieoficjalny endpoint. Dostępność archiwum zależy od Garmin, konta i daty. Aplikacja nie zastępuje nieudanego pobrania danymi z innych endpointów i nie dodaje osobnego źródła treningów. Zgodność jednej próbki nie gwarantuje dostępności wszystkich dat ani wszystkich danych widocznych w Garmin Connect.

Wersje bibliotek są określone w `requirements-probe.txt`, `requirements-analysis.txt` i `pyproject.toml`; procedurę instalacji opisuje [uruchamianie](12-running-and-testing.md).

## Dzienne archiwum a pliki FIT

Żądanie dla wybranej daty zwraca jedno archiwum ZIP, które może zawierać wiele plików FIT różnych kategorii. Liczba i zawartość plików zależą od danych dostępnych na koncie Garmin. Data żądania jest metadanym archiwum: zawarte w nim pomiary nie muszą ograniczać się do tego dnia. Kolejność wpisów ZIP nie jest chronologiczną kolejnością pomiarów. Garmin opisuje dzienny eksport wellness jako ZIP z oryginalnymi plikami FIT w [instrukcji eksportu danych](https://support.garmin.com/de-DE/?faq=W1TvTPW8JZ6LfJSfK512Q8).

Synchronizacja urządzenia może udostępnić w Garmin Connect dane, których brakowało przy wcześniejszym eksporcie. Zaobserwowano, że późniejszy eksport tego samego dnia zawierał dodatkowy FIT, a wcześniej dostępne pliki pozostały identyczne. Jest to obserwacja, a nie gwarancja Garmin: nie ustalono, że pliki FIT nigdy się nie zmieniają, że każda synchronizacja tworzy jeden plik ani po jakim czasie dzień staje się kompletny. Przedział czasów w FIT nie określa częstotliwości jego publikacji.

Ponowne pobranie może zmienić hash całego ZIP-u nawet przy identycznej zawartości FIT. Zmian danych nie należy wnioskować z hasha kontenera: porównanie wymaga hashy rozpakowanych plików i ich pochodzenia. Deduplikacja identycznych FIT po SHA-256 nie dowodzi braku nakładających się pomiarów w różnych plikach. Obecna aplikacja zachowuje pierwszy ZIP i nie aktualizuje automatycznie zakończonych dni; importer odrzuca inny hash ZIP dla zarejestrowanego dnia. Obsługa ponownego pobierania i zmienionych archiwów wymaga osobnej zmiany aplikacji.

## Oryginał i dekodowanie

ZIP jest zachowywany bez ponownego pakowania. FIT odczytuje się bez trwałego rozpakowywania całego archiwum. Strukturalny dekoder `fitdecode` dostarcza fizyczne definicje i wartości raw, a przypięty publiczny profil Garmin FIT SDK — nazwy, jednostki i reguły interpretacji.

Nazwy plików i wiadomości nie dowodzą dostępności konkretnej metryki. Brak nazwy w profilu nie powoduje odrzucenia pola; dane pozostają pod identyfikatorami źródłowymi. Pokrycie strukturalne i rozpoznanie semantyki są różnymi informacjami. Reguły zachowania danych opisują [architektura](03-architecture.md) i [schemat](10-postgresql-schema.md).

## Weryfikacja zgodności archiwów

Porównanie ręcznego i automatycznego eksportu obejmuje poprawność ZIP, listę wpisów, rozmiary i SHA-256 rozpakowanej zawartości. Należy porównać też multizbiór hashy niezależnie od nazw i kolejności. Różna kompresja lub metadane ZIP nie muszą oznaczać zmiany FIT.

Jeżeli FIT się różnią, sprawdza się definicje, typy, wartości, jednostki, czasy i liczbę rekordów. Sama zgodność liczby plików lub wiadomości nie dowodzi zgodności wartości. Brak danych i błędy sieciowe muszą zachować odrębne statusy zgodnie z [synchronizacją](04-synchronization.md).

Pomocniczy `scripts/probe_wellness.py` porównuje dwa lokalne ZIP (`--reference`, `--candidate`) albo pobiera jedną próbkę po lokalnym logowaniu. Nie zastępuje zwykłego procesu pobierania/importu w aplikacji. `scripts/analyze_fit_inventory.py` i `scripts/render_fit_inventory_docs.py` służą analizom metadanych; ich wyniki są lokalnymi raportami poza `docs/`, a nie kontraktem aplikacji.

Źródła formatu: [protokół FIT](https://developer.garmin.com/fit/protocol/) i [oficjalny SDK Python](https://github.com/garmin/fit-python-sdk). Implementacja klienta: [python-garminconnect](https://github.com/cyberjunky/python-garminconnect). Lokalne wyniki prób i skanów przechowuje się w ignorowanych folderach.
