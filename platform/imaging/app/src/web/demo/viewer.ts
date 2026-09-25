// The sample's viewer page: a picture of the real viewer (OHIF, in the
// platform) on a synthetic study of the same kind, because the real one
// needs the imaging engine. Opened by the list's Open links in the viewer's
// own window, by Compare with a prior beside it, and by the reading room in
// its two frames (whose keys, Esc, J and K, this page hears like the real
// viewer's document does).
import { kindOfUid } from './data.ts';
import './viewer.css';

const params = new URLSearchParams(location.search);
const study = params.get('study') ?? '';
const prior = params.get('prior');
const stage = document.getElementById('stage')!;

function picture(uid: string, caption: string): HTMLElement {
  const kind = kindOfUid(uid);
  const fig = document.createElement('figure');
  fig.className = 'pane';
  const img = document.createElement('img');
  img.src = kind ? `sample/viewer-${kind.modality}.jpg` : 'sample/viewer-CT.jpg';
  img.alt = kind ? `The viewer on a synthetic ${kind.modality} study` : 'The viewer';
  img.decoding = 'async';
  const cap = document.createElement('figcaption');
  cap.textContent = caption;
  fig.append(img, cap);
  return fig;
}

const kind = kindOfUid(study);
stage.append(picture(study, `${kind?.modality ?? 'The'} study, as the viewer shows it`));
if (prior) {
  stage.classList.add('compare');
  stage.append(picture(prior, 'The earlier study, beside it'));
}
const note = document.createElement('p');
note.className = 'note';
note.innerHTML = 'Sample: this is a <b>picture</b> of the viewer (OHIF 3.13) on a synthetic study of this kind. In the platform it is the viewer itself, live, with every tool.';
stage.append(note);
