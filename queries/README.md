# Queries

SPARQL прашања за competency questions на knowledge graph-от. Секое прашање одговара на едно од 10-те дефинирани прашања кои онтологијата треба да ги одговори.

## Предуслови

Пред да ги извршите queries, прво генерирајте го knowledge graph-от:

```bash
python scripts/extract_triples.py
```

## Листа на прашања

| Фајл | Прашање |
|------|---------|
| `q01_words_by_dialect.rq` | Кои зборови се карактеристични за одреден дијалект? |
| `q02_dialect_comparison.rq` | Како се разликува лексиката меѓу два дијалекта? |
| `q03_cross_dialect_variants.rq` | Кои зборови имаат варијанти во повеќе дијалекти? |
| `q04_places_by_dialect.rq` | Кои места се споменати во текстовите од даден дијалект? |
| `q05_shared_vocabulary.rq` | Колку зборови се заеднички за сите дијалекти? |
| `q06_top_words_per_dialect.rq` | Кои се најфреквентните зборови по дијалект? |
| `q07_topics_by_dialect.rq` | Кои теми се застапени по дијалект? (бара topic classification) |
| `q08_persons_by_dialect.rq` | Кои лица се споменати и во кои дијалекти? |
| `q09_lexical_diversity.rq` | Кое наречје има најголема лексичка разновидност? |
| `q10_unique_phrases.rq` | Кои фрази се уникатни за одреден дијалект? (бара phrase extraction) |

## Извршување на сите queries

```bash
python queries/run_queries.py
```

Ова ги вчитува сите `.rq` фајлови, ги извршува против `output/vezilka-data.ttl`, и ги печати резултатите во табеларна форма.

## Извршување на поединечен query

Може да се користи `rdflib` директно:

```python
from rdflib import Graph

g = Graph()
g.parse("output/vezilka-data.ttl", format="turtle")

with open("queries/q01_words_by_dialect.rq") as f:
    query = f.read()

for row in g.query(query):
    print(row)
```

## Модификација

Секој `.rq` фајл е стандарден SPARQL query. Може да се промени дијалектот во queries со замена на `vezr:bitolski` со друг дијалект URI, на пример:

- `vezr:skopski`
- `vezr:gevgeliski`
- `vezr:kochanski`
- `vezr:ohridski`

Целосната листа на дијалекти со податоци е дефинирана во `ontology/vezilka.ttl`.

## Забелешки

- Q7 и Q10 враќаат празни резултати бидејќи topic classification и phrase extraction се уште не се имплементирани.
- Q06 моментално користи глобална фреквенција, не per-dialect фреквенција.
- Queries може да се извршат и во Protégé или било кој SPARQL endpoint (Apache Jena Fuseki, GraphDB) со вчитување на `output/vezilka-data.ttl`.
