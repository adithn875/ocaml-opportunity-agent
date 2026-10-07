let weight = function
  | Signal.OxCaml -> 35
  | Signal.Ocaml -> 30
  | Signal.Compiler -> 25
  | Signal.Dune -> 15
  | Signal.Opam -> 15
  | Signal.Functional_programming -> 15
  | Signal.Programming_languages -> 15
  | Signal.Type_systems -> 15
  | Signal.Static_analysis -> 15
  | Signal.Formal_verification -> 15
  | Signal.Formal_methods -> 15
  | Signal.Ocaml_ecosystem -> 15

let total signals =
  List.fold_left
    (fun score signal -> score + weight signal)
    0
    signals

let breakdown signals =
  List.map (fun signal -> (signal, weight signal)) signals
