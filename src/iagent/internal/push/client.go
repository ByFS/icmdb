// Package push implements the CMDB API push client
package push

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"iagent/internal/logx"
	"iagent/internal/payload"
)

// Result is the push response: result has three branches, created / unchanged / diff_created
type Result struct {
	Result          string `json:"result"`
	DeviceID        int    `json:"device_id"`
	PendingChangeID *int   `json:"pending_change_id"`
}

type Client struct {
	serverURL string
	token     string
	http      *http.Client
}

func NewClient(serverURL, token string) *Client {
	return &Client{
		serverURL: serverURL,
		token:     token,
		http:      &http.Client{Timeout: 30 * time.Second},
	}
}

// Push pushes device data. No retry on failure (next cycle full sync self-heals)
func (c *Client) Push(p *payload.Payload) (Result, error) {
	body, err := json.Marshal(p)
	if err != nil {
		return Result{}, fmt.Errorf("marshal payload: %w", err)
	}
	logx.Debugf("push -> %s/api/v1/devices (%d bytes, key=%v)", c.serverURL, len(body), c.token != "")
	req, err := http.NewRequest(http.MethodPost, c.serverURL+"/api/v1/devices", bytes.NewReader(body))
	if err != nil {
		return Result{}, fmt.Errorf("new request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.token != "" {
		// The CMDB push endpoint checks the X-API-Key header (API key auth)
		req.Header.Set("X-API-Key", c.token)
	}
	start := time.Now()
	resp, err := c.http.Do(req)
	if err != nil {
		return Result{}, fmt.Errorf("push: %w", err)
	}
	defer resp.Body.Close()
	logx.Debugf("push <- HTTP %d in %s", resp.StatusCode, time.Since(start).Round(time.Millisecond))
	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		logx.Debugf("push error body: %s", string(b))
		return Result{}, fmt.Errorf("push: HTTP %d", resp.StatusCode)
	}
	var result Result
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return Result{}, fmt.Errorf("decode result: %w", err)
	}
	logx.Debugf("push result: %s device_id=%d", result.Result, result.DeviceID)
	return result, nil
}
