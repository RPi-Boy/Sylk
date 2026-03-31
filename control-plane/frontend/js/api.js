// api.js - Unified Control Plane Client
const API_BASE = "";

class SylkAPI {
    static async fetchWithAuth(endpoint, options = {}) {
        const token = Session.getToken();
        const headers = {
            "Content-Type": "application/json",
            ...options.headers
        };

        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });

            if (response.status === 401) {
                console.error("Unauthorized: Token expired or invalid.");
                Session.clear();
                return null;
            }
            return response.json();
        } catch (error) {
            console.error("API Fetch Error:", error);
            throw error;
        }
    }

    static async login(email, password) {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Invalid credentials");
        }
        return response.json();
    }

    static async signup(username, email, password) {
        const response = await fetch(`${API_BASE}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Signup failed");
        }
        return response.json();
    }

    static async submitTask(code, language = "python", hardware_pref = "default") {
        return this.fetchWithAuth("/tasks", {
            method: 'POST',
            body: JSON.stringify({ code, language, hardware_pref })
        });
    }

    static async deployFunction(slug, code, language) {
        const response = await fetch(`${API_BASE}/functions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug, code, language })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || `Deploy failed (${response.status})`);
        }
        return data;
    }

    static async getNodes() {
        return this.fetchWithAuth("/nodes");
    }

    static async getAnalytics() {
        return this.fetchWithAuth("/analytics/stats");
    }

    static getTelemetryUrl() {
        return `${API_BASE}/telemetry?token=${Session.getToken()}`;
    }
}
