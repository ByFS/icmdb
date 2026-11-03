// iagent CMDB hardware asset collection client (one-shot).
// Triggered by systemd timer: collect -> assemble -> push -> exit.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"iagent/internal/collector"
	"iagent/internal/config"
	"iagent/internal/logx"
	"iagent/internal/payload"
	"iagent/internal/push"
)

// Version is injected at build time: -ldflags "-X main.version=0.1.0"
var version = "dev"

// defaultConfigTemplate is written by --init, with all options documented.
// server_url is left empty so the first real run fails with a clear hint.
const defaultConfigTemplate = `# iagent config file. Priority: CLI flags > this file > built-in defaults.
# Only server_url is required; all other options fall back to defaults.

# CMDB API address (required)
# Push target, the root URL of the icmdb ingest API, e.g. http://cmdb.example.com:8080.
# Empty or missing fails fast on startup (exit 1), nothing is pushed.
server_url: ""

# API key (optional, default "")
# The CMDB API key; only effective when the server has API key auth enabled.
# Sent as "X-API-Key: <token>"; omitted when empty, zero-change integration.
token: ""

# Push interval (optional, default 12h)
# Only used by Ansible to generate the systemd timer schedule; the process itself
# never reads it (one-shot process is driven by the timer, exits after each run).
# Accepts Go duration format: 30m / 1h / 6h / 12h / 24h.
# 12h recommended: aligns with the CMDB offline threshold of 3 days (~6 pushes/cycle).
interval: 12h

# HTTP timeout (optional, default 30s)
# Timeout for a single POST push. Timeout counts as failure: log, no retry,
# the next cycle full sync self-heals.
timeout: 30s

# Debug logging (optional, default false)
# true prints why each field or command failed (the [DEBUG] lines). Keep false
# for the timer runs so logs stay quiet.
debug: false
`

func main() {
	os.Exit(run())
}

// usage prints help (shown when invoked without any arguments).
func usage() {
	fmt.Print(`iagent CMDB hardware asset collection client (one-shot)

Usage:
  iagent                     show this help
  iagent --print             test mode: collect and print JSON to stdout (no push)
  iagent --init              generate default config file (default /etc/iagent/config.yml, never overwrites)
  iagent --config <path>     collect and push to CMDB (config file must contain server_url)

Flags:
`)
	flag.PrintDefaults()
	fmt.Print(`
Examples:
  iagent --print                              # collect once, print JSON directly
  iagent --print --debug                      # print plus debug logs (why a field is null)
  iagent --init                               # generate config template, then fill in server_url
  iagent --config /etc/iagent/config.yml      # real collect and push (invoked by systemd timer)
  iagent --config /etc/iagent/config.yml --debug   # real push with verbose logs
`)
}

func run() int {
	configPath := flag.String("config", "", "config file path (default /etc/iagent/config.yml)")
	serverURL := flag.String("server", "", "CMDB API address, e.g. http://cmdb.example.com:8080")
	token := flag.String("token", "", "CMDB API key (X-API-Key header)")
	initConfig := flag.Bool("init", false, "generate default config file (never overwrites)")
	printOnly := flag.Bool("print", false, "collect and print JSON to stdout, no push, no config file needed (test mode)")
	debug := flag.Bool("debug", false, "verbose debug logging (troubleshooting)")
	flag.Usage = usage
	flag.Parse()

	// --debug works for every mode, including --print (no config file there)
	logx.Debug = *debug

	// Default (no arguments): show help
	if !*initConfig && !*printOnly && *configPath == "" && *serverURL == "" && *token == "" && !*debug {
		flag.Usage()
		return 0
	}

	if *initConfig {
		if *configPath == "" {
			*configPath = "/etc/iagent/config.yml"
		}
		return writeDefaultConfig(*configPath)
	}

	// --print test mode: skip config file, collect then print
	if *printOnly {
		return printPayload()
	}

	if *configPath == "" {
		*configPath = "/etc/iagent/config.yml"
	}

	cfg, err := config.Load(*configPath, *serverURL, *token, *debug)
	if err != nil {
		logx.Errorf("config: %v", err)
		return 1
	}
	// config "debug: true" also enables verbose output
	logx.Debug = cfg.Debug
	logx.Debugf("config loaded: file=%s server=%s timeout=%s debug=%v", *configPath, cfg.ServerURL, cfg.Timeout, cfg.Debug)

	p, err := collectAndBuild()
	if err != nil {
		logx.Errorf("%v", err)
		return 1
	}

	result, err := push.NewClient(cfg.ServerURL, cfg.Token).Push(&p)
	if err != nil {
		logx.Errorf("push: %v", err)
		return 1
	}
	logx.Infof("push ok: result=%s device_id=%d pending_change_id=%v",
		result.Result, result.DeviceID, result.PendingChangeID)
	return 0
}

// collectAndBuild collects and assembles the payload. hostname failure is the only hard failure.
func collectAndBuild() (payload.Payload, error) {
	// hostname failure is the only hard failure: abort, do not push
	osInfo, err := collector.CollectOS()
	if err != nil {
		return payload.Payload{}, fmt.Errorf("collect os: %w", err)
	}
	logx.Debugf("collect os: hostname=%s kernel=%v virt=%v version=%v",
		osInfo.Hostname, ptrString(osInfo.Kernel), ptrString(osInfo.Virt), ptrString(osInfo.Version))

	// Other categories are collected independently; single-field failures are already
	// mapped to null inside the collector
	mgmt, mgmtErr := collector.CollectMgmt()
	if mgmtErr != nil {
		logx.Debugf("collect mgmt: %v (fields become null)", mgmtErr)
	} else {
		logx.Debugf("collect mgmt: ip=%v mac=%v prefix=%v", ptrString(mgmt.IP), ptrString(mgmt.MAC), mgmt.PrefixLength)
	}
	hw, hwErr := collector.CollectHardware()
	if hwErr != nil {
		logx.Debugf("collect hardware: %v (fields become null)", hwErr)
	} else {
		memSlots := 0
		if hw.Memory != nil {
			memSlots = len(hw.Memory.Slots)
		}
		gpuSlots := 0
		if hw.Gpu != nil {
			gpuSlots = len(hw.Gpu.Slots)
		}
		logx.Debugf("collect hardware: nics=%d memory_slots=%d cpus=%d disks=%d psus=%d gpus=%d",
			len(hw.Nics), memSlots, len(hw.Cpus), len(hw.Disks), len(hw.Psus), gpuSlots)
	}

	agent := payload.Agent{
		Version:   version,
		Source:    "icmdb",
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}
	p, err := payload.Build(agent, osInfo, &mgmt, &hw)
	if err != nil {
		return payload.Payload{}, fmt.Errorf("build payload: %w", err)
	}
	return p, nil
}

// ptrString prints the pointed value or "null" for debug lines
func ptrString(s *string) string {
	if s == nil {
		return "null"
	}
	return *s
}

// printPayload implements the --print test mode: collect then print JSON, no push, no config file.
func printPayload() int {
	p, err := collectAndBuild()
	if err != nil {
		logx.Errorf("%v", err)
		return 1
	}
	b, err := json.MarshalIndent(p, "", "  ")
	if err != nil {
		logx.Errorf("marshal payload: %v", err)
		return 1
	}
	fmt.Println(string(b))
	return 0
}

// writeDefaultConfig generates the default config file (--init subcommand).
// Idempotent: refuses to overwrite an existing file, exits with a hint.
func writeDefaultConfig(path string) int {
	if _, err := os.Stat(path); err == nil {
		logx.Infof("config already exists: %s (not overwritten; delete it first to regenerate)", path)
		return 0
	}
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		logx.Errorf("mkdir %s: %v", dir, err)
		return 1
	}
	if err := os.WriteFile(path, []byte(defaultConfigTemplate), 0o644); err != nil {
		logx.Errorf("write config: %v", err)
		return 1
	}
	logx.Infof("config written: %s", path)
	logx.Infof("fill in server_url, then run iagent to start collecting")
	return 0
}
