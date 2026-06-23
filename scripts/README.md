# Scripts

Скрипти за извлекување на RDF тројки од корпусот, валидација на knowledge graph-от, и вчитување во Neo4j.

## Предуслови

```bash
pip install -r requirements.txt
```

Потребни пакети: `rdflib`, `pyshacl`, `neo4j`, `python-dotenv`

## extract_triples.py

Главна скрипта за извлекување на тројки од `data/dijalekti/`. Поминува низ 3 фази
(фаза A — дијалектната хиерархија — е веќе дефинирана во онтологијата):

| Фаза | Опис | Излез |
|------|------|-------|
| B | Токенизација на транскриптите, броење зборови по дијалект | per-dialect word counts |
| C | Градење `Лексема` инстанци | Зборови со `vez:appearsInDialect`, `vez:frequency` |
| D | Sound-correspondence филтер -> `vez:hasVariant` парови | Cross-dialect варијанти |

#### Филтер на варијанти (`is_dialectal_variant`)

Fuzzy matching по edit distance сам по себе задржува лажни парови (сон↔сом, рак↔рок).
Затоа фаза D прифаќа пар **само** ако зборовите се разликуваат по регуларни македонски
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
- `stats.json` — статистика за корпусот (број на тројки, лексеми, варијанти итн.)
- `variants-review.csv` — филтрираните cross-dialect варијанти (111 парови)

### Конфигурација

- `GOVOR_TO_DIALECT` — mapping од `govor` полето во `metadata.json` кон URI-то на дијалектот
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

Резултат: **36,416 јазли / 52,649 врски** (36,368 лексеми + 36 јазли дијалектна хиерархија
+ 12 региони). Лесно се вклопува во Aura Free лимитите (200k/400k).

### Употреба

```bash
cp .env.example .env
python scripts/load_neo4j.py
python scripts/load_neo4j.py --wipe
```

Credentials се читаат од gitignored `.env`.
