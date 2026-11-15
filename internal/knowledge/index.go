package knowledge

import (
	"math"
	"regexp"
	"sort"
	"strings"
)

// Hit is one search result with its relevance score.
type Hit struct {
	Record Record
	Score  float64
}

// Searcher is an in-memory BM25 index. The index is rebuilt from the stored
// records on load, so the knowledge file only ever holds plain records.
type Searcher struct {
	records  []Record
	termFreq []map[string]int
	lengths  []int
	tagTerms []map[string]bool
	askTerms []map[string]bool
	df       map[string]int
	avgdl    float64
}

var wordRe = regexp.MustCompile(`[A-Za-z0-9_]+`)

var stopwords = map[string]bool{
	"the": true, "a": true, "an": true, "and": true, "or": true, "of": true,
	"to": true, "in": true, "is": true, "are": true, "was": true, "were": true,
	"be": true, "been": true, "being": true, "with": true, "as": true, "at": true,
	"by": true, "it": true, "this": true, "that": true, "from": true, "on": true,
	"i": true, "you": true, "my": true, "we": true, "us": true, "they": true,
	"them": true, "their": true, "its": true, "into": true, "me": true,
	"your": true, "our": true, "he": true, "she": true, "him": true, "her": true,
	"his": true, "how": true, "what": true, "when": true, "where": true,
	"which": true, "who": true, "whom": true, "why": true, "do": true,
	"does": true, "did": true, "done": true, "can": true, "could": true,
	"should": true, "would": true, "will": true, "shall": true, "may": true,
	"might": true, "must": true, "about": true, "if": true, "then": true,
	"than": true, "so": true, "but": true, "not": true, "no": true,
	"any": true, "all": true, "some": true, "more": true, "most": true,
	"there": true, "here": true, "these": true, "those": true, "very": true,
	"just": true, "also": true, "please": true, "tell": true, "need": true,
	"want": true, "much": true, "many": true, "same": true, "only": true,
	"use": true, "used": true, "using": true, "make": true, "made": true,
	"get": true, "got": true, "give": true, "let": true, "work": true,
	"works": true, "thing": true, "things": true, "way": true, "best": true,
}

// Tokenize lowercases and splits text into searchable terms.
func Tokenize(s string) []string {
	words := wordRe.FindAllString(strings.ToLower(s), -1)
	out := make([]string, 0, len(words))
	for _, w := range words {
		if len(w) == 1 && !(w >= "0" && w <= "9") {
			continue
		}
		if stopwords[w] {
			continue
		}
		out = append(out, stem(w))
	}
	return out
}

// stem folds the endings that usually separate a query word from the same word
// in a record, so "stored" meets "store" and "releases" meets "release".
func stem(w string) string {
	switch {
	case len(w) > 5 && strings.HasSuffix(w, "ing"):
		w = w[:len(w)-3]
	case len(w) > 4 && strings.HasSuffix(w, "ed") && !strings.HasSuffix(w, "eed"):
		w = w[:len(w)-2]
	case len(w) > 4 && strings.HasSuffix(w, "es"):
		w = w[:len(w)-2]
	case len(w) > 4 && strings.HasSuffix(w, "s") &&
		!strings.HasSuffix(w, "ss") && !strings.HasSuffix(w, "us") && !strings.HasSuffix(w, "is"):
		w = w[:len(w)-1]
	}
	if len(w) > 4 && strings.HasSuffix(w, "e") {
		w = w[:len(w)-1]
	}
	return w
}

// indexText is the searchable text of a record. The question, title and tags
// are repeated because they say what the record is about.
func indexText(r Record) string {
	return strings.Join([]string{
		r.SearchText(),
		r.Input,
		r.Title,
		strings.Join(r.Tags, " "),
	}, "\n")
}

// NewSearcher indexes the given records.
func NewSearcher(records []Record) *Searcher {
	s := &Searcher{
		records:  records,
		termFreq: make([]map[string]int, len(records)),
		lengths:  make([]int, len(records)),
		tagTerms: make([]map[string]bool, len(records)),
		askTerms: make([]map[string]bool, len(records)),
		df:       make(map[string]int),
	}
	total := 0
	for i, rec := range records {
		terms := Tokenize(indexText(rec))
		tf := make(map[string]int, len(terms))
		for _, t := range terms {
			tf[t]++
		}
		s.termFreq[i] = tf
		s.lengths[i] = len(terms)
		s.tagTerms[i] = termSet(Tokenize(strings.Join(rec.Tags, " ")))
		s.askTerms[i] = termSet(Tokenize(rec.Title + " " + rec.Input))
		total += len(terms)
		for t := range tf {
			s.df[t]++
		}
	}
	if len(records) > 0 {
		s.avgdl = float64(total) / float64(len(records))
	}
	return s
}

// Terms reports how many distinct terms the index holds.
func (s *Searcher) Terms() int {
	if s == nil {
		return 0
	}
	return len(s.df)
}

// Search returns the best matching records, highest score first.
func (s *Searcher) Search(query string, k int) []Hit {
	if s == nil || len(s.records) == 0 || k <= 0 {
		return nil
	}
	terms := Tokenize(query)
	if len(terms) == 0 {
		return nil
	}
	const k1, b = 1.4, 0.75
	scores := make([]float64, len(s.records))
	for _, term := range s.expand(terms) {
		df := s.df[term.text]
		if df == 0 {
			continue
		}
		idf := math.Log(1 + (float64(len(s.records))-float64(df)+0.5)/(float64(df)+0.5))
		idf *= term.weight
		for i, tf := range s.termFreq {
			f := tf[term.text]
			if f == 0 {
				continue
			}
			dl := float64(s.lengths[i])
			if dl == 0 {
				continue
			}
			scores[i] += idf * (float64(f) * (k1 + 1)) / (float64(f) + k1*(1-b+b*dl/s.avgdl))
		}
	}
	// Tags and the record's own question are the strongest statement of what a
	// record is about, so reward them on top of document similarity.
	for term := range termSet(terms) {
		for i := range s.records {
			if s.tagTerms[i][term] {
				scores[i] += 1.5
			}
			if s.askTerms[i][term] {
				scores[i] += 0.7
			}
		}
	}
	if phrase := strings.ToLower(strings.TrimSpace(query)); len([]rune(phrase)) > 3 {
		for i := range s.records {
			if strings.Contains(strings.ToLower(s.records[i].SearchText()), phrase) {
				scores[i] += 2.5
			}
		}
	}
	hits := make([]Hit, 0, len(s.records))
	for i, score := range scores {
		if score <= 0 {
			continue
		}
		hits = append(hits, Hit{Record: s.records[i], Score: score})
	}
	sort.SliceStable(hits, func(a, c int) bool { return hits[a].Score > hits[c].Score })
	if len(hits) > k {
		hits = hits[:k]
	}
	return hits
}

func termSet(terms []string) map[string]bool {
	out := make(map[string]bool, len(terms))
	for _, t := range terms {
		out[t] = true
	}
	return out
}

type weightedTerm struct {
	text   string
	weight float64
}

// expand adds prefix matches so a query term like "roll" still finds
// "rollback" and "deploy" finds "deployment". Direct hits weigh more.
func (s *Searcher) expand(terms []string) []weightedTerm {
	out := make([]weightedTerm, 0, len(terms))
	seen := make(map[string]bool, len(terms))
	for _, t := range terms {
		if seen[t] {
			continue
		}
		seen[t] = true
		if s.df[t] > 0 {
			out = append(out, weightedTerm{text: t, weight: 1})
		}
		if len(t) < 4 {
			continue
		}
		matched := 0
		for candidate := range s.df {
			if seen[candidate] || len(candidate) <= len(t) || !strings.HasPrefix(candidate, t) {
				continue
			}
			seen[candidate] = true
			out = append(out, weightedTerm{text: candidate, weight: 0.4})
			matched++
			if matched >= 40 {
				break
			}
		}
	}
	return out
}

// Merge folds new records into an existing set, skipping content duplicates.
func Merge(base, add []Record) (merged []Record, added int, dupes int) {
	seen := make(map[string]bool, len(base)+len(add))
	merged = make([]Record, 0, len(base)+len(add))
	for _, r := range base {
		k := r.key()
		if seen[k] {
			continue
		}
		seen[k] = true
		merged = append(merged, r)
	}
	for _, r := range add {
		k := r.key()
		if seen[k] {
			dupes++
			continue
		}
		seen[k] = true
		merged = append(merged, r)
		added++
	}
	return merged, added, dupes
}

// CountTokens approximates the token weight of a record set.
func CountTokens(records []Record) int {
	total := 0
	for _, r := range records {
		total += len(Tokenize(r.SearchText()))
	}
	return total
}
