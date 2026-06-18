import re
import math
import time
import bisect
import threading
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import OrderedDict, defaultdict
from difflib import SequenceMatcher


STOP_WORDS: Set[str] = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'can', 'shall', 'not', 'no', 'nor',
    'so', 'yet', 'both', 'either', 'neither', 'each', 'every', 'all', 'any',
    'few', 'more', 'most', 'other', 'some', 'such', 'no', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here',
    'there', 'when', 'where', 'why', 'how', 'if', 'then', 'else', 'that',
    'this', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
    'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our',
    'their', 'what', 'which', 'who', 'whom',
}


SYNONYM_GROUPS: List[Set[str]] = [
    {'restart', 'reboot', 'reload', 'restarting', 'relaunch'},
    {'stop', 'halt', 'shutdown', 'terminate', 'kill', 'end'},
    {'start', 'launch', 'begin', 'run', 'execute', 'startup'},
    {'status', 'state', 'condition', 'info', 'check'},
    {'update', 'upgrade', 'patch', 'refresh', 'sync'},
    {'install', 'setup', 'deploy', 'configure', 'installing'},
    {'remove', 'delete', 'uninstall', 'purge', 'clean'},
    {'list', 'show', 'display', 'ls', 'get', 'view'},
    {'log', 'logs', 'logger', 'logging', 'output', 'record'},
    {'config', 'configuration', 'settings', 'preferences', 'setup'},
    {'server', 'host', 'machine', 'node', 'instance'},
    {'command', 'cmd', 'script', 'shell', 'bash', 'cli'},
    {'error', 'fail', 'failure', 'failed', 'exception', 'issue', 'problem'},
    {'success', 'succeed', 'ok', 'pass', 'passed', 'completed'},
    {'build', 'compile', 'make', 'builds', 'building'},
    {'test', 'verify', 'validate', 'check', 'testing'},
    {'backup', 'save', 'archive', 'copy', 'snapshot'},
    {'restore', 'recover', 'rollback', 'revert'},
]


def build_synonym_map(groups: List[Set[str]]) -> Dict[str, Set[str]]:
    synonym_map: Dict[str, Set[str]] = {}
    for group in groups:
        for word in group:
            synonym_map[word] = group
    return synonym_map


SYNONYM_MAP = build_synonym_map(SYNONYM_GROUPS)


def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r'[a-z0-9_\-\.]+', text)
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def fuzzy_similarity(s1: str, s2: str) -> float:
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def get_synonyms(word: str) -> Set[str]:
    word_lower = word.lower()
    return SYNONYM_MAP.get(word_lower, {word_lower})


def _bigrams(term: str) -> List[str]:
    if len(term) < 2:
        padded = term + '$'
    else:
        padded = '$' + term + '$'
    return [padded[i:i + 2] for i in range(len(padded) - 1)]


@dataclass
class SearchDocument:
    doc_id: str
    doc_type: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    timestamp: Optional[float] = None
    status: Optional[str] = None
    server_id: Optional[str] = None
    server_tags: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    doc: SearchDocument
    score: float
    highlights: List[str] = field(default_factory=list)
    matched_terms: List[str] = field(default_factory=list)


@dataclass
class SearchFilter:
    doc_types: Optional[List[str]] = None
    time_range: Optional[Tuple[float, float]] = None
    statuses: Optional[List[str]] = None
    server_ids: Optional[List[str]] = None
    server_tags: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class SearchEngine:
    _CACHE_SIZE = 256

    def __init__(self):
        self._documents: Dict[str, SearchDocument] = {}
        self._inverted_index: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._doc_lengths: Dict[str, float] = {}
        self._doc_terms: Dict[str, Set[str]] = {}
        self._total_doc_length: float = 0.0
        self._avg_doc_length: float = 0.0
        self._doc_count: int = 0
        self._ngram_index: Dict[str, Set[str]] = defaultdict(set)
        self._sorted_terms: List[str] = []
        self._terms_dirty: bool = True
        self._time_sorted: List[Tuple[float, str]] = []
        self._type_index: Dict[str, Set[str]] = defaultdict(set)
        self._status_index: Dict[str, Set[str]] = defaultdict(set)
        self._server_index: Dict[str, Set[str]] = defaultdict(set)
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._server_tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._search_history: List[Dict[str, Any]] = []
        self._popular_searches: Dict[str, int] = defaultdict(int)
        self._cache: "OrderedDict[Tuple, Tuple[List[SearchResult], int]]" = OrderedDict()
        self._lock = threading.RLock()

    def _compute_bm25_score(
        self,
        query_terms: List[str],
        doc_id: str,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> float:
        if doc_id not in self._doc_lengths:
            return 0.0

        score = 0.0
        doc_len = self._doc_lengths[doc_id]
        avg_len = self._avg_doc_length or 1.0

        for term in query_terms:
            term_postings = self._inverted_index.get(term, {})
            if doc_id not in term_postings:
                continue

            df = len(term_postings)
            if df == 0:
                continue

            idf = math.log((self._doc_count - df + 0.5) / (df + 0.5) + 1)
            tf = term_postings[doc_id]

            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * doc_len / avg_len)

            score += idf * numerator / denominator

        return score

    def _add_to_ngram_index(self, term: str) -> None:
        for bg in _bigrams(term):
            self._ngram_index[bg].add(term)

    def _remove_from_ngram_index(self, term: str) -> None:
        for bg in _bigrams(term):
            postings = self._ngram_index.get(bg)
            if postings is None:
                continue
            postings.discard(term)
            if not postings:
                del self._ngram_index[bg]

    def _invalidate_cache(self) -> None:
        self._cache.clear()
        self._terms_dirty = True

    def index_document(self, doc: SearchDocument) -> None:
        with self._lock:
            existing = self._documents.get(doc.doc_id)
            if existing is not None:
                self._remove_document_locked(doc.doc_id)

            self._documents[doc.doc_id] = doc

            tokens = tokenize(doc.title + ' ' + doc.content + ' ' + ' '.join(doc.tags))
            doc_length = len(tokens)
            self._doc_lengths[doc.doc_id] = doc_length
            self._total_doc_length += doc_length

            term_freq: Dict[str, float] = defaultdict(float)
            for token in tokens:
                term_freq[token] += 1

            terms: Set[str] = set()
            for term, freq in term_freq.items():
                self._inverted_index[term][doc.doc_id] = 1 + math.log(freq) if freq > 0 else 0
                self._add_to_ngram_index(term)
                terms.add(term)

            self._doc_terms[doc.doc_id] = terms

            self._type_index[doc.doc_type].add(doc.doc_id)

            if doc.status:
                self._status_index[doc.status].add(doc.doc_id)

            if doc.server_id:
                self._server_index[doc.server_id].add(doc.doc_id)

            for tag in doc.tags:
                self._tag_index[tag.lower()].add(doc.doc_id)

            for stag in doc.server_tags:
                self._server_tag_index[stag.lower()].add(doc.doc_id)

            if doc.timestamp is not None:
                bisect.insort(self._time_sorted, (doc.timestamp, doc.doc_id))

            self._doc_count += 1
            self._avg_doc_length = self._total_doc_length / self._doc_count

            self._invalidate_cache()

    def index_documents(self, docs: List[SearchDocument]) -> None:
        with self._lock:
            for doc in docs:
                self.index_document(doc)

    def _remove_document_locked(self, doc_id: str) -> None:
        doc = self._documents.get(doc_id)
        if doc is None:
            return

        terms = self._doc_terms.pop(doc_id, set())
        for term in terms:
            postings = self._inverted_index.get(term)
            if postings is not None:
                postings.pop(doc_id, None)
                if not postings:
                    del self._inverted_index[term]
                    self._remove_from_ngram_index(term)

        length = self._doc_lengths.pop(doc_id, 0.0)
        self._total_doc_length -= length

        self._type_index[doc.doc_type].discard(doc_id)

        if doc.status:
            self._status_index[doc.status].discard(doc_id)

        if doc.server_id:
            self._server_index[doc.server_id].discard(doc_id)

        for tag in doc.tags:
            self._tag_index[tag.lower()].discard(doc_id)

        for stag in doc.server_tags:
            self._server_tag_index[stag.lower()].discard(doc_id)

        if doc.timestamp is not None:
            entry = (doc.timestamp, doc_id)
            idx = bisect.bisect_left(self._time_sorted, entry)
            if idx < len(self._time_sorted) and self._time_sorted[idx] == entry:
                del self._time_sorted[idx]
            else:
                hi = bisect.bisect_right(self._time_sorted, entry)
                for j in range(idx, hi):
                    if self._time_sorted[j][1] == doc_id:
                        del self._time_sorted[j]
                        break

        del self._documents[doc_id]
        self._doc_count -= 1

        if self._doc_count > 0:
            self._avg_doc_length = self._total_doc_length / self._doc_count
        else:
            self._avg_doc_length = 0.0

    def remove_document(self, doc_id: str) -> None:
        with self._lock:
            if doc_id not in self._documents:
                return
            self._remove_document_locked(doc_id)
            self._invalidate_cache()

    def _fuzzy_match_terms(self, query_term: str, threshold: float = 0.6) -> List[Tuple[str, float]]:
        ql = query_term.lower()
        if not ql:
            return []

        candidates: Set[str] = set()
        if len(ql) >= 2:
            for bg in _bigrams(ql):
                candidates.update(self._ngram_index.get(bg, set()))
        else:
            candidates.update(self._inverted_index.keys())

        if not candidates:
            candidates.update(self._inverted_index.keys())

        matches: List[Tuple[str, float]] = []
        for term in candidates:
            sim = fuzzy_similarity(ql, term)
            if sim >= threshold:
                matches.append((term, sim))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:10]

    def _expand_query(self, query_terms: List[str]) -> List[str]:
        expanded: Set[str] = set()
        for term in query_terms:
            expanded.add(term)
            synonyms = get_synonyms(term)
            expanded.update(synonyms)
        return list(expanded)

    def _filter_doc_ids(self, search_filter: Optional[SearchFilter]) -> Optional[Set[str]]:
        if not search_filter:
            return None

        result_sets: List[Set[str]] = []

        if search_filter.doc_types:
            type_set: Set[str] = set()
            for dt in search_filter.doc_types:
                type_set.update(self._type_index.get(dt, set()))
            result_sets.append(type_set)

        if search_filter.statuses:
            status_set: Set[str] = set()
            for s in search_filter.statuses:
                status_set.update(self._status_index.get(s, set()))
            result_sets.append(status_set)

        if search_filter.server_ids:
            server_set: Set[str] = set()
            for sid in search_filter.server_ids:
                server_set.update(self._server_index.get(sid, set()))
            result_sets.append(server_set)

        if search_filter.tags:
            tag_set: Set[str] = set()
            for tag in search_filter.tags:
                tag_set.update(self._tag_index.get(tag.lower(), set()))
            result_sets.append(tag_set)

        if search_filter.server_tags:
            stag_set: Set[str] = set()
            for stag in search_filter.server_tags:
                stag_set.update(self._server_tag_index.get(stag.lower(), set()))
            result_sets.append(stag_set)

        if search_filter.time_range:
            start, end = search_filter.time_range
            time_set: Set[str] = set()
            lo = bisect.bisect_left(self._time_sorted, (start,))
            hi = bisect.bisect_right(self._time_sorted, (end, chr(0x10FFFF)))
            for i in range(lo, hi):
                time_set.add(self._time_sorted[i][1])
            result_sets.append(time_set)

        if not result_sets:
            return None

        final_set = result_sets[0]
        for s in result_sets[1:]:
            final_set = final_set & s

        return final_set

    def _ensure_sorted_terms(self) -> None:
        if self._terms_dirty:
            self._sorted_terms = sorted(self._inverted_index.keys())
            self._terms_dirty = False

    def _generate_highlights(
        self,
        doc: SearchDocument,
        query_terms: List[str],
        max_snippets: int = 3,
        snippet_length: int = 150,
    ) -> List[str]:
        text = doc.content
        highlights: List[str] = []
        terms_lower = [t.lower() for t in query_terms]

        for term in terms_lower:
            pos = text.lower().find(term)
            if pos == -1:
                continue

            start = max(0, pos - snippet_length // 2)
            end = min(len(text), pos + len(term) + snippet_length // 2)

            snippet = text[start:end]
            if start > 0:
                snippet = '...' + snippet
            if end < len(text):
                snippet = snippet + '...'

            snippet = self._highlight_term(snippet, term)
            highlights.append(snippet)

            if len(highlights) >= max_snippets:
                break

        if not highlights and text:
            snippet = text[:snippet_length]
            if len(text) > snippet_length:
                snippet += '...'
            highlights.append(snippet)

        return highlights

    def _highlight_term(self, text: str, term: str) -> str:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        return pattern.sub(lambda m: f'[[HIGHLIGHT]]{m.group()}[[/HIGHLIGHT]]', text)

    def _cache_key(
        self,
        query: str,
        search_filter: Optional[SearchFilter],
        limit: int,
        offset: int,
        fuzzy: bool,
        expand_synonyms: bool,
    ) -> Tuple:
        if search_filter is None:
            f = None
        else:
            f = (
                tuple(sorted(search_filter.doc_types)) if search_filter.doc_types else None,
                search_filter.time_range,
                tuple(sorted(search_filter.statuses)) if search_filter.statuses else None,
                tuple(sorted(search_filter.server_ids)) if search_filter.server_ids else None,
                tuple(sorted(search_filter.server_tags)) if search_filter.server_tags else None,
                tuple(sorted(search_filter.tags)) if search_filter.tags else None,
            )
        return (query, f, limit, offset, fuzzy, expand_synonyms)

    def _ordered_by_timestamp_desc(self, doc_ids: Set[str]) -> List[str]:
        ordered: List[str] = []
        for i in range(len(self._time_sorted) - 1, -1, -1):
            doc_id = self._time_sorted[i][1]
            if doc_id in doc_ids:
                ordered.append(doc_id)
        for doc_id in doc_ids:
            if self._documents[doc_id].timestamp is None:
                ordered.append(doc_id)
        return ordered

    def search(
        self,
        query: str,
        search_filter: Optional[SearchFilter] = None,
        limit: int = 50,
        offset: int = 0,
        fuzzy: bool = True,
        expand_synonyms: bool = True,
    ) -> Tuple[List[SearchResult], int]:
        with self._lock:
            key = self._cache_key(query, search_filter, limit, offset, fuzzy, expand_synonyms)
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached

            if not query.strip():
                filtered_docs = self._filter_doc_ids(search_filter)
                if filtered_docs is None:
                    ordered_ids = [
                        self._time_sorted[i][1]
                        for i in range(len(self._time_sorted) - 1, -1, -1)
                    ]
                    ordered_ids.extend(
                        doc_id for doc_id, doc in self._documents.items()
                        if doc.timestamp is None
                    )
                else:
                    ordered_ids = self._ordered_by_timestamp_desc(filtered_docs)

                results = [
                    SearchResult(doc=self._documents[doc_id], score=0.0)
                    for doc_id in ordered_ids
                ]
                total = len(results)
                sliced = results[offset:offset + limit]
                self._cache_put(key, (sliced, total))
                return sliced, total

            query_terms = tokenize(query)
            if not query_terms:
                self._cache_put(key, ([], 0))
                return [], 0

            all_terms: Set[str] = set(query_terms)

            if expand_synonyms:
                expanded = self._expand_query(query_terms)
                all_terms.update(expanded)

            fuzzy_terms: Set[str] = set()
            fuzzy_scores: Dict[str, float] = {}

            if fuzzy:
                for qt in query_terms:
                    matches = self._fuzzy_match_terms(qt)
                    for term, sim in matches:
                        fuzzy_terms.add(term)
                        fuzzy_scores[term] = max(fuzzy_scores.get(term, 0), sim)
                all_terms.update(fuzzy_terms)

            filtered_ids = self._filter_doc_ids(search_filter)

            candidate_docs: Set[str] = set()
            for term in all_terms:
                postings = self._inverted_index.get(term)
                if not postings:
                    continue
                posting_docs = set(postings.keys())
                if filtered_ids is not None:
                    posting_docs = posting_docs & filtered_ids
                candidate_docs.update(posting_docs)

            if filtered_ids is not None and not candidate_docs:
                self._cache_put(key, ([], 0))
                return [], 0

            if filtered_ids is None:
                filtered_ids = candidate_docs

            scoring_terms = list(all_terms)
            results: List[SearchResult] = []

            for doc_id in candidate_docs:
                if filtered_ids is not None and doc_id not in filtered_ids:
                    continue

                bm25_score = self._compute_bm25_score(scoring_terms, doc_id)

                fuzzy_bonus = 0.0
                for term in fuzzy_terms:
                    if doc_id in self._inverted_index.get(term, {}):
                        fuzzy_bonus += fuzzy_scores.get(term, 0) * 0.5

                title_bonus = 0.0
                doc = self._documents[doc_id]
                title_lower = doc.title.lower()
                for qt in query_terms:
                    if qt in title_lower:
                        title_bonus += 2.0

                tag_bonus = 0.0
                query_terms_lower = [qt.lower() for qt in query_terms]
                for tag in doc.tags:
                    if tag.lower() in query_terms_lower:
                        tag_bonus += 1.5

                exact_match_bonus = 0.0
                query_lower = query.lower()
                if query_lower in doc.title.lower():
                    exact_match_bonus += 5.0
                if query_lower in doc.content.lower():
                    exact_match_bonus += 2.0

                final_score = bm25_score + fuzzy_bonus + title_bonus + tag_bonus + exact_match_bonus

                if final_score > 0:
                    highlights = self._generate_highlights(doc, scoring_terms)
                    matched_terms = [
                        t for t in scoring_terms
                        if t in self._inverted_index and doc_id in self._inverted_index[t]
                    ]

                    results.append(SearchResult(
                        doc=doc,
                        score=final_score,
                        highlights=highlights,
                        matched_terms=matched_terms,
                    ))

            results.sort(key=lambda r: r.score, reverse=True)
            total = len(results)
            sliced = results[offset:offset + limit]
            self._cache_put(key, (sliced, total))
            return sliced, total

    def _cache_put(self, key: Tuple, value: Tuple[List[SearchResult], int]) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._CACHE_SIZE:
            self._cache.popitem(last=False)

    def get_suggestions(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            if not query.strip():
                return self.get_popular_searches(limit)

            query_lower = query.lower()
            suggestions: List[Dict[str, Any]] = []

            self._ensure_sorted_terms()
            start = bisect.bisect_left(self._sorted_terms, query_lower)
            for i in range(start, len(self._sorted_terms)):
                term = self._sorted_terms[i]
                if not term.startswith(query_lower):
                    break
                suggestions.append({
                    'text': term,
                    'type': 'term',
                    'count': len(self._inverted_index[term]),
                })

            if len(suggestions) < limit:
                fuzzy_matches = self._fuzzy_match_terms(query_lower, threshold=0.5)
                existing_texts = {s['text'] for s in suggestions}
                for term, sim in fuzzy_matches:
                    if term in existing_texts:
                        continue
                    suggestions.append({
                        'text': term,
                        'type': 'fuzzy',
                        'similarity': sim,
                        'count': len(self._inverted_index.get(term, {})),
                    })

            suggestions.sort(key=lambda s: s.get('count', 0), reverse=True)

            popular = self.get_popular_searches(5)
            suggestion_texts = {s['text'] for s in suggestions}
            for p in popular:
                if p['text'] not in suggestion_texts:
                    suggestions.append(p)

            return suggestions[:limit]

    def record_search(self, query: str) -> None:
        if not query.strip():
            return

        with self._lock:
            self._search_history.append({
                'query': query,
                'timestamp': time.time(),
            })

            if len(self._search_history) > 100:
                self._search_history = self._search_history[-100:]

            self._popular_searches[query.lower()] += 1

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(reversed(self._search_history[-limit:]))

    def get_popular_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            sorted_searches = sorted(
                self._popular_searches.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            return [
                {'text': query, 'type': 'popular', 'count': count}
                for query, count in sorted_searches[:limit]
            ]

    def clear_index(self) -> None:
        with self._lock:
            self._documents.clear()
            self._inverted_index.clear()
            self._doc_lengths.clear()
            self._doc_terms.clear()
            self._total_doc_length = 0.0
            self._avg_doc_length = 0.0
            self._doc_count = 0
            self._ngram_index.clear()
            self._sorted_terms = []
            self._terms_dirty = True
            self._time_sorted = []
            self._type_index.clear()
            self._status_index.clear()
            self._server_index.clear()
            self._tag_index.clear()
            self._server_tag_index.clear()
            self._cache.clear()

    @property
    def doc_count(self) -> int:
        return self._doc_count


search_engine = SearchEngine()
