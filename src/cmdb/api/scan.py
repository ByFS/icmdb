"""Subnet scan: TCP probe liveness + ARP cache MAC + reverse DNS, no root needed

Any reachable subnet is scannable: TCP probes cross routers, but ARP-cache
MACs only resolve on the local segment, so remote hosts keep MAC null.
Results are compared against CMDB devices but never stored; jobs live in
process, a restart drops them.
"""

import ipaddress
import secrets
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from cmdb.api.auth import current_username
from cmdb.database import get_session
from cmdb.models import Device, utcnow
from cmdb.schemas import AgentInfo, DevicePush, MgmtInfo, OsInfo
from cmdb.services.audit import record_audit
from cmdb.services.ingest import ingest_push

router = APIRouter(tags=["scan"])

# Any open port makes a host alive; servers may expose only some of these
SCAN_PORTS = [22, 80, 443, 445, 3389, 8080]
PROBE_TIMEOUT = 0.5
# Sanity cap: a /16 at most, anything larger is a mistake
MAX_ADDRESSES = 65536
# Keep only the newest jobs: finished scans retain full host lists, unbounded growth leaks memory
MAX_JOBS = 50

# In-process job registry (single worker uvicorn; a restart drops running jobs)
_jobs: dict[str, dict] = {}


class ScanIn(BaseModel):
    cidr: str


class ScanAddIn(BaseModel):
    job_id: str
    ip: str
    hostname: str | None = None


def _probe_host(ip: str, ports: list[int]) -> bool:
    """TCP connect probe: a host is alive when any port connects"""
    for port in ports:
        try:
            with socket.create_connection((ip, port), timeout=PROBE_TIMEOUT):
                return True
        except OSError:
            continue
    return False


def _arp_cache() -> dict[str, str]:
    """Read the kernel ARP cache (populated by the probe); Flags 0x2 is complete"""
    entries: dict[str, str] = {}
    try:
        with open("/proc/net/arp") as f:
            lines = f.readlines()[1:]
    except OSError:
        return entries
    for line in lines:
        cols = line.split()
        if len(cols) < 4:
            continue
        ip, _hw, flags, mac = cols[:4]
        try:
            complete = int(flags, 0) & 0x2
        except ValueError:
            continue
        if complete and mac != "00:00:00:00:00:00":
            entries[ip] = mac
    return entries


def _reverse_dns(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return ""


def _device_ip_index() -> dict[str, tuple[int, str]]:
    """Map every device IP (mgmt + nic) to (device_id, hostname) for the comparison"""
    # Lazy import: resolved at call time, picks up the test monkeypatch
    from cmdb.database import get_engine_cached
    from cmdb.models import Device, Nic, NicIP
    from sqlmodel import Session, select

    with Session(get_engine_cached()) as session:
        index: dict[str, tuple[int, str]] = {}
        devices = {
            d.id: d.hostname for d in session.exec(select(Device)).all()
        }
        nics = {
            n.id: n.device_id for n in session.exec(select(Nic)).all()
        }
        for nic_ip in session.exec(select(NicIP)).all():
            hostname = devices.get(nics.get(nic_ip.nic_id))
            if hostname:
                index[nic_ip.ip] = (nics[nic_ip.nic_id], hostname)
        for device in session.exec(select(Device)).all():
            if device.mgmt_ip:
                index[device.mgmt_ip] = (device.id, device.hostname)
    return index


def _run_scan(job_id: str, cidr: str) -> None:
    """Scan worker: probe, resolve, compare against CMDB, write the job back"""
    job = _jobs[job_id]
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        if network.prefixlen == 32:
            targets = [str(network.network_address)]
        else:
            targets = [str(h) for h in network.hosts()]
        job["total"] = len(targets)

        alive: list[str] = []
        with ThreadPoolExecutor(max_workers=64) as pool:
            for ip, ok in pool.map(lambda ip: (ip, _probe_host(ip, SCAN_PORTS)), targets):
                job["scanned"] += 1
                if ok:
                    alive.append(ip)

        # The ARP cache is populated by the probe; reverse DNS may block on DNS, run it in a pool too
        arp = _arp_cache()

        def _fill(ip: str) -> dict:
            return {"ip": ip, "mac": arp.get(ip), "hostname": _reverse_dns(ip)}

        hosts = list(ThreadPoolExecutor(max_workers=32).map(_fill, alive))

        known = _device_ip_index()
        for host in hosts:
            hit = known.get(host["ip"])
            host["known"] = hit is not None
            host["device_id"], host["device_hostname"] = hit if hit else (None, None)

        job["hosts"] = hosts
        job["status"] = "done"
    # noqa: BLE001 - the job carries the failure to the poller
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@router.post("/scans")
def start_scan(body: ScanIn) -> dict:
    cidr = body.cidr.strip()
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid CIDR")
    if network.version != 4:
        # the probe pipeline is IPv4 only (TCP connect + ARP cache)
        raise HTTPException(status_code=422, detail="仅支持 IPv4 网段")
    if network.num_addresses > MAX_ADDRESSES:
        raise HTTPException(status_code=400, detail="网段过大, 最多扫描 65536 个地址")

    job_id = secrets.token_hex(8)
    while len(_jobs) >= MAX_JOBS:
        # dict preserves insertion order; evict the oldest job first
        _jobs.pop(next(iter(_jobs)))
    _jobs[job_id] = {
        "job_id": job_id,
        "cidr": cidr,
        "status": "running",
        "scanned": 0,
        "total": 0,
        "hosts": [],
        "error": None,
    }
    threading.Thread(target=_run_scan, args=(job_id, cidr), daemon=True).start()
    return {"job_id": job_id}


@router.get("/scans/{job_id}")
def get_scan(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return job


@router.post("/scans/add")
def add_scan_host(
    body: ScanAddIn, request: Request, session: Session = Depends(get_session)
) -> dict:
    """Add a scanned host to the CMDB as a device

    hostname falls back to the reverse-DNS name, then the IP itself. The push
    ingest path is reused, so an existing hostname lands in a pending diff
    instead of erroring, keeping the CMDB's conflict model
    """
    job = _jobs.get(body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="扫描任务不存在或已过期")
    host = next((h for h in job["hosts"] if h["ip"] == body.ip), None)
    if host is None:
        raise HTTPException(status_code=404, detail="该 IP 不在本次扫描结果中")
    if host.get("known"):
        raise HTTPException(status_code=409, detail="该主机已在 CMDB 中")
    hostname = (body.hostname or "").strip() or host.get("hostname") or body.ip
    push = DevicePush(
        agent=AgentInfo(source="scan"),
        os=OsInfo(hostname=hostname),
        mgmt=MgmtInfo(mac=host.get("mac"), ip=body.ip, prefix_length=None),
    )
    result = ingest_push(session, push, utcnow(), update_last_pushed=False)
    device = session.get(Device, result["device_id"])
    # Reflect the new membership in the in-memory result so the UI updates on repoll
    host["known"] = True
    host["device_id"] = result["device_id"]
    host["device_hostname"] = device.hostname if device else hostname
    record_audit(
        session, current_username(request), "扫描添加设备", f"{hostname} ({body.ip})"
    )
    session.commit()
    return result
