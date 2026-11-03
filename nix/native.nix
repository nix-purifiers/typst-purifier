{ typst, python3 }:
typst.overrideAttrs (old: {
  pname = "purifier-native-typst";
  nativeBuildInputs = old.nativeBuildInputs ++ [ python3 ];
  postPatch = old.postPatch + "\n" + "python3 ${../typst_purifier/patch-sdk.py}";
  doCheck = false;
  doInstallCheck = false;
  cargoBuildFlags = [
    "--package"
    "typst-cli"
  ];
})
