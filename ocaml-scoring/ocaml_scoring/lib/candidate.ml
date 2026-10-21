
type input = {
  title : string;
  score : float;
  description : string option;
  source : string option;
}

type decision = {
  accepted : bool;
  reason : string;
  title_signals : string list;
}

let threshold = 30.0

let contains text phrase =
  let text = String.lowercase_ascii text in
  let phrase = String.lowercase_ascii phrase in
  try
    ignore (Str.search_forward (Str.regexp_string phrase) text 0);
    true
  with Not_found -> false

let strong_title_signals =
  [
    ("OCaml", "ocaml");
    ("OxCaml", "oxcaml");
    ("Compiler", "compiler");
    ("Compilation", "compilation");
    ("Dune", "dune");
    ("opam", "opam");
    ("Functional programming", "functional programming");
    ("Programming languages", "programming language");
    ("Type systems", "type system");
    ("Static analysis", "static analysis");
    ("Formal verification", "formal verification");
    ("Formal methods", "formal methods");
    ("OCaml ecosystem", "ocaml ecosystem");
  ]

let title_signals title =
  let title = Option.value title ~default:"" in
  List.filter_map
    (fun (name, phrase) ->
      if contains title phrase then Some name else None)
    strong_title_signals

let has_description = function
  | Some description -> String.trim description <> ""
  | None -> false

let is_non_opportunity_title title =
  let title = String.lowercase_ascii (String.trim title) in
  let starts_with prefix =
    String.length title >= String.length prefix
    && String.sub title 0 (String.length prefix) = prefix
  in
  starts_with "[ann]"
  || starts_with "awesome "
  || title = "spontaneous application"
  || starts_with "available for hire"

let decide job =
  let signals = title_signals (Some job.title) in
  let source =
    job.source
    |> Option.value ~default:""
    |> String.trim
    |> String.lowercase_ascii
  in
  let description_present = has_description job.description in
  let accept reason =
    { accepted = true; reason; title_signals = signals }
  in
  let reject reason =
    { accepted = false; reason; title_signals = signals }
  in
  if is_non_opportunity_title job.title then
    reject "title identifies an announcement or aggregate job list"
  else if source = "jane street" || source = "ocaml discuss jobs" then
    if description_present then
      accept (source ^ " listing has a description for LLM review")
    else
      reject (source ^ " listing has no description")
  else if source = "ocaml.org jobs" then
    accept "OCaml.org Jobs listing eligible for LLM review"
  else if signals <> [] then
    accept
      ("explicit OCaml-relevant title signal: " ^ String.concat ", " signals)
  else if job.score >= threshold && description_present then
    accept
      (Printf.sprintf
         "score %g meets the %.0f-point threshold with a source description"
         job.score threshold)
  else if job.score >= threshold then
    reject
      (Printf.sprintf
         "score %g has no description or explicit OCaml-relevant title signal"
         job.score)
  else if job.score > 0.0 then
    reject
      (Printf.sprintf
         "score %g is below the %.0f-point threshold without an explicit title signal"
         job.score threshold)
  else
    reject "no deterministic OCaml-relevance evidence"
