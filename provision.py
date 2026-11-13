#!/usr/bin/env python3
"""
provision.py — post-deploy provisioning for the vanilla CHR image.

Owner's model (2026-11-12): the Docker image ships PLAIN MikroTik CHR.
After a deployment boots, THIS script is thrown at it and applies:
  1. the branded default user (default: ramez / ramez, group full)
  2. the branding package (.dpk from MikroTik Branding Maker — ASCII
     terminal logo + defconfig) via /tool fetch from a one-shot HTTP
     server this script runs, then a reboot so the package installs
  3. disables the built-in admin account (LAST, after ramez is verified)

Pure stdlib (RouterOS API on 8728, modern + legacy login).
STATUS: draft for Friday — NOT yet run against a real router. Friday
checks: first API login on pristine CHR, /tool fetch reachability from
the guest to --serve-ip, package name after install, banner eyeball via
SSH/WinBox terminal (the API cannot display the ASCII logo).

Usage:
  python3 provision.py <host> --dpk branding.dpk \
      [--user ramez] [--password ramez] [--api-port 8728] \
      [--serve-ip 172.24.0.1] [--serve-port 18080]
--serve-ip is the address the GUEST uses to reach this host (with the
entrypoint bridge plan that is 172.24.0.1; on a plain Dokploy deploy use
the VPS address the guest can route to).
"""
import argparse, hashlib, http.server, socket, sys, threading, time

# ---------------- RouterOS API (stdlib) ----------------

def enc_len(n):
    if n < 0x80: return bytes([n])
    if n < 0x4000: return (n | 0x8000).to_bytes(2, "big")
    if n < 0x200000: return (n | 0xC00000).to_bytes(3, "big")
    if n < 0x10000000: return (n | 0xE0000000).to_bytes(4, "big")
    return b"\xf0" + n.to_bytes(4, "big")

class Api:
    def __init__(self, host, port=8728, timeout=10):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.buf = b""

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk: raise ConnectionError("API connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _read_len(self):
        b = self._read(1)[0]
        if b & 0x80 == 0: return b
        if b & 0xC0 == 0x80: return ((b & 0x3F) << 8) | self._read(1)[0]
        if b & 0xE0 == 0xC0:
            v = b & 0x1F
            for _ in range(2): v = (v << 8) | self._read(1)[0]
            return v
        if b & 0xF0 == 0xE0:
            v = b & 0x0F
            for _ in range(3): v = (v << 8) | self._read(1)[0]
            return v
        return int.from_bytes(self._read(4), "big")

    def _read_word(self):
        n = self._read_len()
        return self._read(n).decode("utf-8", "replace") if n else ""

    def read_sentence(self):
        words = []
        while True:
            w = self._read_word()
            if w == "": return words
            words.append(w)

    def talk(self, words):
        """Send one sentence; return list of reply dicts (!re rows)."""
        for w in words:
            data = w.encode()
            self.sock.sendall(enc_len(len(data)) + data)
        self.sock.sendall(b"\x00")
        rows, attrs = [], {}
        while True:
            s = self.read_sentence()
            if not s: continue
            kind, rest = s[0], s[1:]
            row = dict(p[1:].split("=", 1) for p in rest if p.startswith("=") and "=" in p[1:])
            if kind == "!re": rows.append(row)
            elif kind == "!done": rows.append(row) if row else None; return rows
            elif kind in ("!trap", "!fatal"):
                raise RuntimeError(f"{words[0]} -> {row.get('message', kind)}")

    def login(self, user, password):
        r = self.talk(["/login", f"=name={user}", f"=password={password}"])
        ret = r[0].get("ret") if r else None
        if ret:  # legacy MD5 challenge login
            digest = hashlib.md5(b"\x00" + password.encode() + bytes.fromhex(ret)).hexdigest()
            self.talk(["/login", f"=name={user}", f"=response=00{digest}"])
        return self

def wait_api(host, port, seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            return Api(host, port).login("admin", "")
        except Exception:
            time.sleep(3)
    raise SystemExit(f"RouterOS API on {host}:{port} never came up")

# ---------------- provisioning ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("--api-port", type=int, default=8728)
    ap.add_argument("--user", default="ramez")
    ap.add_argument("--password", default="ramez")
    ap.add_argument("--dpk", required=True, help="branding .dpk from MikroTik Branding Maker")
    ap.add_argument("--serve-ip", default="172.24.0.1")
    ap.add_argument("--serve-port", type=int, default=18080)
    a = ap.parse_args()

    dpk_bytes = open(a.dpk, "rb").read()
    print(f"[1/6] Waiting for a pristine CHR at {a.host}:{a.api_port} ...")
    admin = wait_api(a.host, a.api_port)
    print("      Logged in as admin (blank password) — vanilla image confirmed.")

    print(f"[2/6] Creating user {a.user} (group full) ...")
    try:
        admin.talk(["/user/add", f"=name={a.user}", "=group=full", f"=password={a.password}",
                    "=comment=branding default admin"])
    except RuntimeError as e:
        if "already" not in str(e): raise
        rows = admin.talk(["/user/print"])
        uid = next(r[".id"] for r in rows if r.get("name") == a.user)
        admin.talk(["/user/set", f"=numbers={uid}", "=group=full", f"=password={a.password}"])
    print("      User ready.")

    print("[3/6] Verifying the new login works ...")
    Api(a.host, a.api_port).login(a.user, a.password)
    print(f"      Login as {a.user} OK.")

    print("[4/6] Serving the branding package and fetching it on the router ...")
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(dpk_bytes)))
            self.end_headers()
            self.wfile.write(dpk_bytes)
        def log_message(self, *x): pass
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", a.serve_port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://{a.serve_ip}:{a.serve_port}/branding.dpk"
    try:
        admin.talk(["/tool/fetch", f"=url={url}", "=dst-path=branding.dpk"])
    except RuntimeError as e:
        print(f"      fetch returned: {e} (checking the file anyway)")
    ok = False
    for _ in range(20):
        rows = admin.talk(["/file/print"])
        f = next((r for r in rows if r.get("name") == "branding.dpk"), None)
        if f and int(f.get("size", 0)) == len(dpk_bytes): ok = True; break
        time.sleep(3)
    srv.shutdown()
    if not ok:
        raise SystemExit("branding.dpk did not land on the router intact — "
                         "check --serve-ip reachability from the guest (Friday checklist).")
    print(f"      branding.dpk on the router ({len(dpk_bytes)} bytes, verified by size).")

    print("[5/6] Rebooting so the branding package installs ...")
    try: admin.talk(["/system/reboot"])
    except Exception: pass  # connection drops on reboot — expected
    time.sleep(10)
    user_api = None
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            user_api = Api(a.host, a.api_port).login(a.user, a.password); break
        except Exception: time.sleep(5)
    if not user_api: raise SystemExit("Router did not come back / ramez login failed after reboot.")
    pkgs = user_api.talk(["/system/package/print"])
    print("      Packages now:", ", ".join(p.get("name", "?") for p in pkgs))

    print("[6/6] Disabling the built-in admin account ...")
    rows = user_api.talk(["/user/print"])
    adm = next(r for r in rows if r.get("name") == "admin")
    user_api.talk(["/user/set", f"=numbers={adm['.id']}", "=disabled=yes"])
    rows = user_api.talk(["/user/print"])
    for r in rows:
        print(f"      user: {r.get('name')} group={r.get('group')} disabled={r.get('disabled')}")
    print("DONE. Eyeball the ASCII banner once via SSH/WinBox terminal to confirm the logo.")

if __name__ == "__main__":
    main()
