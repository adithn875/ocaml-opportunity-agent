import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { matchJob } from "./matching.js";

const config = window.OPPORTUNITY_AGENT_CONFIG;
const message = document.querySelector("#message");
const jobsElement = document.querySelector("#jobs");
const sourceFilter = document.querySelector("#source-filter");
const queryFilter = document.querySelector("#query");
const scoreFilter = document.querySelector("#score-filter");
const savedFilter = document.querySelector("#saved-filter");
const authStatus = document.querySelector("#auth-status");
const authForm = document.querySelector("#auth-form");
const signUpButton = document.querySelector("#sign-up");
const signOutButton = document.querySelector("#sign-out");
const alerts = document.querySelector("#alerts");
const profileSection = document.querySelector("#profile");
const submissionSection = document.querySelector("#submission");

let client;
let jobs = [];
let savedJobIds = new Set();
let feedbackByJob = new Map();
let applicationsByJob = new Map();
let profile = null;
let user = null;

function setMessage(text) {
  message.textContent = text;
}

function csvValues(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function personalized(job) {
  return matchJob(job, profile, feedbackByJob.get(job.id));
}

function filteredJobs() {
  const query = queryFilter.value.trim().toLowerCase();
  const source = sourceFilter.value;
  const profileMinimum = Number(profile?.minimum_score) || 0;
  const minimumScore = Math.max(Number(scoreFilter.value) || 0, profileMinimum);

  return jobs.filter((job) => {
    const searchable = [job.title, job.company, job.description, job.location]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return (
      (!query || searchable.includes(query)) &&
      (!source || job.source === source) &&
      personalized(job).score >= minimumScore &&
      (!savedFilter.checked || savedJobIds.has(job.id))
    );
  });
}

function actionButton(text, disabled, onClick) {
  const button = document.createElement("button");
  button.textContent = text;
  button.disabled = disabled;
  button.addEventListener("click", onClick);
  return button;
}

function applicationSelect(jobId) {
  const select = document.createElement("select");
  const statuses = ["", "interested", "applied", "interviewing", "rejected"];
  for (const status of statuses) {
    select.append(new Option(status || "Track application", status));
  }
  select.value = applicationsByJob.get(jobId) || "";
  select.disabled = !user;
  select.addEventListener("change", () => updateApplication(jobId, select.value));
  return select;
}

function renderJobs() {
  const matches = filteredJobs();
  jobsElement.replaceChildren();

  if (!matches.length) {
    jobsElement.textContent = "No jobs match these filters.";
    return;
  }

  for (const job of matches) {
    const match = personalized(job);
    const article = document.createElement("article");
    const title = document.createElement("h2");
    const link = document.createElement("a");
    link.href = job.source_url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = job.title;
    title.append(link);

    const details = document.createElement("p");
    details.textContent = [job.company, job.location, job.source]
      .filter(Boolean)
      .join(" · ");

    const score = document.createElement("p");
    score.className = "score";
    score.textContent = `Personalized match: ${match.score.toFixed(0)}`;

    const explanation = document.createElement("p");
    explanation.className = "explanation";
    explanation.textContent = match.reasons.join(" · ");

    const actions = document.createElement("div");
    actions.className = "job-actions";
    const saved = savedJobIds.has(job.id);
    actions.append(
      actionButton(saved ? "Saved" : "Save job", !user, () => toggleSavedJob(job.id)),
      actionButton("Interested", !user, () => updateFeedback(job.id, "interested")),
      actionButton("Not relevant", !user, () => updateFeedback(job.id, "not_relevant")),
      applicationSelect(job.id),
    );

    article.append(title, details, score, explanation, actions);
    jobsElement.append(article);
  }
}

function populateSources() {
  const selectedSource = sourceFilter.value;
  const sources = [...new Set(jobs.map((job) => job.source).filter(Boolean))].sort();
  sourceFilter.replaceChildren(new Option("All sources", ""));
  for (const source of sources) sourceFilter.append(new Option(source, source));
  sourceFilter.value = selectedSource;
}

async function loadJobs() {
  const { data, error } = await client
    .from("jobs")
    .select("*")
    .order("final_score", { ascending: false, nullsFirst: false });
  if (error) return setMessage(`Could not load jobs: ${error.message}`);
  jobs = data;
  populateSources();
  renderJobs();
  setMessage(`${jobs.length} opportunities loaded.`);
}

async function loadUserData() {
  savedJobIds = new Set();
  feedbackByJob = new Map();
  applicationsByJob = new Map();
  profile = null;
  if (!user) return;

  const [saved, feedback, applications, profileResult] = await Promise.all([
    client.from("saved_jobs").select("job_id"),
    client.from("job_feedback").select("job_id, label"),
    client.from("job_applications").select("job_id, status"),
    client.from("user_profiles").select("*").maybeSingle(),
  ]);
  const failed = [saved, feedback, applications, profileResult].find((result) => result.error);
  if (failed) return setMessage(`Could not load account data: ${failed.error.message}`);

  savedJobIds = new Set(saved.data.map((row) => row.job_id));
  feedbackByJob = new Map(feedback.data.map((row) => [row.job_id, row.label]));
  applicationsByJob = new Map(applications.data.map((row) => [row.job_id, row.status]));
  profile = profileResult.data;
  if (profile) {
    document.querySelector("#profile-skills").value = profile.skills.join(", ");
    document.querySelector("#profile-locations").value = profile.locations.join(", ");
    document.querySelector("#profile-remote").value = profile.remote_preference;
    document.querySelector("#profile-score").value = profile.minimum_score;
  } else {
    document.querySelector("#profile-form").reset();
  }
}

async function toggleSavedJob(jobId) {
  const saved = savedJobIds.has(jobId);
  const query = saved
    ? client.from("saved_jobs").delete().eq("job_id", jobId)
    : client.from("saved_jobs").insert({ user_id: user.id, job_id: jobId });
  const { error } = await query;
  if (error) return setMessage(`Could not update saved jobs: ${error.message}`);
  if (saved) savedJobIds.delete(jobId);
  else savedJobIds.add(jobId);
  renderJobs();
}

async function updateFeedback(jobId, label) {
  const { error } = await client.from("job_feedback").upsert({
    user_id: user.id,
    job_id: jobId,
    label,
  });
  if (error) return setMessage(`Could not save feedback: ${error.message}`);
  feedbackByJob.set(jobId, label);
  renderJobs();
}

async function updateApplication(jobId, status) {
  const query = status
    ? client.from("job_applications").upsert({ user_id: user.id, job_id: jobId, status })
    : client.from("job_applications").delete().eq("job_id", jobId);
  const { error } = await query;
  if (error) return setMessage(`Could not update application: ${error.message}`);
  if (status) applicationsByJob.set(jobId, status);
  else applicationsByJob.delete(jobId);
  renderJobs();
}

async function loadAlertPreferences() {
  if (!user) return;
  const { data, error } = await client
    .from("alert_preferences")
    .select("minimum_score, frequency")
    .maybeSingle();
  if (error) return setMessage(`Could not load alert preferences: ${error.message}`);
  if (data) {
    document.querySelector("#alert-score").value = data.minimum_score;
    document.querySelector("#alert-frequency").value = data.frequency;
  }
}

async function updateSession(session) {
  user = session?.user ?? null;
  authStatus.textContent = user ? `Signed in as ${user.email}` : "Not signed in";
  authForm.hidden = Boolean(user);
  signOutButton.hidden = !user;
  alerts.hidden = !user;
  profileSection.hidden = !user;
  submissionSection.hidden = !user;
  await Promise.all([loadUserData(), loadAlertPreferences()]);
  renderJobs();
}

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.querySelector("#email").value;
  const password = document.querySelector("#password").value;
  const { error } = await client.auth.signInWithPassword({ email, password });
  setMessage(error ? error.message : "Signed in.");
});

signUpButton.addEventListener("click", async () => {
  const email = document.querySelector("#email").value;
  const password = document.querySelector("#password").value;
  const { error } = await client.auth.signUp({ email, password });
  setMessage(error ? error.message : "Check your email to confirm your account.");
});

signOutButton.addEventListener("click", async () => {
  const { error } = await client.auth.signOut();
  setMessage(error ? error.message : "Signed out.");
});

document.querySelector("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const { error } = await client.from("user_profiles").upsert({
    user_id: user.id,
    skills: csvValues(document.querySelector("#profile-skills").value),
    locations: csvValues(document.querySelector("#profile-locations").value),
    remote_preference: document.querySelector("#profile-remote").value,
    minimum_score: Number(document.querySelector("#profile-score").value),
  });
  if (error) return setMessage(`Could not save profile: ${error.message}`);
  await loadUserData();
  renderJobs();
  setMessage("Matching profile saved.");
});

document.querySelector("#alert-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const { error } = await client.from("alert_preferences").upsert({
    user_id: user.id,
    minimum_score: Number(document.querySelector("#alert-score").value),
    frequency: document.querySelector("#alert-frequency").value,
  });
  setMessage(error ? error.message : "Alert preferences saved.");
});

document.querySelector("#submission-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const { error } = await client.from("employer_submissions").insert({
    title: document.querySelector("#submission-title").value,
    company: document.querySelector("#submission-company").value,
    source_url: document.querySelector("#submission-url").value,
    location: document.querySelector("#submission-location").value || null,
    description: document.querySelector("#submission-description").value || null,
  });
  if (error) return setMessage(`Could not submit opportunity: ${error.message}`);
  event.target.reset();
  setMessage("Submitted for review.");
});

for (const element of [queryFilter, sourceFilter, scoreFilter, savedFilter]) {
  element.addEventListener("input", renderJobs);
  element.addEventListener("change", renderJobs);
}

if (!config?.supabaseUrl || !config?.supabasePublishableKey) {
  authForm.hidden = true;
  setMessage("Configure web/config.js with Supabase project values to load jobs.");
} else {
  client = createClient(config.supabaseUrl, config.supabasePublishableKey);
  client.auth.onAuthStateChange((_, session) => updateSession(session));
  const { data } = await client.auth.getSession();
  await updateSession(data.session);
  await loadJobs();
}
