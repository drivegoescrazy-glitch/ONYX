package main

import (
	"bufio"
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/drivegoescrazy-glitch/onyx/internal/agent"
	"github.com/drivegoescrazy-glitch/onyx/internal/knowledge"
	"github.com/drivegoescrazy-glitch/onyx/internal/tui"
)

// Version is stamped by release builds: -ldflags "-X main.Version=x.y.z".
var Version = "1.0.0"

var ui = tui.New()

func main() {
	store, err := knowledge.Load()
	if err != nil {
		fmt.Fprintln(os.Stderr, ui.Red("onyx: "+err.Error()))
		os.Exit(1)
	}
	args := os.Args[1:]
	if len(args) == 0 {
		runREPL(store)
		return
	}
	var runErr error
	switch strings.ToLower(args[0]) {
	case "train", "learn":
		runErr = runTrain(store, args[1:])
	case "ask", "chat":
		runErr = runAsk(store, args[1:])
	case "knowledge", "kb":
		printKnowledge(store)
	case "forget":
		runErr = runForget(store, args[1:])
	case "version", "-v", "--version":
		fmt.Printf("ONYX %s\n", Version)
	case "help", "-h", "--help":
		printUsage()
	default:
		runErr = runAsk(store, args)
	}
	if runErr != nil {
		if errors.Is(runErr, flag.ErrHelp) {
			return
		}
		fmt.Fprintln(os.Stderr, ui.Red("onyx: "+runErr.Error()))
		os.Exit(1)
	}
}

func runTrain(store *knowledge.Store, args []string) error {
	fs := flag.NewFlagSet("train", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	replace := fs.Bool("replace", false, "replace the existing knowledge instead of adding to it")
	quiet := fs.Bool("quiet", false, "print only the final summary")
	flags, paths := splitFlags(args)
	if err := fs.Parse(flags); err != nil {
		return err
	}
	if len(paths) == 0 {
		paths = defaultTrainingPaths()
		if len(paths) == 0 {
			return errors.New("no training data given — try: onyx train training.jsonl (format: basetrainer.txt)")
		}
	}
	if !*quiet {
		ui.Section("training")
		for _, p := range paths {
			ui.Detail("scanning " + shortPath(p))
		}
	}

	res, err := knowledge.ParsePaths(paths)
	if err != nil {
		return err
	}
	base := store.Records
	if *replace {
		base = nil
	}
	merged, added, dupes := knowledge.Merge(base, res.Records)
	if added == 0 && !*replace {
		ui.Warn(fmt.Sprintf("nothing new — all %s already trained", plural(len(res.Records), "record")))
	}
	searcher := knowledge.NewSearcher(merged)
	store.Records = merged
	store.Manifest = knowledge.Manifest{
		Version:   Version,
		Updated:   time.Now(),
		Records:   len(merged),
		Terms:     searcher.Terms(),
		Tokens:    knowledge.CountTokens(merged),
		Trainings: store.Manifest.Trainings + 1,
		Sources:   knowledge.MergeSources(store.Manifest.Sources, res.Sources),
	}
	if err := store.Save(); err != nil {
		return fmt.Errorf("could not save knowledge: %w", err)
	}

	if !*quiet {
		if !*replace && dupes > 0 {
			ui.Detail(fmt.Sprintf("skipped %s already trained", plural(dupes, "record")))
		}
		if res.Skipped > 0 {
			ui.Detail(fmt.Sprintf("skipped %s that did not match the format", plural(res.Skipped, "line")))
		}
		ui.Detail(fmt.Sprintf("parsed %s from %s", plural(len(res.Records), "record"), plural(len(res.Sources), "file")))
		ui.Detail(fmt.Sprintf("indexed %s · %s", plural(store.Manifest.Terms, "term"), formatNum(store.Manifest.Tokens)+" tokens"))
		ui.Detail("saved " + shortPath(store.KnowledgePath()) + " (" + humanBytes(store.Size()) + ")")
		for _, w := range res.Warnings {
			ui.Warn(w)
		}
	}
	if added == 0 {
		ui.Success(fmt.Sprintf("knowledge unchanged — %s available in the app", plural(len(merged), "record")))
		return nil
	}
	ui.Success(fmt.Sprintf("%s trained — knowledge saved to the app (%s total)",
		plural(added, "record"), formatNum(len(merged))))
	return nil
}

// splitFlags keeps flags working before or after paths, because flag.Parse
// stops at the first positional argument.
func splitFlags(args []string) (flags, positional []string) {
	verbatim := false
	for _, a := range args {
		switch {
		case verbatim, a == "-", !strings.HasPrefix(a, "-"):
			positional = append(positional, a)
		case a == "--":
			verbatim = true
		default:
			flags = append(flags, a)
		}
	}
	return flags, positional
}

func defaultTrainingPaths() []string {
	for _, dir := range []string{"training", "training_data", "train"} {
		if fi, err := os.Stat(dir); err == nil && fi.IsDir() {
			return []string{dir}
		}
	}
	for _, file := range []string{"training.jsonl", "training_data.jsonl", "basetrain.jsonl"} {
		if fi, err := os.Stat(file); err == nil && !fi.IsDir() {
			return []string{file}
		}
	}
	return nil
}

func runAsk(store *knowledge.Store, args []string) error {
	fs := flag.NewFlagSet("ask", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	if err := fs.Parse(args); err != nil {
		return err
	}
	query := strings.TrimSpace(strings.Join(fs.Args(), " "))
	if query == "" {
		return errors.New("nothing to ask — try: onyx ask \"how do I undo a commit?\"")
	}
	ag := agent.New(store)
	ans, err := ag.Answer(context.Background(), query)
	if err != nil {
		return err
	}
	ui.Body(ans.Text)
	if ans.Note != "" {
		fmt.Println(ui.Amber("! " + ans.Note))
	}
	printSources(ans.Hits)
	ui.Meta(ag.ModelLabel(),
		formatNum(agent.EstimateTokens(ans.Text))+" tokens",
		plural(len(ans.Hits), "knowledge hit"))
	return nil
}

func runForget(store *knowledge.Store, args []string) error {
	if !hasFlag(args, "--yes") && !hasFlag(args, "-y") {
		return errors.New("this deletes all trained knowledge — re-run with: onyx forget --yes")
	}
	if err := store.Clear(); err != nil {
		return err
	}
	ui.Success("knowledge cleared — the app keeps no trained data now")
	return nil
}

func hasFlag(args []string, name string) bool {
	for _, a := range args {
		if a == name {
			return true
		}
	}
	return false
}

func runREPL(store *knowledge.Store) {
	ag := agent.New(store)
	ui.Banner(bannerInfo(store, ag))
	reader := bufio.NewReaderSize(os.Stdin, 1<<20)
	for {
		fmt.Print("\n" + ui.Prompt())
		line, err := reader.ReadString('\n')
		line = strings.TrimSpace(line)
		if line != "" {
			var quit bool
			ag, quit = handleInput(store, ag, line)
			if quit {
				return
			}
		}
		if err != nil {
			if !errors.Is(err, io.EOF) {
				fmt.Println(ui.Red("! " + err.Error()))
			}
			fmt.Println(ui.Dim("bye."))
			return
		}
	}
}

func handleInput(store *knowledge.Store, ag *agent.Agent, line string) (*agent.Agent, bool) {
	if !strings.HasPrefix(line, "/") {
		askOnce(ag, line)
		return ag, false
	}
	fields := strings.Fields(line)
	cmd := strings.ToLower(fields[0])
	switch cmd {
	case "/exit", "/quit", "/q":
		fmt.Println(ui.Dim("bye."))
		return ag, true
	case "/help", "/?":
		printHelp()
	case "/clear":
		fmt.Print("\x1b[2J\x1b[H")
		ui.Banner(bannerInfo(store, ag))
	case "/status":
		printStatus(store, ag)
	case "/knowledge", "/kb":
		printKnowledge(store)
	case "/train", "/learn":
		if len(fields) < 2 {
			fmt.Println(ui.Red("! usage: /train <file-or-folder> [--replace]"))
			return ag, false
		}
		if err := runTrain(store, fields[1:]); err != nil {
			fmt.Println(ui.Red("! " + err.Error()))
			return ag, false
		}
		return agent.New(store), false
	case "/forget":
		if len(fields) > 1 && (fields[1] == "--yes" || fields[1] == "-y") {
			if err := store.Clear(); err != nil {
				fmt.Println(ui.Red("! " + err.Error()))
				return ag, false
			}
			ui.Success("knowledge cleared")
			return agent.New(store), false
		}
		fmt.Println(ui.Amber("! that deletes all trained knowledge — run /forget --yes to confirm"))
	case "/model":
		return handleModel(store, ag, fields), false
	default:
		fmt.Println(ui.Red("! unknown command " + cmd + " — /help lists them"))
	}
	return ag, false
}

func handleModel(store *knowledge.Store, ag *agent.Agent, fields []string) *agent.Agent {
	switch {
	case len(fields) == 1:
		fmt.Println(ui.Dim("  model:     " + ag.ModelLabel()))
		endpoint := ag.ModelURL
		if endpoint == "" {
			endpoint = "none"
		}
		fmt.Println(ui.Dim("  endpoint:  " + endpoint))
		fmt.Println(ui.Dim("  connect:   /model http://127.0.0.1:11434/v1 llama3.1:8b"))
		fmt.Println(ui.Dim("  disable:   /model off"))
		fmt.Fprintln(os.Stdout, ui.Dim("  any OpenAI-compatible local server works (Ollama, LM Studio, llama.cpp, vLLM)"))
		return ag
	case strings.EqualFold(fields[1], "off"):
		store.Config.ModelURL = ""
		store.Config.Model = ""
		if err := store.SaveConfig(); err != nil {
			fmt.Println(ui.Red("! " + err.Error()))
			return ag
		}
		ui.Success("model disabled — answering from trained knowledge only")
		return agent.New(store)
	case len(fields) >= 3:
		store.Config.ModelURL = fields[1]
		store.Config.Model = fields[2]
		if err := store.SaveConfig(); err != nil {
			fmt.Println(ui.Red("! " + err.Error()))
			return ag
		}
		ui.Success("model set to " + fields[2] + " at " + fields[1])
		return agent.New(store)
	default:
		fmt.Println(ui.Red("! usage: /model <base-url> <model-name>"))
		return ag
	}
}

func askOnce(ag *agent.Agent, query string) {
	ans, err := ag.Answer(context.Background(), query)
	if err != nil {
		fmt.Println(ui.Red("! " + err.Error()))
		return
	}
	fmt.Println()
	ui.Body(ans.Text)
	if ans.Note != "" {
		fmt.Println(ui.Amber("! " + ans.Note))
	}
	printSources(ans.Hits)
	ui.Meta(ag.ModelLabel(),
		formatNum(agent.EstimateTokens(ans.Text))+" tokens",
		plural(len(ans.Hits), "knowledge hit"))
}

func printSources(hits []knowledge.Hit) {
	if len(hits) == 0 {
		return
	}
	lines := make([]string, 0, len(hits))
	for i, h := range hits {
		meta := h.Record.Source
		if len(h.Record.Tags) > 0 {
			meta = strings.Join(h.Record.Tags, ", ")
		}
		line := fmt.Sprintf("[%d] %s", i+1, h.Record.Label())
		if meta != "" {
			line += "  —  " + meta
		}
		lines = append(lines, line)
	}
	ui.Sources(lines)
}

func printKnowledge(store *knowledge.Store) {
	ui.Section("knowledge")
	if len(store.Records) == 0 {
		fmt.Println(ui.Dim("  nothing trained yet — run: onyx train training.jsonl"))
		return
	}
	ui.Detail(fmt.Sprintf("%s in the app", plural(len(store.Records), "record")))
	ui.Detail("saved    " + shortPath(store.KnowledgePath()) + " (" + humanBytes(store.Size()) + ")")
	if !store.Manifest.Updated.IsZero() {
		ui.Detail("trained  " + store.Manifest.Updated.Local().Format("2006-01-02 15:04") +
			" · " + plural(store.Manifest.Trainings, "run"))
	}
	ui.Detail(fmt.Sprintf("%s · %s", plural(store.Manifest.Terms, "indexed term"), formatNum(store.Manifest.Tokens)+" tokens"))
	for _, src := range store.Manifest.Sources {
		ui.Detail(fmt.Sprintf("%s — %s", shortPath(src.Path), plural(src.Records, "record")))
	}
	fmt.Println()
	for i, rec := range store.Records {
		if i >= 8 {
			fmt.Println(ui.Dim(fmt.Sprintf("  … and %s", plural(len(store.Records)-i, "more record"))))
			break
		}
		fmt.Println("  " + ui.Cyan(fmt.Sprintf("%02d", i+1)) + " " + rec.Label())
	}
}

func printStatus(store *knowledge.Store, ag *agent.Agent) {
	ui.Section("status")
	ui.Detail("version    " + Version)
	ui.Detail("model      " + ag.ModelLabel())
	endpoint := ag.ModelURL
	if endpoint == "" {
		endpoint = "not configured"
	}
	ui.Detail("endpoint   " + endpoint)
	ui.Detail("knowledge  " + plural(len(store.Records), "record") + " · " + humanBytes(store.Size()))
	ui.Detail("store      " + shortPath(store.Dir))
	if !store.Manifest.Updated.IsZero() {
		ui.Detail("trained    " + store.Manifest.Updated.Local().Format("2006-01-02 15:04") +
			" · " + plural(store.Manifest.Trainings, "run"))
	}
}

func bannerInfo(store *knowledge.Store, ag *agent.Agent) tui.BannerInfo {
	line := "none yet — /train <file> teaches it"
	if n := len(store.Records); n > 0 {
		line = fmt.Sprintf("%s · %s", plural(n, "record"), humanBytes(store.Size()))
	}
	dir, err := os.Getwd()
	if err != nil {
		dir = "."
	}
	return tui.BannerInfo{
		Version:   Version,
		Model:     ag.ModelLabel(),
		Knowledge: line,
		Directory: shortPath(dir),
	}
}

func printUsage() {
	fmt.Println(ui.Bold("ONYX") + ui.Dim(" — a locally hosted coding agent that learns from your own data"))
	fmt.Println()
	fmt.Println("  onyx                     start the app")
	fmt.Println("  onyx train <path...>     train on training data and save it to the app")
	fmt.Println("  onyx ask \"<question>\"    one-shot question against trained knowledge")
	fmt.Println("  onyx knowledge           show what the app has learned")
	fmt.Println("  onyx forget --yes        delete all trained knowledge")
	fmt.Println("  onyx version             print the version")
	fmt.Println()
	fmt.Println(ui.Dim("  training data format + the generator prompt live in basetrainer.txt"))
}

func printHelp() {
	fmt.Println(ui.Dim("  commands"))
	fmt.Println("  /train <path> [--replace]   read training data and save it to the app")
	fmt.Println("  /knowledge                  show what the app has learned")
	fmt.Println("  /status                     version, model and store details")
	fmt.Println("  /model                      show or change the local model")
	fmt.Println("  /forget --yes               delete all trained knowledge")
	fmt.Println("  /clear                      clear the screen and redraw the banner")
	fmt.Println("  /exit                       quit")
	fmt.Println(ui.Dim("  anything else is a question answered from your trained knowledge"))
}

func plural(n int, word string) string {
	if n == 1 {
		return "1 " + word
	}
	if strings.HasSuffix(word, "y") {
		return strconv.Itoa(n) + " " + strings.TrimSuffix(word, "y") + "ies"
	}
	return strconv.Itoa(n) + " " + word + "s"
}

func formatNum(n int) string {
	s := strconv.Itoa(n)
	if len(s) <= 3 {
		return s
	}
	var b strings.Builder
	lead := len(s) % 3
	if lead > 0 {
		b.WriteString(s[:lead])
		if len(s) > lead {
			b.WriteString(",")
		}
	}
	for i := lead; i < len(s); i += 3 {
		b.WriteString(s[i : i+3])
		if i+3 < len(s) {
			b.WriteString(",")
		}
	}
	return b.String()
}

func humanBytes(n int64) string {
	const unit = 1024
	if n < unit {
		return fmt.Sprintf("%d B", n)
	}
	div, exp := int64(unit), 0
	for n/div >= unit && exp < 3 {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(n)/float64(div), "KMGT"[exp])
}

func shortPath(p string) string {
	if home, err := os.UserHomeDir(); err == nil && home != "" && strings.HasPrefix(p, home) {
		return "~" + strings.TrimPrefix(p, home)
	}
	return p
}
