{ lib }:
{
  src,
  lockFile ? src + "/typst-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  nodes = data.nodes or [ ];
  safe = s: builtins.isString s && builtins.match "[a-z0-9-]+" s != null;
  version = s: builtins.isString s && builtins.match "[0-9]+\\.[0-9]+\\.[0-9]+" s != null;
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  manifest =
    if data ? inputs && data.inputs ? "typst.toml" then
      builtins.fromTOML data.inputs."typst.toml".content
    else
      { };
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "typst"
    && builtins.isString (data.sdk or null)
    && relative (data.document or null)
    && builtins.pathExists (src + "/${data.document}")
    && (builtins.readDir (dirOf (src + "/${data.document}"))).${baseNameOf data.document} == "regular"
    && builtins.isList (data.defines or null)
    && builtins.all builtins.isString data.defines
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs (data.inputs or null)
    &&
      builtins.attrNames data.inputs == builtins.sort builtins.lessThan (
        lib.unique (
          (lib.optional (builtins.pathExists (src + "/typst.toml")) "typst.toml") ++ data.extraInputs
        )
      )
    && builtins.all (
      name:
      relative name
      && builtins.isAttrs data.inputs.${name}
      && builtins.isString (data.inputs.${name}.content or null)
      && builtins.pathExists (src + "/${name}")
      && (builtins.readDir (dirOf (src + "/${name}"))).${baseNameOf name} == "regular"
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
      && builtins.hashString "sha256" data.inputs.${name}.content == data.inputs.${name}.sha256
    ) (builtins.attrNames data.inputs)
    && data ? package
    && (data.package == null) == (!(data.inputs ? "typst.toml"))
    && (
      data.package == null
      || (
        builtins.isAttrs data.package
        && safe (data.package.name or null)
        && version (data.package.version or null)
        && relative (data.package.entrypoint or null)
        && builtins.pathExists (src + "/${data.package.entrypoint}")
        && manifest ? package
        && builtins.isAttrs manifest.package
        && data.package == { inherit (manifest.package) name version entrypoint; }
      )
    )
    && builtins.isList entries
    && builtins.isList nodes
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://packages.typst.org/preview/" e.url
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && (e.mirrors or null) == [ ]
      && !(e ? git)
    ) entries
    && builtins.all (
      n:
      builtins.isAttrs n
      && (n.namespace or null) == "preview"
      && safe (n.name or null)
      && version (n.version or null)
      && relative (n.entrypoint or null)
      && (n.entry or null) == "archives/${n.name}/${n.version}.tar.gz"
      && (n.url or null) == "https://packages.typst.org/preview/${n.name}-${n.version}.tar.gz"
      && builtins.any (e: e.path == n.entry && e.url == n.url) entries
    ) nodes
    && builtins.length nodes == builtins.length entries
    && builtins.length (lib.unique (map (n: n.entry) nodes)) == builtins.length nodes
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries;
in
{
  purifier = "typst";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Typst lock is missing, stale, or unsupported; run typst-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
