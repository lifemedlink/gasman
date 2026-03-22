async function loadPredictiveAlerts(){

try{

const r = await fetch("/admin/predictive-alerts");
const data = await r.json();

const body = document.getElementById("predictiveAlertRows");

if(!data.length){
body.innerHTML = `
<tr>
<td colspan="5" class="text-center text-muted">
No predictive alerts
</td>
</tr>`;
return;
}

body.innerHTML = data.map(a => `
<tr>

<td class="sev-${a.severity.toLowerCase()}">
${a.severity}
</td>

<td>${a.device}</td>

<td>${a.prediction}</td>

<td>${a.eta}</td>

<td>
<button class="btn btn-sm btn-outline-primary">
Dispatch
</button>
</td>

</tr>
`).join("");

}catch(e){

document.getElementById("predictiveAlertRows").innerHTML = `
<tr>
<td colspan="5" class="text-danger text-center">
Failed to load alerts
</td>
</tr>`;

}

}

loadPredictiveAlerts();
setInterval(loadPredictiveAlerts,10000);
