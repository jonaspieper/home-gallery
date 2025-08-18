let EXPECTED_LEN = null;

async function loadEmbInfo(){
  try{
    const r = await fetch('/gallery/api/embeddings_info');
    const j = await r.json();
    EXPECTED_LEN = j.file_dim || j.model_dim || null; // z.B. 1001
    console.log('EXPECTED_LEN from server:', EXPECTED_LEN);
  }catch(e){
    console.warn('embeddings_info fehlgeschlagen', e);
  }
}

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

// --- Embedding-Suche (ML) ---
let tfReady = false, mobilenetModel = null, embDB = null;

async function ensureModel(){
  if (mobilenetModel) return;
  // mobilenet.load() lädt ein vortrainiertes MobilenetV2
  mobilenetModel = await mobilenet.load({version: 2, alpha: 1.0});
  tfReady = true;
}

async function loadEmbeddings(){
    if (embDB) return;
    const res = await fetch('/gallery/api/embeddings');
    const data = await res.json();
    // zuerst erwartete Länge holen
    if (!EXPECTED_LEN) await loadEmbInfo();
    embDB = data.map(r => {
      const vec = new Float32Array(r.vector);
      const vAdj = l2norm(normalizeVecTo(vec, EXPECTED_LEN));
      return { id: r.id, image: r.image, v: vAdj };
    });
    console.log('Embeddings geladen:', embDB.length, 'Dim:', embDB[0]?.v.length);
  }

function cosine(a, b){
  let dot=0, na=0, nb=0;
  for(let i=0;i<a.length;i++){ const x=a[i], y=b[i]; dot+=x*y; na+=x*x; nb+=y*y; }
  const denom = Math.sqrt(na)*Math.sqrt(nb) || 1;
  return dot/denom;
}

async function fileToTensor(file){
  const img = await new Promise(resolve => {
    const im = new Image(); im.onload=()=>resolve(im);
    im.src = URL.createObjectURL(file);
  });
  // tf.browser.fromPixels → [h,w,3], Mobilenet skaliert intern passend
  const input = tf.browser.fromPixels(img);
  return input;
}

async function embedImageTensorAdaptive(t){
    await ensureModel();
  
    let arr = null;
  
    try {
      const logits = mobilenetModel.infer(t, 'conv_preds');   // [1,1000 oder 1001]
      const v = tf.div(logits, tf.norm(logits));
      arr = await v.data();
      tf.dispose([logits, v]);
    } catch(e) {
      // fallback: average pooling (1280D)
      const pooled = mobilenetModel.infer(t, { pooling: 'avg' }); 
      const v2 = tf.div(pooled, tf.norm(pooled));
      arr = await v2.data();
      tf.dispose([pooled, v2]);
    }
  
    if (!EXPECTED_LEN) await loadEmbInfo();
    const adj = l2norm(normalizeVecTo(arr, EXPECTED_LEN));
    return adj;
  }
  

  async function mlSearchFromFile(file){
    await ensureModel();
    await loadEmbeddings();
    if(!embDB || embDB.length===0){ alert('Keine Embeddings auf dem Server gefunden.'); return; }
  
    const px = await fileToTensor(file);
    const input = tf.tidy(()=> tf.image.resizeBilinear(px, [224,224]).toFloat()
                                  .div(127.5).sub(1.0).expandDims());
    px.dispose();
  
    const q = await embedImageTensorAdaptive(input);
    input.dispose();
  
    console.log('Query len:', q.length, 'DB len:', embDB[0]?.v.length, 'EXPECTED_LEN:', EXPECTED_LEN);
  
    let best = {id:null, score:-2};
    for(const r of embDB){
      // Längen sind jetzt gleich – zur Sicherheit:
      if (r.v.length !== q.length) continue;
      const s = cosine(q, r.v);
      // Debug:
      // console.log(r.id, s.toFixed(4));
      if (s > best.score) best = {id:r.id, score:s};
    }
    console.log('Best:', best.id, 'Score:', best.score);
  
    if(best.id && best.score >= 0.70){
      openById(best.id);
    } else {
      alert('Kein Match. Score: '+best.score.toFixed(3));
    }
  }
  


// Buttons verdrahten
document.getElementById('ml-snap')?.addEventListener('click', ()=>{
  document.getElementById('ml-file').click();
});
document.getElementById('ml-file')?.addEventListener('change', (e)=>{
  const f = e.target.files?.[0];
  if (f) mlSearchFromFile(f);
});

function normalizeVecTo(v, targetLen){
    if (!targetLen || v.length === targetLen) return v;
    const arr = Array.from(v);
    if (v.length < targetLen) {
      // mit Nullen auffüllen
      const pad = new Array(targetLen - v.length).fill(0);
      return new Float32Array(arr.concat(pad));
    } else {
      // hart auf Ziel-Länge abschneiden
      return new Float32Array(arr.slice(0, targetLen));
    }
  }
  
  function l2norm(v){
    let s=0; for(let i=0;i<v.length;i++) s += v[i]*v[i];
    const n = Math.sqrt(s) || 1;
    const out = new Float32Array(v.length);
    for(let i=0;i<v.length;i++) out[i] = v[i]/n;
    return out;
  }
  

await loadEmbInfo();

load();
