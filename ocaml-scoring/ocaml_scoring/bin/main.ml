
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


let json_fields = function
  | `Assoc fields -> fields
  | _ -> invalid_arg "candidate input must be a JSON object"

let json_optional_string fields name =
  match List.assoc_opt name fields with
  | None | Some `Null -> None
  | Some (`String value) -> Some value
  | Some _ -> invalid_arg ("candidate " ^ name ^ " must be a string or null")

let json_title fields =
  match json_optional_string fields "title" with
  | Some title -> title
  | None -> ""

let json_score fields =
  let score =
    match List.assoc_opt "score" fields with
    | None | Some `Null -> 0.0
    | Some (`Int value) -> float_of_int value
    | Some (`Float value) -> value
    | Some _ -> invalid_arg "candidate score must be a finite number or null"
  in
  match classify_float score with
  | FP_nan | FP_infinite ->
      invalid_arg "candidate score must be a finite number or null"
  | FP_normal | FP_subnormal | FP_zero -> score

let json_mode () = Array.exists (( = ) "--json") Sys.argv

let json_required_score fields name =
  match List.assoc_opt name fields with
  | Some (`Int value) -> float_of_int value
  | Some (`Float value) -> value
  | None -> invalid_arg ("final ranking input is missing " ^ name)
  | Some _ ->
      invalid_arg
        ("final ranking " ^ name ^ " must be a finite number")

let evaluate_candidate_mode () =
  let line =
    match read_line_option () with
    | Some line -> line
    | None -> invalid_arg "expected one JSON candidate input line"
  in
  let input =
    try Yojson.Basic.from_string line
    with Yojson.Json_error message -> invalid_arg ("invalid JSON: " ^ message)
  in
  let fields = json_fields input in
  let candidate =
    Ocaml_scoring.Candidate.
      {
        title = json_title fields;
        score = json_score fields;
        description = json_optional_string fields "description";
        source = json_optional_string fields "source";
      }
  in
  let decision = Ocaml_scoring.Candidate.decide candidate in
  let output =
    `Assoc
      [
        ("accepted", `Bool decision.accepted);
        ("reason", `String decision.reason);
        ( "title_signals",
          `List (List.map (fun signal -> `String signal) decision.title_signals) );
      ]
  in
  print_endline (Yojson.Basic.to_string output)

let calculate_final_score_mode () =
  let line =
    match read_line_option () with
    | Some line -> line
    | None -> invalid_arg "expected one JSON final-ranking input line"
  in
  let input =
    try Yojson.Basic.from_string line
    with Yojson.Json_error message -> invalid_arg ("invalid JSON: " ^ message)
  in
  let fields = json_fields input in
  let technical_score = json_required_score fields "technical_score" in
  let practicality_score = json_required_score fields "practicality_score" in
  let final_score =
    Ocaml_scoring.Final_ranking.calculate
      ~technical_score ~practicality_score
  in
  (* %.17g preserves the IEEE-754 value when Python parses this JSON number. *)
  Printf.printf "{\"final_score\":%.17g}\n%!" final_score

let scoring_mode () =
  let title =
    match read_line_option () with
    | Some value -> value
    | None -> "Unknown job"
  in
  let company = read_line_option () in
  let location = read_line_option () in
  let description = read_line_option () in

  let job =
    Ocaml_scoring.Job.{ title; company; description; location }
  in
  let signals = Ocaml_scoring.Detect.detect job in
  let score = Ocaml_scoring.Scoring.total signals in
  let breakdown = Ocaml_scoring.Scoring.breakdown signals in

  if json_mode () then
    let json =
      `Assoc
        [
          ("title", `String job.title);
          ("score", `Int score);
          ( "signals",
            `List
              (List.map
                 (fun (signal, points) ->
                   `Assoc
                     [
                       ("name", `String (signal_name signal));
                       ("weight", `Int points);
                     ])
                 breakdown) );
        ]
    in
    print_endline (Yojson.Basic.to_string json)
  else (
    Printf.printf "Job: %s\n" job.title;
    Printf.printf "Score: %d\n" score;
    Printf.printf "Signals:\n";
    List.iter
      (fun (signal, points) ->
        Printf.printf "  +%d %s\n" points (signal_name signal))
      breakdown)

let () =
  if Array.exists (( = ) "--evaluate-candidate") Sys.argv then
    (try evaluate_candidate_mode () with
    | Invalid_argument message ->
        prerr_endline ("candidate evaluator input error: " ^ message);
        exit 2)
  else if Array.exists (( = ) "--calculate-final-score") Sys.argv then
    (try calculate_final_score_mode () with
    | Invalid_argument message ->
        prerr_endline ("final ranking input error: " ^ message);
        exit 2)
  else
    scoring_mode ()
