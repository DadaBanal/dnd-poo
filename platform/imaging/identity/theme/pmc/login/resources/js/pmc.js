// PMC's sign-in page: say when Caps Lock is on, as Voyager's sign-in does.
// A Windows password is case-sensitive, and after five wrong tries the sign-in
// waits before it will check again (identity/realm-pmc.json).
//
// The words come from the page (footer.ftl, messages_en.properties); this only
// moves the note under the password and fills or empties it. The note is a
// polite live region, so a screen reader hears it once, when it changes.
(function () {
  function start() {
    var password = document.getElementById('password');
    var note = document.getElementById('pmc-caps-lock');
    if (!password || !note) return;
    var group = password.closest('.pf-v5-c-form__group') || password.parentNode;
    group.appendChild(note);

    var text = note.getAttribute('data-text') || 'Caps Lock is on';
    function show(on) {
      var want = on ? text : '';
      if (note.textContent !== want) note.textContent = want;
    }
    function check(event) {
      if (event && typeof event.getModifierState === 'function') {
        show(event.getModifierState('CapsLock'));
      }
    }
    password.addEventListener('keydown', check);
    password.addEventListener('keyup', check);
    password.addEventListener('mousedown', check);
    password.addEventListener('blur', function () { show(false); });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
