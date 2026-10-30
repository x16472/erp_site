//go:build js && wasm

package main

import (
	"errors"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/scanner"
	"go/token"
	"reflect"
	"runtime"
	"strings"
	"syscall/js"

	"github.com/traefik/yaegi/interp"
	"github.com/traefik/yaegi/stdlib"
)

type outputStream string

func (stream outputStream) Write(data []byte) (int, error) {
	js.Global().Call("golangEmit", string(stream), string(data))
	return len(data), nil
}

var (
	standardInput = strings.NewReader("")
	interpreter   *interp.Interpreter
	pendingLines  []string
)

func newInterpreter() (*interp.Interpreter, error) {
	instance := interp.New(interp.Options{
		Stdin:  standardInput,
		Stdout: outputStream("stdout"),
		Stderr: outputStream("stderr"),
		Args:   []string{"main.go"},
	})
	if err := instance.Use(stdlib.Symbols); err != nil {
		return nil, err
	}
	return instance, nil
}

func needsMoreInput(err error) bool {
	var parseErrors scanner.ErrorList
	if !errors.As(err, &parseErrors) {
		return false
	}
	for _, item := range parseErrors {
		if !strings.Contains(item.Msg, "'EOF'") {
			return false
		}
	}
	return len(parseErrors) > 0
}

func validateMain(source string) error {
	file, err := parser.ParseFile(token.NewFileSet(), "main.go", source, 0)
	if err != nil {
		return err
	}
	if file.Name.Name != "main" {
		return fmt.Errorf("main.go 必須使用 package main")
	}
	for _, declaration := range file.Decls {
		if function, ok := declaration.(*ast.FuncDecl); ok && function.Name.Name == "main" && function.Recv == nil {
			return nil
		}
	}
	return fmt.Errorf("main.go 必須包含 func main()")
}

func execute(message js.Value) {
	response := map[string]interface{}{"ok": true, "more": false}
	defer func() {
		if failure := recover(); failure != nil {
			response["ok"] = false
			pendingLines = nil
			fmt.Fprintln(outputStream("stderr"), failure)
		}
		js.Global().Call("golangComplete", response)
	}()

	standardInput.Reset(message.Get("stdin").String())
	source := message.Get("code").String()
	var err error
	switch message.Get("type").String() {
	case "format":
		var formatted []byte
		formatted, err = format.Source([]byte(source))
		if err == nil {
			response["formatted"] = string(formatted)
		}
	case "run":
		pendingLines = nil
		if err = validateMain(source); err == nil {
			// 每次 go run 重新建立程式的全域變數與匯入狀態。
			interpreter, err = newInterpreter()
			if err == nil {
				_, err = interpreter.Eval(source)
			}
		}
	case "repl":
		pendingLines = append(pendingLines, source)
		source = strings.Join(pendingLines, "\n")
		var result reflect.Value
		result, err = interpreter.Eval(source)
		if err != nil && needsMoreInput(err) {
			response["more"] = true
			err = nil
		} else {
			pendingLines = nil
			_, expressionError := parser.ParseExpr(source)
			if err == nil && expressionError == nil && result.IsValid() && result.CanInterface() && result.Kind() != reflect.Func {
				fmt.Fprintln(outputStream("stdout"), result.Interface())
			}
		}
	default:
		err = fmt.Errorf("不支援的 Go 操作")
	}
	if err != nil {
		response["ok"] = false
		pendingLines = nil
		fmt.Fprintln(outputStream("stderr"), err)
	}
}

func main() {
	var err error
	interpreter, err = newInterpreter()
	if err != nil {
		js.Global().Call("golangFatal", err.Error())
		return
	}
	callback := js.FuncOf(func(_ js.Value, args []js.Value) interface{} {
		// 讓 JS callback 先返回，time.Sleep 與 goroutine 才能繼續使用瀏覽器事件迴圈。
		go execute(args[0])
		return nil
	})
	js.Global().Set("golangExecute", callback)
	js.Global().Call("golangReady", runtime.Version())
	select {}
}
