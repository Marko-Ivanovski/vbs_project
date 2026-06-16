# Scripts

Скрипти за извлекување на RDF тројки од корпусот, валидација на knowledge graph-от,
и вчитување во Neo4j.

## Предуслови

```bash
pip install -r requirements.txt
```

Потребни пакети: `rdflib`, `pyshacl`, `neo4j`, `python-dotenv`

## extract_triples.py

Главна скрипта за извлекување на тројки од `data/dijalekti/`. Поминува низ 6 фази:

| Фаза | Опис | Излез |
|------|------|-------|
| B | Парсирање на `metadata.json` -> `ТекстуаленСегмент` тројки | Сегменти со `vez:inDialect`, `vez:text` |
| C | Делење на сегменти во реченици | `Реченица` инстанци |
| D | Токенизација -> `Лексема` инстанци | Зборови со `vez:appearsInDialect`, `vez:frequency` |
| E | NER (gazetteer + regex) -> `Место`, `Лице` | Ентитети со `vez:mentionsPlace/Person` |
| F | Fuzzy matching + дијалектен филтер -> `vez:hasVariant` парови | Cross-dialect варијанти |

#### Филтер на варијанти (`is_dialectal_variant`)

Fuzzy matching по edit distance сам по себе задржува лажни парови (сон↔сом, рак↔рок).
Затоа фаза F прифаќа пар **само** ако зборовите се разликуваат по регуларни македонски
дијалектни гласовни промени (е/и, о/у, ч/ќ, в/л вокализација, елизија на г/в/х/ј/т).
Целосно автоматски, без рачна курација — намерно бира прецизност пред recall.
Ефект: **11,792 → 111** парови.

### Употреба

```bash
python scripts/extract_triples.py
```

### Излез

Сите фајлови се генерираат во `output/`:

- `vezilka-data.ttl` — RDF тројки (schema + data) во Turtle формат
- `stats.json` — статистика за корпусот (број на тројки, лексеми, сегменти итн.)
- `variants-review.csv` — филтрираните cross-dialect варијанти (111 парови)

### Конфигурација

- `GOVOR_TO_DIALECT` — mapping од `govor` полето во `metadata.json` кон URI-то на дијалектот
- `MK_PLACE_GAZETTEER` — листа на познати географски имиња за NER
- `STOPWORDS_MK` — stopwords кои се исклучуваат од лексемите

## validate.py

Валидација на генерираниот knowledge graph со SHACL shapes.

### Употреба

```bash
python scripts/validate.py
```

Ги вчитува `output/vezilka-data.ttl` и `ontology/vezilka-shapes.ttl`, и проверува дали сите инстанци ги задоволуваат дефинираните SHACL shapes (потребни properties, кардиналност, типови на податоци).

### Излез

- Конзолен output: `CONFORMS` или листа на violations
- `output/validation-report.txt` — целосен извештај

## load_neo4j.py

Го вчитува генерираниот RDF граф во **Neo4j Aura** за визуелно истражување. Aura Free
нема n10s (neosemantics) RDF plugin, па скриптата го парсира `output/vezilka-data.ttl` со
`rdflib` и го проектира во native property graph преку Bolt driver:

- секој `vezr:` ресурс → јазол, лабелиран според `rdf:type` (Лексема → `:Lexeme`, Дијалект → `:Dialect`, …) плюс заеднички `:Resource`
- literal properties → својства на јазол (`wordForm`, `frequency`, …)
- object properties → врски (`APPEARS_IN_DIALECT`, `HAS_VARIANT`, …)

Резултат: **73,270 јазли / 126,546 врски** (се вклопува во Aura Free лимитите 200k/400k).

### Употреба

```bash
cp .env.example .env      # внеси NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD
python scripts/load_neo4j.py
python scripts/load_neo4j.py --wipe   # избриши го постоечкиот граф пред вчитување
```

Credentials се читаат од gitignored `.env` (никогаш не се commit-ираат).
