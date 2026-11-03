package config

import (
	"testing"
	"time"
)

func TestLoadDebugFlagOverridesFile(t *testing.T) {
	cfg, err := Load("", "http://cmdb.example.com:8080", "", true)
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if !cfg.Debug {
		t.Fatal("--debug flag must enable debug")
	}
	if cfg.Interval != 12*time.Hour || cfg.Timeout != 30*time.Second {
		t.Fatalf("defaults wrong: interval=%v timeout=%v", cfg.Interval, cfg.Timeout)
	}
}
