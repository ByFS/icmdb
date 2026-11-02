"""Subnet scan tests: CIDR validation, job flow, comparison, real loopback scan"""

import socket
import time

import pytest

from cmdb.api.scan import _directly_connected
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


def test_scan_non_local_subnet_refused(client):
    # 8.8.8.0/24 is routed, not locally connected: refused honestly with the scannable list
    res = client.post("/api/v1/scans", json={"cidr": "8.8.8.0/24"})
    assert res.status_code == 400
    assert "直连网段" in res.json()["detail"]


def test_scan_job_flow_and_comparison(client, monkeypatch):
    from cmdb.api import scan

    # Two devices in CMDB: 192.0.2.11 is known by mgmt_ip, 192.0.2.99 is unknown
    client.post("/api/v1/devices", json=make_push())
    monkeypatch.setattr(
        scan, "_directly_connected", lambda: [__import__("ipaddress").ip_network("192.0.2.0/24")]
    )

    def fake_probe(ip, ports):
        return ip in ("192.0.2.11", "192.0.2.99")

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


def test_scan_loopback_real(client, monkeypatch):
    """Real TCP scan on loopback: the listening port makes 127.0.0.1 alive"""
    import ipaddress

    from cmdb.api import scan

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        monkeypatch.setattr(scan, "SCAN_PORTS", [port])
        # The host may not expose a loopback route in /proc/net/route: stub the check
        monkeypatch.setattr(
            scan, "_directly_connected", lambda: [ipaddress.ip_network("127.0.0.0/8")]
        )
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


def test_directly_connected_parses_routes():
    networks = _directly_connected()
    assert networks, "no directly connected routes parsed"
    for n in networks:
        assert str(n).count("/") == 1
