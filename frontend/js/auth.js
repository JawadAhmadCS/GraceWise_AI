// Authentication + account access system
class AuthSystem {
    constructor() {
        this.apiBaseUrl = window.API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:5000`;
        this.currentUser = JSON.parse(localStorage.getItem('currentUser') || 'null');
        this.accessToken = localStorage.getItem('access_token') || null;
    }

    setApiBaseUrl() {
        if (window.API_BASE_URL) {
            this.apiBaseUrl = window.API_BASE_URL;
        }
    }

    persistSession(token, user) {
        this.accessToken = token;
        this.currentUser = user;
        localStorage.setItem('access_token', token);
        localStorage.setItem('currentUser', JSON.stringify(user));
    }

    clearSession() {
        this.currentUser = null;
        this.accessToken = null;
        localStorage.removeItem('currentUser');
        localStorage.removeItem('access_token');
    }

    // Register new user
    async register(userData) {
        this.setApiBaseUrl();
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    first_name: userData.firstName,
                    last_name: userData.lastName || '',
                    email: userData.email,
                    password: userData.password
                })
            });

            const data = await response.json();
            if (!response.ok) {
                return { success: false, message: data.message || 'Registration failed.' };
            }

            return { success: true, message: data.message || 'Registration successful! Please log in.' };
        } catch (_) {
            return { success: false, message: 'Network error. Please try again.' };
        }
    }

    // Login user
    async login(email, password) {
        this.setApiBaseUrl();
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();
            if (!response.ok) {
                return { success: false, message: data.message || 'Invalid email or password.' };
            }

            this.persistSession(data.access_token, data.user);
            return { success: true, message: data.message || 'Login successful!' };
        } catch (_) {
            return { success: false, message: 'Network error. Please try again.' };
        }
    }

    async forgotPassword(email) {
        this.setApiBaseUrl();
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/forgot-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            const data = await response.json();
            return { success: response.ok, message: data.message || 'Please check your email.' };
        } catch (_) {
            return { success: false, message: 'Network error. Please try again.' };
        }
    }

    async resetPassword(token, newPassword) {
        this.setApiBaseUrl();
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, new_password: newPassword })
            });
            const data = await response.json();
            return { success: response.ok, message: data.message || 'Password reset response received.' };
        } catch (_) {
            return { success: false, message: 'Network error. Please try again.' };
        }
    }

    async validateResetToken(token) {
        this.setApiBaseUrl();
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/reset-password/validate?token=${encodeURIComponent(token)}`);
            const data = await response.json();
            return { valid: response.ok && !!data.valid, message: data.message || '' };
        } catch (_) {
            return { valid: false, message: 'Could not validate reset token.' };
        }
    }

    async syncCurrentUser() {
        this.setApiBaseUrl();
        if (!this.accessToken) return null;
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/me`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.accessToken}`,
                    'Content-Type': 'application/json'
                }
            });
            if (!response.ok) return null;
            const data = await response.json();
            if (data.user) {
                this.currentUser = data.user;
                localStorage.setItem('currentUser', JSON.stringify(data.user));
                return data.user;
            }
            return null;
        } catch (_) {
            return null;
        }
    }

    logout() {
        this.clearSession();
        window.location.href = 'index.html';
    }

    isLoggedIn() {
        return this.currentUser !== null && !!this.accessToken;
    }

    getCurrentUser() {
        return this.currentUser;
    }

    getEffectiveTier() {
        const user = this.currentUser || {};
        const tier = (user.effective_tier || user.subscription_tier || 'free').toLowerCase();
        return tier;
    }

    hasActiveSubscription() {
        const user = this.currentUser || {};
        if (typeof user.subscription_active === 'boolean') {
            return user.subscription_active;
        }
        return this.getEffectiveTier() !== 'free';
    }

    needsOnboarding() {
        const user = this.currentUser || {};
        if (!this.hasActiveSubscription()) return false;
        return !user.onboarding_completed;
    }

    updateUser(userData) {
        if (!this.currentUser) return;
        this.currentUser = { ...this.currentUser, ...userData };
        localStorage.setItem('currentUser', JSON.stringify(this.currentUser));
    }

    redirectAfterLogin() {
        if (!this.currentUser) {
            window.location.href = 'sign_in.html';
            return;
        }

        if (this.currentUser.is_admin) {
            window.location.href = 'admin-dashboard.html';
            return;
        }

        if (this.hasActiveSubscription() && this.needsOnboarding()) {
            window.location.href = 'onboarding.html';
            return;
        }

        window.location.href = 'dashboard.html';
    }

    checkAccess() {
        this.setApiBaseUrl();

        const currentPage = window.location.pathname.split('/').pop() || 'index.html';
        const adminPages = ['admin-dashboard.html', 'all-users.html', 'admin-curriculum.html', 'admin-quiz.html', 'admin-settings.html'];

        const userPages = [
            'dashboard.html',
            'family.html',
            'learning.html',
            'records.html',
            'child-profile.html',
            'curriculum.html',
            'planner.html',
            'quiz.html',
            'ai-assistant.html',
            'devotional.html',
            'progress.html',
            'settings.html',
            'onboarding.html',
            'payment-success.html'
        ];

        if (adminPages.includes(currentPage)) {
            if (!this.isLoggedIn() || !this.currentUser.is_admin) {
                if (typeof showError === 'function') {
                    showError('Access denied. Admin privileges required.');
                }
                window.location.href = 'index.html';
                return false;
            }
            return true;
        }

        if (userPages.includes(currentPage) && !this.isLoggedIn()) {
            if (typeof showWarning === 'function') {
                showWarning('Please sign in to continue.');
            }
            window.location.href = 'sign_in.html';
            return false;
        }

        if (!this.isLoggedIn() || this.currentUser?.is_admin) {
            return true;
        }

        const onboardingAllowedPages = ['onboarding.html', 'premium-plan.html', 'settings.html', 'payment-success.html', 'dashboard.html'];
        const paidOnlyPages = [
            'planner.html',
            'ai-assistant.html',
            'devotional.html',
            'progress.html',
            'curriculum.html'
        ];

        // Let free users use landing + dashboard; only hard-gate specific paid tools.
        if (!this.hasActiveSubscription() && paidOnlyPages.includes(currentPage)) {
            window.location.href = 'premium-plan.html';
            return false;
        }

        if (this.needsOnboarding() && !onboardingAllowedPages.includes(currentPage)) {
            window.location.href = 'onboarding.html';
            return false;
        }

        if (currentPage === 'premium-plan.html' && this.hasActiveSubscription()) {
            if (this.needsOnboarding()) {
                window.location.href = 'onboarding.html';
            } else {
                window.location.href = 'dashboard.html';
            }
            return false;
        }

        if (currentPage === 'onboarding.html' && this.hasActiveSubscription() && !this.needsOnboarding()) {
            window.location.href = 'dashboard.html';
            return false;
        }

        return true;
    }
}

const auth = new AuthSystem();

document.addEventListener('DOMContentLoaded', function () {
    auth.checkAccess();
});
