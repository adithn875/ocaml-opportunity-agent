
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

let test_candidate title score description source expected =
  let input =
    Ocaml_scoring.Candidate.
      { title; score; description; source }
  in
  let decision = Ocaml_scoring.Candidate.decide input in
  Printf.printf "Candidate: %s -> %b\n" title decision.accepted;
  assert (decision.accepted = expected)

let test_candidate_details title score description source expected reason signals =
  let input =
    Ocaml_scoring.Candidate.
      { title; score; description; source }
  in
  let decision = Ocaml_scoring.Candidate.decide input in
  assert (decision.accepted = expected);
  assert (decision.reason = reason);
  assert (decision.title_signals = signals)

let test_candidates () =
  (* Explicit title signal: accepted even with a low score. *)
  test_candidate "Compiler Engineer" 25.0
    (Some "Build language tooling.") None true;

  (* Generic title with no score evidence: rejected. *)
  test_candidate "Frontend Engineer" 0.0
    (Some "Build web applications.") None false;

  (* Score threshold requires a description. *)
  test_candidate "Research Engineer" 45.0
    (Some "Work on static analysis tooling in OCaml.") None true;

  test_candidate "Software Engineer" 30.0
    None None false;

  (* Source-specific rules. *)
  test_candidate "Software Engineer Internship" 0.0
    (Some "Build software and solve technical problems.")
    (Some "Jane Street") true;

  test_candidate "Front End Software Engineer" 0.0
    None (Some "Jane Street") false;

  test_candidate "Research Internship" 0.0
    (Some "Work on OCaml and formal verification.")
    (Some "OCaml Discuss Jobs") true;

  test_candidate "Cryptography Engineer" 0.0
    None (Some "OCaml.org jobs") true;

  (* Announcement and aggregate-list titles take priority. *)
  test_candidate "[ANN] HOL Light released to OPAM" 15.0
    (Some "A package announcement.") None false;

  test_candidate "Spontaneous Application" 30.0
    None (Some "OCaml.org jobs") false;

  test_candidate "Awesome Functional Programming Jobs" 15.0
    (Some "A list of jobs.") (Some "OCaml Discuss Jobs") false;

  (* Additional title signal. *)
  test_candidate "OCaml Developer" 0.0 None None true;

  (* Score boundaries, empty values, and stable title-signal ordering. *)
  test_candidate_details "Research Engineer" 29.0 (Some "Description") None
    false
    "score 29 is below the 30-point threshold without an explicit title signal"
    [];

  test_candidate_details "Research Engineer" 30.0 (Some "  Description  ") None
    true "score 30 meets the 30-point threshold with a source description" [];

  test_candidate_details "" 0.0 (Some "   ") None false
    "no deterministic OCaml-relevance evidence" [];

  test_candidate_details "OCaml Compiler Formal Methods Engineer" 0.0 None None
    true
    "explicit OCaml-relevant title signal: OCaml, Compiler, Formal methods"
    [ "OCaml"; "Compiler"; "Formal methods" ];

  test_candidate_details "Available for Hire: OCaml engineer" 100.0
    (Some "A profile, not an opening.") (Some "OCaml.org jobs") false
    "title identifies an announcement or aggregate job list" [ "OCaml" ];

  print_endline "All candidate tests passed!"

let raises_invalid_argument callback =
  match callback () with
  | exception Invalid_argument _ -> true
  | _ -> false

let test_final_ranking () =
  let calculate = Ocaml_scoring.Final_ranking.calculate in
  assert (calculate ~technical_score:95.0 ~practicality_score:70.0 = 87.5);
  assert
    (calculate ~technical_score:1.0 ~practicality_score:2.0
    = 1.2999999999999998);
  assert (calculate ~technical_score:0.0 ~practicality_score:100.0 = 30.0);
  assert (calculate ~technical_score:100.0 ~practicality_score:0.0 = 70.0);
  assert
    (raises_invalid_argument (fun () ->
         calculate ~technical_score:(-0.1) ~practicality_score:70.0));
  assert
    (raises_invalid_argument (fun () ->
         calculate ~technical_score:70.0 ~practicality_score:100.1));
  print_endline "All final-ranking tests passed!"

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

  print_endline "All scoring tests passed!";
  test_candidates ();
  test_final_ranking ()
