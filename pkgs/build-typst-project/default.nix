{
  lib,
  runCommand,
  fetchurl,
  python3,
  writeText,
  gnutar,
  gzip,
  purifier,
  sdkVersion,
  nativeTypst,
}@scope:
{
  src,
  lockFile ? src + "/typst-purifier.lock.json",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  typstFlags ? [ ],
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (import ../../lib-overlays/default/read-lock.nix { inherit lib; } { inherit src lockFile; });
  environment = import ./environment.nix (builtins.removeAttrs scope [ "nativeTypst" ]) {
    inherit lock fetchers;
  };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".typst-purifier"
        "result"
        "__pycache__"
      ]);
  };
  flags =
    lib.concatMap (d: [
      "--input"
      d
    ]) lock.data.defines
    ++ typstFlags;
  builtProject =
    runCommand "typst-project"
      {
        nativeBuildInputs = [
          nativeTypst
          python3
        ]
        ++ nativeBuildInputs;
      }
      ''
        export HOME="$TMPDIR/home" TYPST_PURIFIER_FROZEN=1
        export TYPST_PACKAGE_PATH=${environment} TYPST_PACKAGE_CACHE_PATH=${environment}
        export SOURCE_DATE_EPOCH=315532800 TYPST_IGNORE_SYSTEM_FONTS=true
        unset TYPST_FONT_PATHS TYPST_PURIFIER_CAPTURE TYPST_ROOT TYPST_FEATURES
        mkdir -p "$HOME" "$out" source
        cp -pr ${source}/. source/
        chmod -R u+w source
        cd source
        typst compile --ignore-system-fonts ${lib.escapeShellArgs flags} --deps "$out/dependencies.json" ${lib.escapeShellArg lock.data.document} "$out/document.pdf"
        ${lib.optionalString doCheck checkCommand}
      '';
  projections = purifier.resourceProjections {
    producer = builtProject;
    roots."document.pdf" = "document.pdf";
    inherit runCommand python3;
  };
  project = builtProject // {
    inherit projections;
  };
  release =
    runCommand "typst-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
          python3
        ];
      }
      ''
        mkdir -p "$out"
        cp ${project}/document.pdf "$out/document.pdf"
        ${lib.optionalString (lock.data.package != null) ''
          mkdir stage
          cp -pr ${source}/. stage/
          chmod -R u+w stage
          python3 ${../../typst_purifier/check-package.py} ${writeText "typst-project-package.json" (builtins.toJSON lock.data.package)} "$PWD/stage"
          tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/${lock.data.package.name}-${lock.data.package.version}.tar.gz" -C stage .
        ''}
      '';
in
assert lock.problems == [ ];
{
  packages = {
    default = project;
    inherit environment project;
  };
  tests = project;
  inherit release projections;
  fetches = lock.entries;
}
