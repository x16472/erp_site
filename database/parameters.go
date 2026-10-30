package database

import (
	"fmt"
	"strings"
)

// bindParameters 只轉換 SQL 語法中的問號，保留字串、識別名稱及註解內容。
func bindParameters(query string, count int) (string, error) {
	var out strings.Builder
	index, blockDepth := 0, 0
	var quote byte
	lineComment := false
	for i := 0; i < len(query); i++ {
		ch := query[i]
		next := byte(0)
		if i+1 < len(query) {
			next = query[i+1]
		}
		if lineComment {
			out.WriteByte(ch)
			if ch == '\n' {
				lineComment = false
			}
			continue
		}
		if blockDepth > 0 {
			out.WriteByte(ch)
			if ch == '/' && next == '*' {
				blockDepth++
				out.WriteByte(next)
				i++
			} else if ch == '*' && next == '/' {
				blockDepth--
				out.WriteByte(next)
				i++
			}
			continue
		}
		if quote != 0 {
			out.WriteByte(ch)
			if ch == quote {
				if next == quote {
					out.WriteByte(next)
					i++
				} else {
					quote = 0
				}
			}
			continue
		}
		switch {
		case ch == '-' && next == '-':
			lineComment = true
			out.WriteString("--")
			i++
		case ch == '/' && next == '*':
			blockDepth = 1
			out.WriteString("/*")
			i++
		case ch == '\'' || ch == '"':
			quote = ch
			out.WriteByte(ch)
		case ch == '[':
			quote = ']'
			out.WriteByte(ch)
		case ch == '?':
			index++
			fmt.Fprintf(&out, "@p%d", index)
		default:
			out.WriteByte(ch)
		}
	}
	if index != count {
		return "", fmt.Errorf("SQL 參數數量不符：需要 %d，收到 %d", index, count)
	}
	return out.String(), nil
}
