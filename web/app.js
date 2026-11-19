import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

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

let client;
let jobs = [];
let savedJobIds = new Set();
let user = null;

function setMessage(text) {
  message.textContent = text;
}

function jobScore(job) {
  return job.final_score ?? job.llm_score ?? job.deterministic_score ?? 0;
}

function filteredJobs() {
  const query = queryFilter.value.trim().toLowerCase();
  const source = sourceFilter.value;
  const minimumScore = Number(scoreFilter.value) || 0;

  return jobs.filter((job) => {
    const searchable = [job.title, job.company, job.description, job.location]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return (
      (!query || searchable.includes(query)) &&
      (!source || job.source === source) &&
      jobScore(job) >= minimumScore &&
      (!savedFilter.checked || savedJobIds.has(job.id))
    );
  });
}

function renderJobs() {
  const matches = filteredJobs();
  jobsElement.replaceChildren();

  if (!matches.length) {
    jobsElement.textContent = "No jobs match these filters.";
    return;
  }

  for (const job of matches) {
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
    score.textContent = `Match score: ${jobScore(job).toFixed(0)}`;

    const save = document.createElement("button");
    const isSaved = savedJobIds.has(job.id);
    save.textContent = isSaved ? "Saved" : "Save job";
    save.disabled = !user;
    save.addEventListener("click", () => toggleSavedJob(job.id));

    article.append(title, details, score, save);
    jobsElement.append(article);
  }
}

function populateSources() {
  const selectedSource = sourceFilter.value;
  const sources = [...new Set(jobs.map((job) => job.source).filter(Boolean))].sort();
  sourceFilter.replaceChildren(new Option("All sources", ""));
  for (const source of sources) {
    sourceFilter.append(new Option(source, source));
  }
  sourceFilter.value = selectedSource;
}

async function loadJobs() {
  const { data, error } = await client
    .from("jobs")
    .select("*")
    .order("final_score", { ascending: false, nullsFirst: false });

  if (error) {
    setMessage(`Could not load jobs: ${error.message}`);
    return;
  }

  jobs = data;
  populateSources();
  renderJobs();
  setMessage(`${jobs.length} opportunities loaded.`);
}

async function loadSavedJobs() {
  savedJobIds = new Set();
  if (!user) {
    renderJobs();
    return;
  }

  const { data, error } = await client.from("saved_jobs").select("job_id");
  if (error) {
    setMessage(`Could not load saved jobs: ${error.message}`);
    return;
  }
  savedJobIds = new Set(data.map((row) => row.job_id));
  renderJobs();
}

async function toggleSavedJob(jobId) {
  if (!user) {
    setMessage("Sign in to save jobs.");
    return;
  }

  const saved = savedJobIds.has(jobId);
  const query = saved
    ? client.from("saved_jobs").delete().eq("job_id", jobId)
    : client.from("saved_jobs").insert({ user_id: user.id, job_id: jobId });
  const { error } = await query;

  if (error) {
    setMessage(`Could not update saved jobs: ${error.message}`);
    return;
  }
  if (saved) savedJobIds.delete(jobId);
  else savedJobIds.add(jobId);
  renderJobs();
}

async function loadAlertPreferences() {
  if (!user) return;
  const { data, error } = await client
    .from("alert_preferences")
    .select("minimum_score, frequency")
    .maybeSingle();
  if (error) {
    setMessage(`Could not load alert preferences: ${error.message}`);
    return;
  }
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
  await loadSavedJobs();
  if (user) await loadAlertPreferences();
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

document.querySelector("#alert-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const { error } = await client.from("alert_preferences").upsert({
    user_id: user.id,
    minimum_score: Number(document.querySelector("#alert-score").value),
    frequency: document.querySelector("#alert-frequency").value,
  });
  setMessage(error ? error.message : "Alert preferences saved.");
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
