/* ---- activity ----------------------------------------------------------- */
async function loadActivity() {
  const [stats, changes, jobs] = await Promise.all([
    API.get('statistics').catch(() => null),
    API.get('changes?last').catch(() => null),
    API.get('jobs?expand').catch(() => [])
  ]);
  if (stats) $('#actStats').innerHTML = `
    <div class="stat"><b>${(+stats.CountStudies).toLocaleString()}</b><span>Studies</span></div>
    <div class="stat g"><b>${(+stats.CountSeries).toLocaleString()}</b><span>Series</span></div>
    <div class="stat o"><b>${(+stats.CountInstances).toLocaleString()}</b><span>Images</span></div>
    <div class="stat k"><b>${bytes(+stats.TotalDiskSize || (+stats.TotalDiskSizeMB || 0) * 1048576)}</b><span>On disk</span></div>`;
  const ch = changes?.Changes || [];
  $('#changeList').innerHTML = ch.length ? ch.slice(0, 14).map(c => `
    <div class="row"><span class="dot ${c.ChangeType === 'StableStudy' ? '' : 'idle'}"></span>
      <div class="row__main"><div class="row__t">${esc(c.ChangeType.replace(/([a-z])([A-Z])/g,'$1 $2'))}</div>
      <div class="row__s">${esc(c.ID)}</div></div>
      <span class="badge badge--grey">${esc(when(dicomDate((c.Date||'').slice(0,8), (c.Date||'').slice(9,15))))}</span>
    </div>`).join('') : '<p style="color:var(--text-3)">No recent arrivals.</p>';
  $('#jobList').innerHTML = jobs.length ? jobs.slice(0, 14).map(j => `
    <div class="row"><span class="dot ${j.State === 'Success' ? '' : j.State === 'Failure' ? 'bad' : 'warn'}"></span>
      <div class="row__main"><div class="row__t">${esc(j.Type)}</div><div class="row__s">${esc(j.ID)}</div>
        ${j.State === 'Running' ? `<div class="bar"><i style="width:${+j.Progress || 0}%"></i></div>` : ''}</div>
      <span class="badge ${j.State === 'Success' ? 'badge--green' : j.State === 'Failure' ? 'badge--orange' : 'badge--soft'}">${esc(j.State)}</span>
    </div>`).join('') : '<p style="color:var(--text-3)">Nothing running.</p>';
}

