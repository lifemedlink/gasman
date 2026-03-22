(function () {

const el = id => document.getElementById(id);
let modal, lastRows = [];

function fmt(v){
  if(v==null) return "-";
  const s=String(v).padStart(6,"0");
  return s.slice(0,-2)+"<span class='text-danger fw-bold'>"+s.slice(-2)+"</span>";
}

async function loadGasParams(){
  const r=await fetch("/admin/gas-parameters",{credentials:"include"});
  const p=await r.json();
  el("pM").innerText=p.molecular_weight_M??"-";
  el("pS").innerText=p.specific_gravity_S??"-";
  el("pLP").innerText=p.operating_pressure_LP??"-";
  el("pT").innerText=p.temperature_T??"-";
  el("pG").innerText=p.gas_constant_G??"-";
  ["M","S","LP","T"].forEach(k=>el("cfg"+k).value=p[
    k==="M"?"molecular_weight_M":
    k==="S"?"specific_gravity_S":
    k==="LP"?"operating_pressure_LP":"temperature_T"]||"");
}

async function loadData(){
  let url="/admin/consumptions/data";
  if(el("historyStart").value && el("historyEnd").value)
    url+=`?start_date=${historyStart.value}&end_date=${historyEnd.value}`;

  const r=await fetch(url,{credentials:"include"});
  const rows=await r.json();
  lastRows=rows;

  const G=parseFloat(el("pG").innerText)||0;
  const tb=el("adminHistoryRows");

  tb.innerHTML=rows.map(r=>{
    const cn=(a,b)=>(((b-a)/100)*G).toFixed(2);
    const total=(cn(r.m1_start,r.m1_end)*1+cn(r.m2_start,r.m2_end)*1+cn(r.m3_start,r.m3_end)*1+cn(r.m4_start,r.m4_end)*1).toFixed(2);
    const rd=(a,b)=>a===b?fmt(a):fmt(a)+" → "+fmt(b);

    return `<tr>
<td>${r.device_id}</td><td>${r.customer_name}</td><td>${r.location}</td>
<td>${r.m1_sl}</td><td>${rd(r.m1_start,r.m1_end)}</td><td>${cn(r.m1_start,r.m1_end)}</td>
<td>${r.m2_sl}</td><td>${rd(r.m2_start,r.m2_end)}</td><td>${cn(r.m2_start,r.m2_end)}</td>
<td>${r.m3_sl}</td><td>${rd(r.m3_start,r.m3_end)}</td><td>${cn(r.m3_start,r.m3_end)}</td>
<td>${r.m4_sl}</td><td>${rd(r.m4_start,r.m4_end)}</td><td>${cn(r.m4_start,r.m4_end)}</td>
<td><b>${total}</b></td>
</tr>`;
  }).join("");
}

window.exportCSV=()=>{
  let csv="Device,Customer,Location,M1.Sl,M1.Rd,M1.Cn,M2.Sl,M2.Rd,M2.Cn,M3.Sl,M3.Rd,M3.Cn,M4.Sl,M4.Rd,M4.Cn,Total\n";
  lastRows.forEach(r=>{
    csv+=`${r.device_id},${r.customer_name},${r.location},${r.m1_sl},${r.m1_start}-${r.m1_end},,${r.m2_sl},${r.m2_start}-${r.m2_end},,${r.m3_sl},${r.m3_start}-${r.m3_end},,${r.m4_sl},${r.m4_start}-${r.m4_end},,\n`;
  });
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));
  a.download="gas_consumption.csv";
  a.click();
};

window.openConfigBox=()=>modal.show();
window.saveConfig=async()=>{
  const r=await fetch("/admin/gas-parameters",{method:"POST",credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({
      password:el("adminPassword").value,
      M:el("cfgM").value,S:el("cfgS").value,
      LP:el("cfgLP").value,T:el("cfgT").value
    })
  });
  if(!r.ok) return alert("Invalid password");
  modal.hide(); loadGasParams(); loadData();
};

document.addEventListener("DOMContentLoaded",()=>{
  modal=new bootstrap.Modal(el("configModal"));
  loadGasParams(); loadData();
  el("historyFetchBtn").onclick=loadData;
});

})();
