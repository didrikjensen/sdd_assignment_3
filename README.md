# sdd_assignment_3

Assignment 3 in TDT4225 – Very Large, Distributed Data Volumes (NTNU).

## Kjør lokalt

Start Docker Desktop. Kjør følgende fra `sdd_assignment_3`:

```bash
docker compose up -d --wait
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python example.py
```

Velg `.venv/bin/python` som Python-interpreter i VS Code.

Oppsettet bruker MongoDB 7.0.1, som angitt i oppgaven. `mongo-init.js`
oppretter brukeren `sdd` med passord `sdd` og `readWrite`-tilgang til databasen
`sdd`. Disse verdiene og `localhost` er fylt inn i `DbConnector.py`.
Admin-brukeren er kun til oppsett; Python bruker `sdd`-brukeren.

Stopp databasen med `docker compose down`. Data beholdes i Docker-volumet.
Init-scriptet kjøres bare første gang med et tomt volum.

## Authors

- [@didrikjensen](https://github.com/didrikjensen)
- [@tahir1611](https://github.com/tahir1611)
