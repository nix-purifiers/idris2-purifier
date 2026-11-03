import json
import queue
import subprocess
import threading
import time


def check(cli, root, env):
    messages = queue.Queue()
    process = subprocess.Popen(
        [cli / "idris2-lsp"],
        cwd=root,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    def read():
        while True:
            headers = {}
            while True:
                line = process.stdout.readline()
                if not line:
                    return
                if line in (b"\r\n", b"\n"):
                    break
                key, value = line.decode().split(":", 1)
                headers[key.lower()] = value.strip()
            messages.put(
                json.loads(process.stdout.read(int(headers["content-length"])))
            )

    threading.Thread(target=read, daemon=True).start()

    def send(message):
        content = json.dumps(dict(jsonrpc="2.0", **message)).encode()
        process.stdin.write(
            b"Content-Length: " + str(len(content)).encode() + b"\r\n\r\n" + content
        )
        process.stdin.flush()

    def response(identifier):
        until = time.monotonic() + 45
        while time.monotonic() < until:
            message = messages.get(timeout=max(0.1, until - time.monotonic()))
            if message.get("id") == identifier:
                return message
        raise AssertionError("Language server did not answer")

    try:
        send(
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": root.as_uri(),
                    "capabilities": {},
                },
            }
        )
        assert "result" in response(1)
        send({"method": "initialized", "params": {}})
        source = root / "Main.idr"
        text = source.read_text()
        send(
            {
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": source.as_uri(),
                        "languageId": "idris",
                        "version": 1,
                        "text": text,
                    }
                },
            }
        )
        line = next(i for i, value in enumerate(text.splitlines()) if "hdec0" in value)
        character = text.splitlines()[line].index("hdec0") + 1
        send(
            {
                "id": 2,
                "method": "textDocument/definition",
                "params": {
                    "textDocument": {"uri": source.as_uri()},
                    "position": {"line": line, "character": character},
                },
            }
        )
        result = response(2)
        assert "/nix/store/" in json.dumps(result) and "HDec.idr" in json.dumps(
            result
        ), result
        assert "depends" not in json.dumps(result), result
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
