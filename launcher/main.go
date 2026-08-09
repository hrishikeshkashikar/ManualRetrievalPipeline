// Manual RAG thin launcher (Windows .exe / macOS .app).
//
// Build Windows:
//   GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o ManualRAG.exe .
// Build macOS (this machine):
//   go build -ldflags="-s -w" -o ManualRAG-darwin .
//   ./scripts/build_mac_dmg.sh
//
// Orchestrates Docker only — models live in the Docker image.

package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

const (
	composeFile = "docker-compose.edge.yml"
	imageTar    = "manual-rag-query.tar.gz"
	imageTag    = "manual-rag-query:latest"
	port        = "8000"
	container   = "manual-rag-edge"
)

// Absolute path to docker CLI (Finder apps often lack /usr/local/bin on PATH).
var dockerBin = "docker"

func main() {
	augmentPath()
	root := findBundleRoot()
	if err := os.Chdir(root); err != nil {
		fatal("cannot cd to bundle root: %v", err)
	}

	logf("")
	logf(" ========================================================")
	logf("  Manual RAG — Edge Query-Only")
	logf(" ========================================================")
	logf("")
	logf("Bundle root: %s", root)

	var err error
	dockerBin, err = findDocker()
	if err != nil {
		fatal("Docker not found. Install Docker Desktop and ensure it is running:\nhttps://www.docker.com/products/docker-desktop/\n\nIf it is already installed, open Docker Desktop once, then try again.")
	}
	logf("Docker CLI: %s", dockerBin)

	if err := runQuiet(dockerBin, "info"); err != nil {
		fatal("Docker Desktop is not running. Start it, wait until the whale icon is idle, then try again.")
	}
	if _, err := os.Stat(composeFile); err != nil {
		fatal("Missing %s next to the app.\nExpected in:\n%s\n\nOpen the DMG / edge bundle folder that contains docker-compose.edge.yml.", composeFile, root)
	}

	dataDir := ""
	if len(os.Args) > 1 {
		dataDir = os.Args[1]
	} else if runtime.GOOS == "darwin" {
		dataDir, err = macChooseFolder()
		if err != nil {
			fatal("Folder selection cancelled or failed.")
		}
	} else {
		fmt.Print("Enter path to data folder (chroma_db + images + manuals): ")
		reader := bufio.NewReader(os.Stdin)
		line, _ := reader.ReadString('\n')
		dataDir = strings.TrimSpace(line)
	}
	if dataDir == "" {
		fatal("No data path provided.")
	}
	dataDir = strings.TrimSuffix(dataDir, "/")
	if abs, err := filepath.Abs(dataDir); err == nil {
		dataDir = abs
	}
	if st, err := os.Stat(dataDir); err != nil || !st.IsDir() {
		fatal("Path not found or not a directory:\n%s", dataDir)
	}

	if err := runQuiet(dockerBin, "image", "inspect", imageTag); err != nil {
		if _, err := os.Stat(imageTar); err != nil {
			fatal("Docker image %s is not loaded and %s is missing.\n\nBuild/export first:\n  ./scripts/build.sh --edge --export\nThen place manual-rag-query.tar.gz next to this app.", imageTag, imageTar)
		}
		notify("Manual RAG", "Loading Docker image (first run can take several minutes)...")
		logf("Loading %s...", imageTar)
		if err := run(dockerBin, "load", "-i", imageTar); err != nil {
			fatal("Failed to load image:\n%v", err)
		}
	}

	os.Setenv("HOST_DATA_DIR", dataDir)
	os.Setenv("API_PORT", port)
	os.Setenv("EDGE_IMAGE", imageTag)

	notify("Manual RAG", "Starting query-only container...")
	logf("Starting query-only container...")
	if err := run(dockerBin, "compose", "-f", composeFile, "up", "-d"); err != nil {
		fatal("Failed to start container:\n%v", err)
	}

	logf("Waiting for health...")
	deadline := time.Now().Add(180 * time.Second)
	for time.Now().Before(deadline) {
		out, _ := exec.Command(dockerBin, "inspect", "--format", "{{.State.Health.Status}}", container).CombinedOutput()
		if strings.TrimSpace(string(out)) == "healthy" {
			break
		}
		time.Sleep(5 * time.Second)
		logf("  ... %s", strings.TrimSpace(string(out)))
	}

	url := "http://localhost:" + port + "/"
	logf("Opening %s", url)
	openBrowser(url)
	notify("Manual RAG", "Ready — opened "+url+"\n\nStop later:\ndocker compose -f "+composeFile+" down")

	if runtime.GOOS == "windows" {
		fmt.Println("Press Enter to close...")
		bufio.NewReader(os.Stdin).ReadBytes('\n')
	}
}

// Finder-launched .apps get a tiny PATH without Homebrew / Docker Desktop bins.
func augmentPath() {
	extras := []string{
		"/usr/local/bin",
		"/opt/homebrew/bin",
		"/Applications/Docker.app/Contents/Resources/bin",
	}
	path := os.Getenv("PATH")
	for _, p := range extras {
		if !strings.Contains(path, p) {
			path = p + string(os.PathListSeparator) + path
		}
	}
	_ = os.Setenv("PATH", path)
}

func findDocker() (string, error) {
	candidates := []string{
		"/Applications/Docker.app/Contents/Resources/bin/docker",
		"/usr/local/bin/docker",
		"/opt/homebrew/bin/docker",
	}
	if p, err := exec.LookPath("docker"); err == nil {
		return p, nil
	}
	for _, c := range candidates {
		if st, err := os.Stat(c); err == nil && !st.IsDir() {
			return c, nil
		}
	}
	return "", fmt.Errorf("docker not found")
}

func findBundleRoot() string {
	exe, err := os.Executable()
	if err != nil {
		wd, _ := os.Getwd()
		return wd
	}
	resolved, err := filepath.EvalSymlinks(exe)
	if err == nil {
		exe = resolved
	}
	dir := filepath.Dir(exe)

	// Candidates:
	//  - next to binary (repo launcher/ or Windows bundle root)
	//  - parent of launcher/
	//  - parent of ManualRAG.app (…/ManualRAG.app/Contents/MacOS → ../../../)
	candidates := []string{
		dir,
		filepath.Join(dir, ".."),
		filepath.Join(dir, "..", "..", ".."),
	}
	for _, c := range candidates {
		abs, err := filepath.Abs(c)
		if err != nil {
			continue
		}
		if _, err := os.Stat(filepath.Join(abs, composeFile)); err == nil {
			return abs
		}
	}
	wd, _ := os.Getwd()
	return wd
}

func run(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func runQuiet(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Stdout = nil
	cmd.Stderr = nil
	return cmd.Run()
}

func openBrowser(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	_ = cmd.Start()
}

func macChooseFolder() (string, error) {
	script := `POSIX path of (choose folder with prompt "Select Manual RAG data folder (must contain chroma_db, images, manuals)")`
	out, err := exec.Command("osascript", "-e", script).CombinedOutput()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

func notify(title, message string) {
	if runtime.GOOS != "darwin" {
		return
	}
	esc := func(s string) string {
		s = strings.ReplaceAll(s, "\\", "\\\\")
		s = strings.ReplaceAll(s, "\"", "\\\"")
		return s
	}
	script := fmt.Sprintf(`display notification "%s" with title "%s"`, esc(message), esc(title))
	_ = exec.Command("osascript", "-e", script).Run()
}

func logf(format string, args ...any) {
	fmt.Printf(format+"\n", args...)
}

func fatal(format string, args ...any) {
	msg := fmt.Sprintf(format, args...)
	fmt.Fprintln(os.Stderr, msg)
	if runtime.GOOS == "darwin" {
		esc := strings.ReplaceAll(msg, "\\", "\\\\")
		esc = strings.ReplaceAll(esc, "\"", "\\\"")
		_ = exec.Command("osascript", "-e", fmt.Sprintf(`display alert "Manual RAG" message "%s" as critical`, esc)).Run()
	}
	if runtime.GOOS == "windows" {
		fmt.Println("Press Enter to close...")
		bufio.NewReader(os.Stdin).ReadBytes('\n')
	}
	os.Exit(1)
}
