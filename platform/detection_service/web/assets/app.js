/* ICS Guardian - shared header/nav/logo + auth state. Included on every page. */
(function () {
  const API = location.origin;                    // same-origin FastAPI
  const LOGO = `<svg viewBox="0 0 48 48" aria-label="ICS Guardian">
    <defs>
      <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1d4ed8"/><stop offset="1" stop-color="#0e6fbf"/></linearGradient>
      <linearGradient id="dg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fd3ff"/><stop offset="1" stop-color="#4a9fe0"/></linearGradient>
    </defs>
    <path d="M24 3 L41 9 V23 C41 34 33 41 24 45 C15 41 7 34 7 23 V9 Z" fill="url(#lg)" stroke="#2b62c9"/>
    <path d="M24 14 C24 14 31 22 31 27.5 A7 7 0 0 1 17 27.5 C17 22 24 14 24 14 Z" fill="url(#dg)"/>
    <circle cx="21.5" cy="26.5" r="1.7" fill="#fff" opacity=".8"/>
    <path d="M20 30.5 L23 33.2 L29 26.8" fill="none" stroke="#0b2a52" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;

  const NAV = [
    ["index.html", "Home"], ["about.html", "About"], ["architecture.html", "Architecture"],
    ["live-demo.html", "Live Demo"], ["soc-dashboard.html", "SOC"], ["console.html", "Console"],
    ["devsecops.html", "DevSecOps"], ["monitoring.html", "Monitoring"], ["media.html", "Media"],
  ];
  // Tabs only an admin may see/open. Operators never get these (hidden in the nav
  // and blocked by the head guard). Keep this in sync with the guard in build_site.py.
  const ADMIN_ONLY = new Set(["architecture.html", "devsecops.html", "media.html"]);

  // ---- token store ----
  const T = {
    get: () => sessionStorage.getItem("icsg_token"),
    user: () => { try { return JSON.parse(sessionStorage.getItem("icsg_user") || "null"); } catch { return null; } },
    set: (tok, u) => { sessionStorage.setItem("icsg_token", tok); sessionStorage.setItem("icsg_user", JSON.stringify(u)); },
    clear: () => { sessionStorage.removeItem("icsg_token"); sessionStorage.removeItem("icsg_user"); },
  };
  window.ICSG = { API, T,
    async api(path, opts = {}) {
      opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
      const tok = T.get(); if (tok) opts.headers["Authorization"] = "Bearer " + tok;
      let r;
      try { r = await fetch(API + path, opts); }
      catch (e) {
        const hint = location.protocol === "file:"
          ? "You opened the page as a local file. Login needs the server: run  docker compose up  and open  http://localhost:8000"
          : "Cannot reach the API. Make sure the backend is running (docker compose up) and you are on the same address (http://localhost:8000).";
        throw Object.assign(new Error(hint), { network: true });
      }
      let body = null; try { body = await r.json(); } catch {}
      if (!r.ok) {
        // FastAPI may return detail as a string OR an array of {loc,msg,type} objects.
        let msg = r.statusText;
        const d = body && body.detail;
        if (typeof d === "string") msg = d;
        else if (Array.isArray(d)) msg = d.map(x => (x && x.msg) ? x.msg : (typeof x === "string" ? x : JSON.stringify(x))).join("; ");
        else if (d && typeof d === "object") msg = d.msg || JSON.stringify(d);
        throw Object.assign(new Error(msg), { status: r.status, body });
      }
      return body;
    },
    logout() { T.clear(); location.href = "index.html"; },
  };

  const cur = (location.pathname.split("/").pop() || "index.html");

  function authArea() {
    const u = T.user();
    if (u) {
      const admin = u.role === "admin"
        ? `<a href="admin.html" class="btn sec" style="padding:6px 10px">Admin</a>` : "";
      return `${admin}
        <a href="account.html" class="who" title="My account"><b>${u.email}</b></a>
        <span class="badge-role ${u.role}">${u.role}</span>
        <button class="btn ghost" style="padding:6px 10px" onclick="ICSG.logout()">Logout</button>`;
    }
    return `<a href="login.html" class="btn sec" style="padding:6px 12px">Login</a>
            <a href="register.html" class="btn" style="padding:6px 12px">Sign up</a>`;
  }

  const isPublic = /^(login|register)\.html$/.test(cur);

  function render() {
    const header = document.createElement("header");
    header.className = "nav";
    if (isPublic) {
      // login / register: NEVER show tabs. Just the brand. Tabs only appear after
      // sign-in (on the real pages), filtered by the account's role.
      header.innerHTML =
        `<nav class="links"></nav><div class="auth"></div>
         <a class="brand" href="login.html" title="ICS Guardian">
           ${LOGO}<span class="bt"><span class="n">ICS<span> Guardian</span></span><span class="s">OT Security</span></span>
         </a>`;
    } else {
      const role = (T.user() || {}).role;
      const links = NAV.filter(([h]) => role === "admin" || !ADMIN_ONLY.has(h));
      header.innerHTML =
        `<nav class="links">${links.map(([h, l]) =>
          `<a href="${h}" class="${h === cur ? "active" : ""}">${l}</a>`).join("")}</nav>
         <div class="auth">${authArea()}</div>
         <a class="brand" href="index.html" title="ICS Guardian home">
           ${LOGO}<span class="bt"><span class="n">ICS<span> Guardian</span></span><span class="s">OT Security</span></span>
         </a>`;
    }
    document.body.insertBefore(header, document.body.firstChild);

    const f = document.createElement("footer");
    f.className = "ft";
    f.innerHTML = `ICS Guardian &middot; Cloud-Native DevSecOps platform for protecting water-chlorination ICS &middot;
      <a href="about.html">About</a> &middot; <span id="apihealth" class="mut">checking API...</span>`;
    document.body.appendChild(f);
    pingHealth();
    // revalidate token with the server; only bounce to login if it is truly
    // invalid/expired (401) - not on a transient network error (backend down).
    if (T.get() && !isPublic) ICSG.api("/auth/me").catch((e) => {
      if (e && e.status === 401) { T.clear(); location.replace("login.html"); }
    });
  }

  async function pingHealth() {
    const el = document.getElementById("apihealth"); if (!el) return;
    try { const h = await ICSG.api("/health"); el.innerHTML = h.model_loaded
      ? '<span style="color:#7fe0ac">API online &middot; model loaded</span>'
      : '<span style="color:#f5c451">API online &middot; model not loaded</span>'; }
    catch { el.innerHTML = '<span style="color:#93a6c2">API offline (static preview)</span>'; }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
  else render();
})();
