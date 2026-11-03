{ idris2Packages }:
idris2Packages.pack.overrideAttrs (old: {
  patches = (old.patches or [ ]) ++ [ ../native/pack.patch ];
  postPatch = (old.postPatch or "") + ''
    substituteInPlace pack.ipkg --replace-fail 'depends = base' 'depends = contrib, base'
  '';
})
