const state = { data: [], filtered: [] };

async function load(){
    const res = await fetch('/gallery/api/items');
    state.data = await res.json();
    state.data.sort((a,b) => (b.created||'').localeCompare(a.created||''));
    state.filtered = state.data;
    render();
  
    // NEU: Hash (#id) auswerten und direkt öffnen
    const hash = decodeURIComponent(location.hash.replace('#',''));
    if (hash) openById(hash);
  }

function openById(id){
const item = state.data.find(x => x.id === id);
if (item) openItem(item);
}

dlg.addEventListener('close', ()=>{
    history.replaceState(null, '', location.pathname);
  });

function render(){
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  state.filtered.forEach(item=>{
    const card = document.createElement('div');
    card.style = 'border:1px solid #333;border-radius:12px;padding:8px;background:#111;cursor:pointer;';
    card.onclick = () => openItem(item);
    card.innerHTML = `
      <img src="${item.thumb||item.image}" style="width:100%;height:140px;object-fit:cover;border-radius:8px;">
      <div style="font-weight:600;margin:.4rem 0 .2rem;">${item.title||'(ohne Titel)'}</div>
      <div style="font-size:.9rem;color:#aaa;">${[item.year,item.location].filter(Boolean).join(' • ')}</div>
    `;
    grid.appendChild(card);
  });
}

function openItem(item){
    const tags = (item.tags||[]).map(t=>`<span style="display:inline-block;background:#222;padding:.2rem .5rem;border-radius:999px;margin-right:.3rem;font-size:.85rem;">#${t}</span>`).join('');
    document.getElementById('modal').innerHTML = `
      <img src="${item.image}" style="width:100%;border-radius:12px;">
      <h2 style="margin:.6rem 0 0">${item.title||'(ohne Titel)'}</h2>
      ${item.artist ? `<p><strong>Künstler:</strong> ${item.artist}</p>` : ''}
      <div style="color:#aaa;margin-top:.2rem">
        ${item.year ? `Jahr: ${item.year}<br>` : ''}
        ${item.location_painted ? `Ort (gemalt): ${item.location_painted}<br>` : ''}
        ${item.location_bought ? `Ort (gekauft): ${item.location_bought}<br>` : ''}
      </div>
      <p style="margin-top:.6rem">${item.description||''}</p>
      ${tags}
      ${item.created ? `<p style="color:#666;margin-top:.5rem;">Angelegt: ${item.created}</p>` : ''}
      <p class="muted">ID: <code>${item.id}</code></p>
  
      <!-- NEU: Button -->
      <button onclick="deleteItem('${item.id}')"
              style="margin-top:1rem;padding:.5rem 1rem;
                     background:#c62828;color:white;
                     border:none;border-radius:6px;cursor:pointer;">
        🗑️ Löschen
      </button>
    `;
    dlg.showModal();
  }
  
async function deleteItem(id){
const pw = prompt("Bitte Passwort zum Löschen eingeben:");
if(!pw) return;

const formData = new FormData();
formData.append("password", pw);

const res = await fetch(`/gallery/delete/${id}`, { method: "POST", body: formData });
const data = await res.json();

if(data.success){
    dlg.close();
    load();
} else {
    alert("Fehler: " + (data.error || "unbekannt"));
}
}
  
load();
