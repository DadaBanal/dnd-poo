/* ---- normalising a study ------------------------------------------------ */
function norm(s) {
  const m = s.MainDicomTags || {}, p = s.PatientMainDicomTags || {}, r = s.RequestedTags || {};
  const d = dicomDate(m.StudyDate, m.StudyTime);
  return {
    id: s.ID, uid: m.StudyInstanceUID || '',
    name: personName(p.PatientName), rawName: p.PatientName || '',
    pid: p.PatientID || '', sex: p.PatientSex || '', dob: p.PatientBirthDate || '',
    acc: m.AccessionNumber || '', desc: m.StudyDescription || '', date: d, dateRaw: m.StudyDate || '',
    mod: (r.ModalitiesInStudy || '').split('\\').filter(Boolean),
    nSeries: +r.NumberOfStudyRelatedSeries || (s.Series ? s.Series.length : 0),
    nInst: +r.NumberOfStudyRelatedInstances || 0,
    referrer: m.ReferringPhysicianName || '', raw: s
  };
}

