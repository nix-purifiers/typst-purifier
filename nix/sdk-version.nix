{ nixpkgsSrc }:
builtins.hashString "sha256" (
  toString nixpkgsSrc
  + builtins.hashFile "sha256" ../typst_purifier/patch-sdk.py
  + builtins.hashFile "sha256" ../typst_purifier/patch-editor.py
)
