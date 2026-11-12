{
  description = "Locked, Nix-resolved Idris packages";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        idris2-purifier = final.lib.makeScope final.newScope (scope: {
          nativePack = scope.callPackage ./pkgs/build-idris2-project/native.nix { };
          nativeLsp = scope.callPackage ./pkgs/build-idris2-project/lsp.nix { };
          mkCompiler = scope.callPackage ./pkgs/build-idris2-project/compiler.nix { nixpkgsSrc = nixpkgs; };
          sdkVersion = import ./pkgs/build-idris2-project/sdk-version.nix {
            nixpkgsSrc = nixpkgs;
            inherit (final) idris2 idris2Packages;
          };
          cli = scope.callPackage ./pkgs/cli/default.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildIdrisProject = scope.callPackage ./pkgs/build-idris2-project/default.nix {
            nixpkgsSrc = nixpkgs;
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).idris2-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/idris2-purifier";
          meta.description = "Lock native Idris packages";
        };
      });
      lib.idris2-purifier = (nixpkgs.lib.extend (import ./lib-overlays/default)).idris2-purifier;
      checks = forAll (
        system:
        let
          pkgs = pkgsFor system;
          build = pkgs.idris2-purifier.buildIdrisProject {
            src = ./examples/minimal;
            doCheck = true;
            checkCommand = ''test "$(./build/exec/proof)" = 42'';
          };
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
