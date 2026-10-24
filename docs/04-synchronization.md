# Synchronizacja i obsługa błędów

## Przebieg synchronizacji

1. Ustal aktualną datę w `Europe/Warsaw`; maksymalny dzień importu to wczoraj. Brak dodatkowego opóźnienia po północy.
2. Domyślny początek historii: 2024-01-01. Użytkownik może podać węższy okres.
3. Sprawdź dni chronologicznie. Pomiń poprawnie pobrane dni oraz potwierdzone dni bez danych.
4. Jeżeli poprawny ZIP istnieje lokalnie, zarejestruj go i przetwórz bez pobierania.
5. Pobierz brakujący dzień, zweryfikuj ZIP i zapisz oryginał. Błąd nie oznacza zakończenia dnia.
6. Przetwórz ZIP do PostgreSQL. Błąd parsera nie unieważnia udanego pobrania; ponawiaj przetwarzanie lokalnego pliku.
7. Wyświetl liczbę dni pobranych, pominiętych, bez danych i z błędem. CLI zwraca niezerowy kod zakończenia przy błędzie; aplikacja Windows pokazuje status i bezpieczne szczegóły błędu.

Nie aktualizujemy automatycznie zakończonych dni. Użytkownik świadomie akceptuje, że późniejsze zmiany Garmin nie zostaną w tej wersji pobrane.

## Stany

- Pobranie: `pending`, `downloaded`, `empty_zip`, `not_found_unverified`, `no_data_confirmed`, `failed`, `local_invalid` — zgodnie z ograniczeniami schematu SQL.
- Przetwarzanie pojedynczego FIT: brak ukończonego wyniku, `complete`, `partial`, `failed`; przerwany przebieg ma osobny status `interrupted`.
- `partial` oznacza zachowanie części rekordów z jednoznacznym opisem ograniczeń; eksport musi sygnalizować niepełne dekodowanie.
- `no_data_confirmed` wymaga udokumentowanej odpowiedzi potwierdzającej brak archiwum dla daty. 401, 403, 429, błędy serwera i nieznane 404 pozostają błędami, dopóki zachowanie endpointu nie zostanie zweryfikowane. Znane `not_found_unverified` są pomijane przy wznowieniu, nadal widoczne jako nierozstrzygnięte; nie stają się potwierdzonym brakiem danych.

Sprawdzać cały zakres od 2024-01-01: nie kończyć wyszukiwania przy pierwszym dniu bez danych. Pierwsza data dostępnego archiwum i pierwszy czas odczytanego pomiaru to dwie różne informacje.

## Błędy i wznowienie

Żądania są sekwencyjne, bez równoległego masowego pobierania. Klient ma timeouty; aplikacja podejmuje najwyżej trzy próby na dzień z lokalną przerwą 3 s i zwiększeniem odstępu po błędzie. Nagłówek `Retry-After`, w sekundach lub jako data HTTP, zwiększa odstęp przed ponowieniem. 401, 403 i 429 zatrzymują bieżące pobieranie; także pięć kolejnych nieudanych dni powoduje zatrzymanie. Postęp jest zachowany. Przed ręcznym wznowieniem po 429 należy odczekać; aplikacja nie ponawia automatycznie takiego żądania. To parametry aplikacji, nie deklarowane limity Garmin.

Nie logować odpowiedzi zawierających zdrowotne dane, hasła, kody MFA, ciasteczka ani tokeny. W panelu szczegółów UI oraz przyszłym trybie bez UI wystarczą data, etap, status i bezpieczny kod błędu.

HTTP 404 jest opisywane jako brak zwróconego archiwum dla konkretnej daty, bez rozstrzygania, czy konto nie ma wtedy danych. Synchronizacja sprawdza kolejne dni. Przy wznowieniu zapisany `not_found_unverified` nie wysyła ponownego żądania, ale pozostaje w liczbie nierozstrzygniętych dni i otrzymuje osobny komunikat w szczegółach. Nie wolno prezentować takiego wznowienia jako pełnego sukcesu.

Błąd importu FIT emituje komunikat z datą, numerem pliku w archiwum i klasą błędu; oryginalny ZIP pozostaje zachowany, a nieukończona transakcja FIT jest wycofana. Po zakończeniu z błędami lub nierozstrzygniętymi dniami UI automatycznie rozwija szczegóły i dopisuje podsumowanie. Nowa operacja czyści panel poprzedniej operacji.

„Pobierz dane” wykonuje pobieranie i import do PostgreSQL. Osobna operacja ponownego przetwarzania korzysta wyłącznie z lokalnych ZIP. Pasek postępu pokazuje aktualny dzień, etap i licznik ukończonych dni. „Zatrzymaj” bezpiecznie kończy pracę z zachowaniem transakcji i postępu. Zamknięcie okna podczas pracy wymaga potwierdzenia zatrzymania i wyjścia. Zwykłe zamknięcie kończy aplikację; pierwsza wersja nie pracuje w zasobniku ani według harmonogramu. Szczegóły w [specyfikacji UI](11-desktop-ui.md).

## Logowanie

Logowanie odbywa się w formularzu ustawień Windows: e-mail, maskowane hasło i kod MFA, jeśli konto go wymaga. Hasło i kod nie są zapisywane. Sesja jest przechowywana poza projektem i bazą, w `%LOCALAPPDATA%/GarminDatabase/auth/session.bin`, zaszyfrowana DPAPI w zakresie użytkownika Windows. Wygaśnięcie sesji wymaga ponownego logowania i nie niszczy istniejących danych. Przeniesienie na inny komputer wymaga nowego logowania. Import lokalny i odczyty MCP nie wymagają logowania Garmin.

## Polecenia realizowane przez moduł CLI

```text
python -m garmin_database.bootstrap.cli sync
python -m garmin_database.bootstrap.cli sync --from 2024-01-01 --to 2026-09-30
python -m garmin_database.bootstrap.cli status
python -m garmin_database.bootstrap.cli reprocess --from 2024-01-01
```

`sync` nadgania brakujące dni do wczoraj. `reprocess` działa wyłącznie na lokalnych archiwach. Aktualizowanie archiwów przez ponowne pobranie to osobny, późniejszy etap.

## Wydajność i warunki przyszłej współbieżności

Obecna implementacja obsługuje dzień sekwencyjnie: przerwa, pobranie, walidacja i zapis ZIP, import wszystkich jego FIT. Worker Qt odciąża okno, ale nie uruchamia równoległych importerów. Lokalne kompletne ZIP również przechodzą odczyt SHA-256 i kontrolę CRC przed rozpoznaniem ukończonego importu. Podsumowania powstają dopiero na żądanie odczytu; import ich nie przelicza dla każdego dnia.

Blokada writera obejmuje całą synchronizację, a jej zagnieżdżenie działa wyłącznie na tym samym obiekcie i wątku. Drugi wątek importera otrzymuje błąd zajętego writera. Niezależnie od tej blokady triggery `file_decodes` i `archive_entries` aktualizują jeden wiersz `dataset_state`; blokada tego wiersza trwa do końca transakcji FIT. Usunięcie samej blokady aplikacji nie zapewni równoległego zapisu. Współdzielenie jednego połączenia psycopg przez taski także nie daje równoległych zapytań ani niezależnych transakcji.

Kierunek optymalizacji do realizacji: najpierw ograniczyć liczbę synchronizacji SQL przez większe, ograniczone pamięciowo partie pól i rozważyć `COPY`. Kolejny etap to nakładanie pojedynczego sekwencyjnego pobierania na import poprzedniego ZIP, z ograniczoną kolejką gotowych archiwów i jednym właścicielem zapisów SQL. Należy zachować zasady odstępów sieciowych, zatrzymania po 401/403/429, wznowienia i transakcji per FIT. Próby powinny mieć jednego właściciela: parametr SDK `retry_attempts` oznacza dodatkowe ponowienia, więc obecne `retry_attempts=1` może ponowić żądanie wewnątrz każdej z trzech prób aplikacji.

Równoległe dekodowanie CPU można rozważyć dopiero po pomiarze zoptymalizowanego zapisu. Jednostką pracy jest cały FIT; kolejność ramek, redefinicje, skrócone timestampy i stan dekodera wewnątrz pliku muszą zostać zachowane. Procesy robocze powinny zwracać ograniczone partie danych do pojedynczego writera, bez współdzielenia połączenia PostgreSQL, klienta Garmin i sesji. Pakowanie procesów wymaga osobnego odbioru Windows/PyInstaller. Ten potok i procesy robocze nie są obecnie dostępne.

Kolejność importu całych FIT nie zmienia ich typowanych wartości, skalowania ani przypisania rozpoznanych czasów do dni Europe/Warsaw. Deduplikacja pozostaje oparta o SHA-256 całego FIT; różne pliki z takimi samymi czasami nie mogą być scalane jako duplikaty. Średnia dzienna obejmuje wszystkie poprawne próbki, a okresowa używa wag `valid_count`; nie wolno uśredniać wyników tasków z jednakową wagą ani przypisywać całego FIT do dnia ZIP. Zmiana porządku sumowania zmiennoprzecinkowego może powodować drobne różnice numeryczne.

Obecny odczyt rozstrzyga identyczne czasy przez `fit_file_id`, `message_index` i `field_definition_id`. ID pliku zależy od kolejności pierwszej rejestracji, dlatego `last_value` oraz kolejność szczegółów przy takim remisie mogą zależeć od importu. Przed dopuszczeniem dowolnej kolejności potrzebny jest stabilny porządek oparty na treści FIT i pozycji w źródle, np. SHA-256 pliku, indeksie wiadomości oraz pozycji definicji/pola. Zmiana reguły wymaga unieważnienia cache przez wersję algorytmu oraz testów zgodności eksportu i MCP. Nie wolno deklarować pełnej niezależności wyników od kolejności na podstawie samej zgodności średnich.

Odbiór optymalizacji musi obejmować tę samą kolekcję syntetycznych FIT importowaną chronologicznie, odwrotnie i w przemieszanej kolejności: zgodność wartości fizycznych, deduplikacji, średnich i liczników, stabilne remisy czasów, dane przekraczające północ/DST, CRC, anulowanie po rozpoczęciu zapisu partii, wymianę wcześniejszego dekodowania, wznowienie i spójność cache. Pomiary czasu wykonuje się w osobnej bazie testowej, bez pomiarów zdrowotnych i bez sekretów w raportach.
