"""
pcap_network_features.py
========================
Extract per-time-window NETWORK features from SWaT/WADI packet captures (.pcap),
aligned to the 1-second process timeline, ready to fuse with the sensor CSVs.

WHY THIS EXISTS
---------------
The anomaly-detection notebook currently uses process/sensor data only. The
platform's design also calls for NETWORK features (Modbus/TCP). The real packet
captures ship with the official SWaT/WADI release from iTrust. This script turns
those .pcap files into a tidy per-second feature table you can merge with the
sensor data on the timestamp column. It uses ONLY the real captures — nothing is
synthesised.

WHAT IT PRODUCES
----------------
A CSV with one row per time bucket (default 1 second) and columns:
    timestamp            bucket start time (UTC)
    pkt_count            packets in the bucket
    byte_count           total bytes
    pkt_rate             packets / second (== pkt_count for 1 s buckets)
    mean_iat, std_iat    inter-arrival time stats (seconds) within the bucket
    n_src_ip, n_dst_ip   unique source / destination IPs
    n_conn               unique (src_ip, dst_ip, dst_port) tuples
    modbus_pkts          packets on Modbus/TCP port (default 502)
    n_func_codes         distinct Modbus function codes seen
    write_pkts           Modbus write-type function codes (5,6,15,16,22,23)
    exception_pkts       Modbus exception responses (function code >= 0x80)
These are standard, well-motivated ICS network features (rate/volume, timing,
topology, and Modbus command semantics) that complement the process view.

USAGE
-----
    pip install scapy pandas numpy
    python pcap_network_features.py --pcap-dir ./SWaT_network --out network_features.csv
    # optional: --bucket 1.0  --modbus-port 502  --limit 0 (0 = all packets)

Then, in the notebook, merge onto the process frame by timestamp (nearest / floor
to the second) and feed the network columns as the second branch of the fusion
model.

NOTE ON DEPENDENCIES
--------------------
scapy reads .pcap natively. For very large captures, prefer running per-file and
concatenating the CSVs, or pre-filter with tshark/editcap. This script streams
packets (PcapReader) so memory stays flat regardless of file size.
"""

import os
import glob
import argparse
from collections import defaultdict

import numpy as np
import pandas as pd

MODBUS_WRITE_FCS = {5, 6, 15, 16, 22, 23}   # write single/multiple coils & registers, mask/rw


def _iter_packets(pcap_path, limit=0):
    """Yield scapy packets from a pcap, streaming (constant memory)."""
    from scapy.all import PcapReader
    n = 0
    with PcapReader(pcap_path) as reader:
        for pkt in reader:
            yield pkt
            n += 1
            if limit and n >= limit:
                break


def _packet_fields(pkt, modbus_port):
    """Extract the fields we need from one packet; return a dict or None if not IP."""
    from scapy.all import IP, TCP
    if IP not in pkt:
        return None
    ip = pkt[IP]
    rec = {
        "time": float(pkt.time),
        "length": int(len(pkt)),
        "src": ip.src,
        "dst": ip.dst,
        "dport": None,
        "is_modbus": False,
        "func_code": None,
        "is_exception": False,
    }
    if TCP in pkt:
        tcp = pkt[TCP]
        rec["dport"] = int(tcp.dport)
        if modbus_port in (int(tcp.dport), int(tcp.sport)):
            rec["is_modbus"] = True
            # Modbus/TCP: 7-byte MBAP header then 1-byte function code
            payload = bytes(tcp.payload)
            if len(payload) >= 8:
                fc = payload[7]
                rec["func_code"] = int(fc)
                rec["is_exception"] = bool(fc & 0x80)
    return rec


def extract_features(pcap_dir, out_csv, bucket=1.0, modbus_port=502, limit=0):
    files = sorted(glob.glob(os.path.join(pcap_dir, "*.pcap")) +
                   glob.glob(os.path.join(pcap_dir, "*.pcapng")))
    if not files:
        raise FileNotFoundError(f"No .pcap/.pcapng files in {pcap_dir}")
    print("Found capture files:", [os.path.basename(f) for f in files])

    # accumulate per-bucket aggregates without holding all packets in memory
    buckets = defaultdict(lambda: {
        "pkt": 0, "bytes": 0, "times": [], "src": set(), "dst": set(),
        "conn": set(), "modbus": 0, "funcs": set(), "write": 0, "exc": 0,
    })

    total = 0
    for f in files:
        print("Processing", os.path.basename(f), "...")
        for pkt in _iter_packets(f, limit):
            rec = _packet_fields(pkt, modbus_port)
            if rec is None:
                continue
            total += 1
            key = int(rec["time"] // bucket)          # bucket index
            b = buckets[key]
            b["pkt"] += 1
            b["bytes"] += rec["length"]
            b["times"].append(rec["time"])
            b["src"].add(rec["src"]); b["dst"].add(rec["dst"])
            b["conn"].add((rec["src"], rec["dst"], rec["dport"]))
            if rec["is_modbus"]:
                b["modbus"] += 1
                if rec["func_code"] is not None:
                    b["funcs"].add(rec["func_code"])
                    if rec["func_code"] in MODBUS_WRITE_FCS:
                        b["write"] += 1
                if rec["is_exception"]:
                    b["exc"] += 1

    print(f"Parsed {total} IP packets into {len(buckets)} time buckets")

    rows = []
    for key in sorted(buckets):
        b = buckets[key]
        t = np.sort(np.asarray(b["times"]))
        iat = np.diff(t) if len(t) > 1 else np.array([0.0])
        rows.append({
            "timestamp": pd.to_datetime(key * bucket, unit="s", utc=True),
            "pkt_count": b["pkt"],
            "byte_count": b["bytes"],
            "pkt_rate": b["pkt"] / bucket,
            "mean_iat": float(iat.mean()),
            "std_iat": float(iat.std()),
            "n_src_ip": len(b["src"]),
            "n_dst_ip": len(b["dst"]),
            "n_conn": len(b["conn"]),
            "modbus_pkts": b["modbus"],
            "n_func_codes": len(b["funcs"]),
            "write_pkts": b["write"],
            "exception_pkts": b["exc"],
        })

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df.to_csv(out_csv, index=False)
    print(f"Wrote {len(df)} rows x {df.shape[1]} columns -> {out_csv}")
    print("\nColumn preview:")
    print(df.head().to_string(index=False))
    return df


def main():
    ap = argparse.ArgumentParser(description="Extract per-second network features from SWaT/WADI pcap.")
    ap.add_argument("--pcap-dir", required=True, help="Folder containing .pcap/.pcapng files")
    ap.add_argument("--out", default="network_features.csv", help="Output CSV path")
    ap.add_argument("--bucket", type=float, default=1.0, help="Time bucket in seconds (match process rate)")
    ap.add_argument("--modbus-port", type=int, default=502, help="Modbus/TCP port")
    ap.add_argument("--limit", type=int, default=0, help="Max packets per file (0 = all)")
    args = ap.parse_args()
    extract_features(args.pcap_dir, args.out, args.bucket, args.modbus_port, args.limit)


if __name__ == "__main__":
    main()
