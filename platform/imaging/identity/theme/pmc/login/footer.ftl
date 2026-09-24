<#macro content>
<#-- PMC: under the sign-in form. Which password this is, and who can help.
     The Caps Lock note starts empty here; js/pmc.js moves it under the
     password and fills it while Caps Lock is on. -->
<p id="pmc-caps-lock" class="pmc-caps-lock" role="status" data-text="${msg("pmcCapsLock")}"></p>
<p class="pmc-help">${msg("pmcHelp")}</p>
</#macro>
