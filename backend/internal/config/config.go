// Package config 讀取專案設定，不將機密輸出至記錄或 HTTP。
package config

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Load 從 root 的 .env 載入設定；呼叫端處理缺少檔案或讀取錯誤。
func Load(root string) (map[string]string, error) {
	f, err := os.Open(filepath.Join(root, ".env"))
	if err != nil {
		return nil, fmt.Errorf("無法讀取專案 .env: %w", err)
	}
	values := make(map[string]string)
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(strings.TrimPrefix(scanner.Text(), "\ufeff"))
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, found := strings.Cut(line, "=")
		if found {
			values[strings.TrimSpace(key)] = strings.Trim(strings.TrimSpace(value), "\"'")
		}
	}
	readErr := scanner.Err()
	closeErr := f.Close()
	if readErr != nil {
		return nil, readErr
	}
	if closeErr != nil {
		return nil, closeErr
	}
	return values, nil
}
