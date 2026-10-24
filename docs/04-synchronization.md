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

„Pobierz dane” wykonuje pobieranie i import do PostgreSQL. Osobna operacja ponownego przetwarzania korzysta wyłącznie z lokalnych ZIP. Pasek postępu pokazuje aktualny dzień, etap i licznik ukończonych dni. „Zatrzymaj” bezpiecznie kończy pracę z zachowaniem transakcji i postępu. Zamknięcie okna podczas pracy wymaga potwierdzenia zatrzymania i wyjścia. Zwykłe zamknięcie kończy aplikację; pierwsza wersja nie pracuje w zasobniku ani według harmonogramu. Szczegóły w [specyfikacji UI](11-desktop-ui.md).

## Logowanie

Logowanie odbywa się w formularzu ustawień Windows: e-mail, maskowane hasło i kod MFA, jeśli konto go wymaga. Hasło i kod nie są zapisywane. Sesja jest przechowywana poza projektem i bazą, w `%LOCALAPPDATA%/GarminDatabase/auth/session.bin`, zaszyfrowana DPAPI w zakresie użytkownika Windows. Wygaśnięcie sesji wymaga ponownego logowania i nie niszczy istniejących danych. Przeniesienie na inny komputer wymaga nowego logowania. Import lokalny i odczyty MCP nie wymagają logowania Garmin.

## Polecenia realizowane przez moduł CLI

```text
python -m garmin_database.cli sync
python -m garmin_database.cli sync --from 2024-01-01 --to 2026-09-30
python -m garmin_database.cli status
python -m garmin_database.cli reprocess --from 2024-01-01
```

`sync` nadgania brakujące dni do wczoraj. `reprocess` działa wyłącznie na lokalnych archiwach. Aktualizowanie archiwów przez ponowne pobranie to osobny, późniejszy etap.
