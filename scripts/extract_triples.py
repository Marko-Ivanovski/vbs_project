"""
Vezilka Dialect Knowledge Graph — Triple Extraction Pipeline

Reads the corpus at data/dijalekti/ and produces RDF triples:
  Phase A: Dialect hierarchy from folder structure (already in ontology, skip)
  Phase B: Text segments from metadata.json
  Phase C: Sentences from segments
  Phase D: Lexemes (words) with dialect links and frequency
  Phase E: Named entities (places, people) via pattern matching
  Phase F: Cross-dialect variant proposals via fuzzy matching

Output: output/vezilka-data.ttl
"""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

VEZ = Namespace("https://w3id.org/vezilka/ontology#")
VEZR = Namespace("https://w3id.org/vezilka/resource/")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "dijalekti"
ONTOLOGY_FILE = Path(__file__).resolve().parent.parent / "ontology" / "vezilka.ttl"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

GOVOR_TO_DIALECT = {
    "skopski": "skopski",
    "bitolski": "bitolski",
    "gevgeliski": "gevgeliski",
    "kochanski": "kochanski",
    "shtipski": "shtipski",
    "kumanovski": "kumanovski",
    "ovchepolski": "ovchepolski",
    "prilepski": "prilepski",
    "veleshki": "veleshki",
    "kichevsko-porechki": "kichevsko_porechki",
    "kichevsko_porechki": "kichevsko_porechki",
    "ohridski": "ohridski",
    "strushki": "strushki",
}

MK_PLACE_GAZETTEER = {
    "Скопје", "Битола", "Охрид", "Прилеп", "Велес", "Куманово",
    "Штип", "Кочани", "Гевгелија", "Струга", "Кичево", "Тетово",
    "Струмица", "Кавадарци", "Неготино", "Валандово", "Кратово",
    "Крива Паланка", "Дебар", "Свети Николе", "Преспа", "Ресен",
    "Македонија", "Република Македонија", "Југославија",
    "Србија", "Бугарија", "Грција", "Албанија", "Хрватска",
    "Германија", "Словенија", "Босна", "Косово", "Црна Гора",
    "Европа", "Америка", "Австралија",
    "Мариово", "Пелагонија", "Повардарје", "Полог",
    "Вардар", "Дојран", "Преспанско Езеро", "Охридско Езеро",
    "Солун", "Београд", "Загреб", "Софија",
}

STOPWORDS_MK = {
    "и", "во", "на", "за", "со", "од", "да", "не", "е", "се",
    "а", "но", "ги", "го", "ја", "ке", "ќе", "ни", "ми", "ти",
    "си", "му", "им", "нас", "вас", "тоа", "тој", "таа", "тие",
    "што", "шо", "кој", "која", "кои", "како", "каде", "кога",
    "или", "ама", "пак", "уште", "веќе", "само", "дека", "оти",
    "ова", "овој", "оваа", "овие", "она", "оној", "онаа", "оние",
    "еден", "една", "едно", "едни", "некој", "нешто", "секој",
    "сум", "сме", "сте", "сè", "сите", "може", "треба",
    "би", "бил", "била", "биле", "било", "бев", "беше",
    "ако", "кога", "така", "тука", "таму", "нема", "има",
    "јас", "ние", "вие", "тие", "мене", "тебе", "нему",
    "мој", "моја", "мое", "мои", "твој", "негов", "нејзин",
    "овде", "онде", "сега", "тогаш", "потоа", "пред", "после",
    "до", "без", "меѓу", "под", "над", "кон", "при", "низ",
    "многу", "малку", "повеќе", "помалку", "најмногу",
    "бидејќи", "затоа", "значи", "навистина", "всушност",
    "ич", "баш", "пра", "ли", "ни", "ич",
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    text = text.strip("_")
    return text[:80]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = []
    for p in parts:
        p = p.strip()
        if len(p) > 2:
            sentences.append(p)
    if not sentences and text.strip():
        sentences = [text.strip()]
    return sentences


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r"[а-яѓѕјљњќџёА-ЯЃЅЈЉЊЌЏЁ]+", text, re.IGNORECASE)
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS_MK]


def find_places(text: str) -> set[str]:
    found = set()
    for place in MK_PLACE_GAZETTEER:
        if place in text:
            found.add(place)
    return found


def find_persons(text: str) -> set[str]:
    found = set()
    pattern = r"\b([А-ЯЃЅЈЉЊЌЏ][а-яѓѕјљњќџ]{2,})\s+([А-ЯЃЅЈЉЊЌЏ][а-яѓѕјљњќџ]{2,})\b"
    for match in re.finditer(pattern, text):
        first, last = match.group(1), match.group(2)
        full = f"{first} {last}"
        if first not in MK_PLACE_GAZETTEER and last not in MK_PLACE_GAZETTEER:
            found.add(full)
    return found


def load_metadata_files() -> list[dict]:
    records = []
    for meta_path in sorted(DATA_DIR.rglob("metadata.json")):
        try:
            with open(meta_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  SKIP (parse error): {meta_path}")
            continue

        if not data or not isinstance(data, list):
            continue

        header = data[0]
        govor = header.get("govor", "")
        dialect_key = GOVOR_TO_DIALECT.get(govor)
        if not dialect_key:
            print(f"  SKIP (unknown govor '{govor}'): {meta_path}")
            continue

        video_title = meta_path.parent.name
        segments = [
            entry for entry in data[1:]
            if isinstance(entry, dict) and entry.get("text", "").strip()
        ]

        records.append({
            "path": meta_path,
            "govor": govor,
            "dialect_key": dialect_key,
            "video_title": video_title,
            "segments": segments,
        })
    return records


def run_pipeline():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    g = Graph()
    g.bind("vez", VEZ)
    g.bind("vezr", VEZR)
    g.bind("skos", SKOS)
    g.bind("owl", OWL)

    print("Loading ontology schema...")
    g.parse(str(ONTOLOGY_FILE), format="turtle")
    schema_triples = len(g)
    print(f"  Schema loaded: {schema_triples} triples")

    print("\nPhase B: Extracting text segments from metadata.json...")
    records = load_metadata_files()
    print(f"  Found {len(records)} video metadata files")

    source_uris = {}
    segment_count = 0
    sentence_count = 0
    all_dialect_words: dict[str, Counter] = defaultdict(Counter)
    all_places: set[str] = set()
    all_persons: set[str] = set()
    segment_entities: list[tuple] = []

    for rec in records:
        dialect_uri = VEZR[rec["dialect_key"]]
        source_slug = slugify(rec["video_title"])
        source_uri = VEZR[f"source_{source_slug}"]

        if source_uri not in source_uris:
            g.add((source_uri, RDF.type, VEZ.Извор))
            g.add((source_uri, VEZ.sourceTitle, Literal(rec["video_title"])))
            g.add((source_uri, VEZ.govor, Literal(rec["govor"])))
            source_uris[source_uri] = True

        for i, seg in enumerate(rec["segments"]):
            text = seg["text"].strip()
            if not text:
                continue

            seg_uri = VEZR[f"seg_{source_slug}_{i:04d}"]
            g.add((seg_uri, RDF.type, VEZ.ТекстуаленСегмент))
            g.add((seg_uri, VEZ.text, Literal(text, lang="mk")))
            g.add((seg_uri, VEZ.inDialect, dialect_uri))
            g.add((seg_uri, VEZ.fromSource, source_uri))
            g.add((seg_uri, VEZ.segmentIndex, Literal(i, datatype=XSD.integer)))
            segment_count += 1

            # Phase C: sentences
            sentences = split_sentences(text)
            for j, sent_text in enumerate(sentences):
                sent_uri = VEZR[f"sent_{source_slug}_{i:04d}_{j:03d}"]
                g.add((sent_uri, RDF.type, VEZ.Реченица))
                g.add((sent_uri, VEZ.text, Literal(sent_text, lang="mk")))
                g.add((seg_uri, VEZ.containsSentence, sent_uri))
                g.add((sent_uri, VEZ.sentenceOf, seg_uri))
                sentence_count += 1

            # Phase D: words
            words = tokenize(text)
            word_counts = Counter(words)
            for word, count in word_counts.items():
                all_dialect_words[rec["dialect_key"]][word] += count

            # Phase E: NER
            places = find_places(text)
            persons = find_persons(text)
            all_places.update(places)
            all_persons.update(persons)
            if places or persons:
                segment_entities.append((seg_uri, places, persons))

    print(f"  Segments: {segment_count}")
    print(f"  Sentences: {sentence_count}")

    # Phase D (cont): create Лексема instances
    print("\nPhase D: Building lexeme instances...")
    global_word_freq: Counter = Counter()
    word_dialects: dict[str, set[str]] = defaultdict(set)

    for dialect_key, word_counts in all_dialect_words.items():
        for word, count in word_counts.items():
            global_word_freq[word] += count
            word_dialects[word].add(dialect_key)

    lexeme_count = 0
    for word, freq in global_word_freq.items():
        word_slug = slugify(word)
        if not word_slug:
            continue
        lex_uri = VEZR[f"lex_{word_slug}"]
        g.add((lex_uri, RDF.type, VEZ.Лексема))
        g.add((lex_uri, VEZ.wordForm, Literal(word)))
        g.add((lex_uri, VEZ.frequency, Literal(freq, datatype=XSD.integer)))

        for dk in word_dialects[word]:
            g.add((lex_uri, VEZ.appearsInDialect, VEZR[dk]))

        lexeme_count += 1

    print(f"  Lexemes: {lexeme_count}")
    print(f"  Total word occurrences: {sum(global_word_freq.values())}")

    # Phase E (cont): create entity instances
    print("\nPhase E: Creating named entity instances...")
    place_uris = {}
    for place_name in sorted(all_places):
        place_slug = slugify(place_name)
        place_uri = VEZR[f"place_{place_slug}"]
        if (place_uri, RDF.type, VEZ.Место) not in g:
            g.add((place_uri, RDF.type, VEZ.Место))
            g.add((place_uri, VEZ.placeName, Literal(place_name)))
            g.add((place_uri, RDFS.label, Literal(place_name, lang="mk")))
        place_uris[place_name] = place_uri

    person_uris = {}
    for person_name in sorted(all_persons):
        person_slug = slugify(person_name)
        person_uri = VEZR[f"person_{person_slug}"]
        g.add((person_uri, RDF.type, VEZ.Лице))
        g.add((person_uri, VEZ.personName, Literal(person_name)))
        g.add((person_uri, RDFS.label, Literal(person_name, lang="mk")))
        person_uris[person_name] = person_uri

    for seg_uri, places, persons in segment_entities:
        for p in places:
            if p in place_uris:
                g.add((seg_uri, VEZ.mentionsPlace, place_uris[p]))
        for p in persons:
            if p in person_uris:
                g.add((seg_uri, VEZ.mentionsPerson, person_uris[p]))

    print(f"  Places: {len(place_uris)}")
    print(f"  Persons: {len(person_uris)}")

    # Phase F: variant proposals
    print("\nPhase F: Proposing cross-dialect variants...")
    variant_pairs = find_variant_candidates(all_dialect_words, global_word_freq)
    for w1, w2 in variant_pairs:
        uri1 = VEZR[f"lex_{slugify(w1)}"]
        uri2 = VEZR[f"lex_{slugify(w2)}"]
        g.add((uri1, VEZ.hasVariant, uri2))

    print(f"  Variant pairs proposed: {len(variant_pairs)}")

    # Save
    output_file = OUTPUT_DIR / "vezilka-data.ttl"
    g.serialize(str(output_file), format="turtle", encoding="utf-8")
    total_triples = len(g)
    print(f"\nDone! Total triples: {total_triples} (schema: {schema_triples}, data: {total_triples - schema_triples})")
    print(f"Output: {output_file}")

    # Stats
    stats = {
        "schema_triples": schema_triples,
        "data_triples": total_triples - schema_triples,
        "total_triples": total_triples,
        "videos": len(records),
        "segments": segment_count,
        "sentences": sentence_count,
        "lexemes": lexeme_count,
        "total_word_occurrences": sum(global_word_freq.values()),
        "places": len(place_uris),
        "persons": len(person_uris),
        "variant_pairs": len(variant_pairs),
        "dialects_with_data": len(all_dialect_words),
        "per_dialect_lexeme_counts": {
            dk: len(wc) for dk, wc in sorted(all_dialect_words.items())
        },
    }
    stats_file = OUTPUT_DIR / "stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"Stats: {stats_file}")

    # Variant review CSV
    if variant_pairs:
        csv_file = OUTPUT_DIR / "variants-review.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("word_1,dialects_1,word_2,dialects_2,edit_distance,correct\n")
            for w1, w2 in variant_pairs:
                d1 = ";".join(sorted(word_dialects[w1]))
                d2 = ";".join(sorted(word_dialects[w2]))
                dist = edit_distance(w1, w2)
                f.write(f"{w1},{d1},{w2},{d2},{dist},\n")
        print(f"Variant review: {csv_file}")


def edit_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return edit_distance(s2, s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(s2)]


def find_variant_candidates(
    dialect_words: dict[str, Counter],
    global_freq: Counter,
    min_freq: int = 3,
    max_edit_dist: int = 2,
) -> list[tuple[str, str]]:
    dialect_exclusive: dict[str, set[str]] = {}
    for dk, wc in dialect_words.items():
        words_here = {w for w, c in wc.items() if c >= min_freq}
        other_dialects = set()
        for dk2, wc2 in dialect_words.items():
            if dk2 != dk:
                other_dialects.update(w for w, c in wc2.items() if c >= min_freq)
        exclusive = words_here - other_dialects
        dialect_exclusive[dk] = exclusive

    candidates = []
    seen = set()

    dialect_keys = sorted(dialect_exclusive.keys())
    for i, dk1 in enumerate(dialect_keys):
        for dk2 in dialect_keys[i + 1:]:
            words1 = dialect_exclusive[dk1]
            words2 = dialect_exclusive[dk2]
            for w1 in words1:
                if len(w1) < 3:
                    continue
                for w2 in words2:
                    if len(w2) < 3:
                        continue
                    if abs(len(w1) - len(w2)) > max_edit_dist:
                        continue
                    pair_key = tuple(sorted([w1, w2]))
                    if pair_key in seen:
                        continue
                    dist = edit_distance(w1, w2)
                    if 0 < dist <= max_edit_dist:
                        candidates.append((w1, w2))
                        seen.add(pair_key)

    candidates.sort(key=lambda p: edit_distance(p[0], p[1]))
    return candidates


if __name__ == "__main__":
    run_pipeline()
