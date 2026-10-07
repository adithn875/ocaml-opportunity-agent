let contains text keyword =
  let text = String.lowercase_ascii text in
  let keyword = String.lowercase_ascii keyword in
  try
    ignore (Str.search_forward (Str.regexp_string keyword) text 0);
    true
  with Not_found -> false

let detect job =
  let text =
    String.concat " "
      [
        job.Job.title;
        Option.value job.Job.company ~default:"";
        Option.value job.Job.description ~default:"";
      ]
    |> String.lowercase_ascii
  in

  let signals = ref [] in

  if contains text "ocaml" then
    signals := Signal.Ocaml :: !signals;

  if contains text "oxcaml" then
    signals := Signal.OxCaml :: !signals;

  if contains text "compiler" then
    signals := Signal.Compiler :: !signals;

  if contains text "dune" then
    signals := Signal.Dune :: !signals;

  if contains text "opam" then
    signals := Signal.Opam :: !signals;

  if contains text "functional programming" then
    signals := Signal.Functional_programming :: !signals;

  if contains text "programming language" then
    signals := Signal.Programming_languages :: !signals;

  if contains text "type system" then
    signals := Signal.Type_systems :: !signals;

  if contains text "static analysis" then
    signals := Signal.Static_analysis :: !signals;

  if contains text "formal verification" then
    signals := Signal.Formal_verification :: !signals;

  if contains text "formal methods" then
    signals := Signal.Formal_methods :: !signals;

  if contains text "ocaml ecosystem" then
    signals := Signal.Ocaml_ecosystem :: !signals;

  !signals
