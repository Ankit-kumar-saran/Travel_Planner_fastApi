// Shared helpers used by every page. Plain JavaScript, no libraries.

// ====== CONFIG: change this if your backend runs on another address ======
const API_BASE = "http://127.0.0.1:8000";


// ---------- Login state (stored in the browser's localStorage) ----------

function getToken() {
  return localStorage.getItem("token");
}

function getUser() {
  try {
    return JSON.parse(localStorage.getItem("user"));
  } catch (e) {
    return null;
  }
}

function saveLogin(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

function clearLogin() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

function isLoggedIn() {
  return !!getToken();
}

function logout() {
  clearLogin();
  window.location.href = "login.html";
}

// Call at the top of pages that need a logged-in user
function requireLogin() {
  if (!isLoggedIn()) {
    const here = window.location.pathname.split("/").pop() + window.location.search;
    window.location.href = "login.html?next=" + encodeURIComponent(here);
    return false;
  }
  return true;
}


// ---------- Small helpers ----------

// Escape text before putting it inside innerHTML. Place names come from outside
// (OpenStreetMap / Google), so we never trust them.
function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function money(value) {
  return "₹" + Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function stars(rating) {
  if (rating === null || rating === undefined) return "No rating";
  return "★ " + Number(rating).toFixed(1);
}

// Read a value from the page URL, e.g. param("id") for place.html?id=5
function param(name) {
  return new URLSearchParams(window.location.search).get(name);
}

// Show (or hide, if text is empty) a message box. type: "error" | "success" | "info"
function showMessage(element, text, type) {
  element.className = "msg " + (type || "error");
  element.textContent = text || "";
  element.style.display = text ? "block" : "none";
}


// ---------- Talking to the backend ----------

// FastAPI sends errors as {"detail": "text"} or, for validation errors, a list.
function formatError(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (data && Array.isArray(data.detail)) {
    return data.detail
      .map(function (d) {
        const field = (d.loc || []).slice(1).join(".");
        return field ? field + ": " + d.msg : d.msg;
      })
      .join("; ");
  }
  return "Request failed (" + status + ")";
}

// api("/places/3")                                    -> GET
// api("/favorites", {method: "POST", body: {...}})    -> POST with JSON
// Pass {auth: false} for calls that must not send the token (login, register).
async function api(path, options) {
  options = options || {};
  const method = options.method || "GET";
  const headers = {};
  const token = getToken();

  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (token && options.auth !== false) headers["Authorization"] = "Bearer " + token;

  let response;
  try {
    response = await fetch(API_BASE + path, {
      method: method,
      headers: headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (e) {
    throw new Error("Cannot reach the server. Is the backend running at " + API_BASE + " ?");
  }

  if (response.status === 204) return null;      // success with no body (DELETE)

  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    // body was not JSON; data stays null
  }

  if (!response.ok) {
    // Token expired or invalid: log out and go to the login page
    if (response.status === 401 && token && options.auth !== false) {
      clearLogin();
      const here = window.location.pathname.split("/").pop() + window.location.search;
      window.location.href = "login.html?next=" + encodeURIComponent(here);
    }
    throw new Error(formatError(data, response.status));
  }
  return data;
}


// ---------- Navigation bar (same on every page) ----------

function renderNav(active) {
  const nav = document.getElementById("nav");
  if (!nav) return;
  const user = getUser();

  function link(page, label, key) {
    return '<a href="' + page + '"' + (active === key ? ' class="active"' : "") + ">" + label + "</a>";
  }

  let html = link("index.html", "Explore", "explore");
  if (isLoggedIn()) {
    html += link("favorites.html", "Favorites", "favorites");
    html += link("trips.html", "My Trips", "trips");
    if (user && user.role === "admin") html += link("admin.html", "Admin", "admin");
    html += '<span class="who">' + esc(user ? user.name : "") + "</span>";
    html += '<a href="#" id="logout-link">Logout</a>';
  } else {
    html += link("login.html", "Login", "login");
    html += link("register.html", "Register", "register");
  }
  nav.innerHTML = html;

  const logoutLink = document.getElementById("logout-link");
  if (logoutLink) {
    logoutLink.addEventListener("click", function (event) {
      event.preventDefault();
      logout();
    });
  }
}
