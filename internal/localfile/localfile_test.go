package localfile

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestReadCapped(t *testing.T) {
	dir := t.TempDir()
	write := func(name, content string) string {
		path := filepath.Join(dir, name)
		if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
		return path
	}

	data, err := ReadCapped(write("small.json", "{}"), 8)
	if err != nil || string(data) != "{}" {
		t.Fatalf("small file: got %q, %v", data, err)
	}

	data, err = ReadCapped(write("exact.json", strings.Repeat("x", 8)), 8)
	if err != nil || len(data) != 8 {
		t.Fatalf("file at the limit: got %d bytes, %v", len(data), err)
	}

	_, err = ReadCapped(write("big.json", strings.Repeat("x", 9)), 8)
	var tooLarge *ErrTooLarge
	if !errors.As(err, &tooLarge) || tooLarge.Limit != 8 {
		t.Fatalf("oversized file: want ErrTooLarge, got %v", err)
	}

	_, err = ReadCapped(filepath.Join(dir, "absent.json"), 8)
	if !os.IsNotExist(err) {
		t.Fatalf("missing file: want a not-exist error, got %v", err)
	}
}
