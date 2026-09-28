const $=id=>document.getElementById(id);
const money=v=>"₹"+Number(v||0).toLocaleString("en-IN",{maximumFractionDigits:2});
const today=new Date(); const first=new Date(today.getFullYear(),today.getMonth(),1);
$("start").value=first.toISOString().slice(0,10); $("end").value=today.toISOString().slice(0,10);

let boot={categories:[],sources:[],users:[]};

async function api(url,opt={}){const r=await fetch(url,{...opt,headers:{"Content-Type":"application/json",...(opt.headers||{})}});if(!r.ok){let x={};try{x=await r.json()}catch{};throw new Error(x.detail||"Request failed")}return r.json()}
function q(){return `start=${$("start").value}&end=${$("end").value}`}
async function refreshAll(){
  try{
    boot=await api("/api/bootstrap");
    const d=await api("/api/dashboard?"+q()), tx=await api("/api/transactions?"+q()), inv=await api("/api/investments");
    $("income").textContent=money(d.income);$("expense").textContent=money(d.expense);$("savings").textContent=money(d.savings);$("networth").textContent=money(d.networth);
    drawDonut(d.categories); drawTrend(d.trend); drawTx(tx); drawCats(); drawSources(); drawInv(inv); drawUsers();
    $("csv").href="/api/report.csv?"+q();$("pdf").href="/api/report.pdf?"+q();
  }catch(e){alert(e.message)}
}
function drawDonut(items){
  const total=items.reduce((a,x)=>a+x.value,0); const colors=items.map(x=>x.color||"#6366f1");
  let acc=0, parts=[];
  items.forEach((x,i)=>{let pct=total?x.value/total*100:0;parts.push(`${colors[i]} ${acc}% ${acc+pct}%`);acc+=pct});
  $("donut").style.background=total?`conic-gradient(${parts.join(",")})`:"#e5e7eb";
  $("legend").innerHTML=items.length?items.map((x,i)=>`<span><i class="dot" style="background:${colors[i]}"></i>${esc(x.name)} ${money(x.value)}</span>`).join(""):"No expenses in range";
}
function drawTrend(items){
  const max=Math.max(1,...items.map(x=>Math.abs(x.net))); 
  $("trend").innerHTML=items.map(x=>{let h=Math.max(3,Math.round(Math.abs(x.net)/max*175));return `<div class="bar ${x.net<0?"neg":""}" title="${x.date}: ${money(x.net)}" style="height:${h}px"></div>`}).join("");
}
function drawTx(rows){
  $("txnRows").innerHTML=rows.map(t=>`<tr><td>${t.date}</td><td><span class="pill">${t.type}</span></td><td>${esc(t.category)}</td><td>${esc(t.source)}</td><td>${money(t.amount)}</td><td>${esc(t.note||"")}${t.recurring?" 🔁":""}</td><td><div class="row-actions"><button onclick="editTxn(${t.id})">Edit</button><button onclick="delTxn(${t.id})">Del</button></div></td></tr>`).join("")||`<tr><td colspan="7" class="muted">No transactions in this period.</td></tr>`;
}
function drawCats(){ $("cats").innerHTML=boot.categories.map(c=>`<span class="tag"><span>${esc(c.icon)}</span>${esc(c.name)} <button onclick="editCat(${c.id})">✎</button> <button onclick="delCat(${c.id})">×</button></span>`).join("")}
function drawSources(){ $("sources").innerHTML=boot.sources.map(s=>`<div class="tag"><b>${esc(s.name)}</b> ${money(s.current_balance)} <button onclick="editSource(${s.id})">✎</button> <button onclick="delSource(${s.id})">×</button></div>`).join("")}
function drawInv(rows){$("invRows").innerHTML=rows.map(i=>`<tr><td>${esc(i.name)}</td><td>${esc(i.kind)}</td><td>${money(i.contribution)}</td><td>${money(i.current_value)}</td><td>${i.date}</td><td><button onclick='editInv(${JSON.stringify(i)})'>Edit</button> <button onclick="delInv(${i.id})">Del</button></td></tr>`).join("")||`<tr><td colspan="6" class="muted">No investment entries.</td></tr>`}
function drawUsers(){if(!window.IS_ADMIN)return;$("users").innerHTML=boot.users.map(u=>`<div class="tag">${esc(u.name)} · ${esc(u.email)} ${u.is_admin?"(admin)":""} <button onclick="delUser(${u.id})">×</button></div>`).join("")}
function esc(s){return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
function modal(title,html){$("modalTitle").textContent=title;$("modalBody").innerHTML=html;$("modal").classList.remove("hidden")}
function closeModal(){$("modal").classList.add("hidden")}
function sel(list,val,type){return list.map(x=>`<option value="${x.id}" ${String(x.id)===String(val)?"selected":""}>${esc(x.name)}</option>`).join("")}
function openTxn(t=null){
  const c=boot.categories.filter(x=>x.type===(t?.type||"expense"));
  modal(t?"Edit transaction":"New transaction",`<form onsubmit="saveTxn(event,${t?.id||0})"><div class="form-grid">
  <label>Type<select id="f_type" onchange="rebuildCat()"><option value="expense" ${t?.type==="expense"?"selected":""}>Expense</option><option value="income" ${t?.type==="income"?"selected":""}>Income</option></select></label>
  <label>Amount<input id="f_amount" type="number" step="0.01" required value="${t?.amount||""}"></label>
  <label>Date<input id="f_date" type="date" required value="${t?.date||$("end").value}"></label>
  <label>Category<select id="f_cat" required>${sel(c,t?.category_id)}</select></label>
  <label>Source<select id="f_src" required>${sel(boot.sources,t?.source_id)}</select></label>
  <label><span>Recurring</span><input id="f_rec" type="checkbox" ${t?.recurring?"checked":""}></label>
  <label class="full">Note<textarea id="f_note">${esc(t?.note||"")}</textarea></label>
  </div><br><button class="primary">Save</button></form>`);
}
function rebuildCat(){const type=$("f_type").value;$("f_cat").innerHTML=sel(boot.categories.filter(x=>x.type===type),"")}
async function saveTxn(e,id){e.preventDefault();const p={type:$("f_type").value,amount:$("f_amount").value,date:$("f_date").value,category_id:$("f_cat").value,source_id:$("f_src").value,recurring:$("f_rec").checked,note:$("f_note").value};try{await api(id?`/api/transactions/${id}`:"/api/transactions",{method:id?"PUT":"POST",body:JSON.stringify(p)});closeModal();refreshAll()}catch(x){alert(x.message)}}
async function editTxn(id){const rows=await api("/api/transactions?"+q());openTxn(rows.find(x=>x.id===id))}
async function delTxn(id){if(confirm("Delete transaction?")){await api("/api/transactions/"+id,{method:"DELETE"});refreshAll()}}

function openCat(c=null){modal(c?"Edit category":"New category",`<form onsubmit="saveCat(event,${c?.id||0})"><div class="form-grid">
<label>Name<input id="c_name" required value="${esc(c?.name||"")}"></label><label>Type<select id="c_type"><option value="expense" ${c?.type!=="income"?"selected":""}>Expense</option><option value="income" ${c?.type==="income"?"selected":""}>Income</option></select></label>
<label>Icon<input id="c_icon" value="${esc(c?.icon||"•")}"></label><label>Color<input id="c_color" type="color" value="${c?.color||"#6366f1"}"></label></div><br><button class="primary">Save</button></form>`)}
async function saveCat(e,id){e.preventDefault();let p={name:$("c_name").value,type:$("c_type").value,icon:$("c_icon").value,color:$("c_color").value};try{await api(id?`/api/categories/${id}`:"/api/categories",{method:id?"PUT":"POST",body:JSON.stringify(p)});closeModal();refreshAll()}catch(x){alert(x.message)}}
function editCat(id){openCat(boot.categories.find(x=>x.id===id))}
async function delCat(id){if(confirm("Delete category?"))try{await api("/api/categories/"+id,{method:"DELETE"});refreshAll()}catch(x){alert(x.message)}}

function openSource(s=null){modal(s?"Edit source":"New payment source",`<form onsubmit="saveSource(event,${s?.id||0})"><div class="form-grid">
<label>Name<input id="s_name" required value="${esc(s?.name||"")}"></label><label>Kind<input id="s_kind" value="${esc(s?.kind||"Other")}"></label>
<label>Opening balance<input id="s_bal" type="number" step="0.01" value="${s?.opening_balance||0}"></label></div><br><button class="primary">Save</button></form>`)}
async function saveSource(e,id){e.preventDefault();let p={name:$("s_name").value,kind:$("s_kind").value,opening_balance:$("s_bal").value};try{await api(id?`/api/sources/${id}`:"/api/sources",{method:id?"PUT":"POST",body:JSON.stringify(p)});closeModal();refreshAll()}catch(x){alert(x.message)}}
function editSource(id){openSource(boot.sources.find(x=>x.id===id))}
async function delSource(id){if(confirm("Delete source?"))try{await api("/api/sources/"+id,{method:"DELETE"});refreshAll()}catch(x){alert(x.message)}}

function openInv(i=null){modal(i?"Edit investment":"New investment",`<form onsubmit="saveInv(event,${i?.id||0})"><div class="form-grid">
<label>Name<input id="i_name" required value="${esc(i?.name||"")}"></label><label>Type<select id="i_kind">${["Equity","Mutual Funds","FD","PPF","Others"].map(x=>`<option ${i?.kind===x?"selected":""}>${x}</option>`).join("")}</select></label>
<label>Contribution<input id="i_con" type="number" step="0.01" required value="${i?.contribution||""}"></label><label>Current value<input id="i_val" type="number" step="0.01" required value="${i?.current_value||""}"></label>
<label>Date<input id="i_date" type="date" required value="${i?.date||$("end").value}"></label><label class="full">Note<textarea id="i_note">${esc(i?.note||"")}</textarea></label>
</div><br><button class="primary">Save</button></form>`)}
async function saveInv(e,id){e.preventDefault();let p={name:$("i_name").value,kind:$("i_kind").value,contribution:$("i_con").value,current_value:$("i_val").value,date:$("i_date").value,note:$("i_note").value};try{await api(id?`/api/investments/${id}`:"/api/investments",{method:id?"PUT":"POST",body:JSON.stringify(p)});closeModal();refreshAll()}catch(x){alert(x.message)}}
function editInv(i){openInv(i)}
async function delInv(id){if(confirm("Delete investment entry?")){await api("/api/investments/"+id,{method:"DELETE"});refreshAll()}}

function openUser(){modal("Add household user",`<form onsubmit="saveUser(event)"><div class="form-grid">
<label>Name<input id="u_name" required></label><label>Email<input id="u_email" type="email" required></label><label>Password<input id="u_pw" type="password" required minlength="10"></label><label>Admin<input id="u_admin" type="checkbox"></label>
</div><br><button class="primary">Create</button></form>`)}
async function saveUser(e){e.preventDefault();try{await api("/api/users",{method:"POST",body:JSON.stringify({name:$("u_name").value,email:$("u_email").value,password:$("u_pw").value,is_admin:$("u_admin").checked})});closeModal();refreshAll()}catch(x){alert(x.message)}}
async function delUser(id){if(confirm("Delete user?"))try{await api("/api/users/"+id,{method:"DELETE"});refreshAll()}catch(x){alert(x.message)}}

$("modal").addEventListener("click",e=>{if(e.target.id==="modal")closeModal()});
refreshAll();
