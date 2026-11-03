// Package logx is a tiny leveled logger for the one-shot collector.
// Info and error lines always print; debug lines print only when enabled
// (--debug flag or config "debug: true") so a timer run stays quiet.
package logx

import (
	"fmt"
	"os"
)

// Debug enables verbose output, set from the --debug flag or the config file
var Debug bool

// Infof prints an info line to stdout
func Infof(format string, a ...any) {
	fmt.Printf("[INFO] "+format+"\n", a...)
}

// Errorf prints an error line to stderr
func Errorf(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "[ERROR] "+format+"\n", a...)
}

// Debugf prints a debug line to stdout only when debug is enabled
func Debugf(format string, a ...any) {
	if !Debug {
		return
	}
	fmt.Printf("[DEBUG] "+format+"\n", a...)
}
