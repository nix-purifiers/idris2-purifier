final: prev: {
  idris2-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
