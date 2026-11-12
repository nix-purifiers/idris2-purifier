{
  project,
  companion,
  target ? "environment",
  sdk ? null,
  profile ? false,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  nativePack = pkgs.callPackage ./native.nix { };
  mkCompiler = pkgs.callPackage ./compiler.nix { inherit nixpkgsSrc; };
  sdkVersion = import ./sdk-version.nix {
    inherit nixpkgsSrc;
    inherit (pkgs) idris2 idris2Packages;
  };
  build =
    pkgs.callPackage ./default.nix
      {
        inherit
          purifier
          nativePack
          mkCompiler
          nixpkgsSrc
          sdkVersion
          ;
      }
      {
        src = /. + project;
        lockFile = /. + companion;
      };
  output =
    if target == "environment" then
      build.packages.environment
    else if target == "release" then
      build.release
    else
      throw "Unknown Idris target";
in
if profile then
  pkgs.writeText "idris-${target}-profile.json" (
    builtins.toJSON {
      inherit output;
      sdk = builtins.storePath sdk;
    }
  )
else
  output
