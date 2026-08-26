"""
Infra fingerprint matcher for the PS 26151 prototype.

Fetches the SSL certificate fingerprint from:
  (a) the hidden service, via Tor  -> nginx-hidden's :443
  (b) a clearnet infrastructure record -> nginx-clearnet's :443 (exposed
      on localhost:8443 by docker-compose, standing in for a real-world
      Shodan/Censys/crt.sh lookup in production)

...and reports whether they match, i.e. whether the hidden service can
be correlated to real-world clearnet infrastructure.

USAGE:
  python match_infra.py --onion <your-onion-address>.onion
"""
import argparse
import socket
import ssl
import hashlib
import sqlite3
import os
import socks  # from PySocks, installed via requests[socks]

# Path to the shared database
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "scraper", "darkweb_intel.db")


def get_cert_fingerprint_via_tor(onion_host, port=443):
    """Fetch the TLS cert fingerprint from a hidden service over Tor."""
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, "127.0.0.1", 9050)
    s.connect((onion_host, port))

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    wrapped = ctx.wrap_socket(s, server_hostname=onion_host)
    der_cert = wrapped.getpeercert(binary_form=True)
    wrapped.close()
    return hashlib.sha256(der_cert).hexdigest()


def get_cert_fingerprint_clearnet(host, port=8443):
    """Fetch the TLS cert fingerprint from a normal (clearnet) endpoint."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with socket.create_connection((host, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as wrapped:
            der_cert = wrapped.getpeercert(binary_form=True)
    return hashlib.sha256(der_cert).hexdigest()


def save_match_to_db(onion_address, clearnet_host, confidence_score=98):
    """Write the infra match result into the infra_links table."""
    if not os.path.exists(DB_PATH):
        print(f"[!] Database not found at {DB_PATH} — skipping DB write.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check if infra_links table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='infra_links'")
    if not cur.fetchone():
        print("[!] infra_links table not found. Run db_setup.py first — skipping DB write.")
        conn.close()
        return

    cur.execute("""
        INSERT INTO infra_links (onion_address, clearnet_host, evidence, confidence_score)
        VALUES (?, ?, ?, ?)
    """, (
        onion_address,
        clearnet_host,
        "SSL certificate SHA-256 fingerprint match — hidden service and clearnet endpoint share identical certificate",
        confidence_score
    ))

    conn.commit()
    conn.close()
    print(f"[+] Match result saved to database ({DB_PATH})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--onion", required=True, help="vulnerable hidden service .onion address")
    parser.add_argument("--clearnet-host", default="localhost", help="clearnet host to compare against")
    parser.add_argument("--clearnet-port", type=int, default=8443)
    args = parser.parse_args()

    print(f"[*] Fetching cert fingerprint from hidden service via Tor: {args.onion}")
    hidden_fp = get_cert_fingerprint_via_tor(args.onion)
    print(f"    -> {hidden_fp}")

    print(f"[*] Fetching cert fingerprint from clearnet record: {args.clearnet_host}:{args.clearnet_port}")
    clearnet_fp = get_cert_fingerprint_clearnet(args.clearnet_host, args.clearnet_port)
    print(f"    -> {clearnet_fp}")

    print()
    if hidden_fp == clearnet_fp:
        print("[MATCH] Hidden service certificate matches known clearnet infrastructure.")
        print("        -> Likely origin: TechCorp Cloud Solutions (techcorp-cloud.example)")
        print("        -> Confidence: HIGH (exact certificate fingerprint match)")

        # Save to database
        clearnet_label = f"{args.clearnet_host}:{args.clearnet_port} (TechCorp Cloud Solutions)"
        save_match_to_db(args.onion, clearnet_label)
    else:
        print("[NO MATCH] No correlation found between this hidden service and the clearnet record checked.")

