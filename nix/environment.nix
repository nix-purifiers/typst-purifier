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
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  tree = purifier.tree (
    {
      name = "typst-fixed-archives";
      entries = checked.entries;
      inherit
        runCommand
        fetchurl
        python3
        writeText
        ;
    }
    // fetchers
  );
in
assert checked.problems == [ ];
assert lib.assertMsg (checked.data.sdk == sdkVersion) "Typst SDK changed; update the lock";
runCommand "typst-locked-packages"
  {
    nativeBuildInputs = [
      gnutar
      gzip
      python3
    ];
  }
  (
    ''mkdir -p "$out"''
    + "\n"
    + lib.concatMapStringsSep "\n" (node: ''
      mkdir -p "$out/${node.namespace}/${node.name}/${node.version}"
      tar -xzf ${tree}/${node.entry} -C "$out/${node.namespace}/${node.name}/${node.version}"
      python3 ${../typst_purifier/check-package.py} ${writeText "typst-package.json" (builtins.toJSON node)} "$out/${node.namespace}/${node.name}/${node.version}"
    '') checked.data.nodes
  )
