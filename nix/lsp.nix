{
  idris2Packages,
  runCommand,
  python3,
}:
let
  emptyPackages = runCommand "idris-empty-packages" { } ''mkdir -p "$out"'';
  api = idris2Packages.idris2Api.overrideAttrs (old: {
    postPatch =
      (old.postPatch or "")
      + "\n"
      + ''
        ${python3}/bin/python3 ${../native/disable-local-packages.py} "$PWD" ${emptyPackages}
      '';
  });
in
(idris2Packages.idris2Lsp.override {
  idris2Packages = idris2Packages // {
    idris2Api = api;
  };
}).overrideAttrs
  (_: {
    postInstall = "";
  })
