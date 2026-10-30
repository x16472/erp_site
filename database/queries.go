package database

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

//go:embed queries.json
var queryCatalog []byte

//go:embed normalized_queries.json
var normalizedCatalog []byte

type queryDefinition struct {
	SQL      string `json:"sql"`
	Dynamic  int    `json:"dynamic"`
	ReadOnly bool   `json:"read_only"`
}

var allowedTables = map[string]bool{
	"Company_WebSettings": true, "Company_Department": true, "Company_Staff": true, "Company_Attendance": true,
	"Company_OperationCategory": true, "Company_OperationSubmission": true, "Company_TrainingDocument": true,
	"Company_TrainingSection": true, "Company_TrainingQuestion": true, "Company_ImportState": true,
}

var identifiersPattern = regexp.MustCompile(`^\[(?:[^\]\x00\r\n]|\]\])+\](?:, \[(?:[^\]\x00\r\n]|\]\])+\])*$`)

func loadQueries() (map[string]queryDefinition, error) {
	var catalog map[string]queryDefinition
	if err := json.Unmarshal(queryCatalog, &catalog); err != nil {
		return nil, fmt.Errorf("查詢目錄無法解析：%w", err)
	}
	return catalog, nil
}

func resolveQuery(catalog map[string]queryDefinition, name string, body []byte, readOnly bool) (string, error) {
	definition, ok := catalog[name]
	if !ok {
		return "", errors.New("不允許未登錄的資料庫查詢")
	}
	if readOnly && !definition.ReadOnly {
		return "", errors.New("唯讀連線不允許資料異動")
	}
	var options []any
	if len(body) > 0 {
		decoder := json.NewDecoder(bytes.NewReader(body))
		decoder.UseNumber()
		if err := decoder.Decode(&options); err != nil {
			return "", errors.New("查詢選項格式錯誤")
		}
	}
	if len(options) != definition.Dynamic {
		return "", errors.New("查詢選項數量不符")
	}
	fragments := make([]string, len(options))
	for i, value := range options {
		text, ok := value.(string)
		if !ok {
			return "", errors.New("查詢選項必須是文字")
		}
		switch name {
		case "domain.table_data.2":
			if i == 0 {
				if !identifiersPattern.MatchString(text) {
					return "", errors.New("欄位識別名稱不合法")
				}
			} else if !allowedQualifiedTable(text) {
				return "", errors.New("資料表不在白名單")
			}
		case "domain.table_data.3":
			if !allowedQualifiedTable(text) {
				return "", errors.New("資料表不在白名單")
			}
		case "domain._count.1":
			if !allowedTables[text] {
				return "", errors.New("資料表不在白名單")
			}
		case "domain.attendance_staff_options.1":
			if text != "employee_id" && text != "department, employee_id" {
				return "", errors.New("不支援的排序方式")
			}
		case "domain.update_training_questions_bulk.2":
			count, err := strconv.Atoi(text)
			if err != nil || count < 1 || count > 500 {
				return "", errors.New("批次筆數必須介於 1 與 500")
			}
			text = strings.TrimSuffix(strings.Repeat("?,", count), ",")
		case "domain._published_question_rows.1":
			var counts []int
			if err := json.Unmarshal([]byte(text), &counts); err != nil || len(counts) != 3 {
				return "", errors.New("題庫篩選數量錯誤")
			}
			text = "q.subject_id=? AND q.domain=N'academic' AND q.status=N'published' AND q.is_active=1 AND q.question_type IN (N'single_choice',N'multiple_choice',N'reading')"
			for j, column := range []string{"q.chapter_id", "q.document_id", "q.question_type"} {
				if counts[j] < 0 || counts[j] > 500 {
					return "", errors.New("題庫篩選數量過多")
				}
				if counts[j] > 0 {
					text += " AND " + column + " IN (" + strings.TrimSuffix(strings.Repeat("?,", counts[j]), ",") + ")"
				}
			}
		default:
			return "", errors.New("查詢沒有動態選項處理器")
		}
		fragments[i] = text
	}
	query := definition.SQL
	for i, fragment := range fragments {
		query = strings.ReplaceAll(query, fmt.Sprintf("{{%d}}", i), fragment)
	}
	return query, nil
}

func allowedQualifiedTable(value string) bool {
	if !strings.HasPrefix(value, "[dbo].[") || !strings.HasSuffix(value, "]") {
		return false
	}
	return allowedTables[strings.TrimSuffix(strings.TrimPrefix(value, "[dbo].["), "]")]
}
