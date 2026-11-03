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
  gnutar,
  gzip,
}@scope:
{
  src,
  lockFile ? src + "/idris2-purifier.lock.json",
  fetchers ? { },
  libraryOverrides ? { },
  nativeBuildInputs ? [ ],
  doCheck ? false,
  checkCommand ? "",
  buildCommand ? "",
}:
let
  lock = purifier.checkLock (import ./read-lock.nix { inherit lib; } { inherit src lockFile; });
  prepared = import ./environment.nix (builtins.removeAttrs scope [
    "gnutar"
    "gzip"
  ]) { inherit lock fetchers libraryOverrides; };
  rawSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".idris2-purifier"
        "build"
        "depends"
        "result"
        "__pycache__"
      ]);
  };
  source = runCommand "idris-validated-source" { } ''
    ${lib.optionalString (lock.data.project != null) ''
      ${python3}/bin/python3 ${../idris2_purifier/check-metadata.py} ${nativePack}/bin/pack ${lib.escapeShellArg "${rawSource}/${lock.data.project.ipkg}"} ${writeText "idris-project.json" (builtins.toJSON lock.data.project)}
    ''}
    mkdir -p "$out"
    cp -pr ${rawSource}/. "$out/"
  '';
  root = prepared.buildIdris {
    src = source;
    ipkgName = lib.removeSuffix ".ipkg" lock.data.project.ipkg;
    version = if lock.data.project.version == null then "unversioned" else lock.data.project.version;
    idrisLibraries = builtins.attrValues prepared.packages;
    inherit nativeBuildInputs;
  };
  project =
    if lock.data.project != null then
      (
        if lock.data.project.executable == null then
          root.library { withSource = true; }
        else
          root.executable
      ).overrideAttrs
        (old: {
          inherit doCheck;
          checkPhase = checkCommand;
          buildPhase = ''
            runHook preBuild
            idris2 --build ${lib.escapeShellArg lock.data.project.ipkg}
            runHook postBuild
          '';
          postBuild =
            (old.postBuild or "")
            + "\n"
            + ''
              ${python3}/bin/python3 ${../native/recompile-chez.py} ${lib.getExe prepared.compiler.chez}
            '';
          installPhase =
            lib.replaceStrings
              [ "idris2 --install-with-src ${lock.data.project.ipkg}" ]
              [ "idris2 --install-with-src ${lib.escapeShellArg lock.data.project.ipkg}" ]
              old.installPhase;
          passthru = (old.passthru or { }) // {
            withSource = project;
          };
        })
    else
      runCommand "idris-project" { nativeBuildInputs = [ prepared.output ] ++ nativeBuildInputs; } ''
        mkdir -p "$out/source"
        cp -pr ${source}/. "$out/source/"
        chmod -R u+w "$out/source"
        cd "$out/source"
        ${buildCommand}
        ${lib.optionalString doCheck checkCommand}
      '';
  release =
    runCommand "idris-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out" source/project
        cp -pr ${source}/. source/project/
        chmod -R u+rwX source
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/idris-source.tar.gz" -C source project
      '';
in
assert lib.assertMsg (lock.data.sdk == sdkVersion) "Pack frontend SDK changed; update the lock";
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
