document.addEventListener('DOMContentLoaded', async function () {
    const currentPlanText = document.getElementById('currentPlanText');
    const currentPlanCard = document.getElementById('currentPlanCard');
    const manageBillingBtn = document.getElementById('manageBillingBtn');
    const retryPaymentBtn = document.getElementById('retryPaymentBtn');
    const cancelSubscriptionBtn = document.getElementById('cancelSubscriptionBtn');
    const backLink = document.querySelector('.back-link');
    const guestPlanHint = document.getElementById('guestPlanHint');
    const planButtons = Array.from(document.querySelectorAll('[data-action-plan]'));

    const planNames = {
        plan: 'Plan',
        thrive: 'Thrive',
        together: 'Together',
        free: 'Free'
    };

    let currentSubscription = null;

    function isSubscriptionActive(subscription) {
        if (!subscription) return false;
        const tier = (subscription.effective_tier || 'free').toLowerCase();
        return tier !== 'free';
    }

    function updatePlanButtons() {
        const active = isSubscriptionActive(currentSubscription);
        const currentTier = (currentSubscription?.effective_tier || 'free').toLowerCase();

        planButtons.forEach((btn) => {
            const planId = btn.getAttribute('data-action-plan');
            if (!planId) return;

            btn.disabled = false;

            if (!active) {
                btn.textContent = `Start ${planNames[planId] || planId}`;
                return;
            }

            if (planId === currentTier) {
                btn.textContent = `Current: ${planNames[planId] || planId}`;
                btn.disabled = true;
            } else {
                btn.textContent = `Switch to ${planNames[planId] || planId}`;
            }
        });
    }

    function setupGuestView() {
        if (currentPlanCard) {
            currentPlanCard.style.display = 'none';
        }

        if (guestPlanHint) {
            guestPlanHint.style.display = 'block';
        }

        if (backLink) {
            backLink.href = 'index.html';
            backLink.textContent = 'Back to Home';
        }

        planButtons.forEach((btn) => {
            const planId = btn.getAttribute('data-action-plan');
            const tierLabel = planNames[planId] || 'Plan';
            btn.disabled = false;
            btn.textContent = `Sign In for ${tierLabel}`;
            btn.addEventListener('click', function () {
                window.location.href = 'sign_in.html';
            });
        });
    }

    function updateSubscriptionCard() {
        if (!currentSubscription) {
            currentPlanText.textContent = 'Subscription data unavailable.';
            retryPaymentBtn.style.display = 'none';
            cancelSubscriptionBtn.style.display = 'none';
            return;
        }

        const tier = (currentSubscription.effective_tier || 'free').toLowerCase();
        const status = (currentSubscription.subscription_status || 'inactive').toLowerCase();
        const tierLabel = planNames[tier] || tier;
        const onboarding = currentSubscription.onboarding_completed ? 'completed' : 'pending';

        currentPlanText.textContent = `Tier: ${tierLabel} | Status: ${status} | Onboarding: ${onboarding}`;
        retryPaymentBtn.style.display = status === 'past_due' ? 'inline-flex' : 'none';
        cancelSubscriptionBtn.style.display = isSubscriptionActive(currentSubscription) ? 'inline-flex' : 'none';
    }

    async function refreshState() {
        try {
            currentSubscription = await billingApi.getSubscription(true);
            updateSubscriptionCard();
            updatePlanButtons();
            await auth.syncCurrentUser();
        } catch (error) {
            currentPlanText.textContent = error.message || 'Could not load subscription.';
            updatePlanButtons();
        }
    }

    async function handlePlanAction(planId) {
        const active = isSubscriptionActive(currentSubscription);
        try {
            if (!active) {
                const session = await billingApi.createCheckoutSession(planId, 0);
                window.location.href = session.checkout_url;
                return;
            }

            const confirmed = window.confirm(`Switch your subscription to ${planNames[planId] || planId}?`);
            if (!confirmed) return;

            await billingApi.changePlan(planId);
            showSuccess('Plan updated successfully.');
            await refreshState();
        } catch (error) {
            showError(error.message || 'Could not complete this action.');
        }
    }

    const isLoggedIn = !!(window.auth && typeof auth.isLoggedIn === 'function' && auth.isLoggedIn());
    if (!isLoggedIn) {
        setupGuestView();
        return;
    }

    if (backLink) {
        backLink.href = 'dashboard.html';
        backLink.textContent = 'Back to Dashboard';
    }

    planButtons.forEach((btn) => {
        btn.addEventListener('click', async function () {
            const planId = btn.getAttribute('data-action-plan');
            if (!planId) return;
            await handlePlanAction(planId);
        });
    });

    if (manageBillingBtn) {
        manageBillingBtn.addEventListener('click', async function () {
            try {
                const url = await billingApi.openPortal('premium-plan.html');
                window.location.href = url;
            } catch (error) {
                showError(error.message || 'Could not open billing portal.');
            }
        });
    }

    if (retryPaymentBtn) {
        retryPaymentBtn.addEventListener('click', async function () {
            try {
                const response = await billingApi.retryPayment();
                showSuccess(response.message || 'Payment retry triggered.');
                await refreshState();
            } catch (error) {
                showError(error.message || 'Unable to retry payment.');
            }
        });
    }

    if (cancelSubscriptionBtn) {
        cancelSubscriptionBtn.addEventListener('click', async function () {
            const confirmed = window.confirm('Cancel your subscription at period end?');
            if (!confirmed) return;

            try {
                await billingApi.cancel(false);
                showSuccess('Cancellation requested. You will keep access until period end.');
                await refreshState();
            } catch (error) {
                showError(error.message || 'Could not cancel subscription.');
            }
        });
    }

    await refreshState();
});
