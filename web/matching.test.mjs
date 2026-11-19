import assert from "node:assert/strict";
import test from "node:test";

import { matchJob } from "./matching.js";

const job = {
  title: "OCaml Compiler Engineer",
  description: "Build compiler tooling and static analysis.",
  location: "Paris, France",
  remote: "remote-worldwide",
  final_score: 70,
};

test("personalized matches raise the score and explain why", () => {
  const result = matchJob(job, {
    skills: ["OCaml", "compiler"],
    locations: ["Paris"],
    remote_preference: "remote",
  });

  assert.equal(result.score, 92);
  assert.deepEqual(result.reasons, [
    "Matches skills: ocaml, compiler",
    "Matches a preferred location",
    "Matches remote preference",
  ]);
});

test("not relevant feedback lowers the personalized score", () => {
  const result = matchJob(job, { skills: [] }, "not_relevant");

  assert.equal(result.score, 40);
  assert.deepEqual(result.reasons, ["Marked not relevant"]);
});
