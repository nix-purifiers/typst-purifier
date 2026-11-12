{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  typst,
  tinymist,
  nativeTypst,
  nativeTinymist,
  cacert,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "typst-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/typst-purifier"
    cp -r typst_purifier nix lib-overlays pkgs "$out/lib/typst-purifier/"
    install -m755 bin/typst-purifier "$out/bin/typst-purifier"
    substituteInPlace "$out/lib/typst-purifier/nix/realize.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/typst-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default TYPST_PURIFIER_GH ${gh}/bin/gh \
      --set TYPST_PURIFIER_ORIGINAL_TYPST ${typst}/bin/typst \
      --set TYPST_PURIFIER_ORIGINAL_TINYMIST ${tinymist}/bin/tinymist \
      --set TYPST_PURIFIER_NATIVE_TYPST ${nativeTypst}/bin/typst \
      --set TYPST_PURIFIER_NATIVE_TINYMIST ${nativeTinymist}/bin/tinymist \
      --set TYPST_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set TYPST_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/typst-purifier" "$out/bin/typst" --add-flags '--native=typst'
    makeWrapper "$out/bin/typst-purifier" "$out/bin/tinymist" --add-flags '--native=tinymist'
  '';
  meta = {
    description = "Native Typst workflow with locked Nix-resolved packages";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "typst-purifier";
  };
}
