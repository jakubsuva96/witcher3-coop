# Checks the LAN stage 1 features without the game:
#   server: version handshake (HELLO/WELCOME, mod and game mismatches, clients without HELLO dropped), LAN discovery,
#   usernames taken from another address, stale co-op channels dropped, crash report uploads (LAN only, safe names);
#   server with --lan: the host announced (WELCOME and HOST), state sent about 30 times a second, the host's newest
#   save handed over, the save port in the discovery answer;
#   package\lan-join.ps1 against that server: host found, save fetched, co-op profile and config.xml written;
#   client: crash.cpp through crash_harness.exe (a crash report, a "no clean exit" report, sending both to the server),
#   profile.cpp through profile_harness.exe (Documents redirected to the co-op profile).
# Usage: lan_stage1_test.py --jar WitcherServer.jar [--harness crash_harness.exe] [--profile-harness profile_harness.exe]
#                           [--port 41910]
import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

PROTOCOL, MOD_VERSION = "1", "0.3.0-dev"
GAME = "5.0.15.65482"

failures = []
passed = []


def check(name, ok, detail=""):
    (passed if ok else failures).append(name if ok else f"{name}: {detail}")
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" ({detail})"), flush=True)


def client(port, source="127.0.0.1"):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((source, 0))
    s.connect(("127.0.0.1", port))
    s.settimeout(0.2)
    return s


def send(s, *fields):
    s.send("\t".join(fields).encode())


def wait_for(s, prefix, seconds):
    """First packet starting with `prefix` within `seconds`, as fields, or None."""
    end = time.time() + seconds
    while time.time() < end:
        try:
            parts = s.recv(8192).decode().split("\t")
        except (socket.timeout, ConnectionResetError):
            continue
        if parts[0] == prefix:
            return parts
    return None


def coop_channels(s, who, seconds):
    seen = set()
    end = time.time() + seconds
    while time.time() < end:
        try:
            parts = s.recv(8192).decode().split("\t")
        except (socket.timeout, ConnectionResetError):
            continue
        if parts[0] == "COOP" and len(parts) >= 4 and parts[2] == who:
            seen.add(parts[3])
    return seen


def server_tests(port, crash_port, server_dir):
    # handshake accepted, with the crash report port
    a = client(port)
    send(a, "HELLO", "Alice", PROTOCOL, MOD_VERSION, GAME)
    w = wait_for(a, "WELCOME", 2)
    check("handshake: WELCOME with version and crash port", w is not None and w[1:4] == [MOD_VERSION, PROTOCOL, str(crash_port)], w)
    send(a, "COOP", "Alice", "en", "1")

    # another W3Coop build
    b = client(port)
    send(b, "HELLO", "Bob", PROTOCOL, "0.2.0", GAME)
    e = wait_for(b, "ERROR", 2)
    check("handshake: other W3Coop build refused", e is not None and e[1:3] == ["VERSION_MISMATCH", MOD_VERSION], e)

    # another game build than a player already in
    c = client(port)
    send(c, "HELLO", "Carol", PROTOCOL, MOD_VERSION, "4.0.4.0")
    e = wait_for(c, "ERROR", 2)
    check("handshake: other game build refused", e is not None and e[1:3] == ["GAME_VERSION_MISMATCH", GAME], e)

    # a client without HELLO (W3Coop 0.2.0 and older) is told and dropped after the grace period
    d = client(port)
    t0 = time.time()
    got = None
    while time.time() - t0 < 9 and got is None:
        send(d, "COOP", "Dave", "hit", "x")
        got = wait_for(d, "ERROR", 0.5)
    check("handshake: client without HELLO dropped", got is not None and got[1] == "VERSION_MISMATCH", got)

    # LAN discovery: the answer comes straight back to the asker
    q = client(port)
    send(q, "DISCOVER", "W3COOP", PROTOCOL)
    h = wait_for(q, "W3COOP_HOST", 2)
    check("discovery: host answers", h is not None and h[1:4] == [PROTOCOL, MOD_VERSION, str(port)], h)

    # the same, broadcast as the game does it (needs a network adapter that takes broadcasts; informational)
    bc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bc.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    bc.bind(("0.0.0.0", 0))
    bc.settimeout(0.3)
    found = None
    for _ in range(4):
        bc.sendto(f"DISCOVER\tW3COOP\t{PROTOCOL}".encode(), ("255.255.255.255", port))
        try:
            data, addr = bc.recvfrom(1024)
            if data.decode().startswith("W3COOP_HOST"):
                found = addr
                break
        except (socket.timeout, ConnectionResetError):
            pass
    print(("PASS " if found else "INFO ") + f"discovery by broadcast: {'answered from ' + found[0] if found else 'no answer on this machine'}", flush=True)
    if found:
        passed.append("discovery by broadcast")

    # a name in use from another address (another PC) is refused, so the client can pick another one
    try:
        other = client(port, "127.0.0.2")
        send(other, "HELLO", "Alice", PROTOCOL, MOD_VERSION, GAME)
        e = wait_for(other, "ERROR", 2)
        check("names: a name in use from another PC is refused", e is not None and e[1] == "USERNAME_TAKEN", e)
        send(other, "HELLO", "Alice2", PROTOCOL, MOD_VERSION, GAME)
        w = wait_for(other, "WELCOME", 2)
        check("names: the renamed player is accepted", w is not None, w)
    except OSError as err:
        print(f"INFO names test skipped: cannot send from 127.0.0.2 ({err})")

    # a channel the player stopped sending is dropped after 10 s; a channel still sent stays
    obs = client(port)
    send(obs, "HELLO", "Obs", PROTOCOL, MOD_VERSION, GAME)
    wait_for(obs, "WELCOME", 2)
    send(a, "COOP", "Alice", "en", "2")
    end = time.time() + 11.5
    while time.time() < end:
        send(a, "COOP", "Alice", "hit", str(int(time.time() * 10)))
        send(obs, "COOP", "Obs", "jr", "1")
        time.sleep(0.5)
    coop_channels(obs, "Alice", 0.5)  # what queued up during the wait, 'en' from its first seconds included
    seen = coop_channels(obs, "Alice", 1.0)
    check("channels: stale channel dropped, live one kept", "hit" in seen and "en" not in seen, seen)

    # crash report endpoint
    url = f"http://127.0.0.1:{crash_port}/crash?user=Tester&report=r1&file=..%2F..%2Fevil.txt"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=b"hello", method="POST"), timeout=5) as r:
            status = r.status
    except urllib.error.HTTPError as err:
        status = err.code
    saved = os.path.join(server_dir, "crash-reports", "Tester", "r1")
    names = os.listdir(saved) if os.path.isdir(saved) else []
    escaped = os.path.exists(os.path.join(server_dir, "evil.txt")) or os.path.exists(os.path.join(server_dir, "crash-reports", "evil.txt"))
    check("crash reports: upload saved inside crash-reports with a safe name", status == 200 and len(names) == 1 and not escaped, (status, names, escaped))
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{crash_port}/crash", timeout=5)
        status = 200
    except urllib.error.HTTPError as err:
        status = err.code
    check("crash reports: GET refused", status == 405, status)


def harness_tests(harness, port, crash_port, server_dir, work):
    wo = os.path.join(work, "WitcherOnline")
    reports = os.path.join(wo, "crash-reports")

    subprocess.run([harness, "crash", wo], capture_output=True, timeout=60)
    crash_dirs = [d for d in os.listdir(reports) if d.endswith("-crash")] if os.path.isdir(reports) else []
    ok = len(crash_dirs) == 1
    if ok:
        d = os.path.join(reports, crash_dirs[0])
        files = set(os.listdir(d))
        report = open(os.path.join(d, "report.txt"), encoding="utf-8", errors="replace").read()
        ok = {"report.txt", "crash.dmp", "WitcherOnline.log"} <= files and "exception 0xC0000005" in report and os.path.getsize(os.path.join(d, "crash.dmp")) > 0
        check("crash: report with minidump, exception and log", ok, (files, report[:200]))
    else:
        check("crash: report with minidump, exception and log", False, crash_dirs)
    check("crash: no second report for the crashed session", not [d for d in os.listdir(reports) if d.endswith("-no-clean-exit")])

    subprocess.run([harness, "killed", wo], capture_output=True, timeout=60)
    subprocess.run([harness, "upload", wo, "127.0.0.1", str(crash_port)], capture_output=True, timeout=60)
    unclean = [d for d in os.listdir(reports) if d.endswith("-no-clean-exit")]
    check("killed: the next start files a no-clean-exit report", len(unclean) == 1, os.listdir(reports))
    if unclean:
        text = open(os.path.join(reports, unclean[0], "report.txt"), encoding="utf-8", errors="replace").read()
        log = os.path.join(reports, unclean[0], "WitcherOnline.log")
        check("killed: report has the previous session and its log", "HarnessPlayer" in text and os.path.exists(log) and "mode killed" in open(log).read(), text[:200])

    sent = [d for d in os.listdir(reports) if os.path.exists(os.path.join(reports, d, "sent.txt"))]
    check("upload: every report marked sent", sorted(sent) == sorted(os.listdir(reports)), (sent, os.listdir(reports)))
    received = os.path.join(server_dir, "crash-reports", "HarnessPlayer")
    got = sorted(os.listdir(received)) if os.path.isdir(received) else []
    check("upload: the host received both reports", sorted(got) == sorted(os.listdir(reports)), got)
    if crash_dirs and crash_dirs[0] in got:
        check("upload: minidump arrived complete",
              os.path.getsize(os.path.join(received, crash_dirs[0], "crash.dmp")) == os.path.getsize(os.path.join(reports, crash_dirs[0], "crash.dmp")))

    subprocess.run([harness, "clean", wo], capture_output=True, timeout=60)
    subprocess.run([harness, "clean", wo], capture_output=True, timeout=60)
    check("clean exit: no new report", len([d for d in os.listdir(reports) if d.endswith("-no-clean-exit")]) == 1, os.listdir(reports))


def updates_per_second(s, seconds):
    """How many UPDATE1A packets arrive per second (the server repeats each player's state on every tick)."""
    count = 0
    end = time.time() + seconds
    while time.time() < end:
        try:
            if s.recv(8192).decode().startswith("UPDATE1A\t"):
                count += 1
        except (socket.timeout, ConnectionResetError):
            pass
    return count / seconds


def normal_server_lan_checks(port):
    # without --lan: no host is named, and state goes out about 10 times a second
    a = client(port)
    send(a, "HELLO", "Norm", PROTOCOL, MOD_VERSION, GAME)
    w = wait_for(a, "WELCOME", 2)
    check("normal server: no LAN host named", w is not None and (len(w) < 5 or w[4] == ""), w)
    send(a, "UPDATE1A", "Norm", "x")
    rate = updates_per_second(a, 3)
    check("normal server: state about 10 times a second", 7 <= rate <= 12, rate)


def lan_server_tests(port, crash_port, saves_dir, lan_join, work):
    # the game on the server's PC (loopback) is the host; the other player hears it in WELCOME and in HOST
    host = client(port)
    send(host, "HELLO", "Geralt", PROTOCOL, MOD_VERSION, GAME)
    w = wait_for(host, "WELCOME", 2)
    check("--lan: the local player is the host", w is not None and len(w) >= 5 and w[4] == "Geralt", w)
    send(host, "UPDATE1A", "Geralt", "x")

    try:
        member = client(port, "127.0.0.2")
        send(member, "HELLO", "Yennefer", PROTOCOL, MOD_VERSION, GAME)
        w = wait_for(member, "WELCOME", 2)
        check("--lan: the member hears who hosts (WELCOME)", w is not None and len(w) >= 5 and w[4] == "Geralt", w)
        # a member in game sends its state all the time, which makes it one of the server's recipients
        send(member, "UPDATE1A", "Yennefer", "x")
        h = wait_for(member, "HOST", 4)
        check("--lan: HOST repeated for the member", h is not None and h[1] == "Geralt", h)
    except OSError as err:
        print(f"INFO member checks skipped: cannot send from 127.0.0.2 ({err})")

    # a fresh listener, so nothing queued up earlier is counted; it hears the host's state only
    listener = client(port)
    send(listener, "HELLO", "Listener", PROTOCOL, MOD_VERSION, GAME)
    wait_for(listener, "WELCOME", 2)
    # both keep sending as games do (a player silent for 5 s times out)
    send(host, "UPDATE1A", "Geralt", "x")
    send(listener, "UPDATE1A", "Listener", "x")
    time.sleep(0.3)
    while True:
        try:
            listener.recv(8192)
        except (socket.timeout, ConnectionResetError):
            break
    seen = {}
    end = time.time() + 3
    next_keepalive = time.time() + 1
    while time.time() < end:
        if time.time() >= next_keepalive:
            send(host, "UPDATE1A", "Geralt", "x")
            send(listener, "UPDATE1A", "Listener", "x")
            next_keepalive += 1
        try:
            parts = listener.recv(8192).decode().split("\t")
        except (socket.timeout, ConnectionResetError):
            continue
        if parts[0] == "UPDATE1A" and len(parts) >= 3:
            seen[parts[2]] = seen.get(parts[2], 0) + 1
    # repeats (for lost packets) come at least twice as often as on a normal server; the tick aims at 33 ms, but
    # Windows wakes a sleeping Java thread in ~15.6 ms steps, so 20-30 a second depending on the timer
    rate = seen.get("Geralt", 0) / 3
    check("--lan: state repeated 20-36 times a second", 18 <= rate <= 36, (rate, seen))

    # what makes it smooth: new state is forwarded the moment it arrives, not on the next tick
    delays = []
    for i in range(10):
        value = f"v{i}"
        sent_at = time.perf_counter()
        send(host, "UPDATE1A", "Geralt", value)
        got_at = None
        end = time.time() + 0.5
        while time.time() < end and got_at is None:
            try:
                parts = listener.recv(8192).decode().split("\t")
            except (socket.timeout, ConnectionResetError):
                continue
            if parts[0] == "UPDATE1A" and len(parts) >= 4 and parts[2] == "Geralt" and parts[3] == value:
                got_at = time.perf_counter()
        if got_at is not None:
            delays.append((got_at - sent_at) * 1000)
        send(listener, "UPDATE1A", "Listener", "x")
        time.sleep(0.15)
    delays.sort()
    median = delays[len(delays) // 2] if delays else None
    check("--lan: new state forwarded on arrival (median under 10 ms)", len(delays) == 10 and median < 10,
          [round(d, 1) for d in delays])

    q = client(port)
    send(q, "DISCOVER", "W3COOP", PROTOCOL)
    d = wait_for(q, "W3COOP_HOST", 2)
    check("--lan: discovery answer carries the save port", d is not None and len(d) >= 6 and d[5] == str(crash_port), d)

    # the host's newest save
    base = f"http://127.0.0.1:{crash_port}/save/latest"
    try:
        info = urllib.request.urlopen(base + "/info", timeout=5).read().decode().strip().split("\t")
        sav = urllib.request.urlopen(base + "/sav", timeout=5).read()
        png = urllib.request.urlopen(base + "/png", timeout=5).read()
    except urllib.error.URLError as err:
        info, sav, png = [str(err)], b"", b""
    newest = os.path.join(saves_dir, "ManualSave_2.sav")
    check("save hand-off: the newest save is offered", info[0] == "ManualSave_2.sav" and info[1] == str(os.path.getsize(newest)), info)
    check("save hand-off: save and screenshot arrive intact",
          sav == open(newest, "rb").read() and png == open(os.path.join(saves_dir, "ManualSave_2.png"), "rb").read())

    # package\lan-join.ps1 on a copy of the game's bin layout: finds the host, fetches the save, writes config.xml
    if lan_join and os.path.exists(lan_join):
        game_bin = os.path.join(work, "game", "bin")
        os.makedirs(os.path.join(game_bin, "w3coop"))
        os.makedirs(os.path.join(game_bin, "WitcherOnline"))
        script = shutil.copy(lan_join, os.path.join(game_bin, "w3coop"))
        run = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Name", "Yennefer",
                              "-Port", str(port)], capture_output=True, text=True, timeout=120)
        print("  lan-join.ps1: " + " | ".join(line for line in run.stdout.splitlines() if line.strip()))
        config = os.path.join(game_bin, "WitcherOnline", "config.xml")
        text = open(config, encoding="utf-8-sig").read() if os.path.exists(config) else ""
        fetched = os.path.join(game_bin, "WitcherOnline", "coop-profile", "The Witcher 3", "gamesaves", "ManualSave_2.sav")
        check("lan-join: host found and config written",
              "<Role>member</Role>" in text and "<CoopProfile>true</CoopProfile>" in text and "<ServerIP>auto</ServerIP>" not in text
              and f"<Port>{port}</Port>" in text, text)
        check("lan-join: host's save in the co-op profile, set to load",
              os.path.exists(fetched) and open(fetched, "rb").read() == open(newest, "rb").read()
              and "<AutoLoadSave>ManualSave_2</AutoLoadSave>" in text, (os.path.exists(fetched), text))


def profile_tests(harness, work):
    wo = os.path.join(work, "profile", "WitcherOnline")
    os.makedirs(wo)
    out = subprocess.run([harness, wo], capture_output=True, text=True, timeout=30).stdout
    check("profile off: Documents untouched", f"known={os.path.join(wo, 'coop-profile')}" not in out, out)

    with open(os.path.join(wo, "config.xml"), "w") as f:
        f.write('<?xml version="1.0"?>\n<Config>\n\t<CoopProfile>true</CoopProfile>\n</Config>\n')
    out = subprocess.run([harness, wo], capture_output=True, text=True, timeout=30).stdout
    want = os.path.join(wo, "coop-profile")
    lines = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    check("profile on: Documents redirected through all three APIs",
          all(os.path.normcase(lines.get(k, "")) == os.path.normcase(want) for k in ("known", "wide", "narrow")), out)
    check("profile on: gamesaves folder created", os.path.isdir(os.path.join(want, "The Witcher 3", "gamesaves")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", required=True)
    ap.add_argument("--harness")
    ap.add_argument("--profile-harness")
    ap.add_argument("--lan-join", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "package", "lan-join.ps1"))
    ap.add_argument("--port", type=int, default=41910)
    a = ap.parse_args()
    crash_port = a.port + 3

    work = tempfile.mkdtemp(prefix="w3c-lan-")
    server_dir = os.path.join(work, "server")
    os.makedirs(server_dir)
    jar = shutil.copy(a.jar, server_dir)
    with open(os.path.join(server_dir, "server.properties"), "w") as f:
        f.write(f"crashPort={crash_port}\n")

    server = subprocess.Popen(["java", "-jar", jar, str(a.port)], cwd=server_dir, stdin=subprocess.PIPE,
                              stdout=open(os.path.join(work, "server.log"), "w"), stderr=subprocess.STDOUT)
    try:
        time.sleep(2)
        server_tests(a.port, crash_port, server_dir)
        normal_server_lan_checks(a.port)
        if a.harness:
            harness_tests(a.harness, a.port, crash_port, server_dir, work)
    finally:
        try:
            server.stdin.write(b"stop\n")
            server.stdin.flush()
            server.wait(5)
        except (OSError, subprocess.TimeoutExpired):
            server.kill()

    # a second server as "Host LAN co-op.cmd" starts it: --lan and the host's saves folder (two saves, the second newer)
    lan_port, lan_crash = a.port + 20, a.port + 23
    lan_dir = os.path.join(work, "server-lan")
    saves = os.path.join(work, "host-saves")
    os.makedirs(lan_dir)
    os.makedirs(saves)
    for i, age in ((1, 120), (2, 0)):
        for ext, size in ((".sav", 300000 + i), (".png", 5000 + i)):
            path = os.path.join(saves, f"ManualSave_{i}{ext}")
            with open(path, "wb") as f:
                f.write(os.urandom(size))
            os.utime(path, (time.time() - age, time.time() - age))
    lan_jar = shutil.copy(a.jar, lan_dir)
    with open(os.path.join(lan_dir, "server.properties"), "w") as f:
        f.write(f"crashPort={lan_crash}\n")
    lan_server = subprocess.Popen(["java", "-jar", lan_jar, str(lan_port), "--lan", "--saves", saves], cwd=lan_dir,
                                  stdin=subprocess.PIPE, stdout=open(os.path.join(work, "server-lan.log"), "w"),
                                  stderr=subprocess.STDOUT)
    try:
        time.sleep(2)
        lan_server_tests(lan_port, lan_crash, saves, a.lan_join, work)
    finally:
        try:
            lan_server.stdin.write(b"stop\n")
            lan_server.stdin.flush()
            lan_server.wait(5)
        except (OSError, subprocess.TimeoutExpired):
            lan_server.kill()

    if a.profile_harness:
        profile_tests(a.profile_harness, work)

    print(f"\n{len(passed)} passed, {len(failures)} failed (server log: {os.path.join(work, 'server.log')})")
    print("RESULT:", "FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
