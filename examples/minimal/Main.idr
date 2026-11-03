module Main

import Data.Refined.Nat
import System

answer : Nat
answer = 42

main : IO ()
main = case hdec0 {a=Nat} {p=IsSucc} answer of
  Just0 _ => printLn answer
  Nothing0 => die "Refined native proof failed"
