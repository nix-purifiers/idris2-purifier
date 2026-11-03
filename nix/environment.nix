{
  lib,
  runCommand,
  fetchgit,
  fetchurl,
  python3,
  writeText,
  callPackage,
  mkCompiler,
  nativePack,
  nixpkgsSrc,
  purifier,
  sdkVersion,
  makeWrapper,
}:
{
  lock,
  fetchers ? { },
  libraryOverrides ? { },
}:
let
  checked = purifier.checkLock lock;
  data = checked.data;
  tree = purifier.tree (
    {
      name = "idris-fixed-sources";
      inherit (checked) entries;
      inherit
        runCommand
        fetchgit
        fetchurl
        python3
        writeText
        ;
    }
    // fetchers
  );
  materialize =
    name: entry:
    let
      selected = purifier.tree (
        {
          name = name + "-fetch";
          entries = builtins.filter (item: item.path == entry) checked.entries;
          inherit
            runCommand
            fetchgit
            fetchurl
            python3
            writeText
            ;
        }
        // fetchers
      );
    in
    runCommand name { } ''
      mkdir -p "$out"
      cp -pr ${selected}/${entry}/. "$out/"
    '';
  compilerSource = materialize "idris-compiler-source" data.compiler.entry;
  compiler = mkCompiler {
    src = compilerSource;
    version = data.compiler.version;
  };
  buildIdris = callPackage (nixpkgsSrc + "/pkgs/development/compilers/idris2/build-idris.nix") {
    idris2 = compiler;
  };
  external = builtins.filter (n: n.type == "git") data.nodes;
  packages = builtins.listToAttrs (
    map (node: {
      name = node.name;
      value =
        let
          raw =
            (buildIdris {
              ipkgName = lib.removeSuffix ".ipkg" node.ipkg;
              version = if node.version == null then "unversioned" else node.version;
              src = materialize "idris-${node.name}-source" node.entry;
              idrisLibraries = map (n: packages.${n}) (
                builtins.filter (name: builtins.any (n: n.name == name) external) node.dependencies
              );
              preBuild = ''
                ${python3}/bin/python3 ${../idris2_purifier/check-metadata.py} ${nativePack}/bin/pack "$src"/${lib.escapeShellArg node.ipkg} ${
                  writeText "idris-native-package.json" (
                    builtins.toJSON {
                      name = node.package;
                      inherit (node) version content dependencies;
                      executable = null;
                    }
                  )
                }
              '';
            }).library
              { withSource = true; };
          prepared = raw.overrideAttrs (old: {
            buildPhase = ''
              runHook preBuild
              idris2 --build ${lib.escapeShellArg node.ipkg}
              runHook postBuild
            '';
            installPhase =
              lib.replaceStrings
                [ "idris2 --install-with-src ${node.ipkg}" ]
                [ "idris2 --install-with-src ${lib.escapeShellArg node.ipkg}" ]
                old.installPhase;
          });
          overridden =
            if builtins.hasAttr node.name libraryOverrides then
              prepared.overrideAttrs libraryOverrides.${node.name}
            else
              prepared;
          final = overridden.overrideAttrs (old: {
            passthru = (old.passthru or { }) // {
              withSource = final;
            };
          });
        in
        final;
    }) external
  );
  manifest = writeText "idris-native-environment.json" (
    builtins.toJSON {
      inherit compiler compilerSource;
      libraries = packages;
      coreLibraries = compiler.prelude;
      support = compiler.libidris2_support;
      lock = data;
    }
  );
  output = runCommand "idris-locked-environment" { nativeBuildInputs = [ makeWrapper ]; } ''
    mkdir -p "$out/bin"
    cp ${manifest} "$out/manifest.json"
    ${lib.optionalString (data.project != null) ''
      ${python3}/bin/python3 ${../idris2_purifier/check-metadata.py} ${nativePack}/bin/pack ${writeText "project.ipkg" data.project.content} ${writeText "idris-root-metadata.json" (builtins.toJSON data.project)}
    ''}
    makeWrapper ${compiler}/bin/idris2 "$out/bin/idris2" \
      --prefix IDRIS2_PACKAGE_PATH ':' ${lib.escapeShellArg (lib.makeSearchPath "lib/idris2-${data.compiler.version}" (builtins.attrValues packages))}
    "$out/bin/idris2" --ttc-version > "$TMPDIR/ttc-version"
    grep -q '^2025081600$' "$TMPDIR/ttc-version" || {
      echo 'Selected compiler has an unsupported TTC ABI for this Pack/LSP frontend' >&2
      exit 1
    }
  '';
in
assert lib.assertMsg (data.sdk == sdkVersion) "Pack frontend SDK changed; update the lock";
{
  inherit
    output
    packages
    compiler
    compilerSource
    buildIdris
    tree
    ;
}
