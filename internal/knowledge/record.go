package knowledge

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Record is one unit of trained knowledge held by the app.
type Record struct {
	ID     string   `json:"id"`
	Kind   string   `json:"kind"`
	Title  string   `json:"title,omitempty"`
	Input  string   `json:"input,omitempty"`
	Output string   `json:"output,omitempty"`
	Text   string   `json:"text,omitempty"`
	Tags   []string `json:"tags,omitempty"`
	Source string   `json:"source,omitempty"`
}

type rawMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// rawRecord accepts the canonical schema plus the common aliases so packs made
// for other trainers (alpaca, sharegpt, prompt/completion) still load.
type rawRecord struct {
	ID          string          `json:"id"`
	Kind        string          `json:"kind"`
	Question    string          `json:"question"`
	Prompt      string          `json:"prompt"`
	Instruction string          `json:"instruction"`
	Input       string          `json:"input"`
	Answer      string          `json:"answer"`
	Completion  string          `json:"completion"`
	Response    string          `json:"response"`
	Output      string          `json:"output"`
	Title       string          `json:"title"`
	Topic       string          `json:"topic"`
	Text        string          `json:"text"`
	Content     string          `json:"content"`
	Body        string          `json:"body"`
	Description string          `json:"description"`
	Tags        json.RawMessage `json:"tags"`
	Source      string          `json:"source"`
	Messages    []rawMessage    `json:"messages"`
}

// Source summarises one file that contributed records.
type Source struct {
	Path    string `json:"path"`
	Records int    `json:"records"`
	Skipped int    `json:"skipped"`
}

// ParseResult is everything a training run read off disk.
type ParseResult struct {
	Records  []Record
	Sources  []Source
	Skipped  int
	Warnings []string
}

var supportedExt = map[string]bool{
	".jsonl":    true,
	".ndjson":   true,
	".json":     true,
	".txt":      true,
	".md":       true,
	".markdown": true,
}

// SearchText is the blob a record is indexed and matched on.
func (r Record) SearchText() string {
	parts := []string{r.Title, r.Input, r.Output, r.Text, strings.Join(r.Tags, " ")}
	var b strings.Builder
	for _, p := range parts {
		if strings.TrimSpace(p) != "" {
			b.WriteString(p)
			b.WriteString("\n")
		}
	}
	return strings.TrimSpace(b.String())
}

// Body is the answer-carrying part of a record.
func (r Record) Body() string {
	switch {
	case strings.TrimSpace(r.Output) != "":
		return strings.TrimSpace(r.Output)
	case strings.TrimSpace(r.Text) != "":
		return strings.TrimSpace(r.Text)
	}
	return strings.TrimSpace(r.Input)
}

// Label is the short human name used in listings and citations.
func (r Record) Label() string {
	switch {
	case strings.TrimSpace(r.Title) != "":
		return firstLine(r.Title, 88)
	case strings.TrimSpace(r.Input) != "":
		return firstLine(r.Input, 88)
	case strings.TrimSpace(r.Text) != "":
		return firstLine(r.Text, 88)
	case strings.TrimSpace(r.Output) != "":
		return firstLine(r.Output, 88)
	}
	return r.ID
}

// key fingerprints record content, so retraining the same file never duplicates.
func (r Record) key() string {
	norm := strings.ToLower(strings.Join([]string{
		strings.TrimSpace(r.Input),
		strings.TrimSpace(r.Output),
		strings.TrimSpace(r.Text),
		strings.TrimSpace(r.Title),
	}, "\x00"))
	sum := sha256.Sum256([]byte(norm))
	return hex.EncodeToString(sum[:12])
}

// ParsePaths loads every training file under the given files and folders.
func ParsePaths(paths []string) (ParseResult, error) {
	var res ParseResult
	seen := make(map[string]bool)
	for _, p := range paths {
		info, err := os.Stat(p)
		if err != nil {
			return ParseResult{}, fmt.Errorf("%s: %w", p, err)
		}
		files := []string{p}
		if info.IsDir() {
			files = nil
			err := filepath.WalkDir(p, func(path string, d os.DirEntry, err error) error {
				if err != nil {
					return err
				}
				if d.IsDir() {
					switch d.Name() {
					case ".git", "node_modules", "dist", "vendor":
						return filepath.SkipDir
					}
					return nil
				}
				if supportedExt[strings.ToLower(filepath.Ext(path))] {
					files = append(files, path)
				}
				return nil
			})
			if err != nil {
				return ParseResult{}, err
			}
			sort.Strings(files)
			if len(files) == 0 {
				res.Warnings = append(res.Warnings, p+": no .jsonl/.json/.txt/.md files")
				continue
			}
		}
		for _, f := range files {
			recs, skipped, warns, err := parseFile(f)
			if err != nil {
				return ParseResult{}, err
			}
			src := Source{Path: f, Skipped: skipped}
			for _, r := range recs {
				if strings.TrimSpace(r.Source) == "" {
					r.Source = f
				}
				if strings.TrimSpace(r.ID) == "" {
					r.ID = fmt.Sprintf("%s-%03d", slug(filepath.Base(f)), src.Records+1)
				}
				k := r.key()
				if seen[k] {
					src.Skipped++
					res.Skipped++
					continue
				}
				seen[k] = true
				src.Records++
				res.Records = append(res.Records, r)
			}
			res.Skipped += skipped
			res.Sources = append(res.Sources, src)
			for _, w := range warns {
				if len(res.Warnings) < 5 {
					res.Warnings = append(res.Warnings, f+": "+w)
				}
			}
		}
	}
	if len(res.Records) == 0 {
		return res, errors.New("no usable training records found")
	}
	return res, nil
}

func parseFile(path string) ([]Record, int, []string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, 0, nil, err
	}
	switch strings.ToLower(filepath.Ext(path)) {
	case ".jsonl", ".ndjson":
		return parseJSONL(data)
	case ".json":
		return parseJSON(data)
	default:
		return parseText(data, path), 0, nil, nil
	}
}

func parseJSONL(data []byte) ([]Record, int, []string, error) {
	var recs []Record
	skipped := 0
	var warns []string
	sc := bufio.NewScanner(bytes.NewReader(data))
	sc.Buffer(make([]byte, 0, 64*1024), 8*1024*1024)
	line := 0
	for sc.Scan() {
		line++
		raw := strings.TrimSpace(sc.Text())
		if raw == "" || strings.HasPrefix(raw, "//") || strings.HasPrefix(raw, "#") {
			continue
		}
		rec, err := parseRecord([]byte(raw))
		if err != nil {
			skipped++
			if len(warns) < 3 {
				warns = append(warns, fmt.Sprintf("line %d: %v", line, err))
			}
			continue
		}
		recs = append(recs, rec)
	}
	if err := sc.Err(); err != nil {
		return nil, 0, nil, err
	}
	return recs, skipped, warns, nil
}

func parseJSON(data []byte) ([]Record, int, []string, error) {
	var arr []json.RawMessage
	if err := json.Unmarshal(data, &arr); err == nil {
		return recordsFromRaw(arr)
	}
	var obj map[string]json.RawMessage
	if err := json.Unmarshal(data, &obj); err == nil {
		for _, key := range []string{"records", "data", "examples", "items", "training_data", "train"} {
			v, ok := obj[key]
			if !ok {
				continue
			}
			var inner []json.RawMessage
			if json.Unmarshal(v, &inner) == nil {
				return recordsFromRaw(inner)
			}
		}
		rec, err := parseRecord(data)
		if err != nil {
			return nil, 1, []string{err.Error()}, nil
		}
		return []Record{rec}, 0, nil, nil
	}
	return parseJSONL(data)
}

func recordsFromRaw(items []json.RawMessage) ([]Record, int, []string, error) {
	var recs []Record
	skipped := 0
	var warns []string
	for i, item := range items {
		rec, err := parseRecord(item)
		if err != nil {
			skipped++
			if len(warns) < 3 {
				warns = append(warns, fmt.Sprintf("entry %d: %v", i+1, err))
			}
			continue
		}
		recs = append(recs, rec)
	}
	return recs, skipped, warns, nil
}

func parseText(data []byte, path string) []Record {
	base := filepath.Base(path)
	chunks := chunkText(string(data))
	recs := make([]Record, 0, len(chunks))
	for i, chunk := range chunks {
		title := base
		if len(chunks) > 1 {
			title = fmt.Sprintf("%s (%d/%d)", base, i+1, len(chunks))
		}
		recs = append(recs, Record{
			ID:    fmt.Sprintf("%s-%02d", slug(base), i+1),
			Kind:  "doc",
			Title: title,
			Text:  chunk,
		})
	}
	return recs
}

func chunkText(text string) []string {
	text = strings.ReplaceAll(text, "\r\n", "\n")
	const maxLen = 1200
	var chunks []string
	var cur strings.Builder
	flush := func() {
		s := strings.TrimSpace(cur.String())
		if s != "" {
			chunks = append(chunks, s)
		}
		cur.Reset()
	}
	for _, para := range strings.Split(text, "\n\n") {
		para = strings.TrimSpace(para)
		if para == "" {
			continue
		}
		if cur.Len() > 0 && cur.Len()+len(para) > maxLen {
			flush()
		}
		runes := []rune(para)
		for len(runes) > maxLen*3 {
			chunks = append(chunks, strings.TrimSpace(string(runes[:maxLen*3])))
			runes = runes[maxLen*3:]
		}
		para = strings.TrimSpace(string(runes))
		if para == "" {
			continue
		}
		if cur.Len() > 0 {
			cur.WriteString("\n\n")
		}
		cur.WriteString(para)
	}
	flush()
	return chunks
}

func parseRecord(data []byte) (Record, error) {
	var raw rawRecord
	if err := json.Unmarshal(data, &raw); err != nil {
		return Record{}, fmt.Errorf("invalid JSON: %v", err)
	}
	input := firstNonEmpty(raw.Input, raw.Question, raw.Prompt, raw.Instruction)
	output := firstNonEmpty(raw.Output, raw.Answer, raw.Completion, raw.Response)
	text := firstNonEmpty(raw.Text, raw.Content, raw.Body)
	title := firstNonEmpty(raw.Title, raw.Topic)
	if output == "" && text == "" {
		text = raw.Description
	}
	for _, m := range raw.Messages {
		content := strings.TrimSpace(m.Content)
		if content == "" {
			continue
		}
		switch strings.ToLower(strings.TrimSpace(m.Role)) {
		case "user", "human":
			if input == "" {
				input = content
			} else {
				input += "\n\n" + content
			}
		case "assistant", "model", "gpt":
			output = content
		case "system":
			if title == "" {
				title = firstLine(content, 80)
			}
		}
	}
	rec := Record{
		ID:     strings.TrimSpace(raw.ID),
		Kind:   strings.TrimSpace(raw.Kind),
		Title:  strings.TrimSpace(title),
		Input:  strings.TrimSpace(input),
		Output: strings.TrimSpace(output),
		Text:   strings.TrimSpace(text),
		Tags:   parseTags(raw.Tags),
		Source: strings.TrimSpace(raw.Source),
	}
	if rec.Kind == "" {
		if rec.Text != "" && rec.Output == "" {
			rec.Kind = "doc"
		} else {
			rec.Kind = "qa"
		}
	}
	if rec.Text == "" && rec.Output == "" {
		return Record{}, errors.New(`needs "input"+"output" or "text"`)
	}
	return rec, nil
}

func parseTags(raw json.RawMessage) []string {
	if len(raw) == 0 {
		return nil
	}
	var list []string
	if err := json.Unmarshal(raw, &list); err == nil {
		return cleanTags(list)
	}
	var single string
	if err := json.Unmarshal(raw, &single); err == nil {
		return cleanTags(strings.Split(single, ","))
	}
	return nil
}

func cleanTags(in []string) []string {
	out := make([]string, 0, len(in))
	seen := make(map[string]bool, len(in))
	for _, t := range in {
		t = strings.TrimSpace(t)
		if t == "" || seen[strings.ToLower(t)] {
			continue
		}
		seen[strings.ToLower(t)] = true
		out = append(out, t)
	}
	if len(out) == 0 {
		return nil
	}
	return out
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

func firstLine(s string, limit int) string {
	s = strings.TrimSpace(s)
	if idx := strings.IndexByte(s, '\n'); idx >= 0 {
		s = strings.TrimSpace(s[:idx])
	}
	runes := []rune(s)
	if len(runes) > limit {
		return strings.TrimSpace(string(runes[:limit])) + "…"
	}
	return s
}

func slug(s string) string {
	var b strings.Builder
	lastDash := true
	for _, r := range strings.ToLower(s) {
		switch {
		case (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9'):
			b.WriteRune(r)
			lastDash = false
		default:
			if !lastDash {
				b.WriteByte('-')
				lastDash = true
			}
		}
	}
	out := strings.Trim(b.String(), "-")
	if out == "" {
		return "record"
	}
	if len(out) > 40 {
		out = out[:40]
	}
	return out
}
