{
  nixpkgsSrc,
  idris2,
  idris2Packages,
}:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    compiler = toString idris2.src;
    pack = toString idris2Packages.pack.src;
    adapter = builtins.hashFile "sha256" ../../native/pack.patch;
    packageLookup = builtins.hashFile "sha256" ../../native/disable-local-packages.py;
    languageServer = builtins.hashFile "sha256" ./lsp.nix;
  }
)
