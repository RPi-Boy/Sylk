// session.js - Manages Auth Persistence
const Session = {
    setToken: (token, email, username) => {
        localStorage.setItem("sylk_auth_token", token);
        localStorage.setItem("sylk_auth_email", email);
        localStorage.setItem("sylk_auth_username", username);
    },
    getToken: () => localStorage.getItem("sylk_auth_token"),
    getUsername: () => localStorage.getItem("sylk_auth_username"),
    clear: () => {
        localStorage.removeItem("sylk_auth_token");
        localStorage.removeItem("sylk_auth_email");
        localStorage.removeItem("sylk_auth_username");
        if (!window.location.pathname.endsWith("auth.html")) {
            window.location.href = "auth.html";
        }
    },
    requireAuth: () => {
        if (!Session.getToken() && !window.location.pathname.endsWith("auth.html")) {
            window.location.href = "auth.html";
        }
    }
};

// Auto-run auth check on page load if not on auth.html or landing page
if (!window.location.pathname.endsWith("auth.html") && !window.location.pathname.endsWith("index.html") && window.location.pathname !== "/") {
    Session.requireAuth();
}
