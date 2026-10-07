let test_job title description expected_score =
  let job =
    Ocaml_scoring.Job.
      {
        title;
        company = None;
        description = Some description;
        location = None;
      }
  in

  let signals = Ocaml_scoring.Detect.detect job in
  let score = Ocaml_scoring.Scoring.total signals in

  Printf.printf "%s -> %d\n" title score;
  assert (score = expected_score)

let () =
  test_job
    "OCaml Compiler Engineer"
    "Work on the OCaml compiler and functional programming tools."
    70;

  test_job
    "Functional Programming Engineer"
    "Work on programming languages and type systems."
    45;

  test_job
    "Frontend Engineer"
    "Build modern web applications using JavaScript and React."
    0;

  test_job
    "OCaml Ecosystem Engineer"
    "Work with the OCaml ecosystem and tooling."
    45;

  test_job
    "Formal Methods Engineer"
    "Work on formal methods and formal verification."
    30;

  print_endline "All scoring tests passed!"
