{
  pkgs,
  src ? ./fixtures/javascript,
  expected ? 42,
}:
let
  build = pkgs.idris2-purifier.buildIdrisProject {
    inherit src;
    javascriptTargets = {
      browser = "browser";
      node = "node";
    };
  };
  rejects =
    source: targets: name:
    !(builtins.tryEval (
      (pkgs.idris2-purifier.buildIdrisProject {
        src = source;
        javascriptTargets = targets;
      }).javascriptPackages.${name}.drvPath
    )).success;
in
assert rejects src { bad = "wasm"; } "bad";
assert rejects src { "../escape" = "node"; } "../escape";
assert rejects ../examples/minimal { browser = "browser"; } "browser";
assert rejects ./fixtures/javascript-library { node = "node"; } "node";
pkgs.runCommand "idris-native-javascript-consumers"
  {
    nativeBuildInputs = [
      pkgs.nodejs
      pkgs.chromium
      pkgs.python3
      pkgs.jdk
    ];
    passthru = { inherit build; };
  }
  ''
      export HOME="$TMPDIR/home"
      mkdir -p "$HOME" "$out"
      node -e 'require(process.argv[1]); if(globalThis.purifierAnswer !== ${toString expected}) throw new Error("Idris Node result")' \
        ${build.javascriptPackages.node}/node/proof.html
      chromium --headless --no-sandbox --disable-gpu --dump-dom \
        file://${build.projections.browser.web.directory}/proof.html > "$out/dom.html" 2> "$TMPDIR/chromium.log"
      grep 'data-answer="${toString expected}"' "$out/dom.html"
      cmp ${build.javascriptPackages.browser}/web/proof.html ${build.projections.browser.web.directory}/proof.html
      cat > Resource.java <<'JAVA'
      import java.nio.file.*;
      import java.util.Arrays;
      class Resource {
        public static void main(String[] args) throws Exception {
          try (var stream = Resource.class.getResourceAsStream("/proof.html")) {
            if (stream == null || !Arrays.equals(stream.readAllBytes(), Files.readAllBytes(Path.of(args[0]))))
              throw new AssertionError("Idris Java resource differs from native HTML");
          }
        }
      }
    JAVA
      javac Resource.java
      java -cp .:${build.projections.browser.java-resources.classPath} Resource \
        ${build.javascriptPackages.browser}/web/proof.html
      cat > serve.py <<'PY'
      import http.server, pathlib
      from functools import partial
      server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(http.server.SimpleHTTPRequestHandler,
          directory="${build.projections.browser.web.directory}"))
      pathlib.Path("port").write_text(str(server.server_port))
      server.serve_forever()
    PY
      python -c 'import textwrap; exec(textwrap.dedent(open("serve.py").read()))' > "$TMPDIR/http.log" 2>&1 &
      server=$!
      trap 'kill "$server"' EXIT
      for attempt in $(seq 1 100); do test -s port && break; sleep 0.05; done
      test -s port
      chromium --headless --no-sandbox --disable-gpu --dump-dom \
        "http://127.0.0.1:$(cat port)/proof.html" > "$out/http-dom.html" 2>> "$TMPDIR/chromium.log"
      grep 'data-answer="${toString expected}"' "$out/http-dom.html"
  ''
