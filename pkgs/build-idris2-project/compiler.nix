{
  lib,
  newScope,
  nixpkgsSrc,
  runCommand,
  python3,
}:
{ src, version }:
let
  directory = nixpkgsSrc + "/pkgs/by-name/id/idris2";
  emptyPackages = runCommand "idris-empty-packages" { } ''mkdir -p "$out"'';
  scope = lib.makeScope newScope (self: {
    idris2-version = version;
    idris2-src = src;
    mkPrelude = self.callPackage (directory + "/mkPrelude.nix") { };
    prelude = self.callPackage (directory + "/prelude.nix") { };
    base = self.callPackage (directory + "/base.nix") { };
    linear = self.callPackage (directory + "/linear.nix") { };
    network = self.callPackage (directory + "/network.nix") { };
    contrib = self.callPackage (directory + "/contrib.nix") { };
    test = self.callPackage (directory + "/test.nix") { };
    libidris2_support = self.callPackage (directory + "/libidris2_support.nix") { };
    idris2-unwrapped = (self.callPackage (directory + "/unwrapped.nix") { }).overrideAttrs (old: {
      postPatch =
        (old.postPatch or "")
        + "\n"
        + ''
          ${python3}/bin/python3 ${../../native/disable-local-packages.py} "$PWD" ${emptyPackages}
        '';
    });
  });
in
scope.idris2-unwrapped.withPackages (_: [ ])
