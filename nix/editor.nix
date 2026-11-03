{ tinymist, python3 }:
tinymist.overrideAttrs (old: {
  pname = "purifier-native-tinymist";
  nativeBuildInputs = old.nativeBuildInputs ++ [ python3 ];
  postPatch = (old.postPatch or "") + "\n" + "python3 ${../typst_purifier/patch-editor.py}";
  doCheck = false;
  doInstallCheck = false;
  cargoBuildFlags = [
    "--package"
    "tinymist-cli"
  ];
})
