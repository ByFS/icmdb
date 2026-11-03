"""Subnet scan tests: CIDR validation, job flow, comparison, real loopback scan"""

import socket
import time

import pytest

from test_api import make_push


def _wait_job(client, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"/api/v1/scans/{job_id}")
        assert res.status_code == 200
        job = res.json()
        if job["status"] != "running":
            return job
        time.sleep(0.1)
    pytest.fail("scan job did not finish in time")


def test_scan_invalid_cidr(client):
    res = client.post("/api/v1/scans", json={"cidr": "not-a-cidr"})
    assert res.status_code == 422


def test_scan_non_local_subnet_accepted(client, monkeypatch):
    # Routed subnets are allowed: this host can reach upper-layer networks
    from cmdb.api import scan

    monkeypatch.setattr(scan, "_probe_host", lambda ip, ports: False)
    res = client.post("/api/v1/scans", json={"cidr": "8.8.8.0/24"})
    assert res.status_code == 200
    job = _wait_job(client, res.json()["job_id"])
    assert job["status"] == "done"
    assert job["total"] == 254


def test_scan_job_flow_and_comparison(client, monkeypatch):
    from cmdb.api import scan

    # Two devices in CMDB: 192.0.2.11 is known by mgmt_ip, 192.0.2.98/99 are unknown
    client.post("/api/v1/devices", json=make_push())
    # deterministic: no reverse-DNS names, the add flow falls back to the IP
    monkeypatch.setattr(scan, "_reverse_dns", lambda ip: "")

    def fake_probe(ip, ports):
        return ip in ("192.0.2.11", "192.0.2.98", "192.0.2.99")

    monkeypatch.setattr(scan, "_probe_host", fake_probe)

    res = client.post("/api/v1/scans", json={"cidr": "192.0.2.0/24"})
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    job = _wait_job(client, job_id)
    assert job["status"] == "done"
    # hosts() excludes the network and broadcast addresses
    assert job["total"] == 254
    hosts = {h["ip"]: h for h in job["hosts"]}
    assert hosts["192.0.2.11"]["known"] is True
    assert hosts["192.0.2.11"]["device_hostname"] == "demo-node-01"
    assert hosts["192.0.2.99"]["known"] is False
    assert hosts["192.0.2.99"]["device_id"] is None
    # Unprobed hosts are not in the results
    assert "192.0.2.12" not in hosts

    # Direct add with an explicit hostname
    res = client.post(
        "/api/v1/scans/add",
        json={"job_id": job_id, "ip": "192.0.2.99", "hostname": "scan-added-node"},
    )
    assert res.status_code == 200
    assert res.json()["result"] == "created"
    added_id = res.json()["device_id"]
    dev = client.get(f"/api/v1/devices/{added_id}")
    assert dev.status_code == 200
    assert dev.json()["hostname"] == "scan-added-node"
    assert dev.json()["mgmt_ip"] == "192.0.2.99"
    # the repolled job marks the host known
    job = _wait_job(client, job_id)
    host99 = next(h for h in job["hosts"] if h["ip"] == "192.0.2.99")
    assert host99["known"] is True
    assert host99["device_id"] == added_id
    # re-adding a known host conflicts
    res = client.post("/api/v1/scans/add", json={"job_id": job_id, "ip": "192.0.2.99"})
    assert res.status_code == 409
    # hostname falls back to the IP when nothing is given
    res = client.post("/api/v1/scans/add", json={"job_id": job_id, "ip": "192.0.2.98"})
    assert res.status_code == 200
    dev = client.get(f"/api/v1/devices/{res.json()['device_id']}")
    assert dev.json()["hostname"] == "192.0.2.98"
    # unknown job and unknown ip are 404
    assert client.post("/api/v1/scans/add", json={"job_id": "nope", "ip": "192.0.2.98"}).status_code == 404
    assert client.post("/api/v1/scans/add", json={"job_id": job_id, "ip": "192.0.2.12"}).status_code == 404
    # the add is audited
    audit = client.get("/api/v1/audit-logs?page=1&page_size=10")
    assert any(a["action"] == "扫描添加设备" for a in audit.json()["items"])


def test_scan_loopback_real(client, monkeypatch):
    """Real TCP scan on loopback: the listening port makes 127.0.0.1 alive"""
    from cmdb.api import scan

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        monkeypatch.setattr(scan, "SCAN_PORTS", [port])
        res = client.post("/api/v1/scans", json={"cidr": "127.0.0.1/32"})
        assert res.status_code == 200
        job = _wait_job(client, res.json()["job_id"])
        assert job["status"] == "done"
        assert job["total"] == 1
        assert len(job["hosts"]) == 1
        host = job["hosts"][0]
        assert host["ip"] == "127.0.0.1"
        # Loopback has no ARP entry: no MAC is expected
        assert host["mac"] is None
    finally:
        server.close()
