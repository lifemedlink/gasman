/* =========================================================
   GASMAN ENTERPRISE DATABASE OPERATIONS PANEL
   Frontend Controller

   Features
   ✔ Database KPI monitoring
   ✔ Largest tables analytics
   ✔ GASMAN log cleanup
   ✔ DATA LOGGER cleanup
   ✔ Table optimization
   ✔ Safe API handling
   ✔ Auto refresh
========================================================= */


/* =========================================================
   UTILITY SAFE ELEMENT
========================================================= */

function el(id){
return document.getElementById(id);
}


/* =========================================================
   LOAD DATABASE STATS
========================================================= */

async function loadDatabaseStats(){

try{

const r = await fetch("/admin/database-stats");

if(!r.ok) throw new Error("API error");

const data = await r.json();

/* KPI VALUES */

if(el("dbSize"))
el("dbSize").innerText =
(Number(data.db_total)||0).toFixed(2) + " MB";

if(el("diskTotal"))
el("diskTotal").innerText =
(Number(data.disk_total)||0).toFixed(2) + " GB";

if(el("diskUsed"))
el("diskUsed").innerText =
(Number(data.disk_used)||0).toFixed(2) + " GB";

if(el("diskFree"))
el("diskFree").innerText =
(Number(data.disk_free)||0).toFixed(2) + " GB";

}catch(e){

console.error("Database stats failed:",e);

}

}


/* =========================================================
   LOAD OLD GASMAN LOG COUNT
========================================================= */

async function loadOldLogs(){

try{

const r = await fetch("/admin/old-log-count");

if(!r.ok) throw new Error("API error");

const data = await r.json();

if(el("kpiOldLogs"))
el("kpiOldLogs").innerText =
data.old_logs || 0;

}catch(e){

console.error("Old log count failed:",e);

}

}


/* =========================================================
   CLEAN GASMAN LOGS
========================================================= */

async function cleanupGasman(){
const ok = await verifyServicePassword();
if(!ok) return;
if(!confirm("Delete GASMAN logs older than 90 days?")) return;

try{

const r = await fetch("/admin/cleanup-gasman",{method:"POST"});

if(!r.ok) throw new Error("API error");

const data = await r.json();

alert("Deleted " + (data.deleted || 0) + " GASMAN logs");

loadDatabaseStats();
loadOldLogs();
loadLargestTables();

}catch(e){

console.error(e);
alert("Cleanup failed");

}

}


/* =========================================================
   CLEAN DATA LOGGER TABLES
========================================================= */

async function cleanupLogger(){
const ok = await verifyServicePassword();
if(!ok) return;
if(!confirm("Clean DATA LOGGER tables? This will remove telemetry history.")) return;

try{

const r = await fetch("/admin/cleanup-datalogger",{method:"POST"});

if(!r.ok) throw new Error("API error");

const data = await r.json();

if(data.error){

alert("Cleanup error: " + data.error);
return;

}

alert(
"Cleanup complete\n\n" +
"Raw rows deleted: " + (data.raw_deleted || 0) +
"\nHistorical rows deleted: " + (data.historical_deleted || 0)
);

loadDatabaseStats();
loadLargestTables();

}catch(e){

console.error(e);
alert("Cleanup failed");

}

}


/* =========================================================
   LOAD LARGEST TABLE ANALYTICS
========================================================= */

async function loadLargestTables(){

try{

const r = await fetch("/admin/database-operations");

if(!r.ok) throw new Error("API error");

const data = await r.json();

const body = el("largestTables");

if(!body) return;

if(!data.largest_tables || !data.largest_tables.length){

body.innerHTML = `
<tr>
<td colspan="4" class="text-center text-muted">
No tables found
</td>
</tr>
`;

return;

}

body.innerHTML = data.largest_tables.map(t=>{

const db =
t.table_schema ??
t.TABLE_SCHEMA ??
"unknown";

const table =
t.table_name ??
t.TABLE_NAME ??
"unknown";

const rows =
Number(
t.table_rows ??
t.TABLE_ROWS ??
0
);

const size =
Number(
t.size_mb ??
0
);

return `
<tr>
<td>${db}</td>
<td>${table}</td>
<td>${rows}</td>
<td>${size.toFixed(2)}</td>
</tr>
`;

}).join("");

}catch(e){

console.error("Largest tables load failed:",e);

}

}


/* =========================================================
   OPTIMIZE ALL TABLES
========================================================= */

async function optimizeTables(){
const ok = await verifyServicePassword();
if(!ok) return;
if(!confirm("Optimize all database tables?\n\nThis may take some time.")) return;

try{

const r = await fetch("/admin/optimize-tables",{method:"POST"});

if(!r.ok) throw new Error("API error");

const data = await r.json();

alert(
"Optimization complete\n\nTables optimized: " +
(data.tables_optimized || 0)
);

loadDatabaseStats();
loadLargestTables();

}catch(e){

console.error(e);
alert("Optimization failed");

}

}
/* =========================================================
   CREATE BACKUP
========================================================= */

async function createBackup(){
const ok = await verifyServicePassword();
if(!ok) return;
if(!confirm("Create database backup?")) return;

const r = await fetch("/admin/create-backup",{method:"POST"});

const data = await r.json();

alert("Backup created: " + data.file);

loadBackups();

}


/* =========================================================
   LOAD BACKUPS
========================================================= */

async function loadBackups(){

const r = await fetch("/admin/list-backups");

const data = await r.json();

const table = document.getElementById("backupTable");

table.innerHTML = data.backups.map(b=>`

<tr>
<td>${b.name}</td>
<td>${b.size} MB</td>
<td>${new Date(b.created).toLocaleString()}</td>

<td>

<button class="btn btn-sm btn-success"
onclick="downloadBackup('${b.name}')">

Download

</button>

<button class="btn btn-sm btn-danger"
onclick="restoreBackup('${b.name}')">

Restore

</button>

<button class="btn btn-sm btn-danger"
onclick="deleteBackup('${b.name}')">

Delete

</button>
</td>

</tr>

`).join("");

}


/* =========================================================
   DOWNLOAD BACKUP
========================================================= */

function downloadBackup(file){

window.location =
"/admin/download-backup/" + file;

}


/* =========================================================
   RESTORE BACKUP
========================================================= */

async function restoreBackup(file){
const ok = await verifyServicePassword();
if(!ok) return;
if(!confirm("Restore backup?\nThis will overwrite current database.")) return;

await fetch("/admin/restore-backup/"+file,{
method:"POST"
});

alert("Database restored");

}

/* =========================================================
   DELETE BACKUP
========================================================= */

async function deleteBackup(file){
const ok = await verifyServicePassword();
if(!ok) return;

if(!confirm("Delete backup?\n\n" + file)) return;

try{

const r = await fetch("/admin/delete-backup/" + file,{
method:"DELETE"
});

const data = await r.json();

if(data.status === "deleted"){

alert("Backup deleted");

loadBackups();

}else{

alert("Delete failed: " + data.message);

}

}catch(e){

alert("Delete failed");

}

}
/* =========================================================
   INITIAL DASHBOARD LOAD
========================================================= */

function initDatabaseDashboard(){

loadDatabaseStats();
loadOldLogs();
loadLargestTables();

}

/* =========================================================
   SERVICE PASSWORD MODAL CONTROLLER
========================================================= */

let serviceResolver = null;
let serviceModal = null;

function verifyServicePassword(){

serviceModal = new bootstrap.Modal(
document.getElementById("servicePasswordModal")
);

document.getElementById("servicePasswordInput").value = "";
document.getElementById("servicePasswordError").style.display = "none";

serviceModal.show();

return new Promise(resolve=>{
serviceResolver = resolve;
});

}


async function submitServicePassword(){

const password =
document.getElementById("servicePasswordInput").value;

const r = await fetch("/admin/verify-service-password",{
method:"POST",
headers:{
"Content-Type":"application/json"
},
body:JSON.stringify({password})
});

const data = await r.json();

if(data.status !== "ok"){

document.getElementById("servicePasswordError").style.display = "block";
return;

}

serviceModal.hide();

if(serviceResolver){
serviceResolver(true);
}

}
/* =========================================================
   AUTO REFRESH
========================================================= */

setInterval(()=>{

loadDatabaseStats();
loadOldLogs();
loadLargestTables();

},60000); // refresh every 60 seconds


/* =========================================================
   START DASHBOARD
========================================================= */

initDatabaseDashboard();
