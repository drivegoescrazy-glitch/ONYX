package knowledge

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Manifest describes where the stored knowledge came from.
type Manifest struct {
	Version   string    `json:"version"`
	Updated   time.Time `json:"updated"`
	Records   int       `json:"records"`
	Terms     int       `json:"terms"`
	Tokens    int       `json:"tokens"`
	Trainings int       `json:"trainings"`
	Sources   []Source  `json:"sources"`
}

// Config holds the optional local-model connection.
type Config struct {
	ModelURL string `json:"model_url,omitempty"`
	Model    string `json:"model,omitempty"`
}

// Store is the app's own knowledge file plus its configuration.
type Store struct {
	Dir      string
	Manifest Manifest
	Records  []Record
	Config   Config
}

type knowledgeFile struct {
	Manifest Manifest `json:"manifest"`
	Records  []Record `json:"records"`
}

// HomeDir resolves the app data directory: $ONYX_HOME or ~/.onyx.
func HomeDir() (string, error) {
	if h := os.Getenv("ONYX_HOME"); h != "" {
		return h, nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ".onyx"), nil
}

// KnowledgePath is the trained knowledge file.
func (s *Store) KnowledgePath() string { return filepath.Join(s.Dir, "knowledge.json") }

// ConfigPath is the settings file.
func (s *Store) ConfigPath() string { return filepath.Join(s.Dir, "config.json") }

// Load reads the saved knowledge and config, tolerating a first run.
func Load() (*Store, error) {
	dir, err := HomeDir()
	if err != nil {
		return nil, err
	}
	s := &Store{Dir: dir}
	if data, err := os.ReadFile(s.KnowledgePath()); err == nil {
		var f knowledgeFile
		if err := json.Unmarshal(data, &f); err != nil {
			return nil, fmt.Errorf("knowledge file %s is corrupt: %w", s.KnowledgePath(), err)
		}
		s.Manifest = f.Manifest
		s.Records = f.Records
	} else if !os.IsNotExist(err) {
		return nil, err
	}
	if data, err := os.ReadFile(s.ConfigPath()); err == nil {
		_ = json.Unmarshal(data, &s.Config)
	}
	return s, nil
}

// Save writes the trained knowledge so it survives restarts.
func (s *Store) Save() error {
	if err := os.MkdirAll(s.Dir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(knowledgeFile{Manifest: s.Manifest, Records: s.Records}, "", " ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return writeAtomic(s.KnowledgePath(), data)
}

// SaveConfig writes the model settings.
func (s *Store) SaveConfig() error {
	if err := os.MkdirAll(s.Dir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(s.Config, "", " ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return writeAtomic(s.ConfigPath(), data)
}

// Clear deletes all trained knowledge while keeping settings.
func (s *Store) Clear() error {
	if err := os.Remove(s.KnowledgePath()); err != nil && !os.IsNotExist(err) {
		return err
	}
	s.Records = nil
	s.Manifest = Manifest{Version: s.Manifest.Version}
	return nil
}

// Size reports the on-disk size of the knowledge file.
func (s *Store) Size() int64 {
	if fi, err := os.Stat(s.KnowledgePath()); err == nil {
		return fi.Size()
	}
	return 0
}

// MergeSources keeps one entry per path, newest stats win.
func MergeSources(old, add []Source) []Source {
	index := make(map[string]int, len(old)+len(add))
	out := make([]Source, 0, len(old)+len(add))
	for _, src := range old {
		index[src.Path] = len(out)
		out = append(out, src)
	}
	for _, src := range add {
		if i, ok := index[src.Path]; ok {
			out[i] = src
			continue
		}
		index[src.Path] = len(out)
		out = append(out, src)
	}
	return out
}

func writeAtomic(path string, data []byte) error {
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	return nil
}
