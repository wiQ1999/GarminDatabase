# Interfejs Windows i ustawienia aplikacji

Uzgodnione wymagania z 2026-10-11, zrealizowane w aplikacji opisanej w [instrukcji uruchamiania](12-running-and-testing.md). Dokument zastępuje wcześniejsze założenie pierwszej wersji konsolowej. Zakres pozyskiwania i zachowania danych pozostaje bez zmian.

## Uruchamianie i wygląd

- Windows 11, samodzielne okno uruchamiane z `.exe` w folderze aplikacji. Bez instalatora, konsoli, przeglądarki i konieczności osobnej instalacji Pythona. Można utworzyć skrót na pulpicie.
- Interfejs po polsku; polskie etykiety parametrów i oryginalna nazwa Garmin w krótkim opisie. Nazwy pól eksportu JSON pozostają zgodne ze specyfikacją eksportu.
- Jeden motyw: ciemne tło, grafitowe powierzchnie, jasny tekst, niebieskie akcenty. Wygląd wzorowany na Garmin Connect, proste menu po lewej i zawartość po prawej.
- Ikony podstawowych parametrów odtworzyć na podstawie trzech zrzutów Garmin Connect dostarczonych przez użytkownika. Zachować charakterystyczne symbole i kolory: tętno — czerwone serce, kroki — niebieskie ślady stóp, stres — pomarańczowa postać z symbolem napięcia, oddech — turkusowy symbol przepływu powietrza, HRV — serce z linią pulsu i oznaczeniem snu, piętra — turkusowe schody ze strzałką, kalorie — zielony płomień, intensywność — pomarańczowy stoper. Brakujące ikony przygotować w podobnym stylu.
- Pozostałe symbole na referencjach obejmują Body Battery, gotowość treningową, aklimatyzację saturacji, wiek sprawnościowy, stan wytrenowania, VO2 max, charakter obciążenia, ocenę wytrzymałości i próg mleczanowy. Referencje nie są dowodem dostępności tych parametrów w ZIP ani podstawą rozszerzenia źródła danych.

Zrzuty pozostają referencją wyglądu, nie źródłem wartości pomiarowych ani elementem repozytorium. Nie kopiować do dokumentacji widocznych prywatnych pomiarów. Realizacja używa PySide6 Essentials/Qt Widgets, wykresu QPainter, własnych symboli SVG wzorowanych na referencjach oraz PyInstaller onedir.

## Start

Pokazać ostatni pobrany dzień, stan importu do PostgreSQL, zakres historii, brakujące lub nierozstrzygnięte dni, dostępność parametrów i rozmiar danych. Nie utożsamiać niezweryfikowanych 404 z potwierdzonym brakiem danych.

Główny przycisk **„Pobierz dane”** pobiera brakujące archiwa do wczoraj według `Europe/Warsaw`, następnie przetwarza je do PostgreSQL. Poprawne lokalne archiwa wykorzystuje bez ponownego pobierania. Osobno dostępna jest operacja ponownego przetworzenia archiwów lokalnych bez żądań pobrania.

Postęp obejmuje pasek, aktualnie obsługiwany dzień i etap, licznik ukończonych dni oraz **„Zatrzymaj”**. Szczegóły błędów są dostępne w rozwijanym panelu bez sekretów i surowych danych zdrowotnych. Zatrzymanie zachowuje ukończone operacje; nieukończona transakcja nie jest prezentowana jako zakończony import. Wznowienie pomija ukończoną pracę.

Podczas pracy można przeglądać już zaimportowane dane. Zamknięcie okna przy aktywnej operacji pyta o zatrzymanie i wyjście. Aplikacja nie pozostaje w tle po zamknięciu; pobieranie pierwszej wersji uruchamia użytkownik.

## Dane

Lista rozpoznanych parametrów z ikonami i grupami: sen, serce i HRV, stres, oddychanie i saturacja, ruch, pozostałe. Pokazywać tylko parametry rozpoznane w danych użytkownika. Osobne reprezentacje, np. pomiar chwilowy i podsumowanie dzienne, zachowują odrębne etykiety.

Wybrany parametr jest prezentowany na prostym wykresie, bez tabeli rekordów i bez powiększania fragmentu. Najechanie kursorem pokazuje datę lub godzinę, wartość i jednostkę. Przerwy pozostają widoczne: brak interpolacji i łączenia linii przez rozpoznane luki. Podpis czasu określa strefę; niejednoznaczne czasy źródłowe nie otrzymują zgadywanej strefy.

Oś czasu ma podpisy pośrednie, do ośmiu na szerokim wykresie. Ich liczbę dobiera się do rzeczywistej szerokości napisów, aby nie nachodziły na siebie. Krótkie odcinki pokazują również sekundy, zakresy przekraczające północ — datę i godzinę, a dłuższa historia — daty. Przy zmianie czasu letniego podpisy godzin zawierają przesunięcie względem UTC. Znaczniki osi służą orientacji i nie są dodatkowymi pomiarami.

Wybór parametru, zmiana zakresu lub dat automatycznie odświeżają wykres. Przycisk „Pokaż wykres” został usunięty. Podczas odczytu na pierwszym planie wykresu widać animowane koło i napis „Ładowanie wykresu…”, a poprzedni obraz jest rozmyty i nie pokazuje tooltipów. Filtry pozostają dostępne. Przy szybkich zmianach UI pokazuje wynik ostatniego wyboru, pomijając starsze wyniki i błędy. Po aktualnym wyniku albo błędzie animacja znika; błąd usuwa poprzedni obraz, żeby nie udawał danych aktualnego parametru.

Zakresy: **Dzień**, **7 dni**, **30 dni**, **90 dni**, **Cała historia**, własny zakres. Początkowy zakres to 30 dni dla podsumowań; domyślny koniec to ostatni zakończony dzień. „Dzień” pokazuje oryginalne szczegóły. Dłuższe zakresy są dostępne dla `source_summary` oraz HRV, tętna chwilowego, oddechu, saturacji i stresu, dla których aplikacja liczy średnie dzienne. Podpis wykresu i tooltip jednoznacznie oznaczają obliczone średnie. Kategorie i pozostałe liczniki bez podsumowań Garmin zachowują wyszarzone opcje poza dniem i automatyczne przełączenie na „Dzień”. Datę początku można edytować tylko w „Własnym zakresie”.

| Okres | Prezentowane dane |
| --- | --- |
| Pojedynczy dzień | Szczegółowe pomiary dostępne w źródle oraz podsumowania Garmin, jeśli istnieją |
| Dłuższy okres | Podsumowania Garmin lub jawnie oznaczone średnie dzienne pięciu obsługiwanych parametrów pomiarowych |
| Kategorie i pozostałe liczniki bez podsumowań Garmin | Tylko „Dzień”; pozostałe filtry są wyszarzone, a poprzedni dłuższy zakres jest automatycznie korygowany |

Checkbox **„Linia trendu”** jest domyślnie odznaczony. Włącza przerywaną linię z podpisem „Trend liniowy (obliczony)”, dopasowaną metodą najmniejszych kwadratów względem rzeczywistego czasu. Obejmuje poprawne skończone wartości liczbowe aktualnego wykresu. Nie dodaje punktów w lukach ani nie zmienia próbek; sama prosta trendu jest wskazówką wizualną i może przebiegać przez okresy bez pomiarów. Checkbox jest niedostępny podczas ładowania, dla kategorii i przy braku co najmniej dwóch obserwacji z różnymi czasami. Wybór obowiązuje w bieżącym oknie, bez zapisu w ustawieniach.

Linia trendu jest obliczana wyłącznie na wykresie i nie jest podsumowaniem Garmin. Nie trafia do PostgreSQL lub JSON. Późniejsze wymaganie użytkownika wprowadza średnie i podsumowania historii w bazie i eksporcie; opisuje je [eksport](05-export.md). Nie redukować źródłowych próbek w bazie lub plikach szczegółowych na potrzeby UI. Zapytanie pobiera wybrany parametr i okres, a nie całą bazę. Nie dodawać ocen ani interpretacji medycznych.

Nierozpoznane pola zachować w PostgreSQL. UI pokazuje ich obecność i liczbę z jednoznaczną etykietą, że chodzi o warianty pól, a nie liczbę parametrów zdrowotnych; bez zgadywanych nazw i wykresów. Pełne rekordy można przeglądać narzędziem PostgreSQL, np. psql lub pgAdmin, poza zakresem interfejsu.

## Eksport

Wybór parametrów, zakresu historii, dziennego lub miesięcznego okresu obliczonych podsumowań, liczby ostatnich dni szczegółowych (domyślnie 90) i folderu nadrzędnego. Osobne `history/{parametr}.json` i `details/{parametr}.json`. Okres obliczonych podsumowań nie zmienia oryginalnych podsumowań Garmin. Nie ma zbiorczego `recent.json` ani opcji pełnych próbek w historii. Format i kompletność określa [specyfikacja eksportu](05-export.md).

Zapamiętywać ostatnie ustawienia. Każdy eksport tworzy unikatowy folder `GarminDatabase_DATA_CZAS`; nie usuwa i nie zastępuje poprzednich eksportów. Po zakończeniu pokazać folder, liczbę i łączny rozmiar plików oraz **„Otwórz folder eksportu”**, otwierający ostatni ukończony pakiet. Pliki zawierają dane i niezbędne etykiety, bez instrukcji dla AI.

## Ustawienia, sesja i lokalizacje

Formularz Garmin obejmuje e-mail, maskowane hasło i kod uwierzytelnienia, jeśli Garmin go wymaga. Nad polami logowania znajduje się informacja, że dotyczą konta Garmin Connect, oraz klikalny adres `https://connect.garmin.com/`, otwierany w domyślnej przeglądarce. Hasło i kod MFA są używane do logowania, ale nie są zapisywane. Sesja umożliwia kolejne pobrania bez ponownego podawania hasła do czasu jej wygaśnięcia.

Docelowe lokalizacje dla Windows:

```text
%LOCALAPPDATA%/GarminDatabase/
  settings.json
  auth/session.bin

D:/Projects/GarminDatabase/
  data/raw/YYYY-MM-DD.zip
  exports/
```

`settings.json` przechowuje ostatnie wybory eksportu, lokalizacje danych i preferencje interfejsu; nie zawiera sekretów. Na koncie użytkownika odpowiada ścieżce `C:/Users/wikto/AppData/Local/GarminDatabase/settings.json`. Ustawienia zapisywać atomowo. Lokalizacje archiwów i eksportów są konfigurowalne. Baza PostgreSQL jest wskazana przez `database_dsn` w ustawieniach lub `GARMIN_DATABASE_DSN`/libpq. Pole połączenia w UI nie przyjmuje hasła; hasło dostarcza plik pgpass lub środowisko procesu. Serwer musi działać przed uruchomieniem UI. Zobacz [konfigurację PostgreSQL](13-postgresql-setup.md).

Tokeny sesji w `auth/session.bin` szyfrować Windows DPAPI w zakresie użytkownika, bez opcji ochrony wspólnej dla wszystkich kont komputera. Nie zapisywać sesji w PostgreSQL ani w Temp. Sam katalog lub zapis w bazie nie zapewniają szyfrowania. Domyślnie odszyfrowanie wymaga tego samego użytkownika Windows i komputera; po przeniesieniu potrzebne jest ponowne logowanie. Nie dodawać własnego stałego klucza szyfrującego w aplikacji. Zobacz [DPAPI](https://learn.microsoft.com/en-us/windows/win32/SecCrypto/example-c-program-using-cryptprotectdata) i [zalecenia lokalizacji danych aplikacji](https://github.com/MicrosoftDocs/windows-dev-docs/blob/docs/hub/apps/develop/windows-app-restore.md).

Istniejący skrypt historyczny nadal korzysta z sesji w `private/garmin-session`; ten dokument nie zmienia jego implementacji ani nie oznacza, że sesja skryptu została zaszyfrowana. Docelowa aplikacja ma zapewnić własne bezpieczne logowanie. Wszystkie archiwa, baza, eksporty, logi i sesje pozostają poza Git.

## Udostępnianie danych i lokalny MCP

Ustawienia zawierają przewijaną sekcję „Udostępnianie danych” i tabelę Parametr/Jednostka/Eksport/MCP/Podsumowanie. Wybory eksportu i MCP są niezależne, nie ograniczają importu ani przeglądania w Danych. Można filtrować grupę, zaznaczać/odznaczać ją w danym kanale i kopiować wybór między kanałami. Nieobsługiwane parametry MCP mają nieaktywny checkbox z wyjaśnieniem. Zmiany stosuje przycisk „Zapisz ustawienia”.

Ustawienia wersji 2 mają `export_parameters`, `mcp_parameters`, `mcp_enabled` oraz dotychczasowe `parameters` jako ostatni podzbiór pakietu. Pusta lista oznacza brak wyboru i pozostaje pusta po restarcie. Migracja starszych ustawień zachowuje zapisany podzbiór eksportu; dawny pusty wybór „wszystko” zamienia na aktualny jawny katalog. W nowej pustej bazie brak parametrów do włączenia; po imporcie użytkownik wybiera nowo rozpoznane serie. MCP początkowo jest wyłączony i niczego nie udostępnia.

Ekran Eksport pokazuje tylko parametry dozwolone na liście eksportowej. Dostęp MCP obejmuje pięć obecnie obsługiwanych średnich próbek i wymaga osobnego włączenia. „Skopiuj konfigurację klienta MCP” kopiuje JSON `mcpServers` z bezwzględnymi ścieżkami serwera i ustawień, bez danych pomiarowych. W konfiguracji źródłowej używa Pythona i `mcp_stdio.py`, a w dystrybucji sąsiedniego folderu `GarminDatabaseMCP`.

Proces uruchamia zgodny klient `stdio`; okno aplikacji nie musi działać. Nie ma osobnego przycisku startu serwera. Serwer ponownie sprawdza zapisane ustawienia przy odczycie i przed odpowiedzią, więc wyłączenie dostępu działa również dla już uruchomionego klienta. Zmiana folderu danych lub listy MCP unieważnia kursory. Uszkodzony plik ustawień zamyka dostęp zamiast włączać wszystkie parametry. Eksport korzysta z wyboru rozpoczętego zadania; stare pakiety użytkownika nie są usuwane.

## Raspberry Pi i dostęp sieciowy — późniejszy etap

Wspólny rdzeń Python obsługuje pobieranie, import, ponowne przetwarzanie i eksport niezależnie od UI. Raspberry Pi ma działać bez okna jako automat importu według harmonogramu oraz hub dostępu do danych. Eksport nie staje się automatyczny bez osobnej zmiany wymagań.

Sposób udostępniania danych, uwierzytelnianie klientów, lokalizacja głównej bazy i połączenie z Windows wymagają projektu w tym etapie. Windows DPAPI nie jest przenośnym magazynem sesji dla Raspberry Pi; mechanizm ochrony sesji na Linux zostanie ustalony osobno. Nie przewiduje się obecnie dostępu sieciowego w pierwszej wersji Windows.

## Kryteria odbioru UI

- Aplikacja uruchamia się na Windows 11 bez instalacji Pythona i pokazuje cztery sekcje w ustalonym motywie.
- Pobranie i import nie blokują okna; przeglądanie zatwierdzonych danych działa podczas pracy.
- Zatrzymanie, zamknięcie i wznowienie nie gubią ukończonych dni ani nie zostawiają częściowego importu jako zakończonego.
- Punkty wykresu używają źródłowych wartości lub oznaczonych średnich dziennych. Kategorie i liczniki bez podsumowań Garmin mają tylko zakres dzienny. Obliczona linia trendu jest odrębną, oznaczoną warstwą bez zapisu wyników.
- Parametr, zakres i daty odświeżają wykres automatycznie; spinner działa nad rozmytym obrazem i znika także po błędzie. Starsze zapytanie nie nadpisuje nowszego wyboru.
- Logowanie obsługuje MFA i wygasłą sesję; zapisane tokeny są chronione DPAPI, a hasło i kod nie trafiają na dysk ani do logów.
- Ustawienia eksportu przetrwają ponowne uruchomienie. Historia zawiera podsumowania, szczegóły pełne dane po jednym pliku na parametr, a kolejne pakiety mają różne foldery i nie usuwają starych wyników.
