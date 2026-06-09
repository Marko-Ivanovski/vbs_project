# Scripts

Скрипти за извлекување на RDF тројки од корпусот и валидација на knowledge graph-от.

## Предуслови

```bash
pip install -r requirements.txt
```

Потребни пакети: `rdflib`, `pyshacl`

## extract_triples.py

Главна скрипта за извлекување на тројки од `data/dijalekti/`. Поминува низ 6 фази:

| Фаза | Опис | Излез |
|------|------|-------|
| B | Парсирање на `metadata.json` -> `ТекстуаленСегмент` тројки | Сегменти со `vez:inDialect`, `vez:text` |
| C | Делење на сегменти во реченици | `Реченица` инстанци |
| D | Токенизација -> `Лексема` инстанци | Зборови со `vez:appearsInDialect`, `vez:frequency` |
| E | NER (gazetteer + regex) -> `Место`, `Лице` | Ентитети со `vez:mentionsPlace/Person` |
| F | Fuzzy matching -> `vez:hasVariant` парови | Cross-dialect варијанти |

### Употреба

```bash
python scripts/extract_triples.py
```

### Излез

Сите фајлови се генерираат во `output/`:

- `vezilka-data.ttl` — RDF тројки (schema + data) во Turtle формат
- `stats.json` — статистика за корпусот (број на тројки, лексеми, сегменти итн.)
- `variants-review.csv` — предложени cross-dialect варијанти за рачна курација

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
