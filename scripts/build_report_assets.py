"""Lag HTML-visninger av faktiske resultater og kodeutdrag til rapportfigurene.

HTML-visningene er mellomfiler for render_report_figures.py. Beregningene ligger i
queries.py; resultatgrunnlaget fra kontrollkjøringene ligger i report/results.
"""
import ast
import html
import json
import math
import tempfile
import textwrap
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(tempfile.gettempdir()) / 'sdd_assignment3_report_html'
OUT.mkdir(parents=True, exist_ok=True)
MANIFEST = []
STYLE = '''body{margin:0;background:white;color:#172332;font-family:Arial,sans-serif}
.capture{width:900px;padding:20px;box-sizing:border-box;background:white}
h1{font-size:23px;margin:0 0 5px;color:#00509e} .sub{font-size:14px;color:#4b5966;margin:0 0 16px}
table{width:100%;border-collapse:collapse;table-layout:auto;font-size:18px;line-height:1.2}
th{text-align:left;font-size:15px;color:#31485b;background:#edf3f7;padding:9px 8px;border-bottom:2px solid #00509e}
td{padding:7px 8px;border-bottom:1px solid #dce3e8;vertical-align:top}
tbody tr:nth-child(even){background:#f7f9fb} .num{text-align:right;white-space:nowrap}
.note{font-size:14px;color:#4b5966;margin:13px 0 0;line-height:1.35}
pre{font:16.5px/1.25 Menlo,Consolas,monospace;margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
.highlight{background:#f7f9fb!important;padding:12px;border:1px solid #dce3e8}h2{font-size:19px;margin:20px 0 8px;color:#00509e}
'''
FMT=HtmlFormatter(style='friendly',nowrap=False)
STYLE+=FMT.get_style_defs('.highlight')
def e(v): return html.escape(str(v))
def num(v,d=0):
    if v is None: return 'Ukjent'
    return f'{v:,.{d}f}'.replace(',',' ').replace('.',',')
def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
def asset(name,title,body,note='',sub='Resultater fra kontrollkjøring'):
    content=f'<!doctype html><html lang="no"><meta charset="utf-8"><title>{e(title)}</title><style>{STYLE}</style><body><main class="capture"><h1>{e(title)}</h1><p class="sub">{e(sub)}</p>{body}'+(f'<p class="note">{e(note)}</p>' if note else '')+'</main></body></html>'
    p=OUT/(name+'.html'); p.write_text(content)
    MANIFEST.append({'name':name,'html':str(p),'image':str(ROOT/'report'/(name+'.jpg'))})
def result(n):
    data=json.loads((ROOT/f'report/results/task_{n}.json').read_text())
    return data[0] if len(data)==1 and isinstance(data[0],list) else data

r=result(1)
asset('resultat_01','Oppgave 1 · Regissører med høyest medianinntekt',table(['Regissør','Filmer','Kjent<br>inntekt','Medianinntekt<br>(USD)','Snitt<br>vote_average'],[[e(x['director']),x['movie_count'],x['revenue_count'],num(x['median_revenue']),num(x['mean_vote_average'],3)] for x in r]),'Alle 10 regissører. Medianen bruker bare positive registrerte inntekter.')
r=result(2)
asset('resultat_02','Oppgave 2 · Skuespillerpar',table(['Skuespiller A','Skuespiller B','Felles<br>filmer','Snitt<br>vote_average'],[[e(x['actor_a']),e(x['actor_b']),x['movie_count'],num(x['mean_vote_average'],3)] for x in r[:15]]),'De første 15 av totalt 45 650 par, sortert etter antall felles filmer.')
r=result(3)
asset('resultat_03','Oppgave 3 · Skuespillernes sjangerbredde',table(['Skuespiller','Filmer','Unike<br>sjangre','Fem eksempelsjangre'],[[e(x['actor']),x['movie_count'],x['genre_count'],e(', '.join(x['example_genres']))] for x in r]),'Alle 10 skuespillere. Ved lik sjangerbredde brukes stigende person-ID.')
r=result(4)
asset('resultat_04','Oppgave 4 · Filmsamlinger etter registrert inntekt',table(['Samling','Filmer','Kjent<br>inntekt','Sum inntekt<br>(USD)','Median<br>vote_average','Første / siste<br>utgivelse'],[[e(x['collection'].removesuffix(' Collection')),x['movie_count'],x['revenue_count'],num(x['total_revenue']),num(x['median_vote_average'],2),e(x['earliest_release'])+'<br>'+e(x['latest_release'])] for x in r]),'Alle 10 samlinger. Totalene gjelder registrerte inntekter og er ikke inflasjonsjustert.')
r=result(5)
asset('resultat_05','Oppgave 5 · Spilletid per tiår og primærsjanger',table(['Tiår','Primærsjanger','Filmer','Kjent<br>spilletid','Median<br>(minutter)'],[[str(x['_id']['decade'])+'-tallet',e(x['_id']['genre']),x['movie_count'],x['runtime_count'],num(x['median_runtime'],1)] for x in r[:15]]),'De første 15 av totalt 232 grupper, sortert etter tiår og synkende median spilletid.')
r=result(6)
asset('resultat_06','Oppgave 6 · Kvinneandel blant de fem øverst krediterte',table(['Tiår','Gjennomsnittlig kvinneandel','Antall filmer'],[[str(int(x['_id']))+'-tallet',num(x['avg_female_share'],3),num(x['movies'])] for x in r]),'Alle 15 tiår. Andelen beregnes per film blant de fem øverst krediterte med kjent kjønn.')
r=result(7)
asset('resultat_07','Oppgave 7 · Teksttreff på noir',table(['Tittel','År','vote_average','vote_count'],[[e(x['title']),x['year'],num(x['vote_average'],1),num(x['vote_count'])] for x in r]),'Alle 5 filmer med teksttreff og minst 50 stemmer. Ordgrensekontroll i rå CSV gir samme filmer.')
r=result(8)
for name,part,label in [('resultat_08',r[:10],'1–10'),('resultat_08_del2',r[10:],'11–20')]:
    asset(name,f'Oppgave 8 · Regissør–skuespiller-par, plass {label}',table(['Regissør','Skuespiller','Filmer','Snitt<br>vote_average','Snittinntekt<br>(USD)'],[[e(x['director']),e(x['actor']),x['films'],num(x['mean_vote_average'],3),num(x['mean_revenue'])] for x in part]),f'Plass {label} av topp 20. Bare filmer med minst 100 stemmer inngår; inntekt 0 utelates fra inntektssnittet.')
r=result(9)
asset('resultat_09','Oppgave 9 · Språk blant filmer med USA som produksjonsland',table(['Originalspråk','Antall filmer','Eksempeltittel'],[[e(x['_id']),x['count'],e(x['example'])] for x in r]),'Alle 10 språkgrupper. Selskapsland kan ikke fastslås eksakt fra feltene i datasettet.')
if (ROOT/'report/results/task_10.json').exists():
    groups=json.loads((ROOT/'report/results/task_10.json').read_text())
    seconds=json.loads((ROOT/'report/results/timing_10.json').read_text())['seconds']
    for name,r,title in [('resultat_10',groups[0],'mest sjangerbrede brukere'),('resultat_10_varians',groups[1],'brukere med høyest varians')]:
        asset(name,'Oppgave 10 · '+title,table(['userId','Antall ratings','Populasjonsvarians','Unike sjangre'],[[x['_id'],num(x['n']),num(x['variance'],4),x['genres']] for x in r]),f'Alle 10 brukere. Minst 20 ratings kreves. Kjøretid for hele spørringen i kontrollkjøringen: {num(seconds,1)} sekunder.')

source=(ROOT/'queries.py').read_text(); tree=ast.parse(source)
for f in [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name.startswith('task_')]:
    n=int(f.name.split('_')[1]); raw=ast.get_source_segment(source,f)
    lines=[line for line in raw.splitlines() if line.strip()]
    omitted = False
    def cost(ls): return sum(max(1,math.ceil(len(line)/94)) for line in ls)
    if cost(lines)>28 and n != 10:
        if n==2: marker=next(i for i,l in enumerate(lines) if '"cast_a": "$cast"' in l)
        elif n==1: marker=next(i for i,l in enumerate(lines) if 'revenues = [' in l)
        elif n==3: marker=next(i for i,l in enumerate(lines) if 'genres = set()' in l)
        elif n==4: marker=next(i for i,l in enumerate(lines) if '"total_revenue"' in l)
        elif n==5: marker=next(i for i,l in enumerate(lines) if '"decade": {' in l)
        elif n==8: marker=next(i for i,l in enumerate(lines) if '"films": {"$sum"' in l)
        elif n==10: marker=next(i for i,l in enumerate(lines) if '"$lookup"' in l)
        else: marker=len(lines)//2
        selections=sorted(set(range(min(4,len(lines))))|set(range(max(4,marker-2),min(len(lines),marker+8)))|set(range(max(0,len(lines)-7),len(lines))))
        chosen=[]; previous=-1
        for i in selections:
            if previous>=0 and i>previous+1:
                chosen.append('    # ... (utdrag; hele funksjonen ligger i queries.py)')
                omitted = True
            chosen.append(lines[i]); previous=i
        lines=chosen
    body=highlight('\n'.join(lines),PythonLexer(),FMT)
    asset(f'kode_{n:02d}',f'queries.py · task_{n}',body,('Kodeutdrag fra gjeldende innleveringsfil. Utelatte linjer er markert med «...».' if omitted else 'Hele funksjonen fra gjeldende innleveringsfil; blanklinjer er utelatt.'),'Samme funksjonsnavn og pprint-format i alle oppgavene')

evidence=json.loads((ROOT/'report/results/insertion_evidence.json').read_text())
m=evidence['example']
body=table(['Kontroll','Verdi'],[['movies.count_documents({})',num(evidence['movies'])],['ratings.estimated_document_count()',num(evidence['ratings'])]])
body+='<h2>Eksempelfilm: movies.find_one({"_id": 862})</h2>'
body+=table(['Felt','Registrert verdi'],[['_id',m['_id']],['title',e(m['title'])],['release_date',e(m['release_date'])],['revenue (USD)',num(m['revenue'])],['genres',e(', '.join(x['name'] for x in m['genres']))],['Antall cast-/crew-oppføringer',f'{m["cast_count"]} / {m["crew_count"]}']])
asset('innsetting_kontroll','Kontroll av innsettingen',body,'Utdrag fra en lesekontroll av den eksisterende databasen. Ratings-antallet samsvarer med 26 024 289 rader i råfilen.','Dokumentantall, datatyper og innebygde lister')
(OUT/'manifest.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2))
print('HTML-visninger:',len(MANIFEST)); print(OUT/'manifest.json')
