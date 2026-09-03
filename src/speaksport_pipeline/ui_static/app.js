const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
  data: { facilities: [], modifications: [], runs: [], jobs: [], tools: [], references: {} },
  runFilter: "all",
  runTarget: null,
  currentJob: null,
  editingFacility: null,
  editingModification: null,
  editingModificationData: null,
  slugTouched: { facility: false, modification: false },
};

const titles = {
  dashboard: ["Workspace", "Prompt operations at a glance"],
  facility: ["Facility builder", "Create a structured facility setup"],
  modification: ["Prompt updates", "Modernize an existing customer prompt"],
  runs: ["Run history", "Review progress and generated artifacts"],
};

const timezones = [
  ["America/New_York", "Eastern — New York"],
  ["America/Chicago", "Central — Chicago"],
  ["America/Denver", "Mountain — Denver"],
  ["America/Phoenix", "Arizona — Phoenix"],
  ["America/Los_Angeles", "Pacific — Los Angeles"],
  ["America/Detroit", "Eastern — Detroit"],
  ["Pacific/Honolulu", "Hawaii — Honolulu"],
];

const capabilityNames = {
  eligibility: "Booking eligibility",
  availability: "Availability search",
  booking: "Book tee times",
  booking_lookup: "Existing bookings",
  cancellation_eligibility: "Cancellation eligibility",
  cancellation: "Cancel reservations",
  transfer: "Call transfer",
  day_of_week: "Date resolution",
  inventory_warmup: "Inventory warm-up",
  weather: "Weather forecast",
  customer_record_lookup: "Customer records",
  identity_confirmation: "Confirm identity",
  sms: "Send SMS",
};

const recommendedIntegrated = new Set([
  "eligibility", "availability", "booking", "booking_lookup", "cancellation_eligibility",
  "cancellation", "transfer", "day_of_week", "inventory_warmup", "weather",
]);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

function slugify(value) {
  return String(value).toLowerCase().trim().replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function lines(value) {
  return String(value || "").split("\n").map((item) => item.trim()).filter(Boolean);
}

function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.className = error ? "show error" : "show";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.className = ""; }, 4200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function go(view) {
  $$(".view").forEach((node) => node.classList.toggle("active", node.id === `view-${view}`));
  $$(".nav-item").forEach((node) => node.classList.toggle("active", node.dataset.view === view));
  $("#view-eyebrow").textContent = titles[view][0];
  $("#view-title").textContent = titles[view][1];
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (view === "runs") renderRuns();
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

function formatCost(value) {
  return value == null ? "—" : `$${Number(value).toFixed(2)}`;
}

function statusPill(item) {
  const outcome = String(item.validation_outcome || item.status || "unknown");
  const tone = /fail|error/i.test(outcome) ? "fail" : /created|running|generated/i.test(outcome) ? "warn" : "";
  return `<span class="pill ${tone}">${escapeHtml(outcome)}</span>`;
}

function runRow(run, full = false) {
  const artifacts = (run.artifacts || []).map((item) => (
    `<a target="_blank" href="/api/file?path=${encodeURIComponent(item.path)}">${escapeHtml(item.name.replace(/\.md$/, ""))}</a>`
  )).join("");
  return `<div class="run-row" data-kind="${escapeHtml(run.kind)}">
    <div class="run-main"><strong>${escapeHtml(run.slug)}</strong><span>${escapeHtml(run.run_id)}</span></div>
    <span>${run.kind === "modification" ? "Prompt update" : "New facility"}</span>
    ${statusPill(run)}
    <span>${formatCost(run.cost_usd)}</span>
    ${full ? `<div class="artifact-links">${artifacts || "No artifacts"}</div>` : `<span>${formatDate(run.created_at)}</span>`}
  </div>`;
}

function renderDashboard() {
  const validRuns = state.data.runs.filter((run) => String(run.validation_outcome).toUpperCase() === "PASS").length;
  const totalCost = state.data.runs.reduce((sum, run) => sum + Number(run.cost_usd || 0), 0);
  const active = state.data.jobs.filter((job) => job.status === "running").length;
  $("#metrics").innerHTML = [
    ["Facilities", state.data.facilities.length, "◇"],
    ["Prompt updates", state.data.modifications.length, "↻"],
    ["Validated runs", validRuns, "✓"],
    ["Active / total cost", `${active} / $${totalCost.toFixed(2)}`, "↗"],
  ].map(([label, value, icon]) => `<div class="metric"><div><span>${label}</span><strong>${value}</strong></div><i>${icon}</i></div>`).join("");

  $("#recent-runs").innerHTML = state.data.runs.length
    ? state.data.runs.slice(0, 6).map((run) => runRow(run)).join("")
    : `<div class="empty">No runs yet. Your first completed pipeline will appear here.</div>`;

  const facilities = state.data.facilities.slice(0, 8).map((item) => entityRow(item, "facility"));
  const modifications = state.data.modifications.slice(0, 4).map((item) => entityRow(item, "modification"));
  $("#facility-list").innerHTML = [...facilities, ...modifications].join("") || `<div class="empty">No saved setups yet.</div>`;
  bindEntityActions();
}

function entityRow(item, kind) {
  const detail = kind === "facility"
    ? `${String(item.tee_sheet || "unspecified").replace("_", " ")} · ${String(item.integration_type || "").replace("_", " ")}`
    : "Prompt modification";
  const edit = kind === "facility"
    ? `<button data-edit-facility="${escapeHtml(item.slug)}">Edit</button>`
    : `<button data-edit-modification="${escapeHtml(item.slug)}">Edit</button>`;
  return `<div class="entity"><span class="entity-mark">${escapeHtml(item.display_name.slice(0, 2).toUpperCase())}</span><div><strong>${escapeHtml(item.display_name)}</strong><small>${escapeHtml(detail)}</small></div>${edit}<button data-run-kind="${kind}" data-run-slug="${escapeHtml(item.slug)}">Run</button></div>`;
}

function bindEntityActions() {
  $$('[data-edit-facility]').forEach((button) => button.onclick = () => editFacility(button.dataset.editFacility));
  $$('[data-edit-modification]').forEach((button) => button.onclick = () => editModification(button.dataset.editModification));
  $$('[data-run-kind]').forEach((button) => button.onclick = () => openRunDialog(button.dataset.runKind, button.dataset.runSlug));
}

function populateTimezones() {
  [$("#facility-timezone"), $("#mod-timezone")].forEach((select) => {
    select.innerHTML = timezones.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
  });
  $("#facility-timezone").value = "America/New_York";
  $("#mod-timezone").value = "America/New_York";
}

function toolCompatible(tool, mode) {
  return (tool.compatible_modes || []).includes(mode);
}

function recommendedToolNames(mode, teeSheet) {
  const capabilities = mode === "integrated" ? new Set(recommendedIntegrated) : new Set(["sms", "transfer", "weather"]);
  if (mode === "integrated" && teeSheet === "club_prophet") {
    capabilities.add("customer_record_lookup");
    capabilities.add("identity_confirmation");
  }
  return new Set(state.data.tools.filter((tool) => toolCompatible(tool, mode) && capabilities.has(tool.capability)).map((tool) => tool.logical_name));
}

function renderTools(containerId, mode, teeSheet, selected = null) {
  const container = $(`#${containerId}`);
  const recommended = selected || recommendedToolNames(mode, teeSheet);
  container.innerHTML = state.data.tools.map((tool) => {
    const compatible = toolCompatible(tool, mode);
    const requiredIdentity = teeSheet === "club_prophet" && ["customer_record_lookup", "identity_confirmation"].includes(tool.capability);
    const checked = compatible && (recommended.has(tool.logical_name) || requiredIdentity);
    return `<label class="tool-option ${compatible ? "" : "disabled"}"><input type="checkbox" value="${escapeHtml(tool.logical_name)}" data-capability="${escapeHtml(tool.capability)}" ${checked ? "checked" : ""} ${!compatible || requiredIdentity ? "disabled" : ""}/><div><strong>${escapeHtml(tool.logical_name)}</strong><small>${escapeHtml(capabilityNames[tool.capability] || tool.capability)}</small></div></label>`;
  }).join("");
}

function selectedTools(containerId) {
  return $$(`#${containerId} input[type=checkbox]`).filter((input) => input.checked).map((input) => input.value);
}

function addDestination(containerId, value = {}) {
  const row = document.createElement("div");
  row.className = "destination-row";
  row.innerHTML = `<label>Identifier<input class="destination-id" required value="${escapeHtml(value.identifier || "")}" placeholder="pro_shop" /></label><label>Display name<input class="destination-name" value="${escapeHtml(value.display_name || "")}" placeholder="Pro Shop" /></label><label>Responsibility<input class="destination-responsibility" required value="${escapeHtml(value.responsibility || "")}" placeholder="Tee times, course conditions, and general golf operations" /></label><button type="button" class="remove-row" aria-label="Remove">×</button>`;
  $(".remove-row", row).onclick = () => row.remove();
  $(`#${containerId}`).append(row);
}

function destinations(containerId) {
  return $$(".destination-row", $(`#${containerId}`)).map((row) => ({
    identifier: $(".destination-id", row).value.trim(),
    display_name: $(".destination-name", row).value.trim() || null,
    responsibility: $(".destination-responsibility", row).value.trim(),
  })).filter((item) => item.identifier || item.responsibility);
}

function syncFacilityFields(resetTools = false) {
  const mode = $("#facility-mode").value;
  const teeSheet = $("#facility-tee-sheet").value;
  const multi = $("#facility-course-configuration").value === "multi_course";
  const runtime = $("#facility-course-source").value === "runtime";
  $$(".integrated-only").forEach((node) => node.classList.toggle("hidden", mode !== "integrated"));
  $(".booking-url-field").classList.toggle("hidden", mode === "integrated");
  $("#facility-tee-sheet").disabled = mode !== "integrated";
  $(".course-source-field").classList.toggle("hidden", !multi);
  $(".expected-course-field").classList.toggle("hidden", !multi || !runtime);
  $(".exact-courses-field").classList.toggle("hidden", !multi || runtime);
  $("#facility-search-all-courses").disabled = !multi;
  $("#facility-per-booking").disabled = false;
  $("#facility-disclose-fee").disabled = !$("#facility-per-booking").checked;
  $("#facility-fee-application").disabled = !$("#facility-per-booking").checked;
  $(".conditional-fee-rules").classList.toggle("hidden", $("#facility-fee-application").value !== "conditional" || !$("#facility-per-booking").checked);
  if (resetTools) renderTools("facility-tools", mode, teeSheet);
}

function syncModificationFields(resetTools = false) {
  const teeSheet = $("#mod-tee-sheet").value;
  $("#mod-per-booking").disabled = false;
  if (resetTools) renderTools("mod-tools", "integrated", teeSheet);
}

function facilityConfig() {
  const mode = $("#facility-mode").value;
  const integrated = mode === "integrated";
  const multi = $("#facility-course-configuration").value === "multi_course";
  const courseSource = multi ? $("#facility-course-source").value : "configured";
  const primaryUrl = $("#facility-website").value.trim();
  const sourceUrls = [...new Set([primaryUrl, ...lines($("#facility-source-urls").value)])];
  const perBooking = integrated && $("#facility-per-booking").checked;
  const feeApplication = perBooking ? $("#facility-fee-application").value : "none";
  return {
    schema_version: "1",
    slug: $("#facility-slug").value.trim(),
    display_name: $("#facility-name").value.trim(),
    website_url: primaryUrl,
    timezone: $("#facility-timezone").value,
    integration_type: mode,
    tee_sheet: integrated ? $("#facility-tee-sheet").value : "unspecified",
    course_configuration: integrated ? $("#facility-course-configuration").value : "single_course",
    course_values_source: integrated ? courseSource : "configured",
    expected_course_count: integrated && multi && courseSource === "runtime" ? Number($("#facility-course-count").value) : null,
    search_all_courses_for_availability: Boolean(integrated && multi && $("#facility-search-all-courses").checked),
    exact_course_values: integrated && multi && courseSource === "configured" ? lines($("#facility-courses").value) : [],
    references: {
      prompt: state.data.references[mode],
      eligibility: integrated ? state.data.references.eligibility : null,
    },
    enabled_tools: selectedTools("facility-tools"),
    greeting: "",
    disclaimer: "",
    announcement: "",
    booking_url: integrated ? null : $("#facility-booking-url").value.trim(),
    transfer_policy: {
      first_shop_transfer_deflection: Boolean(integrated && $("#facility-guardrail").checked),
      allow_after_hours_transfers: $("#facility-after-hours-transfer").checked,
    },
    availability_policy: { single_player_requires_partially_filled_slot: Boolean(integrated && $("#facility-single-partial").checked) },
    availability_pricing: {
      speaksport_per_booking_model: perBooking,
      booking_fee_application: feeApplication,
      disclose_booking_fee_when_applied: Boolean(perBooking && $("#facility-disclose-fee").checked),
      booking_fee_rules: feeApplication === "conditional" ? lines($("#facility-fee-rules").value) : [],
    },
    transfer_destinations: destinations("facility-destinations"),
    booking_rules: integrated ? lines($("#facility-booking-rules").value) : [],
    cancellation_modification_policy: integrated ? $("#facility-cancellation").value.trim() : "",
    walking_riding_cart_policies: integrated ? lines($("#facility-cart-policies").value) : [],
    caller_details: { first_name: true, last_name: true, email: true, confirm_existing_email: true },
    allowed_source_urls: sourceUrls,
    included_source_paths: [],
    excluded_source_paths: [],
    crawl_entire_domain: false,
    allow_subdomains: false,
    ignored_facts: [],
    reference_leakage_exceptions: [],
  };
}

function facilityPayload() {
  return {
    config: facilityConfig(),
    notes: {
      client_notes: $("#facility-client-notes").value,
      booking_policies: $("#facility-booking-rules").value,
      transfer_notes: $("#facility-transfer-notes").value,
      known_exclusions: $("#facility-exclusions").value,
    },
  };
}

function resetFacilityForm() {
  $("#facility-form").reset();
  $("#facility-editing-slug").value = "";
  $("#facility-form-title").textContent = "Create a new facility";
  $("#save-facility").textContent = "Save facility";
  $("#cancel-facility-edit").classList.add("hidden");
  $("#facility-timezone").value = "America/New_York";
  $("#facility-tee-sheet").value = "foreup";
  $("#facility-course-configuration").value = "single_course";
  $("#facility-course-source").value = "configured";
  $("#facility-fee-application").value = "none";
  $("#facility-destinations").innerHTML = "";
  addDestination("facility-destinations", { identifier: "pro_shop", display_name: "Pro Shop", responsibility: "Tee-time assistance, booking changes, course conditions, and general golf operations." });
  state.editingFacility = null;
  state.slugTouched.facility = false;
  renderTools("facility-tools", "integrated", "foreup");
  syncFacilityFields();
}

async function editFacility(slug) {
  try {
    const data = await api(`/api/facilities/${encodeURIComponent(slug)}`);
    resetFacilityForm();
    const c = data.config;
    state.editingFacility = slug;
    state.slugTouched.facility = true;
    $("#facility-editing-slug").value = slug;
    $("#facility-form-title").textContent = `Edit ${c.display_name}`;
    $("#save-facility").textContent = "Save changes";
    $("#cancel-facility-edit").classList.remove("hidden");
    $("#facility-name").value = c.display_name;
    $("#facility-slug").value = c.slug;
    $("#facility-slug").disabled = true;
    $("#facility-website").value = c.website_url;
    $("#facility-timezone").value = c.timezone;
    $("#facility-mode").value = c.integration_type;
    $("#facility-tee-sheet").value = c.tee_sheet;
    $("#facility-booking-url").value = c.booking_url || "";
    $("#facility-course-configuration").value = c.course_configuration;
    $("#facility-course-source").value = c.course_values_source;
    $("#facility-course-count").value = c.expected_course_count || 2;
    $("#facility-courses").value = (c.exact_course_values || []).join("\n");
    $("#facility-search-all-courses").checked = c.search_all_courses_for_availability;
    $("#facility-single-partial").checked = c.availability_policy.single_player_requires_partially_filled_slot;
    $("#facility-guardrail").checked = c.transfer_policy.first_shop_transfer_deflection;
    $("#facility-after-hours-transfer").checked = c.transfer_policy.allow_after_hours_transfers;
    $("#facility-per-booking").checked = c.availability_pricing.speaksport_per_booking_model;
    $("#facility-fee-application").value = c.availability_pricing.booking_fee_application;
    $("#facility-disclose-fee").checked = c.availability_pricing.disclose_booking_fee_when_applied;
    $("#facility-fee-rules").value = (c.availability_pricing.booking_fee_rules || []).join("\n");
    $("#facility-booking-rules").value = (c.booking_rules || []).join("\n");
    $("#facility-cancellation").value = c.cancellation_modification_policy || "";
    $("#facility-cart-policies").value = (c.walking_riding_cart_policies || []).join("\n");
    $("#facility-client-notes").value = data.notes.client_notes || "";
    $("#facility-transfer-notes").value = data.notes.transfer_notes || "";
    $("#facility-exclusions").value = data.notes.known_exclusions || "";
    $("#facility-source-urls").value = (c.allowed_source_urls || []).filter((url) => url !== c.website_url).join("\n");
    $("#facility-destinations").innerHTML = "";
    (c.transfer_destinations || []).forEach((item) => addDestination("facility-destinations", item));
    if (!c.transfer_destinations?.length) addDestination("facility-destinations");
    renderTools("facility-tools", c.integration_type, c.tee_sheet, new Set(c.enabled_tools));
    syncFacilityFields();
    go("facility");
  } catch (error) { toast(error.message, true); }
}

function modificationPayload() {
  const slug = $("#mod-slug").value.trim();
  const teeSheet = $("#mod-tee-sheet").value;
  const multi = $("#mod-course-configuration").value === "multi_course";
  const source = multi ? $("#mod-course-source").value : "configured";
  const courseInput = lines($("#mod-courses").value);
  const feeRules = lines($("#mod-fee-rules").value);
  const perBooking = $("#mod-per-booking").checked;
  const previous = state.editingModificationData || {};
  const previousConfig = previous.config || {};
  const previousFacility = previous.facility || {};
  return {
    config: {
      ...previousConfig,
      schema_version: "1", slug, display_name: $("#mod-name").value.trim(),
      original_prompt_file: "original-prompt.md", update_notes_file: "update-notes.md",
      additional_context_files: [],
      required_output_markers: lines($("#mod-required-markers").value),
      forbidden_output_patterns: lines($("#mod-forbidden-patterns").value),
      preservation: {
        knowledge_base: $("#mod-kb-mode").value,
        identity_and_voice: "preserve", transfer_destinations: "preserve",
        unmentioned_behavior: "preserve_when_compatible",
      },
    },
    facility: {
      ...previousFacility,
      schema_version: "1", slug, display_name: $("#mod-name").value.trim(),
      website_url: $("#mod-website").value.trim(), timezone: $("#mod-timezone").value,
      integration_type: "integrated", tee_sheet: teeSheet,
      course_configuration: $("#mod-course-configuration").value,
      course_values_source: source,
      expected_course_count: multi && source === "runtime" ? Number(courseInput[0] || 2) : null,
      search_all_courses_for_availability: multi && $("#mod-search-all-courses").checked,
      exact_course_values: multi && source === "configured" ? courseInput : [],
      references: { prompt: state.data.references.integrated, eligibility: state.data.references.eligibility },
      enabled_tools: selectedTools("mod-tools"), greeting: "", disclaimer: "", announcement: "", booking_url: null,
      transfer_policy: {
        first_shop_transfer_deflection: $("#mod-guardrail").checked,
        allow_after_hours_transfers: $("#mod-after-hours-transfer").checked,
      },
      availability_policy: { single_player_requires_partially_filled_slot: $("#mod-single-partial").checked },
      availability_pricing: {
        speaksport_per_booking_model: perBooking,
        booking_fee_application: perBooking ? (feeRules.length ? "conditional" : "all_callers") : "none",
        disclose_booking_fee_when_applied: false,
        booking_fee_rules: perBooking ? feeRules : [],
      },
      transfer_destinations: destinations("mod-destinations"),
      booking_rules: lines($("#mod-booking-rules").value),
      cancellation_modification_policy: $("#mod-cancellation-policy").value.trim(),
      walking_riding_cart_policies: [],
      caller_details: { first_name: true, last_name: true, email: true, confirm_existing_email: true },
      allowed_source_urls: [$("#mod-website").value.trim()], included_source_paths: [], excluded_source_paths: [],
      crawl_entire_domain: false, allow_subdomains: false, ignored_facts: [], reference_leakage_exceptions: [],
    },
    original_prompt: $("#mod-original").value,
    update_notes: $("#mod-notes").value,
  };
}

function resetModificationForm() {
  $("#modification-form").reset();
  $("#mod-editing-slug").value = "";
  $("#mod-form-title").textContent = "Create a prompt update";
  $("#save-modification").textContent = "Save prompt update";
  $("#cancel-mod-edit").classList.add("hidden");
  $("#mod-slug").disabled = false;
  $("#mod-timezone").value = "America/New_York";
  $("#mod-tee-sheet").value = "foreup";
  $("#mod-course-configuration").value = "single_course";
  $("#mod-course-source").value = "configured";
  $("#mod-booking-rules").value = "";
  $("#mod-cancellation-policy").value = "";
  $("#mod-destinations").innerHTML = "";
  addDestination("mod-destinations", { identifier: "pro_shop", display_name: "Pro Shop", responsibility: "General golf operations and requests the assistant cannot complete." });
  renderTools("mod-tools", "integrated", "foreup");
  syncModificationFields();
  state.editingModification = null;
  state.editingModificationData = null;
  state.slugTouched.modification = false;
}

async function editModification(slug) {
  try {
    const data = await api(`/api/modifications/${encodeURIComponent(slug)}`);
    resetModificationForm();
    const c = data.config;
    const f = data.facility;
    state.editingModification = slug;
    state.editingModificationData = data;
    state.slugTouched.modification = true;
    $("#mod-editing-slug").value = slug;
    $("#mod-form-title").textContent = `Edit ${c.display_name}`;
    $("#save-modification").textContent = "Save changes";
    $("#cancel-mod-edit").classList.remove("hidden");
    $("#mod-name").value = c.display_name;
    $("#mod-slug").value = c.slug;
    $("#mod-slug").disabled = true;
    $("#mod-timezone").value = f.timezone;
    $("#mod-website").value = f.website_url;
    $("#mod-tee-sheet").value = f.tee_sheet;
    $("#mod-kb-mode").value = c.preservation.knowledge_base;
    $("#mod-guardrail").checked = f.transfer_policy.first_shop_transfer_deflection;
    $("#mod-after-hours-transfer").checked = f.transfer_policy.allow_after_hours_transfers;
    $("#mod-single-partial").checked = f.availability_policy.single_player_requires_partially_filled_slot;
    $("#mod-search-all-courses").checked = f.search_all_courses_for_availability;
    $("#mod-per-booking").checked = f.availability_pricing.speaksport_per_booking_model;
    $("#mod-original").value = data.original_prompt;
    $("#mod-notes").value = data.update_notes;
    $("#mod-booking-rules").value = (f.booking_rules || []).join("\n");
    $("#mod-cancellation-policy").value = f.cancellation_modification_policy || "";
    $("#mod-course-configuration").value = f.course_configuration;
    $("#mod-course-source").value = f.course_values_source;
    $("#mod-courses").value = f.course_values_source === "runtime"
      ? String(f.expected_course_count || 2)
      : (f.exact_course_values || []).join("\n");
    $("#mod-required-markers").value = (c.required_output_markers || []).join("\n");
    $("#mod-forbidden-patterns").value = (c.forbidden_output_patterns || []).join("\n");
    $("#mod-fee-rules").value = (f.availability_pricing.booking_fee_rules || []).join("\n");
    $("#mod-destinations").innerHTML = "";
    (f.transfer_destinations || []).forEach((item) => addDestination("mod-destinations", item));
    if (!f.transfer_destinations?.length) addDestination("mod-destinations");
    renderTools("mod-tools", "integrated", f.tee_sheet, new Set(f.enabled_tools));
    syncModificationFields();
    go("modification");
  } catch (error) { toast(error.message, true); }
}

function renderActiveJobs() {
  const jobs = state.data.jobs || [];
  $("#active-jobs").innerHTML = jobs.map((job) => `<div class="job-card"><span class="job-spinner" style="${job.status === "running" ? "" : "animation:none;border-color:#8fc5a8"}"></span><div><strong>${escapeHtml(job.slug)} · ${escapeHtml(job.status)}</strong><span>${escapeHtml(job.kind)} run started ${formatDate(job.started_at)}</span></div><button data-job-id="${job.id}">View progress</button></div>`).join("");
  $$('[data-job-id]').forEach((button) => button.onclick = () => openLog(button.dataset.jobId));
}

function renderRuns() {
  const search = $("#run-search").value.toLowerCase();
  const values = state.data.runs.filter((run) => (
    (state.runFilter === "all" || run.kind === state.runFilter)
    && `${run.slug} ${run.run_id}`.toLowerCase().includes(search)
  ));
  $("#all-runs").innerHTML = values.length ? values.map((run) => runRow(run, true)).join("") : `<div class="empty">No runs match this view.</div>`;
  renderActiveJobs();
}

function openRunDialog(kind, slug) {
  state.runTarget = { kind, slug };
  $("#run-approval").checked = false;
  $("#confirm-run").disabled = true;
  const copy = kind === "facility"
    ? `This will crawl ${slug}'s approved public sources, then send normalized content and project references to OpenRouter.`
    : `This will send ${slug}'s original prompt, requested updates, and current runtime references to OpenRouter. No website crawl is performed.`;
  $("#run-dialog-copy").textContent = copy;
  $(".approval-check span").textContent = kind === "facility"
    ? "I approve sending these facility materials and public website content to Firecrawl and OpenRouter."
    : "I approve sending this original prompt, update notes, facility configuration, and current runtime references to OpenRouter.";
  $("#run-dialog").showModal();
}

async function startRun() {
  if (!state.runTarget || !$("#run-approval").checked) return;
  const { kind, slug } = state.runTarget;
  const collection = kind === "facility" ? "facilities" : "modifications";
  try {
    const job = await api(`/api/${collection}/${encodeURIComponent(slug)}/run`, {
      method: "POST", body: JSON.stringify({ approved_external_processing: true }),
    });
    $("#run-dialog").close();
    state.data.jobs.unshift(job);
    toast(`Started ${slug}. You can follow it in Run history.`);
    go("runs");
    openLog(job.id);
  } catch (error) { toast(error.message, true); }
}

async function openLog(jobId) {
  state.currentJob = jobId;
  $("#log-dialog").showModal();
  await refreshLog();
}

async function refreshLog() {
  if (!state.currentJob || !$("#log-dialog").open) return;
  try {
    const job = await api(`/api/jobs/${state.currentJob}`);
    $("#log-title").textContent = `${job.slug} · ${job.status}`;
    $("#job-log").textContent = job.log || "Waiting for the first update…";
    $("#job-log").scrollTop = $("#job-log").scrollHeight;
    const index = state.data.jobs.findIndex((item) => item.id === job.id);
    if (index >= 0) state.data.jobs[index] = job;
    if (job.status === "running") setTimeout(refreshLog, 1500);
    else {
      await refreshData(false);
      renderRuns();
      toast(job.status === "completed" ? `${job.slug} completed.` : `${job.slug} needs attention.`, job.status !== "completed");
    }
  } catch (error) { toast(error.message, true); }
}

async function refreshData(notify = true) {
  try {
    state.data = await api("/api/bootstrap");
    $("#contract-version").textContent = `Tool contracts ${state.data.tool_contract_version}`;
    renderDashboard();
    renderRuns();
    if (notify) toast("Workspace refreshed.");
  } catch (error) { toast(error.message, true); }
}

function wireEvents() {
  $$(".nav-item").forEach((button) => button.onclick = () => go(button.dataset.view));
  $$('[data-go]').forEach((button) => button.onclick = () => go(button.dataset.go));
  $("#refresh-button").onclick = () => refreshData();
  $("#facility-name").addEventListener("input", (event) => {
    if (!state.slugTouched.facility) $("#facility-slug").value = slugify(event.target.value);
  });
  $("#facility-slug").addEventListener("input", () => { state.slugTouched.facility = true; });
  $("#mod-name").addEventListener("input", (event) => {
    if (!state.slugTouched.modification) $("#mod-slug").value = `${slugify(event.target.value)}-update`;
  });
  $("#mod-slug").addEventListener("input", () => { state.slugTouched.modification = true; });
  $("#facility-mode").onchange = () => syncFacilityFields(true);
  $("#facility-tee-sheet").onchange = () => syncFacilityFields(true);
  $("#facility-course-configuration").onchange = () => syncFacilityFields();
  $("#facility-course-source").onchange = () => syncFacilityFields();
  $("#facility-per-booking").onchange = () => syncFacilityFields();
  $("#facility-fee-application").onchange = () => syncFacilityFields();
  $("#recommended-tools").onclick = () => renderTools("facility-tools", $("#facility-mode").value, $("#facility-tee-sheet").value);
  $("#add-facility-destination").onclick = () => addDestination("facility-destinations");
  $("#add-mod-destination").onclick = () => addDestination("mod-destinations");
  $("#mod-tee-sheet").onchange = () => syncModificationFields(true);
  $("#mod-file").onchange = async (event) => {
    const [file] = event.target.files;
    if (file) $("#mod-original").value = await file.text();
  };
  $("#cancel-facility-edit").onclick = () => { $("#facility-slug").disabled = false; resetFacilityForm(); };
  $("#cancel-mod-edit").onclick = resetModificationForm;

  $("#facility-form").onsubmit = async (event) => {
    event.preventDefault();
    try {
      const editing = state.editingFacility;
      const result = await api(editing ? `/api/facilities/${editing}` : "/api/facilities", {
        method: editing ? "PUT" : "POST", body: JSON.stringify(facilityPayload()),
      });
      $("#facility-slug").disabled = false;
      await refreshData(false);
      toast(editing ? "Facility changes saved." : "Facility files created.");
      if (!editing) openRunDialog("facility", result.slug);
      else go("dashboard");
      if (!editing) resetFacilityForm();
    } catch (error) { toast(error.message, true); }
  };

  $("#modification-form").onsubmit = async (event) => {
    event.preventDefault();
    try {
      const editing = state.editingModification;
      const result = await api(editing ? `/api/modifications/${editing}` : "/api/modifications", {
        method: editing ? "PUT" : "POST", body: JSON.stringify(modificationPayload()),
      });
      await refreshData(false);
      toast(editing ? "Prompt update changes saved." : "Prompt update workspace created.");
      if (!editing) openRunDialog("modification", result.slug);
      else go("dashboard");
      resetModificationForm();
    } catch (error) { toast(error.message, true); }
  };

  $("#run-approval").onchange = (event) => { $("#confirm-run").disabled = !event.target.checked; };
  $("#confirm-run").onclick = startRun;
  $("[data-close-log]").onclick = () => { $("#log-dialog").close(); state.currentJob = null; };
  $$("[data-run-filter]").forEach((button) => button.onclick = () => {
    state.runFilter = button.dataset.runFilter;
    $$("[data-run-filter]").forEach((item) => item.classList.toggle("active", item === button));
    renderRuns();
  });
  $("#run-search").oninput = renderRuns;
}

async function init() {
  populateTimezones();
  wireEvents();
  await refreshData(false);
  resetFacilityForm();
  resetModificationForm();
  renderDashboard();
}

init();
