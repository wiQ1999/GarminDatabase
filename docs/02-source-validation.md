# Źródło danych i jego weryfikacja

## Ręczny wzorzec

Garmin Connect → [Informacje o koncie](https://connect.garmin.com/app/settings/accountInformation) → „Eksportuj dane dotyczące dobrostanu” → wskazana data.

Próbka użytkownika: `C:/Users/wikto/Downloads/2026-10-09.zip`, 58 033 bajty. Lista wpisów została sprawdzona bez ekstrakcji:

| Typ nazwy pliku | Liczba | Łączny rozmiar po rozpakowaniu, bajty |
| --- | ---: | ---: |
| WELLNESS | 10 | 102001 |
| METRICS | 6 | 3236 |
| HRV_STATUS | 1 | 1281 |
| SKIN_TEMP | 1 | 13696 |
| SLEEP_DATA | 1 | 933 |
| SLEEP_DISRUPTIONS | 1 | 420 |
| Razem | 20 | 121567 |

Nazwy nie stanowią dowodu konkretnego zestawu pól. Użytkownik tego dnia zarejestrował dwie jazdy rowerowe. W archiwum nie ma osobno nazwanego pliku aktywności; nie potwierdzono, czy jakieś rekordy opisują te jazdy. Nie dodajemy osobnego źródła treningów.

## Kandydat WebAPI

W kodzie `python-garminconnect`, sprawdzonym 2026-10-10, `download_health_snapshot(requested_date)` pobiera bajty z `/download-service/files/wellness/{requested_date}`. Test na koncie użytkownika potwierdził zgodność z ręcznym eksportem dobrostanu dla 2026-10-09. Wynik dotyczy tej próbki; nie dowodzi dostępności wszystkich dat ani parametrów widocznych w Garmin Connect.

Źródła pierwotne:

- [Implementacja biblioteki](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/__init__.py)
- [Przykład logowania i obsługi MFA](https://github.com/cyberjunky/python-garminconnect/blob/master/example.py)

Endpoint jest nieoficjalny; nie zakładamy stałej dostępności ani opublikowanych limitów. Przed implementacją trzeba przypiąć sprawdzoną wersję biblioteki i parsera. Nie zastępować nieudanego pobrania danymi z innych endpointów.

## Próba przed budową aplikacji

Skrypt `scripts/probe_wellness.py` ma dwie funkcje: pobranie pojedynczego ZIP i porównanie go z ręcznym eksportem albo porównanie dwóch lokalnych ZIP bez logowania. Nie implementuje jeszcze dekodowania FIT.

W projekcie przygotowano `.venv` z `garminconnect==0.3.17` i `tzdata==2026.5`. Sprawdzono obecność kandydata metody, sygnaturę logowania i dostępność strefy `Europe/Warsaw`. Dla tego środowiska uruchomienie z katalogu projektu:

```powershell
.venv/Scripts/python.exe scripts/probe_wellness.py --date 2026-10-09 --reference "C:/Users/wikto/Downloads/2026-10-09.zip"
```

Skrypt pyta lokalnie o login, hasło i ewentualny kod MFA. Nie wpisywać ich do czatu. Próbny skrypt nie zapisuje sesji ani hasła. Pobranie trafia do `data/raw/2026-10-09.zip`; skrypt odmawia nadpisania istniejącego pliku.

Porównanie lokalne:

```powershell
.venv/Scripts/python.exe scripts/probe_wellness.py --date 2026-10-09 --reference "C:/Users/wikto/Downloads/2026-10-09.zip" --candidate "data/raw/2026-10-09.zip"
```

### Ocena rezultatu

1. Sprawdzić poprawność ZIP i sumy kontrolne wpisów.
2. Porównać nazwy, rozmiary i SHA-256 rozpakowanej zawartości; porównać również multizbiór hashy niezależnie od nazw i kolejności plików.
3. Zgodność zawartości FIT jest silniejszym dowodem niż zgodność binarna całych ZIP, których metadane i kompresja mogą się różnić.
4. Jeśli FIT różnią się, zdekodować oba zestawy: porównać identyfikatory wiadomości i pól, wartości, jednostki, znaczniki czasu oraz liczbę rekordów. Wyjaśnić różnice; nie deklarować zgodności na podstawie liczby plików.
5. Ustalić faktyczną obecność parametrów i pól nieobsługiwanych przez parser.
6. Sprawdzić próbkę starszego dnia oraz kontrolowany dzień bez danych. Nie utożsamiać dowolnego 404 z brakiem danych.

Pełny import historii jest następnym etapem dopiero po pozytywnym wyniku próby. Nie można obiecać, że Garmin nadal udostępnia wszystkie dawne pomiary.

## Stan weryfikacji

- Lista plików ręcznego ZIP: sprawdzona.
- Kod kandydata WebAPI: sprawdzony.
- Lokalne porównanie próbki z nią samą, wykrycie zmienionej zawartości, zmian nazw/kolejności i nieprawidłowego ZIP: sprawdzone. To test porównywarki, nie dowód zgodności WebAPI.
- Pobranie na koncie użytkownika dla 2026-10-09: wykonane przez użytkownika; raport przekazany w rozmowie.
- Zgodność próbki: wszystkie 20 plików mają identyczne nazwy, rozmiary i SHA-256; `entries_equal_including_names=true`, `content_equal_ignoring_names=true`. Potwierdzono również przez lokalne porównanie zapisanych archiwów.
- Całe ZIP nie są identyczne binarnie (`zip_bytes_equal=false`); różnica nie dotyczy zawartości plików FIT. Dokładnych różnic opakowania ZIP nie analizowano.
- Zakres pól FIT i dostępność starszych dat: przeskanowano całą pobraną historię, wyniki w [analizie FIT](08-fit-analysis.md). Pobrano 844 archiwa; 169 dat ma nierozstrzygnięte 404. Znaczenie tych 404 nadal nie jest potwierdzone.
- Logowanie umożliwiło użytkownikowi pobranie próbki. Nie ustalono, czy użyto MFA; ponowne użycie zapisanej sesji nie jest testowane przez skrypt.

Odtworzenie środowiska na innym komputerze z Pythonem:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-probe.txt
```
