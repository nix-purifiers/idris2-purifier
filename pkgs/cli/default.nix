{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  git,
  nix-prefetch-git,
  idris2,
  idris2Packages,
  nativePack,
  nativeLsp,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
  clang,
  gnumake,
  coreutils,
  findutils,
  gnugrep,
  gnutar,
  gzip,
  cacert,
}:
stdenvNoCC.mkDerivation {
  pname = "idris2-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/idris2-purifier"
    cp -r idris2_purifier pkgs lib-overlays native "$out/lib/idris2-purifier/"
    install -m755 bin/idris2-purifier "$out/bin/idris2-purifier"
    substituteInPlace "$out/lib/idris2-purifier/pkgs/build-idris2-project/realize.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/idris2-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          git
          clang
          gnumake
          coreutils
          findutils
          gnugrep
          gnutar
          gzip
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default IDRIS2_PURIFIER_GH ${gh}/bin/gh \
      --set IDRIS2_PURIFIER_ORIGINAL_IDRIS ${idris2}/bin/idris2 \
      --set IDRIS2_PURIFIER_ORIGINAL_PACK ${idris2Packages.pack}/bin/pack \
      --set IDRIS2_PURIFIER_ORIGINAL_LSP ${idris2Packages.idris2Lsp}/bin/idris2-lsp \
      --set IDRIS2_PURIFIER_NATIVE_PACK ${nativePack}/bin/pack \
      --set IDRIS2_PURIFIER_NATIVE_LSP ${nativeLsp}/bin/idris2-lsp \
      --set IDRIS2_PURIFIER_PREFETCH_GIT ${nix-prefetch-git}/bin/nix-prefetch-git \
      --set IDRIS2_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set IDRIS2_PURIFIER_SDK "$out"
    for program in idris2 pack idris2-lsp; do
      makeWrapper "$out/bin/idris2-purifier" "$out/bin/$program" --add-flags "--native=$program"
    done
  '';
  meta = {
    description = "Native Idris and Pack with locked Nix-resolved libraries";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "idris2-purifier";
  };
}
