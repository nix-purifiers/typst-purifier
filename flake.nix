{
  description = "Locked, Nix-resolved Typst packages";
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
        typst-purifier = final.lib.makeScope final.newScope (scope: {
          nativeTypst = scope.callPackage ./nix/native.nix { };
          nativeTinymist = scope.callPackage ./nix/editor.nix { };
          sdkVersion = import ./nix/sdk-version.nix { nixpkgsSrc = nixpkgs; };
          cli = scope.callPackage ./nix/cli.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildTypstProject = scope.callPackage ./nix/build-project.nix {
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
        default = (pkgsFor system).typst-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/typst-purifier";
          meta.description = "Lock native Typst packages";
        };
      });
      lib.typst-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      checks = forAll (
        system:
        let
          pkgs = pkgsFor system;
          build = pkgs.typst-purifier.buildTypstProject {
            src = ./examples/minimal;
            doCheck = true;
            checkCommand = "typst eval --ignore-system-fonts --in main.typ 'query(<purifier-proof>).first().value' | grep -Fx 42";
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
