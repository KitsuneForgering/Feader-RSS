// Package localfile reads user-editable files (configuration, legacy state,
// imported OPML) with a byte ceiling, so an oversized or hostile file is
// rejected before it is materialized in memory instead of after parsing.
package localfile

import (
	"fmt"
	"io"
	"os"
)

const (
	// MaxConfigBytes bounds rss-reader.json; it matches the panel's
	// maxSettingsFileBytes. A 100-feed configuration is ~20 KiB.
	MaxConfigBytes = 1 << 20
	// MaxOPMLBytes bounds imported OPML documents, which may come from
	// other readers with far more subscriptions than Feader keeps.
	MaxOPMLBytes = 8 << 20
	// MaxLegacyStateBytes bounds the pre-SQLite items.json state file.
	MaxLegacyStateBytes = 64 << 20
)

// ErrTooLarge is returned by ReadCapped when the file exceeds the limit.
type ErrTooLarge struct {
	Path  string
	Limit int64
}

func (e *ErrTooLarge) Error() string {
	return fmt.Sprintf("%s exceeds %d byte limit", e.Path, e.Limit)
}

// ReadCapped reads at most limit+1 bytes of path and returns ErrTooLarge
// instead of silently truncating. Open errors are returned unwrapped, so
// os.IsNotExist keeps working for callers that treat a missing file as empty.
func ReadCapped(path string, limit int64) ([]byte, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, limit+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > limit {
		return nil, &ErrTooLarge{Path: path, Limit: limit}
	}
	return data, nil
}
