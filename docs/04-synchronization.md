# Synchronizacja i obsługa błędów

## Reguły pierwszej wersji

1. Ustal aktualną datę w `Europe/Warsaw`; maksymalny dzień importu to wczoraj. Brak dodatkowego opóźnienia po północy.
2. Domyślny początek historii: 2024-01-01. Użytkownik może podać węższy okres.
3. Sprawdź dni chronologicznie. Pomiń poprawnie pobrane dni oraz potwierdzone dni bez danych.
4. Jeżeli poprawny ZIP istnieje lokalnie, zarejestruj go i przetwórz bez pobierania.
5. Pobierz brakujący dzień, zweryfikuj ZIP i zapisz oryginał. Błąd nie oznacza zakończenia dnia.
6. Przetwórz ZIP do SQLite. Błąd parsera nie unieważnia udanego pobrania; ponawiaj przetwarzanie lokalnego pliku.
7. Wyświetl liczbę dni pobranych, pominiętych, bez danych i z błędem. W przyszłym trybie bez UI przy błędach zwróć niezerowy kod zakończenia; w aplikacji Windows pokaż status i bezpieczne szczegóły błędu.

Nie aktualizujemy automatycznie zakończonych dni. Użytkownik świadomie akceptuje, że późniejsze zmiany Garmin nie zostaną w tej wersji pobrane.

## Stany

- Pobranie: `pending`, `downloaded`, `no_data`, `failed`.
- Przetwarzanie: `pending`, `complete`, `partial`, `failed`.
- `partial` oznacza zachowanie części rekordów z jednoznacznym opisem ograniczeń; eksport musi sygnalizować niepełne dekodowanie.
- `no_data` wymaga udokumentowanej odpowiedzi potwierdzającej brak archiwum dla daty. 401, 403, 429, błędy serwera i nieznane 404 pozostają błędami, dopóki zachowanie endpointu nie zostanie zweryfikowane.

Sprawdzać cały zakres od 2024-01-01: nie kończyć wyszukiwania przy pierwszym dniu bez danych. Pierwsza data dostępnego archiwum i pierwszy czas odczytanego pomiaru to dwie różne informacje.

## Błędy i wznowienie

Żądania sekwencyjne, bez równoległego masowego pobierania. Timeouty i ograniczona liczba prób; opóźnienie zwiększane przy błędach przejściowych. Respektować `Retry-After`, jeśli dostępny. Po utrzymującym się 429 lub błędzie logowania zatrzymać pobieranie, zachować postęp i pozwolić wznowić kolejnym uruchomieniem. Parametry tempa ustalić podczas próby; nie wymyślać limitów Garmin.

Nie logować odpowiedzi zawierających zdrowotne dane, hasła, kody MFA, ciasteczka ani tokeny. W panelu szczegółów UI oraz przyszłym trybie bez UI wystarczą data, etap, status i bezpieczny kod błędu.

„Pobierz dane” wykonuje pobieranie i import do SQLite. Osobna operacja ponownego przetwarzania korzysta wyłącznie z lokalnych ZIP. Pasek postępu pokazuje aktualny dzień, etap i licznik ukończonych dni. „Zatrzymaj” bezpiecznie kończy pracę z zachowaniem transakcji i postępu. Zamknięcie okna podczas pracy wymaga potwierdzenia zatrzymania i wyjścia. Zwykłe zamknięcie kończy aplikację; pierwsza wersja nie pracuje w zasobniku ani według harmonogramu. Szczegóły w [specyfikacji UI](11-desktop-ui.md).

## Logowanie

Docelowe logowanie odbywa się w formularzu ustawień Windows: e-mail, maskowane hasło i kod MFA, jeśli konto go wymaga. Hasło i kod nie są zapisywane. Sesja jest przechowywana poza projektem i bazą, w `%LOCALAPPDATA%/GarminDatabase/auth/session.bin`, zaszyfrowana DPAPI w zakresie użytkownika Windows. Wygaśnięcie sesji wymaga ponownego logowania i nie niszczy istniejących danych. Przeniesienie na inny komputer wymaga nowego logowania. Istniejące skrypty próbne i historyczne nadal mają dotychczasowe logowanie konsolowe; nie są jeszcze docelowym UI.

## Planowane polecenia — jeszcze niezaimplementowane

```text
garmin-db sync
garmin-db sync --from 2024-01-01 --to 2026-10-09
garmin-db status
garmin-db reprocess --from 2024-01-01
```

`sync` nadgania brakujące dni do wczoraj. `reprocess` działa wyłącznie na lokalnych archiwach. Aktualizowanie archiwów przez ponowne pobranie to osobny, późniejszy etap.
