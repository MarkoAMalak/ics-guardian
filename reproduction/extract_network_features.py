"""
extract_network_features.py  —  SWaT.A6 (Dec 2019) network feature extractor
============================================================================
Pure-Python pcap parser (NO scapy / tshark / pip installs needed — just python3).
Turns the 15 Dec2019 pcap files into a per-second NETWORK feature table, labelled
with the A6 attack schedule, ready to fuse with the process CSV (Dec2019.xlsx).

WHY PURE PYTHON: the target machine has python3 + tcpdump but no scapy/tshark and
no network to install them. This script parses the raw pcap/Ethernet/IP/TCP/Modbus
bytes directly with `struct`, streaming, so memory stays flat on multi-GB files.

ATTACK SCHEDULE (from the dataset Log.docx, 6 Dec 2019, local time GMT+8):
  Attack 1 - Exfiltrate Historian Data (NETWORK attack):
      10:30-10:35, 10:45-10:50, 11:00-11:05, 11:15-11:20
  Attack 2 - Disrupt Sensor & Actuator (PROCESS attack):
      12:30-12:33, 12:43-12:46, 12:56-12:59, 13:09-13:12, 13:22-13:25
Pre-attack pcap = file 00; post-attack pcap = file 14.

NOTE: SWaT PLCs use EtherNet/IP (CIP) on TCP 44818 / UDP 2222 (not Modbus). The
`ics_pkts` column counts traffic on those ICS ports; generic volume/timing/topology
features carry most of the anomaly signal (e.g. the exfiltration attack shows up as
byte-volume and new-connection spikes).

OUTPUT columns (one row per 1-second bucket):
  timestamp_utc, pkt_count, byte_count, pkt_rate, mean_iat, std_iat,
  n_src_ip, n_dst_ip, n_conn, n_dst_ports, ics_pkts, non_ics_pkts,
  label (0/1), attack (none|exfiltration|disruption)

USAGE
  python3 extract_network_features.py --pcap-dir "SWaT.A6_Dec 2019/pcap" \
      --out network_features_A6.csv
  # quick validation on one file, first 200k packets:
  python3 extract_network_features.py --pcap-dir "SWaT.A6_Dec 2019/pcap" \
      --out sample.csv --only Dec2019_00000_20191206100500.pcap --limit 200000
"""

import os, glob, struct, argparse, datetime
from collections import defaultdict

# SWaT PLCs speak EtherNet/IP (CIP): TCP 44818 + UDP 2222 (I/O). 502 kept for Modbus plants.
ICS_PORTS = {44818, 2222, 502}
TZ = datetime.timezone(datetime.timedelta(hours=8))   # dataset local time GMT+8

def _win(h1, m1, h2, m2):
    d = datetime.datetime(2019, 12, 6, h1, m1, tzinfo=TZ)
    e = datetime.datetime(2019, 12, 6, h2, m2, tzinfo=TZ)
    return (d.timestamp(), e.timestamp())

ATTACKS = (
    [("exfiltration", *_win(10,30,10,35)), ("exfiltration", *_win(10,45,10,50)),
     ("exfiltration", *_win(11,0,11,5)),   ("exfiltration", *_win(11,15,11,20))] +
    [("disruption", *_win(12,30,12,33)), ("disruption", *_win(12,43,12,46)),
     ("disruption", *_win(12,56,12,59)), ("disruption", *_win(13,9,13,12)),
     ("disruption", *_win(13,22,13,25))]
)

def label_for(ts):
    for name, s, e in ATTACKS:
        if s <= ts < e:
            return 1, name
    return 0, "none"

# ----------------------- pure-python pcap parser -----------------------
def iter_pcap(path, limit=0):
    """Yield (ts, wire_len, src_ip, dst_ip, dport, is_ics)."""
    with open(path, "rb") as f:
        gh = f.read(24)
        if len(gh) < 24:
            return
        magic = gh[:4]
        if magic == b"\xd4\xc3\xb2\xa1":      # little-endian, microseconds
            endian, usec = "<", True
        elif magic == b"\xa1\xb2\xc3\xd4":     # big-endian, microseconds
            endian, usec = ">", True
        elif magic == b"\x4d\x3c\xb2\xa1":     # little-endian, nanoseconds
            endian, usec = "<", False
        elif magic == b"\xa1\xb2\x3c\x4d":
            endian, usec = ">", False
        else:
            raise ValueError(f"Not a classic pcap file: magic={magic!r}")
        linktype = struct.unpack(endian + "I", gh[20:24])[0]
        rec = struct.Struct(endian + "IIII")
        n = 0
        while True:
            hdr = f.read(16)
            if len(hdr) < 16:
                break
            ts_sec, ts_frac, incl, orig = rec.unpack(hdr)
            data = f.read(incl)
            if len(data) < incl:
                break
            ts = ts_sec + (ts_frac / 1e6 if usec else ts_frac / 1e9)
            out = _parse_frame(data, linktype, orig)
            if out is not None:
                yield (ts, *out)
            n += 1
            if limit and n >= limit:
                break

def _parse_frame(data, linktype, wire_len):
    off = 0
    if linktype == 1:                 # Ethernet
        if len(data) < 14:
            return None
        etype = int.from_bytes(data[12:14], "big")
        off = 14
        while etype == 0x8100 and len(data) >= off + 4:   # VLAN tag(s)
            etype = int.from_bytes(data[off+2:off+4], "big")
            off += 4
        if etype != 0x0800:            # not IPv4
            return None
    elif linktype == 101:              # raw IP
        pass
    else:
        return None
    if len(data) < off + 20:
        return None
    vihl = data[off]
    if (vihl >> 4) != 4:
        return None
    ihl = (vihl & 0x0f) * 4
    proto = data[off + 9]
    src = ".".join(str(b) for b in data[off+12:off+16])
    dst = ".".join(str(b) for b in data[off+16:off+20])
    dport = None; is_ics = False
    if proto == 6:                     # TCP
        t = off + ihl
        if len(data) >= t + 4:
            sport = int.from_bytes(data[t:t+2], "big")
            dport = int.from_bytes(data[t+2:t+4], "big")
            is_ics = (sport in ICS_PORTS or dport in ICS_PORTS)
    elif proto == 17:                  # UDP (EtherNet/IP I/O on 2222)
        t = off + ihl
        if len(data) >= t + 4:
            sport = int.from_bytes(data[t:t+2], "big")
            dport = int.from_bytes(data[t+2:t+4], "big")
            is_ics = (sport in ICS_PORTS or dport in ICS_PORTS)
    return (wire_len, src, dst, dport, is_ics)

# ----------------------- aggregation -----------------------
def extract(pcap_dir, out_csv, only=None, limit=0, bucket=1.0):
    files = sorted(glob.glob(os.path.join(pcap_dir, "Dec2019_*")))
    files = [f for f in files if not f.endswith(".txt") and "README" not in f]
    if only:
        files = [f for f in files if os.path.basename(f) == only]
    if not files:
        raise FileNotFoundError(f"No pcap files in {pcap_dir}")
    print("Files:", [os.path.basename(f) for f in files])

    buckets = defaultdict(lambda: {"pkt":0,"bytes":0,"times":[],"src":set(),"dst":set(),
                                    "conn":set(),"ics":0,"dports":set()})
    total = 0
    for f in files:
        print("  parsing", os.path.basename(f), "...", flush=True)
        for (ts, wlen, src, dst, dport, is_ics) in iter_pcap(f, limit):
            total += 1
            k = int(ts // bucket)
            b = buckets[k]
            b["pkt"] += 1; b["bytes"] += wlen; b["times"].append(ts)
            b["src"].add(src); b["dst"].add(dst); b["conn"].add((src, dst, dport))
            if dport is not None: b["dports"].add(dport)
            if is_ics: b["ics"] += 1
    print(f"Parsed {total} IPv4 packets into {len(buckets)} one-second buckets")

    import csv
    cols = ["timestamp_utc","pkt_count","byte_count","pkt_rate","mean_iat","std_iat",
            "n_src_ip","n_dst_ip","n_conn","n_dst_ports","ics_pkts","non_ics_pkts",
            "label","attack"]
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(cols)
        for k in sorted(buckets):
            b = buckets[k]
            t = sorted(b["times"])
            iat = [t[i+1]-t[i] for i in range(len(t)-1)] or [0.0]
            mean_iat = sum(iat)/len(iat)
            var = sum((x-mean_iat)**2 for x in iat)/len(iat)
            lab, atk = label_for(k*bucket)
            w.writerow([
                datetime.datetime.fromtimestamp(k*bucket, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                b["pkt"], b["bytes"], b["pkt"]/bucket, round(mean_iat,6), round(var**0.5,6),
                len(b["src"]), len(b["dst"]), len(b["conn"]), len(b["dports"]),
                b["ics"], b["pkt"]-b["ics"], lab, atk,
            ])
    print(f"Wrote {len(buckets)} rows -> {out_csv}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap-dir", required=True)
    ap.add_argument("--out", default="network_features_A6.csv")
    ap.add_argument("--only", default=None, help="process a single file by name")
    ap.add_argument("--limit", type=int, default=0, help="max packets per file (0=all)")
    args = ap.parse_args()
    extract(args.pcap_dir, args.out, args.only, args.limit)

if __name__ == "__main__":
    main()
