package tui

import (
	"fmt"
	"os"
	"strings"
	"unicode/utf8"
)

const (
	reset = "\x1b[0m"
	bold  = "\x1b[1m"
	dim   = "\x1b[2m"
	blue  = "\x1b[94m"
	cyan  = "\x1b[36m"
	green = "\x1b[32m"
	red   = "\x1b[31m"
	amber = "\x1b[33m"
	gray  = "\x1b[90m"
)

// Renderer writes the Codex-like chrome, with colour when the terminal is real.
type Renderer struct {
	color bool
}

// BannerInfo is the content of the startup panel.
type BannerInfo struct {
	Version   string
	Model     string
	Knowledge string
	Directory string
}

func New() *Renderer {
	on := os.Getenv("NO_COLOR") == "" && os.Getenv("TERM") != "dumb"
	if on {
		fi, err := os.Stdout.Stat()
		on = err == nil && fi.Mode()&os.ModeCharDevice != 0
	}
	return &Renderer{color: on}
}

func (r *Renderer) wrap(code, s string) string {
	if !r.color {
		return s
	}
	return code + s + reset
}

func (r *Renderer) Dim(s string) string   { return r.wrap(dim, s) }
func (r *Renderer) Bold(s string) string  { return r.wrap(bold, s) }
func (r *Renderer) Blue(s string) string  { return r.wrap(blue, s) }
func (r *Renderer) Cyan(s string) string  { return r.wrap(cyan, s) }
func (r *Renderer) Green(s string) string { return r.wrap(green, s) }
func (r *Renderer) Red(s string) string   { return r.wrap(red, s) }
func (r *Renderer) Amber(s string) string { return r.wrap(amber, s) }
func (r *Renderer) Gray(s string) string  { return r.wrap(gray, s) }

// Prompt is the input marker at the top of every turn.
func (r *Renderer) Prompt() string { return r.Bold(r.Blue("› ")) }

// Banner prints the startup panel.
func (r *Renderer) Banner(b BannerInfo) {
	rows := []string{
		r.Bold(">_ ONYX") + " " + r.Dim("(v"+b.Version+")"),
		"",
		label(r, "model:", b.Model),
		label(r, "knowledge:", b.Knowledge),
		label(r, "directory:", b.Directory),
		"",
		r.Dim("Ask a question, or type /help to see the commands."),
	}
	width := 0
	for _, row := range rows {
		if l := visibleLen(row); l > width {
			width = l
		}
	}
	if width < 58 {
		width = 58
	}
	fmt.Println()
	fmt.Println(r.Gray("╭" + strings.Repeat("─", width+2) + "╮"))
	for _, row := range rows {
		fmt.Println(r.Gray("│") + " " + row + strings.Repeat(" ", width-visibleLen(row)) + " " + r.Gray("│"))
	}
	fmt.Println(r.Gray("╰" + strings.Repeat("─", width+2) + "╯"))
}

func label(r *Renderer, name, value string) string {
	pad := 12 - len(name)
	if pad < 1 {
		pad = 1
	}
	return r.Dim(name) + strings.Repeat(" ", pad) + value
}

// Section starts a block of work, e.g. "› training".
func (r *Renderer) Section(title string) {
	fmt.Println()
	fmt.Println(r.Bold(r.Blue("› ")) + r.Bold(title))
}

// Detail is a dim step line inside a section.
func (r *Renderer) Detail(msg string) {
	fmt.Println(r.Dim("  · " + msg))
}

// Success reports a completed step.
func (r *Renderer) Success(msg string) {
	fmt.Println("  " + r.Green("✓ ") + msg)
}

// Warn reports something the user should read but which is not fatal.
func (r *Renderer) Warn(msg string) {
	fmt.Println("  " + r.Amber("! ") + r.Amber(msg))
}

// Body prints an answer.
func (r *Renderer) Body(text string) {
	fmt.Println(strings.TrimRight(text, "\n"))
}

// Meta is the dim status line printed under an answer.
func (r *Renderer) Meta(parts ...string) {
	var kept []string
	for _, p := range parts {
		if strings.TrimSpace(p) != "" {
			kept = append(kept, p)
		}
	}
	if len(kept) == 0 {
		return
	}
	fmt.Println("  " + r.Dim(strings.Join(kept, "  ·  ")))
}

// Sources prints the citation block for an answer.
func (r *Renderer) Sources(lines []string) {
	if len(lines) == 0 {
		return
	}
	rule := strings.Repeat("─", 44)
	fmt.Println()
	fmt.Println(r.Gray("  ── sources " + rule))
	for _, ln := range lines {
		fmt.Println(r.Gray("  " + ln))
	}
}

func visibleLen(s string) int {
	n := 0
	for i := 0; i < len(s); {
		if s[i] == 0x1b && i+1 < len(s) && s[i+1] == '[' {
			i += 2
			for i < len(s) && !(s[i] >= '@' && s[i] <= '~') {
				i++
			}
			i++
			continue
		}
		_, size := utf8.DecodeRuneInString(s[i:])
		if size == 0 {
			break
		}
		i += size
		n++
	}
	return n
}
