let signal_name = function
  | Ocaml_scoring.Signal.Ocaml -> "OCaml"
  | Ocaml_scoring.Signal.OxCaml -> "OxCaml"
  | Ocaml_scoring.Signal.Compiler -> "Compiler"
  | Ocaml_scoring.Signal.Dune -> "Dune"
  | Ocaml_scoring.Signal.Opam -> "opam"
  | Ocaml_scoring.Signal.Functional_programming -> "Functional programming"
  | Ocaml_scoring.Signal.Programming_languages -> "Programming languages"
  | Ocaml_scoring.Signal.Type_systems -> "Type systems"
  | Ocaml_scoring.Signal.Static_analysis -> "Static analysis"
  | Ocaml_scoring.Signal.Formal_verification -> "Formal verification"
  | Ocaml_scoring.Signal.Formal_methods -> "Formal methods"
  | Ocaml_scoring.Signal.Ocaml_ecosystem -> "OCaml ecosystem"

let read_line_option () =
  match read_line () with
  | line -> if line = "" then None else Some line
  | exception End_of_file -> None

let () =
  let title =
    match read_line_option () with
    | Some value -> value
    | None -> "Unknown job"
  in

  let company = read_line_option () in
  let location = read_line_option () in
  let description = read_line_option () in

  let job =
    Ocaml_scoring.Job.
      {
        title;
        company;
        description;
        location;
      }
  in

  let signals = Ocaml_scoring.Detect.detect job in
  let score = Ocaml_scoring.Scoring.total signals in
  let breakdown = Ocaml_scoring.Scoring.breakdown signals in

  Printf.printf "Job: %s\n" job.title;
  Printf.printf "Score: %d\n" score;
  Printf.printf "Signals:\n";

  List.iter
    (fun (signal, points) ->
      Printf.printf "  +%d %s\n" points (signal_name signal))
    breakdown
