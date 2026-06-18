"""
Vezilka Dialect Knowledge Graph — Triple Extraction Pipeline

Reads the corpus at data/dijalekti/ and produces RDF triples:
  Phase A: Dialect hierarchy from folder structure (already in ontology, skip)
  Phase B: Tokenize transcripts, accumulate per-dialect word counts
  Phase C: Lexemes (words) with dialect links and corpus frequency
  Phase D: Cross-dialect variant pairs via sound-correspondence filtering

Output: output/vezilka-data.ttl
"""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, SKOS, XSD

VEZ = Namespace("http://example.org/vezilka/ontology#")
VEZR = Namespace("http://example.org/vezilka/resource/")

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


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r"[а-яѓѕјљњќџёА-ЯЃЅЈЉЊЌЏЁ]+", text, re.IGNORECASE)
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS_MK]


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

    print("\nPhase B: Tokenizing transcripts, counting words per dialect...")
    records = load_metadata_files()
    print(f"  Found {len(records)} video metadata files")

    all_dialect_words: dict[str, Counter] = defaultdict(Counter)
    segment_count = 0

    for rec in records:
        for seg in rec["segments"]:
            text = seg["text"].strip()
            if not text:
                continue
            segment_count += 1
            for word, count in Counter(tokenize(text)).items():
                all_dialect_words[rec["dialect_key"]][word] += count

    print(f"  Transcript segments scanned: {segment_count}")

    # Phase C: create Лексема instances
    print("\nPhase C: Building lexeme instances...")
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

    # Phase D: variant proposals
    print("\nPhase D: Proposing cross-dialect variants...")
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
        "segments_scanned": segment_count,
        "lexemes": lexeme_count,
        "total_word_occurrences": sum(global_word_freq.values()),
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


# =============================================================
# Dialectal variant validation
#
# Fuzzy edit-distance alone keeps orthographic false friends (the
# сон/сом, рак/рок problem). A candidate pair is accepted only if w1
# aligns to w2 using exclusively *regular* Macedonian cross-dialect
# sound correspondences. This is fully automatic (no manual review)
# and trades recall for precision, as intended.
# =============================================================

# Allowed single-character substitutions (unordered).
_VARIANT_SUB_PAIRS = {
    frozenset(("е", "и")),
    frozenset(("о", "у")),
    frozenset(("ќ", "ч")),
    frozenset(("ѓ", "џ")),
    frozenset(("ѕ", "з")),
    frozenset(("х", "в")),
    frozenset(("х", "ф")),
    frozenset(("в", "ф")),
    frozenset(("л", "в")),
    frozenset(("њ", "н")),
    frozenset(("љ", "л")),
}

# Characters whose insertion/deletion is a regular elision (intervocalic
# г/в/х/ј loss: сега ~ сеа, човек ~ чоек; final/cluster т: што ~ шо).
_VARIANT_INDEL_CHARS = set("гвхјт")


def _align_ops(s1: str, s2: str) -> list[tuple[str, str, str]]:
    """Edit-distance alignment with backtrace -> list of (op, c1, c2)."""
    n, m = len(s1), len(s2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)

    ops: list[tuple[str, str, str]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if (
            i > 0 and j > 0
            and dp[i][j] == dp[i - 1][j - 1] + (0 if s1[i - 1] == s2[j - 1] else 1)
        ):
            op = "match" if s1[i - 1] == s2[j - 1] else "sub"
            ops.append((op, s1[i - 1], s2[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(("del", s1[i - 1], ""))
            i -= 1
        else:
            ops.append(("ins", "", s2[j - 1]))
            j -= 1
    return ops


def is_dialectal_variant(w1: str, w2: str, max_changes: int = 2) -> bool:
    """True only if w1/w2 differ by regular Macedonian sound correspondences."""
    if len(w1) < 3 or len(w2) < 3:
        return False
    changes = 0
    for op, c1, c2 in _align_ops(w1, w2):
        if op == "match":
            continue
        changes += 1
        if changes > max_changes:
            return False
        if op == "sub":
            if frozenset((c1, c2)) not in _VARIANT_SUB_PAIRS:
                return False
        else:  # ins / del
            if (c1 or c2) not in _VARIANT_INDEL_CHARS:
                return False
    return changes >= 1


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
                    if 0 < dist <= max_edit_dist and is_dialectal_variant(w1, w2):
                        candidates.append((w1, w2))
                        seen.add(pair_key)

    candidates.sort(key=lambda p: edit_distance(p[0], p[1]))
    return candidates


if __name__ == "__main__":
    run_pipeline()
