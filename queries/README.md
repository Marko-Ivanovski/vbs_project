# Queries

SPARQL прашања за competency questions на knowledge graph-от. Секое прашање одговара на едно од 8-те дефинирани прашања кои онтологијата треба да ги одговори.

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
| `q04_shared_vocabulary.rq` | Колку зборови се заеднички за сите дијалекти? |
| `q05_top_words_per_dialect.rq` | Кои се најфреквентните зборови по дијалект? |
| `q06_dialect_similarity.rq` | Кои дијалекти се најслични според заеднички варијантни зборови? |
| `q07_lexical_diversity.rq` | Кое наречје има најголема лексичка разновидност? |
| `q08_most_variable_words.rq` | Кои зборови варираат најмногу низ дијалектите? |

## Извршување на сите queries

```bash
python queries/run_queries.py
```

Ова ги вчитува сите `.rq` фајлови, ги извршува против `output/vezilka-data.ttl`, и ги печати резултатите во табеларна форма.

## Модификација

Секој `.rq` фајл е стандарден SPARQL query. Може да се промени дијалектот во queries со замена на `vezr:bitolski` со друг дијалект URI, на пример:

- `vezr:skopski`
- `vezr:gevgeliski`
- `vezr:kochanski`
- `vezr:ohridski`

Целосната листа на дијалекти со податоци е дефинирана во `ontology/vezilka.ttl`.
