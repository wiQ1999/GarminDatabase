# Interfejs Windows i ustawienia aplikacji

Dokument opisuje dostępny interfejs Windows, jego zachowanie i wymagania prezentacji. Procedury startu, budowania i testowania znajdują się w [instrukcji uruchamiania](12-running-and-testing.md).

Błąd startu pokazuje zrozumiałą przyczynę i kod diagnostyczny, np. `STARTUP/PASSWORD_MISSING`, `STARTUP/PASSWORD_REJECTED` lub `STARTUP/SERVER_UNAVAILABLE`. Nie ogranicza się do nazwy `OperationalError`. Bezpieczny zapis w `%LOCALAPPDATA%/GarminDatabase/logs/startup-failure.json` zawiera kategorię, typ, opcjonalny SQLSTATE, ścieżkę programu i ustawień oraz wynik kontroli dostępu do pliku haseł. Nie zapisuje haseł, connection stringu ani treści wyjątku PostgreSQL. Brak uprawnień do zapisania diagnostyki nie zasłania pierwotnego komunikatu błędu.

## Uruchamianie i wygląd

- Windows 11, samodzielne okno uruchamiane z `.exe` w folderze aplikacji. Bez instalatora, konsoli, przeglądarki i konieczności osobnej instalacji Pythona. Można utworzyć skrót na pulpicie.
- Interfejs po polsku; polskie etykiety parametrów i oryginalna nazwa Garmin w krótkim opisie. Nazwy pól eksportu JSON pozostają zgodne ze specyfikacją eksportu.
- Autorska niebieska ikona z motywem połączenia i bazy danych pojawia się w nagłówku obok nazwy, jako ikona okna i obu plików EXE. Jej kolorystyka nawiązuje do [materiałów Garmin Connect](https://developer.garmin.com/brand-guidelines/connect/). Źródło SVG i wersje PNG/ICO są w `src/garmin_database/resources/app-icon.*`; `scripts/generate_app_icon.py` odtwarza PNG i dziewięć rozdzielczości ICO z SVG. Build używa ICO, a Qt wspólnego PNG.
- Jeden motyw: ciemne tło, grafitowe powierzchnie, jasny tekst, niebieskie akcenty. Wygląd wzorowany na Garmin Connect, proste menu po lewej i zawartość po prawej.
- Ikony podstawowych parametrów odtworzyć na podstawie trzech zrzutów Garmin Connect dostarczonych przez użytkownika. Zachować charakterystyczne symbole i kolory: tętno — czerwone serce, kroki — niebieskie ślady stóp, stres — pomarańczowa postać z symbolem napięcia, oddech — turkusowy symbol przepływu powietrza, HRV — serce z linią pulsu i oznaczeniem snu, piętra — turkusowe schody ze strzałką, kalorie — zielony płomień, intensywność — pomarańczowy stoper. Brakujące ikony przygotować w podobnym stylu.
- Pozostałe symbole na referencjach obejmują Body Battery, gotowość treningową, aklimatyzację saturacji, wiek sprawnościowy, stan wytrenowania, VO2 max, charakter obciążenia, ocenę wytrzymałości i próg mleczanowy. Referencje nie są dowodem dostępności tych parametrów w ZIP ani podstawą rozszerzenia źródła danych.

Zrzuty pozostają referencją wyglądu, nie źródłem wartości pomiarowych ani elementem repozytorium. Nie kopiować do dokumentacji widocznych prywatnych pomiarów. Realizacja używa PySide6 Essentials/Qt Widgets, wykresu QPainter, własnych symboli SVG wzorowanych na referencjach oraz PyInstaller onedir.

## Start

Pokazać ostatni pobrany dzień, stan importu do PostgreSQL, zakres historii, brakujące lub nierozstrzygnięte dni, dostępność parametrów i rozmiar danych. Nie utożsamiać niezweryfikowanych 404 z potwierdzonym brakiem danych.

Stan odczytuje się w tle przy otwarciu okna i co 15 sekund. Automatyczna kontrola katalogu parametrów odbywa się najwyżej raz na minutę; katalog pobiera się ponownie tylko po zmianie rewizji danych. Ukryte lub zminimalizowane okno pomija odczyty cykliczne. Główny widok pokazuje informację o aktualizacji automatycznej i pasywny obracający się wskaźnik podczas odczytu. Zakończenie importu ani pojedyncza zmiana w bazie nie wyzwalają dodatkowego odczytu. Nowy stan pojawia się przy kolejnym cyklu; nie ma przycisku ręcznego odświeżania.

Odświeżenie zachowuje niezapisane wybory eksportu, MCP i filtr grupy. Niezmieniony katalog nie przebudowuje list ani nie uruchamia zapytania wykresu. Zakres „Cała historia” korzysta z zapamiętanego początku historii. Liczniki stanu pojawiają się przed odczytem katalogu; opóźnienie lub błąd listy parametrów nie zasłania poprawnego stanu bazy. Po błędzie pozostają ostatnie poprawne informacje. Osobny obszar komunikatów zastępuje poprzedni błąd danego odczytu i usuwa go po odzyskaniu poprawnego wyniku, bez dopisywania duplikatów przy kolejnych cyklach. Przekroczenie czasu zapytania ma inny komunikat niż brak połączenia. Próby katalogu także po błędzie zachowują odstęp co najmniej minuty; stan nadal odświeża się co 15 sekund.

Główne przyciski to **„Pobierz nowe dane”** (od ostatniego pobranego dnia włącznie, także wcześniejsze błędy i niekompletne importy) oraz **„Pobierz wszystko”** (pełny zakres). Oba kończą się dzisiaj Europe/Warsaw i dopisują nowe FIT bez zapisywania ZIP na dysku. Wykresy obejmują bieżący dzień z widoczną informacją o możliwej niepełności danych.

Postęp obejmuje pasek, aktualnie obsługiwany dzień i etap, licznik ukończonych dni oraz **„Zatrzymaj”**. **Dziennik operacji jest stale widoczny na widoku głównym**, od uruchomienia aplikacji, bez przycisku pokazywania lub ukrywania szczegółów. Pokazuje postęp pobierania, importu i eksportu, wyniki oraz błędy, a także bezpieczne komunikaty logowania i czynności pomocniczych, np. zapisu ustawień. Nie zawiera sekretów ani surowych danych zdrowotnych. Nowe pobieranie, import lub eksport rozpoczynają nowy dziennik bieżącej operacji. Zatrzymanie zachowuje ukończone operacje; nieukończona transakcja nie jest prezentowana jako zakończony import. Wznowienie pomija ukończoną pracę.

Pobieranie, import i ponowne przetwarzanie pokazują animację także na przycisku rozpoczętej operacji. „Zatrzymaj” animuje oczekiwanie na zakończenie bieżącej czynności. Prezentacja postępu i szczegółów jest odświeżana najwyżej 10 razy na sekundę, z końcowym opróżnieniem bufora przed wynikiem lub błędem. Panel zachowuje najwyżej 500 ostatnich wierszy.

Po zakończeniu dnia dziennik pokazuje „Wynik dnia” z jego rezultatem. Po zakończeniu lub wcześniejszym przerwaniu synchronizacji etykieta etapu pokazuje nagłówek „Podsumowanie całej operacji”, a dziennik pełny zakres i oddzielne liczniki. Historyczne dni HTTP 404 pozostają opisane jako nierozstrzygnięte i nie oznaczają błędu importu ostatniego dnia. Zakończenie z samymi 404 ma inny nagłówek niż zakończenie z błędami pobierania/importu. Szczegółowy [kontrakt komunikatów](04-synchronization.md#błędy-i-wznowienie) jest wspólny dla GUI i CLI.

Podczas pracy można przeglądać już zaimportowane dane. Zamknięcie okna przy aktywnej operacji pyta o zatrzymanie i wyjście. Aplikacja nie pozostaje w tle po zamknięciu; pobieranie pierwszej wersji uruchamia użytkownik.

Wątki kończą się przez sygnały zakończenia, bez blokującego oczekiwania w wątku okna. Podczas zatrzymywania odczytów okno nadal obsługuje zdarzenia i pokazuje stan zamykania. Odczyt stanu ma budżet 10 sekund, a wykresu 60 sekund; aktywne zapytanie PostgreSQL można anulować przy zamykaniu. Zmiana połączenia unieważnia odpowiedzi z poprzedniej konfiguracji.

## Dane

Lista rozpoznanych parametrów z ikonami i grupami: sen, serce i HRV, stres, oddychanie i saturacja, ruch, pozostałe. Pokazywać tylko parametry rozpoznane w danych użytkownika. Osobne reprezentacje, np. pomiar chwilowy i podsumowanie dzienne, zachowują odrębne etykiety.

„Średni poziom stresu podczas snu” (`sleep_assessment.average_stress_during_sleep`) należy do grupy Stres. Kategoria porządkuje prezentację i filtry wyboru; odczyt, obliczenia i dostęp MCP opierają się na stabilnych kluczach parametrów oraz zapisanej polityce udostępniania. Przeniesienie do grupy Stres nie dodaje tej źródłowej statystyki nocnej do pięciu średnich próbek obsługiwanych przez MCP.

Wybrany parametr jest prezentowany na prostym wykresie, bez tabeli rekordów i bez powiększania fragmentu. Najechanie kursorem pokazuje datę lub godzinę, wartość i jednostkę. Przerwy pozostają widoczne: brak interpolacji i łączenia linii przez rozpoznane luki. Podpis czasu określa strefę; niejednoznaczne czasy źródłowe nie otrzymują zgadywanej strefy.

Oś czasu ma podpisy pośrednie, do ośmiu na szerokim wykresie. Ich liczbę dobiera się do rzeczywistej szerokości napisów, aby nie nachodziły na siebie. Krótkie odcinki pokazują również sekundy, zakresy przekraczające północ — datę i godzinę, a dłuższa historia — daty. Przy zmianie czasu letniego podpisy godzin zawierają przesunięcie względem UTC. Znaczniki osi służą orientacji i nie są dodatkowymi pomiarami.

Wybór parametru, zmiana zakresu lub dat automatycznie odświeżają wykres. Przycisk „Pokaż wykres” został usunięty. Podczas odczytu na pierwszym planie wykresu widać animowane koło i napis „Ładowanie wykresu…”, a poprzedni obraz jest rozmyty i nie pokazuje tooltipów. Filtry pozostają dostępne. Przy szybkich zmianach UI pokazuje wynik ostatniego wyboru, pomijając starsze wyniki i błędy. Po aktualnym wyniku albo błędzie animacja znika; błąd usuwa poprzedni obraz, żeby nie udawał danych aktualnego parametru.

Zakresy: **Dzień**, **7 dni**, **30 dni**, **90 dni**, **Cała historia**, własny zakres. Początkowy zakres to 30 dni dla podsumowań; domyślny koniec to bieżący dzień. „Dzień” pokazuje oryginalne szczegóły. Dłuższe zakresy są dostępne dla `source_summary` oraz HRV, tętna chwilowego, oddechu, saturacji i stresu, dla których aplikacja liczy średnie dzienne. Podpis wykresu i tooltip jednoznacznie oznaczają obliczone średnie. Kategorie i pozostałe liczniki bez podsumowań Garmin zachowują wyszarzone opcje poza dniem i automatyczne przełączenie na „Dzień”. Datę początku można edytować tylko w „Własnym zakresie”.

| Okres | Prezentowane dane |
| --- | --- |
| Pojedynczy dzień | Szczegółowe pomiary dostępne w źródle oraz podsumowania Garmin, jeśli istnieją |
| Dłuższy okres | Podsumowania Garmin lub jawnie oznaczone średnie dzienne pięciu obsługiwanych parametrów pomiarowych |
| Kategorie i pozostałe liczniki bez podsumowań Garmin | Tylko „Dzień”; pozostałe filtry są wyszarzone, a poprzedni dłuższy zakres jest automatycznie korygowany |

Checkbox **„Linia trendu”** jest domyślnie odznaczony. Włącza przerywaną linię z podpisem „Trend liniowy (obliczony)”, dopasowaną metodą najmniejszych kwadratów względem rzeczywistego czasu. Obejmuje poprawne skończone wartości liczbowe aktualnego wykresu. Nie dodaje punktów w lukach ani nie zmienia próbek; sama prosta trendu jest wskazówką wizualną i może przebiegać przez okresy bez pomiarów. Checkbox jest niedostępny podczas ładowania, dla kategorii i przy braku co najmniej dwóch obserwacji z różnymi czasami. Wybór obowiązuje w bieżącym oknie, bez zapisu w ustawieniach.

Linia trendu jest obliczana wyłącznie na wykresie i nie jest podsumowaniem Garmin. Nie trafia do PostgreSQL lub JSON. Średnie i podsumowania historii w bazie i eksporcie opisuje [eksport](05-export.md). Nie redukować źródłowych próbek w bazie lub plikach szczegółowych na potrzeby UI. Zapytanie pobiera wybrany parametr i okres, a nie całą bazę. Nie dodawać ocen ani interpretacji medycznych.

Nierozpoznane pola zachować w PostgreSQL. UI pokazuje ich obecność i liczbę z jednoznaczną etykietą, że chodzi o warianty pól, a nie liczbę parametrów zdrowotnych; bez zgadywanych nazw i wykresów. Pełne rekordy można przeglądać narzędziem PostgreSQL, np. psql lub pgAdmin, poza zakresem interfejsu.

### Objaśnienia parametrów

Pod wykresem widoczny jest przewijany opis wybranego parametru: znaczenie, czujniki lub algorytm opisany przez Garmin, ograniczenia, sposób prezentacji w aplikacji i klikalne źródła. Zmienia się od razu wraz z wyborem parametru, także podczas odczytywania wykresu; stary wynik zapytania nie zastępuje nowego opisu. Objaśnienia są lokalne i nie wykonują zapytań SQL ani sieci przy wyborze. Odnośniki otwierają domyślną przeglądarkę przez worker. Wspólne z MCP definicje i granice interpretacji opisuje [katalog parametrów](14-parameter-descriptions.md).

## Eksport

Wybór parametrów, zakresu historii, dziennego lub miesięcznego okresu obliczonych podsumowań, liczby ostatnich dni szczegółowych (domyślnie 90) i folderu nadrzędnego. Osobne `history/{parametr}.json` i `details/{parametr}.json`. Okres obliczonych podsumowań nie zmienia oryginalnych podsumowań Garmin. Nie ma zbiorczego `recent.json` ani opcji pełnych próbek w historii. Format i kompletność określa [specyfikacja eksportu](05-export.md).

Zapamiętywać ostatnie ustawienia. Każdy eksport tworzy unikatowy folder `GarminDatabase_DATA_CZAS`; nie usuwa i nie zastępuje poprzednich eksportów. Po zakończeniu pokazać folder, liczbę i łączny rozmiar plików oraz **„Otwórz folder eksportu”**, otwierający ostatni ukończony pakiet. Pliki zawierają dane i niezbędne etykiety, bez instrukcji dla AI.

## Ustawienia, sesja i lokalizacje

Ustawienia mają trzy oddzielne sekcje: „Dane lokalne i PostgreSQL”, „Logowanie do Garmin Connect” i „Udostępnianie danych”. Przycisk „Wybierz…” jest na prawym końcu wiersza folderu danych. Przewijana zawartość nie zasłania dolnego przycisku „Zapisz ustawienia” ani komunikatu o zapisie. Zapis konfiguracji nie nadpisuje informacji o stanie logowania.

Sprawdzenie połączenia i zapis ustawień, zapis preferencji i przygotowanie eksportu, przygotowanie konfiguracji MCP oraz otwieranie folderu lub przeglądarki działają poza wątkiem okna. Przycisk rozpoczętej czynności pokazuje animację do wyniku lub błędu. Wybór folderu korzysta z nieblokująco otwieranego dialogu Qt, dzięki czemu timery i animacje nadal działają. Krótkie działania, takie jak nawigacja i zaznaczanie parametrów, reagują od razu. Animacje przycisków i wykresu nie wykonują cykli, gdy ich element jest ukryty.

Formularz Garmin obejmuje e-mail i maskowane hasło. Nad polami logowania znajduje się informacja, że dotyczą konta Garmin Connect, oraz klikalny adres `https://connect.garmin.com/`, otwierany w domyślnej przeglądarce. Po podaniu danych przycisk „Zaloguj do Garmin” otwiera osobne okno z animowanym wskaźnikiem i informacją o postępie. Logowanie ma własny worker, niezależny od importu i eksportu. Błąd pozostaje widoczny w tym oknie i przy formularzu; po powrocie i ponownym wpisaniu hasła można od razu rozpocząć kolejną próbę, bez restartu aplikacji. Każda próba tworzy nowego klienta Garmin. Hasło jest usuwane z pola po rozpoczęciu próby, a zamknięcie wątku zwalnia przechwytującą je funkcję.

Jeśli Garmin wymaga kodu MFA, pojawia się osobne okno nad oknem logowania. Kod jest widoczny podczas wpisywania; maskowanie dotyczy wyłącznie hasła. Każde żądanie czeka na nowy kod, zerując poprzedni stan potwierdzenia. Anulowanie kodu anuluje logowanie. „Anuluj” lub zamknięcie okna logowania czeka na zakończenie bieżącego żądania sieciowego; wątku nie kończymy siłowo. Po zakończeniu można ponowić logowanie. Anulowana próba nie zastępuje wcześniej zapisanej sesji. Hasło i kod MFA są używane do logowania, ale nie są zapisywane. Sesja umożliwia kolejne pobrania bez ponownego podawania hasła do czasu jej wygaśnięcia.

Punkty wejścia: `Window.build_settings` i `Window.login` w `src/garmin_database/adapters/inbound/desktop/window.py`; okno postępu i MFA: `src/garmin_database/adapters/inbound/desktop/login_dialog.py`; magazyn DPAPI: `src/garmin_database/adapters/outbound/security/dpapi_session.py`; sprawdzenie anulowania przed zapisem sesji: `GarminSource.login` w `src/garmin_database/adapters/outbound/garmin/client.py`.

MFA obsługuje wyłącznie `LoginDialog`; ogólny worker importu i eksportu nie otwiera drugiego okna kodu. Dialog wyświetla bezpieczny komunikat przygotowany przez rdzeń/worker i nie rozpoznaje ponownie błędów przez przeszukiwanie tekstu.

Biblioteka `garminconnect==0.3.20` przygotowuje sesję mobilną przez pobranie strony logowania przed wysłaniem danych. Samo poprawne logowanie w przeglądarce nie potwierdza, że Garmin zaakceptuje token aplikacji w API. Okno pokazuje etap połączenia, oczekiwania na kod, potwierdzania MFA i dostępu aplikacji oraz lokalnego zapisu sesji. Błąd `LoginFailed` zawiera wyłącznie etap, dozwoloną kategorię i ewentualny strukturalny status HTTP; nie pokazuje treści wyjątku biblioteki ani odpowiedzi Garmin. Przykłady kodów: `MFA_VERIFY/ACCESS_DENIED`, `MFA_VERIFY/CONNECTION`, `CONNECT/RATE_LIMIT`, `SESSION_SAVE/LOCAL_SESSION`. Etap MFA obejmuje również wymianę tokenów i pobranie profilu, więc sam kod etapu nie dowodzi niepoprawności kodu MFA. Biblioteka czasem usuwa status HTTP podczas opakowania błędu; wtedy aplikacja go nie zgaduje.

Przed wysłaniem kodu MFA usuwane są białe znaki z jego początku i końca. Po błędzie nadal można ponowić próbę z nowym klientem; wcześniejsza zapisana sesja zostaje zachowana, dopóki nowa próba nie zakończy się pomyślnie. Aktualizacja klienta nie wykonuje automatycznego resetu sesji.

Biblioteka Garmin może opakować lokalny błąd transportu w wyjątek uwierzytelnienia. Jeśli łańcuch zawiera brak lokalnego pliku, aplikacja pokazuje kategorię `LOCAL_RUNTIME` i informację o pełnej paczce, zamiast przypisywać przyczynę danym konta. Wymagane zasoby TLS i kontrolę paczki opisuje [instrukcja budowania](12-running-and-testing.md#build-i-smoke).

Docelowe lokalizacje dla Windows:

```text
%LOCALAPPDATA%/GarminDatabase/
  settings.json
  auth/session.bin

D:/Projects/GarminDatabase/
  data/raw/YYYY-MM-DD.zip  # tylko wcześniejsze archiwa lub lokalne źródła CLI
  exports/
```

`settings.json` przechowuje ostatnie wybory eksportu, lokalizacje danych i preferencje interfejsu; nie zawiera sekretów. Ustawienia zapisywać atomowo. Lokalizacje archiwów i eksportów są konfigurowalne. Baza PostgreSQL jest wskazana przez `database_dsn` w ustawieniach lub `GARMIN_DATABASE_DSN`/libpq. Pole połączenia w UI nie przyjmuje hasła; hasło dostarcza plik pgpass lub środowisko procesu. Serwer musi działać przed uruchomieniem UI. Zobacz [konfigurację PostgreSQL](13-postgresql-setup.md).

Tokeny sesji w `auth/session.bin` szyfrować Windows DPAPI w zakresie użytkownika, bez opcji ochrony wspólnej dla wszystkich kont komputera. Nie zapisywać sesji w PostgreSQL ani w Temp. Sam katalog lub zapis w bazie nie zapewniają szyfrowania. Domyślnie odszyfrowanie wymaga tego samego użytkownika Windows i komputera; po przeniesieniu potrzebne jest ponowne logowanie. Nie dodawać własnego stałego klucza szyfrującego w aplikacji. Zobacz [DPAPI](https://learn.microsoft.com/en-us/windows/win32/SecCrypto/example-c-program-using-cryptprotectdata) i [zalecenia lokalizacji danych aplikacji](https://github.com/MicrosoftDocs/windows-dev-docs/blob/docs/hub/apps/develop/windows-app-restore.md).

Reset logowania wykonuje się przy zamkniętej aplikacji przez usunięcie wyłącznie `%LOCALAPPDATA%/GarminDatabase/auth/session.bin`, na wyraźne zlecenie użytkownika. Aplikacja nie ma drugiego dyskowego cache logowania, a ręczna próba używa nowego klienta i danych podanych w formularzu. Reset nie wymaga usuwania `settings.json`, połączenia PostgreSQL, bazy, eksportów ani plików pgpass. Nie kasujemy sesji automatycznie podczas startu ani po każdym błędzie.

Wszystkie archiwa, baza, eksporty, logi i sesje pozostają poza Git. Zasady tej sekcji dotyczą aplikacji, nie pomocniczych skryptów analitycznych.

## Udostępnianie danych i lokalny MCP

Ustawienia zawierają przewijaną sekcję „Udostępnianie danych” i tabelę Parametr/Jednostka/Eksport/MCP/Podsumowanie. Wybory eksportu i MCP są niezależne, nie ograniczają importu ani przeglądania w Danych. Można filtrować grupę, zaznaczać/odznaczać ją w danym kanale i kopiować wybór między kanałami. Nieobsługiwane parametry MCP mają nieaktywny checkbox z wyjaśnieniem. Zmiany stosuje przycisk „Zapisz ustawienia”.

Ustawienia wersji 2 mają `export_parameters`, `mcp_parameters`, `mcp_enabled` oraz dotychczasowe `parameters` jako ostatni podzbiór pakietu. Pusta lista oznacza brak wyboru i pozostaje pusta po restarcie. Migracja starszych ustawień zachowuje zapisany podzbiór eksportu; dawny pusty wybór „wszystko” zamienia na aktualny jawny katalog. W nowej pustej bazie brak parametrów do włączenia; po imporcie użytkownik wybiera nowo rozpoznane serie. MCP początkowo jest wyłączony i niczego nie udostępnia.

Ekran Eksport pokazuje tylko parametry dozwolone na liście eksportowej. Dostęp MCP obejmuje pięć obecnie obsługiwanych średnich próbek i wymaga osobnego włączenia. „Skopiuj konfigurację klienta MCP” kopiuje JSON `mcpServers` z bezwzględnymi ścieżkami serwera i ustawień, bez danych pomiarowych. W konfiguracji źródłowej używa Pythona i bezwzględnej ścieżki `bootstrap/mcp.py` wewnątrz zainstalowanego pakietu, a w dystrybucji sąsiedniego folderu `GarminDatabaseMCP`.

Proces uruchamia zgodny klient `stdio`; okno aplikacji nie musi działać. Nie ma osobnego przycisku startu serwera. Serwer ponownie sprawdza zapisane ustawienia przy odczycie i przed odpowiedzią, więc wyłączenie dostępu działa również dla już uruchomionego klienta. Zmiana folderu danych lub listy MCP unieważnia kursory. Uszkodzony plik ustawień zamyka dostęp zamiast włączać wszystkie parametry. Eksport korzysta z wyboru rozpoczętego zadania; stare pakiety użytkownika nie są usuwane.

## Raspberry Pi i dostęp sieciowy — późniejszy etap

Wspólny rdzeń Python obsługuje pobieranie, import, ponowne przetwarzanie i eksport niezależnie od UI. Raspberry Pi ma działać bez okna jako automat importu według harmonogramu oraz hub dostępu do danych. Eksport nie staje się automatyczny bez osobnej zmiany wymagań.

Sposób udostępniania danych, uwierzytelnianie klientów, lokalizacja głównej bazy i połączenie z Windows wymagają projektu w tym etapie. Windows DPAPI nie jest przenośnym magazynem sesji dla Raspberry Pi; mechanizm ochrony sesji na Linux zostanie ustalony osobno. Nie przewiduje się obecnie dostępu sieciowego w pierwszej wersji Windows.

## Kryteria odbioru UI

- Aplikacja uruchamia się na Windows 11 bez instalacji Pythona i pokazuje cztery sekcje w ustalonym motywie.
- Pobranie i import nie blokują okna; przeglądanie zatwierdzonych danych działa podczas pracy.
- Odczyt stanu, zapis ustawień, eksport, przygotowanie konfiguracji i otwieranie folderów nie blokują obsługi zdarzeń; oczekiwanie pokazuje animację. Odświeżanie automatyczne ma ograniczoną częstotliwość i zachowuje niezapisane wybory.
- Zatrzymanie, zamknięcie i wznowienie nie gubią ukończonych dni ani nie zostawiają częściowego importu jako zakończonego.
- Punkty wykresu używają źródłowych wartości lub oznaczonych średnich dziennych. Kategorie i liczniki bez podsumowań Garmin mają tylko zakres dzienny. Obliczona linia trendu jest odrębną, oznaczoną warstwą bez zapisu wyników.
- Parametr, zakres i daty odświeżają wykres automatycznie; spinner działa nad rozmytym obrazem i znika także po błędzie. Starsze zapytanie nie nadpisuje nowszego wyboru.
- Logowanie obsługuje MFA i wygasłą sesję; zapisane tokeny są chronione DPAPI, a hasło i kod nie trafiają na dysk ani do logów.
- Ustawienia eksportu przetrwają ponowne uruchomienie. Historia zawiera podsumowania, szczegóły pełne dane po jednym pliku na parametr, a kolejne pakiety mają różne foldery i nie usuwają starych wyników.
