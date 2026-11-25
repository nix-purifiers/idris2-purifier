module Main

import Data.Refined.Nat

%foreign "javascript:lambda: x => { const value = Number(x); globalThis.purifierAnswer = value; if (typeof document !== 'undefined') document.body.dataset.answer = String(value); }"
prim__publish : Int -> PrimIO ()

main : IO ()
main = case hdec0 {a=Nat} {p=IsSucc} 43 of
  Just0 _ => primIO (prim__publish 43)
  Nothing0 => primIO (prim__publish 0)
