function normalizedTerms(values) {
  return (values || [])
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
}

export function matchJob(job, profile, feedbackLabel) {
  const baseScore = Number(
    job.final_score ?? job.llm_score ?? job.deterministic_score ?? 0,
  );
  const text = [job.title, job.company, job.description, job.location]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const skills = normalizedTerms(profile?.skills);
  const locations = normalizedTerms(profile?.locations);
  const matchingSkills = skills.filter((skill) => text.includes(skill));
  const reasons = [];
  let score = baseScore;

  if (matchingSkills.length) {
    score += Math.min(matchingSkills.length * 6, 18);
    reasons.push(`Matches skills: ${matchingSkills.join(", ")}`);
  }

  if (locations.some((location) => (job.location || "").toLowerCase().includes(location))) {
    score += 5;
    reasons.push("Matches a preferred location");
  }

  const isRemote = (job.remote || "").toLowerCase().includes("remote");
  if (profile?.remote_preference === "remote" && isRemote) {
    score += 5;
    reasons.push("Matches remote preference");
  }

  if (feedbackLabel === "interested") {
    score += 8;
    reasons.push("Marked interested");
  }
  if (feedbackLabel === "not_relevant") {
    score -= 30;
    reasons.push("Marked not relevant");
  }

  return {
    score: Math.max(0, Math.min(100, score)),
    reasons: reasons.length ? reasons : ["Base technical ranking"],
  };
}
