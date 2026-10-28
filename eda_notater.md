# Notater: datamodell (Del 1.2)

## 1. Leses dataene sammen?

Jeg gikk gjennom spørring 1 til 9 i Part 2 og så på hvilke felt hver av dem trenger:

| # | Filmfelt | Cast/crew |
|---|---|---|
| 1 | revenue, vote_average | crew (Director) |
| 2 | vote_average | cast |
| 3 | genres | cast |
| 4 | collection, revenue, vote_average, dato | nei |
| 5 | dato, genres, runtime | nei |
| 6 | dato | cast (order, gender) |
| 7 | overview, tagline, vote_count, vote_average | nei |
| 8 | vote_count, vote_average, revenue | crew og cast |
| 9 | original_language, selskap/land | nei |

Fem av ni spørringer (1, 2, 3, 6 og 8) trenger filmfelt og cast/crew samtidig. Ingen spørringer bruker cast/crew uten filmfeltene.

**Valg:** Cast, crew og keywords bygges inn i filmdokumentet. Det er én credits-rad og én keywords-rad per film, altså et 1:1-forhold. Dataene leses alltid sammen med filmen og endres aldri alene. Hvis de lå i egne samlinger, måtte nesten hver spørring bruke `$lookup`, og det er tregere og akkurat det MongoDB-modellering prøver å unngå. Ingen spørring bruker `keywords`, men jeg bygger dem inn likevel fordi de er små og hører til filmen.

## 2. Hvor store blir dokumentene?

Den lengste cast-listen har 313 personer og den lengste crew-listen har 435. Den største credits-raden er rundt 79 kB som tekst. Det er under 1 % av grensen på 16 MB, så det er trygt å bygge inn cast og crew.

Ratings er en annen sak. Filmen med flest ratings har 91 921, og den mest aktive brukeren har 18 276. Med rundt 50 til 60 byte per rating blir det omtrent 5 MB, så det hadde faktisk fått plass under 16 MB. Grunnene til å ikke bygge dem inn er andre:

- Forholdet er ubegrenset. Listen vokser for hver nye rating og vil til slutt nå grensen.
- Hver gang en populær film leses, følger flere MB med ratings med, også i spørringer som ikke bruker dem.
- Spørring 10 grupperer på bruker, ikke film. Da må alle 26 millioner ratings uansett pakkes ut av filmdokumentene med `$unwind`.

**Valg:** `ratings` blir en egen samling med ett dokument per rating og en referanse til filmen.

## 3. Hvilken `_id`?

- **`movies`:** `_id` er TMDB-`id` som heltall. Den er unik etter at duplikatene er fjernet, og det er den credits og keywords kobles på.
- **`ratings`:** MongoDB lager en `ObjectId`. Ingen enkeltkolonne er unik, og jeg trenger ikke å slå opp enkeltratings på id.

Jeg oversetter fra MovieLens-id til TMDB-id når dataene settes inn, ikke når jeg spør. Spørring 10 trenger sjangrene til hver film en bruker har ratet. Hvis ratingen allerede har `tmdb_id`, går koblingen rett til `movies._id`. Ellers måtte hver spørring gått via `links` først, og det hadde blitt en dobbel join over 26 millioner rader.

Et rating-dokument ser slik ut:

```
{ user_id, movielens_id, tmdb_id (eller null), rating, timestamp (datetime) }
```

Jeg beholder også `movielens_id` og kaster ikke ratings som mangler `tmdb_id`. Spørring 10 spør etter antall ratings og varians per bruker, og de tallene er gyldige selv om filmen mangler i metadataene. Det er bare sjangertellingen som trenger koblingen. Dette passer med det jeg fant i EDA-en: en manglende ekstern ID gjør ikke ratingen ugyldig.

## 4. Skal `links` være en egen samling?

Nei. `links` er bare et hjelpemiddel under innsettingen. Jeg leser den inn i en Python-dict `movieId → tmdbId` og bruker den til å legge `tmdb_id` på hver rating. Når oversettingen er gjort ved innsetting, er det ingen spørringer som trenger den.

Jeg kan i tillegg legge `imdb_id` og `movielens_id` inn i filmdokumentet. Det koster lite og gjør det lettere å spore filmene tilbake til kildene.

**Sjekket:** om flere `movieId` peker til samme `tmdbId`, eller omvendt.

- I `links.csv` finnes det ingen duplikate `movieId`, så dicten `movieId → tmdbId` er entydig.
- 29 `tmdbId` deles av flere `movieId` (59 rader totalt, maks 3 per `tmdbId`). For eksempel hører `tmdbId` 4912 til både `movieId` 6003 og 144606. Alle 29 finnes i `movies_metadata`.
- I `links_small.csv` er det ingen slike konflikter.
- Dette gjelder 9 453 av 26 024 289 ratings, altså 0,036 %.

**Valg:** Jeg gjør ikke noe spesielt med dette. Alle ratings beholdes og peker på samme `tmdb_id`. Det som skjer er at to MovieLens-filmer slås sammen til én TMDB-film, og snittet og antallet ratings for de 29 filmene blir litt for høye. Effekten er så liten at det er akseptabelt, og siden `movielens_id` ligger på hver rating kan jeg alltid skille dem fra hverandre om det trengs.

## Samlet modell

- **`movies`** (ca. 45 000 dokumenter): filmfeltene pluss `genres`, `production_companies`, `production_countries`, `spoken_languages`, `belongs_to_collection`, `keywords`, `cast` og `crew` bygget inn.
- **`ratings`** (ca. 26 millioner dokumenter): én rating per dokument med referanse til filmen via `tmdb_id`. Indeks på `user_id` og `tmdb_id`.

## Rensing før innsetting

Dette er rensereglene jeg tar med inn i `load_data.py`. De bygger på EDA-en i `eda_didrik.ipynb` (links og ratings) og `eda_tahir.ipynb` (movies, credits og keywords). Råfilene endres aldri, all rensing skjer i Python før innsetting.

### movies_metadata

| Problem | Løsning |
|---|---|
| 3 filmer er splittet over 6 rader (10 og 15 felt i stedet for 24) | Slå sammen hvert par: overview-fortsettelsen legges til teksten, og de siste 14 feltene flyttes tilbake til riktige kolonner. Gir 45 463 rader |
| `id`, `budget`, `popularity` og `release_date` er tekst | Konverter til `int`, `float` og `datetime`. Feilformaterte verdier skal gi feilmelding, ikke bli NaN i det stille |
| 17 helt identiske ekstrarader | Fjern |
| 13 `id`-er har to rader med ulik `popularity` (to av dem også ulik `vote_count`) | Behold raden med høyest `vote_count`, så er alle feltene fra én ekte rad og `popularity` ikke et snitt. Gir én rad per `id` |
| `genres`, `production_companies`, `production_countries`, `spoken_languages` og `belongs_to_collection` er tekst | Parse med `ast.literal_eval`. Det er Python-repr og ikke JSON, så `json.loads` feiler |
| `belongs_to_collection` mangler i 40 972 rader | Lagres som `null`. Filmen tilhører ikke en serie, og jeg fyller ikke inn noe |
| `release_date` mangler i 84 rader | Lagres som `null`, ikke imputert. Filmene beholdes, men er med i år- og tiårsberegninger bare når datoen er kjent |
| `runtime` er 0 (1 558 rader) eller mangler (257 rader) | 0 betyr ukjent, så lagres som `null`. Ikke imputert med snitt eller median, siden det ville ødelagt medianen i oppgave 5 |
| `budget` og `revenue` er 0 i henholdsvis 36 557 og 38 041 rader | 0 betyr ukjent, så lagres som `null`. Filmene beholdes |
| 946 filmer mangler både `overview` og `tagline` | Beholdes uten tekst. De gir ikke treff i tekstsøket i oppgave 7, og det er en begrensning |
| `original_language` mangler for 11 filmer, `status` for 81 | Beholdes som `null`. Filmene utelates fra språkberegningen i oppgave 9 |

### credits

| Problem | Løsning |
|---|---|
| 37 identiske ekstrarader og 7 ekstra `id`-forekomster | Fjern identiske rader. De 7 gjenværende parene har samme cast og crew i ulik rekkefølge, så behold første rad per `id` |
| `cast` og `crew` er tekst | Parse med `ast.literal_eval` og bygg inn i filmdokumentet |
| 2 414 filmer har tom cast og 771 tom crew | Beholdes med tom liste. Ikke fylt inn |
| 223 765 cast-oppføringer har `gender` 0 | Beholdes. Utelates fra kjønnsberegningen i oppgave 6 |
| 887 filmer mangler regissør | Beholdes. Utelates fra regissøranalysene, ingen imputering |

### keywords

| Problem | Løsning |
|---|---|
| 987 identiske ekstrarader | Fjern |
| `keywords` er tekst | Parse med `ast.literal_eval` |
| 4 oppføringer med keyword-`id` 13091 og navn som bare er mellomrom | Fjern de 4 oppføringene. Filmene og de andre keywordene beholdes |
| 14 340 tomme lister (31,56 %) | Beholdes som tom liste |

### links og ratings

| Problem | Løsning |
|---|---|
| `tmdbId` er `float64` og mangler i 219 av 45 843 rader | Konverter til heltall (`Int64`). Radene beholdes og får `tmdb_id` = `null` på ratingene |
| 29 `tmdbId` deles av flere `movieId` (30 ekstra rader) | Behold alle ratings, de peker på samme `tmdb_id`. `movielens_id` beholdes |
| 161 `tmdbId` finnes ikke i `movies_metadata` | Ratingene beholdes, men faller bort i spørringer som trenger sjanger |
| `timestamp` er Unix-tid | Konverter til `datetime` |
| `ratings_small` er ikke et utsnitt av `ratings` (bare 6 % av parene går igjen) | Ikke bland dem. `--small` bruker `ratings_small` med `links_small`, full kjøring bruker `ratings` med `links` |
| Ratings, brukere og filmer | Ingen manglende verdier, duplikater eller ratings utenfor 0,5 til 5, så ingenting fjernes |

### Valg som er tatt

1. **De 13 duplikate `id`-ene i movies.** Jeg trenger én rad per film siden `_id` skal være TMDB-`id`. **Valg:** Jeg beholder raden med høyest `vote_count`, siden den har mest data bak seg. Da blir `popularity` også fra den raden og ikke et snitt som ikke finnes i kilden. Det avviker fra Tahirs notebook, som setter `popularity` til snittet.
2. **`budget` og `revenue` lik 0.** Spørring 1 og 4 summerer og tar median på `revenue`. Hvis 0 teller med, blir medianen kunstig lav. **Valg:** Jeg lagrer 0 som `null`, slik som for `runtime`. I spørringene hoppes filmer uten `revenue` over, og det skrives i rapporten.
3. **De lange `runtime`-verdiene** (for eksempel Centennial på 1 256 minutter). **Valg:** Jeg beholder dem, siden de ikke er bevist feil, og bruker median i oppgave 5 som tåler slike verdier.

## Rapporttekst – oppgave 1

Inntekt lik 0 beholdes i databasen, men behandles som ukjent i inntektsberegninger. Dette er en antakelse om uregistrert inntekt. Medianen beregnes fra positive inntekter; alle filmer telles fortsatt, og antall filmer med kjent inntekt oppgis separat.
