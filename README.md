# idris2-purifier

Locked, Nix-resolved Idris libraries for Pack.

## Quickstart

```sh
nix shell 'github:nix-purifiers/idris2-purifier'
idris2-purifier lock
pack build
```

Pack's native resolver reads the project's `.ipkg` and `pack.toml`, selects its
curated collection and dependencies, and records exact Git revisions. Nix builds
that collection's compiler and libraries. Your project builds in its working tree.

The shell provides `pack`, `idris2` and `idris2-lsp` wrappers. Without a lockfile,
they warn and run their ordinary, impure tools. Invalid or stale locks fail.
The wrappers can also be installed through your normal Nix configuration.

Commit `idris2-purifier.lock.json`. Source edits do not require relocking;
selection metadata changes do:

```sh
idris2-purifier lock --update
pack build
```

Use `--ipkg path` to select a package explicitly. A project without an `.ipkg`
can select libraries directly:

```sh
idris2-purifier lock refined
idris2 -p refined --check Main.idr
```

## Development

```sh
pack run
idris2 --build proof.ipkg
idris2 --list-packages
idris2-lsp
```

Use your project's package filename in the compiler command. Pack keeps its own
mutable project builds and installation state private under `.idris2-purifier/`.
Prepared dependencies, sources and compiler remain readonly in Nix. The native
language server can navigate into those library sources.

Library projects can use `pack test library-name` with their native Pack test
configuration. Track the test `.ipkg` with `--input` when creating the lock.

Locked tools do not load packages from a local `depends/` cache. Missing cached
dependency metadata and attempts to fetch new dependencies fail before Git
transport. Add them to the lock instead. The selected root project remains a
mutable local package; other local dependency projects are not supported yet.

## Lock and environment

The lock includes original `.ipkg` contents and native dependency edges,
installation hashes, collection and compiler selection, source hashes, and
selection inputs. Native metadata is checked again during Nix compilation.
The initial frontend supports Idris 0.8.0, TTC ABI 2025081600 and the six standard
runtime core libraries on Linux. Compiler API and papers core packages are
outside this initial integration. Automatic dependency applications and
documentation installation are also unsupported.

```sh
idris2-purifier prefetch
idris2-purifier exec -- your-command
```

`--input path` tracks additional selection files. Use `--project` and `--lock`
for an external companion; native tools accept `IDRIS2_PURIFIER_PROJECT` and
`IDRIS2_PURIFIER_LOCK`. Ancestor Pack configurations are selection inputs too.
Environment generations keep their compiler, libraries and frontend SDK rooted
for Nix garbage collection while older sessions remain active.

## Publication

```sh
idris2-purifier bundle
idris2-purifier publish --tag v0.1.0
```

The reproducible source archive contains the native `.ipkg` and can be built
by an ordinary Idris/Pack consumer. Publication uploads the exact realized bytes
to an existing GitHub release.

## Building with Nix

An optional definition can use the overlay's named builder:

```nix
pkgs.idris2-purifier.buildIdrisProject {
  src = ./.;
  doCheck = true;
  checkCommand = "./build/exec/proof";
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`libraryOverrides` provides library-specific build changes.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
