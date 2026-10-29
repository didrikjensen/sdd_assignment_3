# sdd_assignment_3

Assignment 3 in TDT4225 – Very Large, Distributed Data Volumes (NTNU).

## Kjør lokalt

Start Docker Desktop. Kjør følgende fra `sdd_assignment_3`:

```bash
docker compose up -d --wait
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python example.py
```

Velg `.venv/bin/python` (Windows: `.venv\Scripts\python.exe`) som Python-interpreter i VS Code.

## Kjørerekkefølge

Legg datafilene i `data/` (mappen er ikke med i repoet). Kjør deretter fra tom database:

```bash
python setup_db.py       # oppretter kolleksjonene movies og ratings med skjema
python insert_data.py    # renser og setter inn filmer og ratings (full ratings.csv, tar en stund)
python queries.py        # kjører alle spørringene
python queries.py 6 7    # eller bare utvalgte oppgaver
```

`insert_data.py` avbryter hvis kolleksjonene allerede har data. Start på nytt med
`docker compose down -v` og kjør rekkefølgen over.

EDA ligger i `eda.ipynb`. Kjør den med samme `.venv` (kjernen krever `ipykernel`).

Oppsettet bruker MongoDB 7.0.1, som angitt i oppgaven. `mongo-init.js`
oppretter brukeren `sdd` med passord `sdd` og `readWrite`-tilgang til databasen
`sdd`. Disse verdiene og `localhost` er fylt inn i `DbConnector.py`.
Admin-brukeren er kun til oppsett; Python bruker `sdd`-brukeren.

Stopp databasen med `docker compose down`. Data beholdes i Docker-volumet.
Init-scriptet kjøres bare første gang med et tomt volum.

## Authors

- [@didrikjensen](https://github.com/didrikjensen)
- [@tahir1611](https://github.com/tahir1611)

## Rapport og kontroll av tekstsøk

Rapportkilden og figurene ligger i `report/`. Fullstendige spørringsresultater ligger i
`report/results/`, inkludert alle par fra oppgave 2 og alle grupper fra oppgave 5.
Rapportfigurene viser lesbare tabeller fra disse resultatene. Alle spørringer skriver
ut med `pprint`; funksjonsnavnene er `task_1` til `task_10`.

Kjør `python scripts/verify_noir.py` for å sammenligne delstrengsøk og ordgrensesøk
i råfilen. Kontrollen skriver `report/noir_verification.json`.

Figurene kan regenereres med `python scripts/render_report_figures.py`.
Kompiler `report/main.tex` i Overleaf eller med en lokal LaTeX-installasjon.
