# Interfejs Windows i ustawienia aplikacji

Uzgodnione wymagania z 2026-10-11. Dokument opisuje planowaną aplikację, nie istniejącą implementację. Zastępuje wcześniejsze założenie pierwszej wersji konsolowej. Zakres pozyskiwania i zachowania danych pozostaje bez zmian.

## Uruchamianie i wygląd

- Windows 11, samodzielne okno uruchamiane z `.exe` w folderze aplikacji. Bez instalatora, konsoli, przeglądarki i konieczności osobnej instalacji Pythona. Można utworzyć skrót na pulpicie.
- Interfejs po polsku; polskie etykiety parametrów i oryginalna nazwa Garmin w krótkim opisie. Nazwy pól eksportu JSON pozostają zgodne ze specyfikacją eksportu.
- Jeden motyw: ciemne tło, grafitowe powierzchnie, jasny tekst, niebieskie akcenty. Wygląd wzorowany na Garmin Connect, proste menu po lewej i zawartość po prawej.
- Ikony podstawowych parametrów odtworzyć na podstawie trzech zrzutów Garmin Connect dostarczonych przez użytkownika. Zachować charakterystyczne symbole i kolory: tętno — czerwone serce, kroki — niebieskie ślady stóp, stres — pomarańczowa postać z symbolem napięcia, oddech — turkusowy symbol przepływu powietrza, HRV — serce z linią pulsu i oznaczeniem snu, piętra — turkusowe schody ze strzałką, kalorie — zielony płomień, intensywność — pomarańczowy stoper. Brakujące ikony przygotować w podobnym stylu.
- Pozostałe symbole na referencjach obejmują Body Battery, gotowość treningową, aklimatyzację saturacji, wiek sprawnościowy, stan wytrenowania, VO2 max, charakter obciążenia, ocenę wytrzymałości i próg mleczanowy. Referencje nie są dowodem dostępności tych parametrów w ZIP ani podstawą rozszerzenia źródła danych.

Zrzuty pozostają referencją wyglądu, nie źródłem wartości pomiarowych ani elementem repozytorium. Nie kopiować do dokumentacji widocznych prywatnych pomiarów. Technologia UI, biblioteka wykresów, pakowanie i finalne zasoby ikon wymagają realizacji; nie zostały jeszcze wybrane ani utworzone.

## Start

Pokazać ostatni pobrany dzień, stan importu do SQLite, zakres historii, brakujące lub nierozstrzygnięte dni, dostępność parametrów i rozmiar danych. Nie utożsamiać niezweryfikowanych 404 z potwierdzonym brakiem danych.

Główny przycisk **„Pobierz dane”** pobiera brakujące archiwa do wczoraj według `Europe/Warsaw`, następnie przetwarza je do SQLite. Poprawne lokalne archiwa wykorzystuje bez ponownego pobierania. Osobno dostępna jest operacja ponownego przetworzenia archiwów lokalnych bez żądań pobrania.

Postęp obejmuje pasek, aktualnie obsługiwany dzień i etap, licznik ukończonych dni oraz **„Zatrzymaj”**. Szczegóły błędów są dostępne w rozwijanym panelu bez sekretów i surowych danych zdrowotnych. Zatrzymanie zachowuje ukończone operacje; nieukończona transakcja nie jest prezentowana jako zakończony import. Wznowienie pomija ukończoną pracę.

Podczas pracy można przeglądać już zaimportowane dane. Zamknięcie okna przy aktywnej operacji pyta o zatrzymanie i wyjście. Aplikacja nie pozostaje w tle po zamknięciu; pobieranie pierwszej wersji uruchamia użytkownik.

## Dane

Lista rozpoznanych parametrów z ikonami i grupami: sen, serce i HRV, stres, oddychanie i saturacja, ruch, pozostałe. Pokazywać tylko parametry rozpoznane w danych użytkownika. Osobne reprezentacje, np. pomiar chwilowy i podsumowanie dzienne, zachowują odrębne etykiety.

Wybrany parametr jest prezentowany na prostym wykresie, bez tabeli rekordów i bez powiększania fragmentu. Najechanie kursorem pokazuje datę lub godzinę, wartość i jednostkę. Przerwy pozostają widoczne: brak interpolacji i łączenia linii przez rozpoznane luki. Podpis czasu określa strefę; niejednoznaczne czasy źródłowe nie otrzymują zgadywanej strefy.

Zakresy: **Dzień**, **7 dni**, **30 dni**, **90 dni**, **Cała historia**, własny zakres. Domyślnie 30 dni; domyślny koniec to ostatni zakończony dzień. Zakres „Dzień” umożliwia wybór konkretnej daty i szczegółowych pomiarów tego dnia.

| Okres | Prezentowane dane |
| --- | --- |
| Pojedynczy dzień | Szczegółowe pomiary dostępne w źródle oraz podsumowania Garmin, jeśli istnieją |
| Dłuższy okres | Wyłącznie podsumowania dostarczone przez Garmin |
| Dłuższy okres bez podsumowań źródłowych | Informacja o braku tej reprezentacji i możliwość wyboru pojedynczego dnia |

Nie obliczać własnych średnich, minimów, maksimów, trendów, ocen ani interpretacji medycznych. Nie redukować próbek w bazie lub eksporcie na potrzeby UI. Zapytanie pobiera tylko wybrany parametr, reprezentację i okres, a nie całą bazę. Liczniki techniczne dostępności nie są wskaźnikami zdrowotnymi.

Nierozpoznane pola zachować w SQLite. UI pokazuje ich obecność i liczbę z jednoznaczną etykietą, że chodzi o warianty pól, a nie liczbę parametrów zdrowotnych; bez zgadywanych nazw i wykresów. Pełne rekordy można przeglądać zewnętrznym narzędziem SQLite, poza zakresem interfejsu.

## Eksport

Wybór parametrów, zakresu historii, okresu szczegółowego (domyślnie 90 zakończonych dni) i folderu wynikowego. Format i kompletność określa [specyfikacja eksportu](05-export.md). Ograniczenie wykresów do szczegółów pojedynczego dnia nie ogranicza eksportu szczegółowego dowolnego okresu.

Zapamiętywać ostatnie ustawienia. Kolejny eksport zastępuje wcześniejsze pliki wygenerowane przez aplikację w wybranym folderze, bez gromadzenia wersji i bez usuwania obcych plików. Po zakończeniu pokazać wynik, rozmiary plików i **„Otwórz folder eksportu”**. Pliki zawierają dane i niezbędne etykiety, bez instrukcji dla AI.

## Ustawienia, sesja i lokalizacje

Formularz Garmin obejmuje e-mail, maskowane hasło i kod uwierzytelnienia, jeśli Garmin go wymaga. Hasło i kod MFA są używane do logowania, ale nie są zapisywane. Sesja umożliwia kolejne pobrania bez ponownego podawania hasła do czasu jej wygaśnięcia.

Docelowe lokalizacje dla Windows:

```text
%LOCALAPPDATA%/GarminDatabase/
  settings.json
  auth/session.bin

D:/Projects/GarminDatabase/
  data/raw/YYYY-MM-DD.zip
  data/garmin.sqlite3
  exports/
```

`settings.json` przechowuje ostatnie wybory eksportu, lokalizacje danych i preferencje interfejsu; nie zawiera sekretów. Na koncie użytkownika odpowiada ścieżce `C:/Users/wikto/AppData/Local/GarminDatabase/settings.json`. Ustawienia zapisywać atomowo. Lokalizacje archiwów, SQLite i eksportów są konfigurowalne.

Tokeny sesji w `auth/session.bin` szyfrować Windows DPAPI w zakresie użytkownika, bez opcji ochrony wspólnej dla wszystkich kont komputera. Nie zapisywać sesji w SQLite ani w Temp. Sam katalog lub zapis w bazie nie zapewniają szyfrowania. Domyślnie odszyfrowanie wymaga tego samego użytkownika Windows i komputera; po przeniesieniu potrzebne jest ponowne logowanie. Nie dodawać własnego stałego klucza szyfrującego w aplikacji. Zobacz [DPAPI](https://learn.microsoft.com/en-us/windows/win32/SecCrypto/example-c-program-using-cryptprotectdata) i [zalecenia lokalizacji danych aplikacji](https://github.com/MicrosoftDocs/windows-dev-docs/blob/docs/hub/apps/develop/windows-app-restore.md).

Istniejący skrypt historyczny nadal korzysta z sesji w `private/garmin-session`; ten dokument nie zmienia jego implementacji ani nie oznacza, że sesja skryptu została zaszyfrowana. Docelowa aplikacja ma zapewnić własne bezpieczne logowanie. Wszystkie archiwa, baza, eksporty, logi i sesje pozostają poza Git.

## Raspberry Pi — późniejszy etap

Wspólny rdzeń Python obsługuje pobieranie, import, ponowne przetwarzanie i eksport niezależnie od UI. Raspberry Pi ma działać bez okna jako automat importu według harmonogramu oraz hub dostępu do danych. Eksport nie staje się automatyczny bez osobnej zmiany wymagań.

Sposób udostępniania danych, uwierzytelnianie klientów, lokalizacja głównej bazy i połączenie z Windows wymagają projektu w tym etapie. Windows DPAPI nie jest przenośnym magazynem sesji dla Raspberry Pi; mechanizm ochrony sesji na Linux zostanie ustalony osobno. Nie przewiduje się obecnie dostępu sieciowego w pierwszej wersji Windows.

## Kryteria odbioru UI

- Aplikacja uruchamia się na Windows 11 bez instalacji Pythona i pokazuje cztery sekcje w ustalonym motywie.
- Pobranie i import nie blokują okna; przeglądanie zatwierdzonych danych działa podczas pracy.
- Zatrzymanie, zamknięcie i wznowienie nie gubią ukończonych dni ani nie zostawiają częściowego importu jako zakończonego.
- Wykres używa wyłącznie źródłowych wartości właściwej reprezentacji i zachowuje luki; brak podsumowań nie uruchamia własnej agregacji.
- Logowanie obsługuje MFA i wygasłą sesję; zapisane tokeny są chronione DPAPI, a hasło i kod nie trafiają na dysk ani do logów.
- Ustawienia eksportu przetrwają ponowne uruchomienie, a eksport zastępuje wyłącznie wyniki aplikacji.
