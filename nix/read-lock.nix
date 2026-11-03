{ lib }:
{
  src,
  lockFile ? src + "/idris2-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  nodes = data.nodes or [ ];
  entries = data.entries or [ ];
  safe = s: builtins.isString s && builtins.match "[A-Za-z0-9_+-]+" s != null;
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  commit = s: builtins.isString s && builtins.match "[a-f0-9]{40}" s != null;
  entryFor =
    n:
    builtins.any (e: e.path == (n.entry or null) && e.git.url == n.url && e.git.rev == n.rev) entries;
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "idris2"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.compiler or null)
    && (data.compiler.version or null) == "0.8.0"
    && commit (data.compiler.rev or null)
    && builtins.isString (data.compiler.url or null)
    && (data.compiler.entry or null) == "sources/compiler"
    && builtins.isString (data.compiler.collection or null)
    && builtins.match "[A-Za-z0-9_+.-]+" data.compiler.collection != null
    && !(builtins.elem data.compiler.collection [
      "."
      ".."
    ])
    && builtins.isList (data.requirements or null)
    && builtins.all builtins.isString data.requirements
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs (data.configurations or null)
    && builtins.all builtins.isString (builtins.attrValues data.configurations)
    && data ? project
    && (
      data.project == null
      || (
        builtins.isAttrs data.project
        && safe (data.project.name or null)
        && relative (data.project.ipkg or null)
        && builtins.isString (data.project.content or null)
        && data.project ? version
        && (data.project.version == null || builtins.isString data.project.version)
        && data.project ? executable
        && (data.project.executable == null || builtins.isString data.project.executable)
        && builtins.isList (data.project.dependencies or null)
      )
    )
    && builtins.isAttrs (data.inputs or null)
    &&
      builtins.attrNames data.inputs == builtins.sort builtins.lessThan (
        lib.unique (
          data.extraInputs
          ++ lib.optional (data.project != null) data.project.ipkg
          ++ lib.optional (builtins.pathExists (src + "/pack.toml")) "pack.toml"
        )
      )
    && builtins.all (
      name:
      relative name
      && builtins.pathExists (src + "/${name}")
      && builtins.isAttrs data.inputs.${name}
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
    ) (builtins.attrNames data.inputs)
    && (
      data.project == null
      || builtins.hashString "sha256" data.project.content == data.inputs.${data.project.ipkg}.sha256
    )
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isAttrs (e.git or null)
      && builtins.isString (e.git.url or null)
      && commit (e.git.rev or null)
      && (e.git.submodules or null) == false
      && (e.git.leaveDotGit or null) == false
      && (e.git.commitObject or null) == null
    ) entries
    && entryFor data.compiler
    && builtins.isList nodes
    && (
      data.project == null
      || builtins.all (name: builtins.any (node: node.name == name) nodes) data.project.dependencies
    )
    && builtins.all (
      n:
      builtins.isAttrs n
      && safe (n.name or null)
      && builtins.isString (n.package or null)
      && n ? version
      && (n.version == null || builtins.isString n.version)
      && builtins.isString (n.content or null)
      && builtins.isString (n.hash or null)
      && builtins.match "[a-f0-9]{32}|[a-f0-9]{40}" n.hash != null
      && builtins.isList (n.dependencies or null)
      && builtins.all (d: builtins.any (other: other.name == d) nodes) n.dependencies
      && (
        (n.type or null) == "core"
        && builtins.elem n.name [
          "prelude"
          "base"
          "linear"
          "network"
          "contrib"
          "test"
        ]
        ||
          (n.type or null) == "git"
          && builtins.isString (n.url or null)
          && relative (n.ipkg or null)
          && commit (n.rev or null)
          && (n.entry or null) == "sources/${n.name}"
          && entryFor n
      )
    ) nodes
    && builtins.length entries == 1 + builtins.length (builtins.filter (n: n.type == "git") nodes)
    && builtins.length (lib.unique (map (n: n.name) nodes)) == builtins.length nodes
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries;
in
{
  purifier = "idris2";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Idris lock is missing, stale or unsupported; run idris2-purifier lock --update";
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
