/**
 * GASMAN – Admin Activity (Industry Audit Trail Version)
 */

(function () {

const body = document.getElementById("adminActivityRows");
if (!body) return;

let SUMMARY = [];
let TIMELINE = [];
let refreshTimer = null;

const modal = new bootstrap.Modal(
document.getElementById("trackingModal")
);

const fromInput = document.getElementById("fromDate");
const toInput = document.getElementById("toDate");
const statusFilter = document.getElementById("statusFilter");

const today = new Date().toISOString().slice(0,10);
fromInput.value = today;
toInput.value = today;


/* ======================================================
TASK FLOW (FSM)
====================================================== */

const STATUS_FLOW = [
"ASSIGNED",
"EN_ROUTE",
"ON_SITE",
"FILLING",
"FILLED",
"COMPLETED"
];

const STATUS_LABELS = {

ASSIGNED : "ACCEPTED",
EN_ROUTE : "EN ROUTE",
ON_SITE : "ON SITE",
FILLING : "FILLING",
FILLED : "FILLED",
COMPLETED : "COMPLETED",
CANCELLED : "CANCELLED",
REJECTED : "REJECTED"

};


/* ======================================================
AUDIT DESCRIPTIONS
====================================================== */

function getAuditMessage(e){

const user = e.user_name || "Driver";

switch(e.status_after){

case "ASSIGNED":
return `Driver <b>${user}</b> accepted task`;

case "EN_ROUTE":
return `Navigation started`;

case "ON_SITE":
return `Location reached`;

case "FILLING":
return `Gas filling started`;

case "FILLED":
return `Tank filled`;

case "COMPLETED":
return `Gas stable — task closed`;

case "REJECTED":
return `Task rejected`;

case "CANCELLED":
return `Task cancelled`;

default:
return e.action || "-";

}

}


/* ======================================================
AUTO REFRESH
====================================================== */

function startAutoRefresh(){

if(refreshTimer) clearInterval(refreshTimer);

refreshTimer = setInterval(loadActivity,5000);

}


/* ======================================================
LOAD ACTIVITY
====================================================== */

async function loadActivity(){

const from = fromInput.value;
const to = toInput.value;

const res = await GASMAN_UTILS.safeFetch(
`/get_activity?start_date=${from}&end_date=${to}`
);

if(!res || !res.summary){

body.innerHTML =
`<tr><td colspan="9" class="text-center text-muted">No activity</td></tr>`;

return;

}

SUMMARY = res.summary || [];
TIMELINE = res.timeline || [];

applyFilters();
updateKPIs();

}


/* ======================================================
KPI UPDATE
====================================================== */

function updateKPIs(){

document.getElementById("kpiTotal").innerText =
SUMMARY.length;

document.getElementById("kpiCompleted").innerText =
SUMMARY.filter(r => r.status === "COMPLETED").length;

document.getElementById("kpiCancelled").innerText =
SUMMARY.filter(r => r.status === "CANCELLED").length;

}


/* ======================================================
STATUS BADGE
====================================================== */

function getStatusBadge(status){

const label = STATUS_LABELS[status] || status;

if(status==="COMPLETED")
return `<span class="badge-status status-COMPLETED">${label}</span>`;

if(status==="CANCELLED" || status==="REJECTED")
return `<span class="badge-status status-CANCELLED">${label}</span>`;

if(status==="ON_SITE" || status==="FILLING")
return `<span class="badge-status status-ON_SITE">${label}</span>`;

return `<span class="badge-status status-ASSIGNED">${label}</span>`;

}


/* ======================================================
PIPELINE LIFECYCLE VIEW
====================================================== */

function getProgressBar(status,trackingId){

const events = TIMELINE
.filter(e => e.tracking_id === trackingId)
.sort((a,b)=> new Date(a.created_at)-new Date(b.created_at));

let cancelStage = null;

/* detect where cancel happened */

events.forEach((e,i)=>{

if(e.status_after === "CANCELLED"){

/* detect previous lifecycle stage */

for(let j=i-1;j>=0;j--){

if(STATUS_FLOW.includes(events[j].status_after)){
cancelStage = events[j].status_after;
break;
}

}

if(!cancelStage){
cancelStage = "ASSIGNED";
}

}

});

const cancelIndex = STATUS_FLOW.indexOf(cancelStage);
const currentIndex = STATUS_FLOW.indexOf(status);

return `

<div class="lifecycle-pipeline"
onclick="openTimeline('${trackingId}')">

${STATUS_FLOW.map((s,i)=>{

const label = STATUS_LABELS[s] || s;

/* ==========================
TASK COMPLETED
========================== */

if(status === "COMPLETED"){

return `
<div class="lifecycle-step done">
<span class="lifecycle-dot"></span>
<span>${label}</span>
</div>
${i < STATUS_FLOW.length-1 ? `<span class="lifecycle-arrow">→</span>` : ""}
`;

}

/* ==========================
TASK CANCELLED
========================== */

if(status === "CANCELLED"){

if(i < cancelIndex){

return `
<div class="lifecycle-step done">
<span class="lifecycle-dot"></span>
<span>${label}</span>
</div>
${i < STATUS_FLOW.length-1 ? `<span class="lifecycle-arrow">→</span>` : ""}
`;

}

if(i === cancelIndex){

return `
<div class="lifecycle-step cancelled">
<span class="lifecycle-dot"></span>
<span>${label}</span>
</div>
${i < STATUS_FLOW.length-1 ? `<span class="lifecycle-arrow">→</span>` : ""}
`;

}

return `
<div class="lifecycle-step">
<span class="lifecycle-dot"></span>
<span>${label}</span>
</div>
${i < STATUS_FLOW.length-1 ? `<span class="lifecycle-arrow">→</span>` : ""}
`;

}

/* ==========================
NORMAL FLOW
========================== */

const done = i < currentIndex;
const active = i === currentIndex;

return `

<div class="lifecycle-step
${done ? "done":""}
${active ? "active":""}">

<span class="lifecycle-dot"></span>
<span>${label}</span>

</div>

${i < STATUS_FLOW.length-1 ? `<span class="lifecycle-arrow">→</span>` : ""}

`;

}).join("")}

</div>

`;

}

/* ======================================================
RENDER TABLE
====================================================== */

function renderTable(data){

if(!data.length){

body.innerHTML =
`<tr><td colspan="9" class="text-center text-muted">No activity</td></tr>`;

return;

}

body.innerHTML = data.map(r=>{

const created = r.created_at
? new Date(r.created_at).toLocaleString()
: "-";

const gasDisplay =
(r.gas_start ?? "-") +
" → " +
(r.gas_end ?? "-");

return `

<tr>

<td>${created}</td>

<td><strong>${r.device_id}</strong></td>

<td>${r.user_name || "-"}</td>

<td>${r.customer_name || "-"}</td>

<td>${r.location || "-"}</td>

<td>
${getStatusBadge(r.status)}
</td>

<td>
${getProgressBar(r.status,r.tracking_id)}
</td>

<td>${gasDisplay}</td>

<td>
<a href="#"
onclick="openTimeline('${r.tracking_id}')">
${r.tracking_id || "-"}
</a>
</td>

</tr>

`;

}).join("");

}


/* ======================================================
TIMELINE MODAL (INDUSTRY AUDIT TRAIL)
====================================================== */

window.openTimeline = function(trackingId){

document.getElementById("trackId").innerText = trackingId;

const rawEvents = TIMELINE
.filter(e => e.tracking_id === trackingId)
.sort((a,b)=> new Date(a.created_at)-new Date(b.created_at));

const events=[];
const seen=new Set();

rawEvents.forEach(e=>{
if(!seen.has(e.status_after)){
events.push(e);
seen.add(e.status_after);
}
});

const box=document.getElementById("trackingTimeline");

box.innerHTML = events.map(e=>{

const label=STATUS_LABELS[e.status_after] || e.status_after;
const time=new Date(e.created_at).toLocaleTimeString();
const message=getAuditMessage(e);

return `

<div class="timeline-item">

<span class="timeline-dot"></span>

<div class="border rounded p-3 bg-light">

<div class="fw-semibold">

✓ ${label}

</div>

<div class="text-muted small mt-1">

${message}

</div>

<div class="text-muted small mt-1">

${time}

</div>

</div>

</div>

`;

}).join("");

modal.show();

};


/* ======================================================
FILTERS
====================================================== */

function applyFilters(){

let filtered=[...SUMMARY];

const selectedStatus=statusFilter.value;

if(selectedStatus)
filtered=filtered.filter(
r=>r.status===selectedStatus
);

renderTable(filtered);

}


fromInput.addEventListener("change",loadActivity);
toInput.addEventListener("change",loadActivity);
statusFilter.addEventListener("change",applyFilters);


loadActivity();
startAutoRefresh();

})();
