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

// Pages that do NOT require authentication to view
const PUBLIC_PAGES = [
    "auth.html",
    "index.html",
    "logs.html",
    "metrics.html",
    "projects.html",
    "deploy.html",
    "/"
];

const currentPath = window.location.pathname;
const isPublicPage = PUBLIC_PAGES.some(page => currentPath.endsWith(page) || currentPath === page);

if (!isPublicPage) {
    Session.requireAuth();
}
