package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/drivegoescrazy-glitch/onyx/internal/knowledge"
)

const offlineLabel = "knowledge-only (offline)"

// Answer is one reply, with the records it was grounded in.
type Answer struct {
	Text      string
	Hits      []knowledge.Hit
	Generated bool
	Model     string
	Note      string
}

// Agent answers questions from the app's trained knowledge.
type Agent struct {
	store    *knowledge.Store
	searcher *knowledge.Searcher
	client   *http.Client

	ModelURL string
	Model    string
}

// New builds an agent over the saved knowledge, honouring env overrides.
func New(store *knowledge.Store) *Agent {
	a := &Agent{
		store:    store,
		searcher: knowledge.NewSearcher(store.Records),
		client:   &http.Client{Timeout: 180 * time.Second},
		ModelURL: store.Config.ModelURL,
		Model:    store.Config.Model,
	}
	if v := strings.TrimSpace(os.Getenv("ONYX_MODEL_URL")); v != "" {
		a.ModelURL = v
	}
	if v := strings.TrimSpace(os.Getenv("ONYX_MODEL")); v != "" {
		a.Model = v
	}
	return a
}

// Reload re-indexes after a training run.
func (a *Agent) Reload() { a.searcher = knowledge.NewSearcher(a.store.Records) }

// Records reports how many records are loaded.
func (a *Agent) Records() int { return len(a.store.Records) }

// Enabled reports whether a generation model is configured.
func (a *Agent) Enabled() bool { return a.ModelURL != "" && a.Model != "" }

// ModelLabel is the status line shown under the banner.
func (a *Agent) ModelLabel() string {
	if a.Enabled() {
		return a.Model + " (local)"
	}
	return offlineLabel
}

// Answer resolves a question against the trained knowledge.
func (a *Agent) Answer(ctx context.Context, query string) (Answer, error) {
	query = strings.TrimSpace(query)
	if query == "" {
		return Answer{}, errors.New("nothing to ask")
	}
	hits := a.searcher.Search(query, 6)
	ans := Answer{Hits: hits}
	if a.Enabled() {
		text, err := a.complete(ctx, query, hits)
		if err == nil {
			ans.Text = text
			ans.Generated = true
			ans.Model = a.Model
			return ans, nil
		}
		ans.Note = "local model unavailable (" + shortErr(err) + ") — answered from trained knowledge"
	}
	ans.Text = retrievalAnswer(hits)
	if !a.Enabled() {
		if len(hits) > 0 {
			ans.Note = "no local model configured — showing your best matching trained records (/model to connect one)"
		} else if ans.Note == "" {
			ans.Note = "no local model configured and nothing trained on that yet"
		}
	}
	return ans, nil
}

func retrievalAnswer(hits []knowledge.Hit) string {
	if len(hits) == 0 {
		return strings.Join([]string{
			"Nothing trained on that yet.",
			"",
			"Teach the app with:",
			"  onyx train training.jsonl",
			"or, inside the app:",
			"  /train training.jsonl",
			"",
			"basetrainer.txt explains the training-data format (and gives any AI the",
			"prompt that turns a subject into a pack).",
		}, "\n")
	}
	var b strings.Builder
	b.WriteString(truncateBody(hits[0].Record.Body()))
	if len(hits) > 1 {
		b.WriteString("\n\nAlso in your trained knowledge:")
		for i, h := range hits[1:] {
			if i >= 4 {
				break
			}
			b.WriteString(fmt.Sprintf("\n  %d. %s", i+2, h.Record.Label()))
		}
	}
	return b.String()
}

func truncateBody(body string) string {
	body = strings.TrimSpace(body)
	const limit = 2000
	runes := []rune(body)
	if len(runes) > limit {
		return strings.TrimSpace(string(runes[:limit])) + "…"
	}
	return body
}

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatRequest struct {
	Model       string        `json:"model"`
	Messages    []chatMessage `json:"messages"`
	Temperature float64       `json:"temperature"`
	Stream      bool          `json:"stream"`
	MaxTokens   int           `json:"max_tokens,omitempty"`
}

type chatResponse struct {
	Choices []struct {
		Message chatMessage `json:"message"`
	} `json:"choices"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error"`
}

func (a *Agent) complete(ctx context.Context, query string, hits []knowledge.Hit) (string, error) {
	reqBody, err := json.Marshal(chatRequest{
		Model: a.Model,
		Messages: []chatMessage{
			{Role: "system", Content: systemPrompt(a.store.Records, hits)},
			{Role: "user", Content: query},
		},
		Temperature: 0.2,
		Stream:      false,
		MaxTokens:   1200,
	})
	if err != nil {
		return "", err
	}
	url := strings.TrimRight(strings.TrimSpace(a.ModelURL), "/")
	if !strings.HasSuffix(url, "/chat/completions") {
		url += "/chat/completions"
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(reqBody))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	if key := strings.TrimSpace(os.Getenv("ONYX_API_KEY")); key != "" {
		req.Header.Set("Authorization", "Bearer "+key)
	}
	resp, err := a.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return "", err
	}
	if resp.StatusCode >= 300 {
		return "", fmt.Errorf("%s: %s", resp.Status, firstLine(string(data), 160))
	}
	var out chatResponse
	if err := json.Unmarshal(data, &out); err != nil {
		return "", fmt.Errorf("invalid model response: %v", err)
	}
	if out.Error != nil && strings.TrimSpace(out.Error.Message) != "" {
		return "", errors.New(out.Error.Message)
	}
	if len(out.Choices) == 0 {
		return "", errors.New("model returned no choices")
	}
	text := strings.TrimSpace(out.Choices[0].Message.Content)
	if text == "" {
		return "", errors.New("model returned an empty message")
	}
	return text, nil
}

func systemPrompt(records []knowledge.Record, hits []knowledge.Hit) string {
	var b strings.Builder
	b.WriteString("You are ONYX, a coding agent running locally on the user's machine.\n")
	b.WriteString("Treat the trained knowledge records below as ground truth when they are relevant, and cite them like [1], [2].\n")
	b.WriteString("If the records do not cover the question, say so in one sentence and then answer from general knowledge.\n")
	b.WriteString("Be concise and concrete. Use short code blocks when they help. Never pretend you ran a command or browsed the web.\n")
	b.WriteString(fmt.Sprintf("\nThe app holds %d trained records.\n", len(records)))
	if len(hits) == 0 {
		b.WriteString("\nNo trained records matched this question.\n")
		return b.String()
	}
	b.WriteString("\n<knowledge>\n")
	for i, h := range hits {
		tags := ""
		if len(h.Record.Tags) > 0 {
			tags = ", tags: " + strings.Join(h.Record.Tags, ", ")
		}
		title := h.Record.Label()
		b.WriteString(fmt.Sprintf("[%d] %s (id: %s%s)\n", i+1, title, h.Record.ID, tags))
		if in := strings.TrimSpace(h.Record.Input); in != "" {
			b.WriteString("Q: " + in + "\n")
		}
		body := truncateBody(h.Record.Body())
		if limit := 1400; len(body) > limit {
			body = strings.TrimSpace(body[:limit]) + "…"
		}
		b.WriteString("A: " + body + "\n\n")
	}
	b.WriteString("</knowledge>\n")
	return b.String()
}

// EstimateTokens is the rough token count used for the status line.
func EstimateTokens(s string) int {
	return (len(s) + 3) / 4
}

func shortErr(err error) string {
	msg := strings.ReplaceAll(err.Error(), "\n", " ")
	return firstLine(msg, 120)
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
