let technical_weight = 0.70
let practicality_weight = 0.30

let validate_score name score =
  match classify_float score with
  | FP_nan | FP_infinite ->
      invalid_arg (name ^ " must be between 0 and 100")
  | FP_normal | FP_subnormal | FP_zero ->
      if score < 0.0 || score > 100.0 then
        invalid_arg (name ^ " must be between 0 and 100")

let calculate ~technical_score ~practicality_score =
  validate_score "technical_score" technical_score;
  validate_score "practicality_score" practicality_score;
  (* Keep the two multiplications as distinct rounding steps, matching Python. *)
  let technical_component = technical_weight *. technical_score in
  let practicality_component = practicality_weight *. practicality_score in
  technical_component +. practicality_component
