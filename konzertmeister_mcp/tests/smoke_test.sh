#!/usr/bin/env bash
# Start the built app image like the Supervisor would (without Home Assistant
# and without Konzertmeister) and check the basics from inside the container.
set -euo pipefail
image="$1"
data=$(mktemp -d)
echo '{"log_level": "info"}' > "$data/options.json"

# A fake Home Assistant config folder with a file readable for everyone.
ha=$(mktemp -d)
echo "api_password: top-secret" > "$ha/secrets.yaml"
chmod 755 "$ha"; chmod 644 "$ha/secrets.yaml"
echo "homeassistant: {}" > "$ha/configuration.yaml"; chmod 644 "$ha/configuration.yaml"

# AppArmor: run the container with the app's own profile, like Home Assistant
# does. Required on CI (the GitHub runners have AppArmor), optional elsewhere.
here="$(cd "$(dirname "$0")/.." && pwd)"
security=()
if [ -d /sys/kernel/security/apparmor ] && command -v apparmor_parser >/dev/null; then
  sudo apparmor_parser -r -W "$here/apparmor.txt"
  security=(--security-opt apparmor=konzertmeister_mcp)
  apparmor=1
elif [ -n "${CI:-}" ]; then
  echo "AppArmor is not available on this CI runner" >&2; exit 1
else
  echo "(AppArmor not available here – testing without the profile)"
  apparmor=0
fi
# ALLOW_ANY_UI_CLIENT: the page normally only answers Home Assistant's ingress
# proxy; here the checks run inside the container (127.0.0.1).
docker run -d --name app-smoke "${security[@]}" -e ALLOW_ANY_UI_CLIENT=1 -v "$data:/data" -v "$ha:/homeassistant" "$image" >/dev/null
trap 'docker logs app-smoke || true; docker rm -f app-smoke >/dev/null 2>&1 || true' EXIT

check() {
  docker exec app-smoke python3 -c "$1"
}

for _ in $(seq 1 30); do
  if check "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/status.json', timeout=2)" 2>/dev/null; then
    break
  fi
  sleep 2
done

echo "1. App page answers in English and German"
check "
import urllib.request
def page(lang):
    req = urllib.request.Request('http://127.0.0.1:8099/', headers={'Accept-Language': lang})
    return urllib.request.urlopen(req, timeout=5).read().decode()
de, en = page('de-DE,de;q=0.9'), page('en-US')
assert 'Konzertmeister MCP' in en and 'type=\"password\"' in en, 'key form missing'
assert 'lang=\"de\"' in de and 'Schlüssel speichern' in de, 'German page missing'
assert 'lang=\"en\"' in en and 'Save key' in en, 'English page missing'
"

echo "2. Endpoint is protected by the secret path; without key a stand-in explains why"
check "
import json, urllib.request, urllib.error
def code(url, method='GET'):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, method=method, data=b'{}' if method=='POST' else None), timeout=5).status
    except urllib.error.HTTPError as e:
        return e.code
assert code('http://127.0.0.1:8100/') == 404
assert code('http://127.0.0.1:8100/mcp', 'POST') == 404
assert code('http://127.0.0.1:8100/wrong-secret/mcp', 'POST') == 404
secret = open('/data/clubs/1/secret_path').read().strip()
def mcp(method, mid=1):
    req = urllib.request.Request(f'http://127.0.0.1:8100/{secret}/mcp', method='POST',
        data=json.dumps({'jsonrpc': '2.0', 'id': mid, 'method': method, 'params': {}}).encode(),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())
init = mcp('initialize')
assert init['id'] == 1 and 'no API key' in init['result']['instructions'], init
call = mcp('tools/call', 7)
assert call['id'] == 7 and call['result']['isError'], call
assert code('http://127.0.0.1:8099/mcp-unavailable/1', 'POST') == 403
"

echo "3. Secret path is never written to the log"
secret=$(docker exec app-smoke python3 -c "print(open('/data/clubs/1/secret_path').read().strip())")
if docker logs app-smoke 2>&1 | grep -q "$secret"; then
  echo "secret path found in log" >&2
  exit 1
fi

echo "4. Every MCP server runs as its own user, with Landlock where available, and only reaches its folder"
docker exec app-smoke python3 -c "
import os, sys, time
sys.path.insert(0, '/app')
import clubs as C, common
svc = C.Services()
club = svc.club('1')
second = svc.add_club()
ident = common.mcp_identity(club.user)
assert ident and ident[0] != 0, 'unprivileged user missing'
assert common.mcp_identity(second.user) not in (None, ident), 'second association has no user of its own'
club.private.mkdir(mode=0o700, exist_ok=True)
common.write_private(club.key_file, 'smoke-test-key-0123456789')
common.hand_over(club.private, ident)
club.start_mcp()
for _ in range(60):
    if club.mcp_state() == 'ready':
        break
    time.sleep(0.5)
assert club.mcp_state() == 'ready', 'server did not start'
st = os.stat(club.key_file)
assert st.st_uid == ident[0] and st.st_mode & 0o777 == 0o600
assert os.stat(club.private).st_mode & 0o777 == 0o700
club.stop_mcp()
print('USERS', club.user, club.private, club.key_file, second.user)
" > /tmp/smoke-users
cat /tmp/smoke-users
read -r _ user1 private1 key1 user2 < <(grep '^USERS ' /tmp/smoke-users)
docker exec -u "$user1" app-smoke python3 -c "
import os, sys
private = sys.argv[1]
open(private + '/ok.txt', 'w').write('x'); os.remove(private + '/ok.txt')
for path in ('/data/clubs/1/secret_path', '/data/clubs/1/settings.json', '/data/clubs/1/webhook_id',
             '/data/report_secret', '/data/options.json', '/data/clubs.json'):
    try:
        open(path).read()
    except (PermissionError, FileNotFoundError):
        continue
    raise SystemExit(f'MCP user could read {path}')
for path in ('/data', '/data/clubs', '/data/clubs/1'):
    try:
        os.listdir(path)
        raise SystemExit(f'MCP user could list {path}')
    except PermissionError:
        pass
for path in ('/app/launcher.py', '/data/new_file', '/data/clubs/1/settings.json', '/etc/passwd', '/homeassistant/x.yaml'):
    try:
        open(path, 'a').close()
    except PermissionError:
        continue
    raise SystemExit(f'MCP user could write {path}')
" "$private1"
docker exec -u "$user2" app-smoke python3 -c "
import sys
try:
    open(sys.argv[1]).read()
    raise SystemExit('second association could read the key of the first')
except PermissionError:
    pass
" "$key1"
docker exec -u "$user1" -w "$private1" app-smoke python3 -c "
import sys; sys.path.insert(0, '/app')
import mcp_server, httpx, ssl
if mcp_server.lock_down(sys.argv[1]):
    for path in ('/homeassistant/secrets.yaml', '/data/options.json'):
        try:
            open(path).read()
        except PermissionError:
            continue
        raise SystemExit(f'could read {path} despite Landlock')
    open(sys.argv[1] + '/still-writable', 'w').close()
else:
    print('   (Landlock not available on this kernel)')
ssl.create_default_context()  # TLS certificates still load
" "$private1"

if [ "$apparmor" = 1 ]; then
echo "5. AppArmor: even root in the container only reaches the helper integration"
docker exec app-smoke python3 -c "
import os, time, subprocess
assert 'konzertmeister_mcp' in open('/proc/1/attr/current').read(), 'not confined by the profile'
for _ in range(30):
    if os.path.exists('/homeassistant/custom_components/konzertmeister_mcp_webhook/manifest.json'):
        break
    time.sleep(1)
else:
    raise SystemExit('helper integration was not installed')
for action, path in (('r', '/homeassistant/secrets.yaml'), ('a', '/homeassistant/configuration.yaml'),
                     ('w', '/homeassistant/new_file.yaml')):
    try:
        open(path, action).close()
    except PermissionError:
        continue
    raise SystemExit(f'root could {action} {path} despite AppArmor')
try:
    os.mkdir('/homeassistant/www')
    raise SystemExit('root could create folders in the Home Assistant folder')
except PermissionError:
    pass
try:
    subprocess.run(['/bin/sh', '-c', 'true'], check=True)
    raise SystemExit('a shell could be started despite AppArmor')
except PermissionError:
    pass
"
test -f "$ha/custom_components/konzertmeister_mcp_webhook/manifest.json"
grep -q "top-secret" "$ha/secrets.yaml"
fi

echo "6. Health check passes"
for _ in $(seq 1 30); do
  status=$(docker inspect -f '{{.State.Health.Status}}' app-smoke)
  [ "$status" = "healthy" ] && break
  sleep 3
done
[ "$status" = "healthy" ] || { echo "health status: $status" >&2; exit 1; }

echo "Smoke test passed"
