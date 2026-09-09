/* ---- the study sheet ---------------------------------------------------- */
const sheet = $('#sheet');
let openIndex = -1;
function viewerLinks(s) {
  return state.viewers.map(v => ({ ...v, href: API.url(v.tpl.replace('{orthancId}', s.id).replace('{studyUid}', encodeURIComponent(s.uid))) }));
}
async function openStudy(i) {
  const s = state.studies[i]; if (!s) return;
  openIndex = i; state.cursor = i; markCursor();
  $('#sheetTitle').textContent = s.name;
  $('#sheetSub').textContent = [s.pid, s.sex, age(s.dob, s.date), s.acc && `Acc ${s.acc}`].filter(Boolean).join('  ·  ');
  $('#sheetTags').innerHTML = `${modBadges(s.mod)}
    <span class="badge badge--soft">${esc(when(s.date))}</span>
    ${s.nSeries ? `<span class="badge badge--soft">${s.nSeries} series</span>` : ''}
    ${s.nInst ? `<span class="badge badge--soft">${s.nInst} images</span>` : ''}`;
  const links = viewerLinks(s).filter(v => v.rank < 9);   // clinical viewers only; the admin UI lives under System
  // The built-in viewer is first because it is the only one that needs nothing
  // installed on the server: on the day a viewer plugin fails to load, this is
  // still there. The plugin viewers stay, listed after it, unchanged.
  $('#sheetFoot').innerHTML = `
    <button class="btn btn--primary" id="openViewer"><svg><use href="#i-eye"/></svg>Open in PMC Viewer</button>
    ${links.map(v => `<a class="btn" href="${esc(v.href)}" target="_blank" rel="noopener">
        <svg><use href="#i-open"/></svg>${esc(v.label)}</a>`).join('')}
    ${CFG.features.download ? `<a class="btn" href="${esc(API.url(`studies/${s.id}/archive`))}" download>
        <svg><use href="#i-download"/></svg>DICOM (.zip)</a>` : ''}
    <div class="spacer"></div>
    <button class="btn btn--ghost btn--icon" id="copyUid" title="Copy the study UID" aria-label="Copy the study UID"><svg><use href="#i-copy"/></svg></button>`;
  $('#sheetBody').innerHTML = `
    <dl class="kv">
      <dt>Study</dt><dd>${esc(s.desc || '—')}</dd>
      <dt>Performed</dt><dd>${s.date ? esc(s.date.toLocaleString(undefined,{dateStyle:'full', timeStyle:'short'})) : '—'}</dd>
      <dt>Referred by</dt><dd>${esc(personName(s.referrer) || '—')}</dd>
      <dt>Accession</dt><dd class="mono">${esc(s.acc || '—')}</dd>
      <dt>Study UID</dt><dd class="mono">${esc(s.uid || '—')}</dd>
    </dl>
    <h3 style="font-size:14.5px;margin-top:18px">Series</h3><div class="rule-dot"></div>
    <div class="series" id="seriesWrap">${'<div class="skel" style="height:180px"></div>'.repeat(3)}</div>
    <details><summary>Everything the archive holds for this study</summary>
      <div class="inner"><table class="tagtable"><tbody>
        ${Object.entries({ ...s.raw.PatientMainDicomTags, ...s.raw.MainDicomTags })
          .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}
        <tr><td>OrthancID</td><td>${esc(s.id)}</td></tr>
      </tbody></table></div></details>`;
  $('#openViewer').onclick = () => { sheet.close(); openViewer(s); };
  $('#copyUid').onclick = async () => {
    try { await navigator.clipboard.writeText(s.uid); toast('Study UID copied', 'ok'); }
    catch { toast('Copy is blocked in this browser', 'warn'); }
  };
  if (!sheet.open) sheet.showModal();
  try {
    const series = await API.get(`studies/${s.id}/series`);
    series.sort((a, b) => (+a.MainDicomTags?.SeriesNumber || 0) - (+b.MainDicomTags?.SeriesNumber || 0));
    $('#seriesWrap').innerHTML = series.map((se, k) => `
      <div class="serie">
        <div class="thumb" data-study="${esc(s.id)}" data-mod="${esc(se.MainDicomTags?.Modality || s.mod[0] || '')}" data-seed="${k + 3}" data-serie="${esc(se.ID)}">
          <div class="thumb__ph" style="font-size:18px">${esc(se.MainDicomTags?.Modality || '')}</div>
          <img alt="" decoding="async">
        </div>
        <div class="serie__b">
          <b title="${esc(se.MainDicomTags?.SeriesDescription || '')}">${esc(se.MainDicomTags?.SeriesDescription || `Series ${se.MainDicomTags?.SeriesNumber || k + 1}`)}</b>
          <span>${se.Instances ? `${se.Instances.length} image${se.Instances.length === 1 ? '' : 's'}` : ''}</span>
        </div>
      </div>`).join('') || '<p style="color:var(--text-3)">This study has no series.</p>';
    $$('#seriesWrap .thumb').forEach(box => {
      if (state.demo) { fillThumb(box); return; }
      const se = series.find(x => x.ID === box.dataset.serie);
      const iid = se?.Instances?.[Math.floor((se.Instances.length - 1) / 2)];
      if (!iid) return;
      const img = box.querySelector('img');
      img.onerror = () => { img.onerror = () => img.remove(); img.src = API.url(`instances/${iid}/frames/0/preview`); };
      img.onload = () => img.classList.add('ready');
      img.src = API.url(`instances/${iid}/preview`);
    });
  } catch (e) { $('#seriesWrap').innerHTML = `<p style="color:var(--text-3)">Series could not be read (${esc(e.status || e.message)}).</p>`; }
}
$('#sheetClose').onclick = () => sheet.close();
sheet.addEventListener('click', e => { if (e.target === sheet) sheet.close(); });
$$('[data-close]').forEach(b => b.onclick = () => $('#' + b.dataset.close).close());

