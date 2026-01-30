/**
 * Demo Automation Script
 * Simulates mouse movement, clicking, and typing for a demo video.
 */

class GhostCursor {
    constructor() {
        this.cursor = document.createElement('div');
        this.cursor.id = 'ghost-cursor';
        this.cursor.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M5.5 3.5L19 10L11.5 12.5L16 20.5L13.5 22L9 14L4 18.5V3.5Z" fill="black" stroke="white" stroke-width="1.5"/>
            </svg>`;
        Object.assign(this.cursor.style, {
            position: 'fixed',
            top: '0',
            left: '0',
            zIndex: '9999',
            pointerEvents: 'none',
            transition: 'transform 0.05s linear',
            transform: 'translate(0, 0)' // Initial state
        });
        document.body.appendChild(this.cursor);

        // Hide real cursor and focus rings
        const style = document.createElement('style');
        style.innerHTML = `
            body.demo-active { cursor: none !important; } 
            body.demo-active * { cursor: none !important; }
            body.demo-active *:focus { outline: none !important; }
        `;
        document.head.appendChild(style);
        document.body.classList.add('demo-active');

        this.x = 100;
        this.y = 100;
        this.updatePosition();
    }

    updatePosition() {
        this.cursor.style.transform = `translate(${this.x}px, ${this.y}px)`;
    }

    async moveTo(selector, duration = 1000) {
        const element = document.querySelector(selector);
        if (!element) return;

        const rect = element.getBoundingClientRect();
        const targetX = rect.left + rect.width / 2;
        const targetY = rect.top + rect.height / 2;

        const startX = this.x;
        const startY = this.y;
        const startTime = performance.now();

        return new Promise(resolve => {
            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);

                // Ease-in-out
                const ease = progress < 0.5 ? 2 * progress * progress : -1 + (4 - 2 * progress) * progress;

                this.x = startX + (targetX - startX) * ease;
                this.y = startY + (targetY - startY) * ease;
                this.updatePosition();

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    resolve();
                }
            };
            requestAnimationFrame(animate);
        });
    }

    async click(selector) {
        await this.moveTo(selector, 800);

        // Visualize click
        this.cursor.style.transform = `translate(${this.x}px, ${this.y}px) scale(0.9)`;
        await new Promise(r => setTimeout(r, 100));
        this.cursor.style.transform = `translate(${this.x}px, ${this.y}px) scale(1)`;

        const element = document.querySelector(selector);
        if (element) element.click();
    }

    async type(selector, text, cpm = 500) {
        await this.moveTo(selector, 800);
        await this.click(selector); // Focus

        const element = document.querySelector(selector);
        if (!element) return;

        element.value = "";
        const charDelay = 60000 / cpm; // ms per char

        for (const char of text) {
            element.value += char;
            // Trigger input event for frameworks/listeners
            element.dispatchEvent(new Event('input', { bubbles: true }));
            await new Promise(r => setTimeout(r, charDelay + Math.random() * 20)); // Add jitter
        }
    }

    async wait(ms) {
        return new Promise(r => setTimeout(r, ms));
    }
}

// Demo Scenario
async function runDemo() {
    // Check if demo is requested (e.g. via URL param ?demo=true)
    const urlParams = new URLSearchParams(window.location.search);
    if (!urlParams.has('demo')) return;

    // Wait for load
    await new Promise(r => setTimeout(r, 1000));

    const ghost = new GhostCursor();
    const step = parseInt(sessionStorage.getItem('demo_step') || '0');

    console.log(`Starting Demo Step: ${step}`);

    if (step === 0) {
        // Step 0: Initial Load -> Click New Chat
        // Just to show activity, move around a bit
        await ghost.moveTo('.nav-brand', 1000); // Hover over logo
        await ghost.wait(500);

        // Go to New Chat
        await ghost.click('.btn-new-chat');

        // Page will reload, set next step
        sessionStorage.setItem('demo_step', '1');
        return;
    }

    // Note: Step 1 continues after reload
    if (step === 1) {
        // Step 1: Typing Q1
        await ghost.wait(1000);

        const questions = [
            "근로계약서 미작성 시 벌금은 얼마인가요?",
            "퇴직금 지급 기준이 어떻게 되나요?",
            "주휴수당 계산법 알려줘"
        ];

        // Question 1
        await ghost.type('#messageInput', questions[0]);
        await ghost.wait(500);
        await ghost.click('#sendBtn');

        // Wait for answer (heuristic wait or observer)
        // Since we don't know exactly when AI finishes, we'll wait a fixed safe time or look for the typing indicator to stop
        await waitForResponse();

        // Question 2
        await ghost.type('#messageInput', questions[1]);
        await ghost.wait(500);
        await ghost.click('#sendBtn');
        await waitForResponse();

        // Question 3
        await ghost.type('#messageInput', questions[2]);
        await ghost.wait(500);
        await ghost.click('#sendBtn');
        await waitForResponse();

        // Step done, move to next
        sessionStorage.setItem('demo_step', '2');

        // Reload page to refresh sidebar or just continue?
        // Let's continue immediately.
        runDeleteStep(ghost);
    } else if (step === 2) {
        // Just in case we reloaded
        runDeleteStep(ghost);
    }
}

async function runDeleteStep(ghost) {
    // Step 2: Delete Chat
    await ghost.wait(1000);

    // Hover over the first session item (current one)
    // We need to assume the first session in the list is the one we want to delete, or the active one.
    // The active session has .session-item.active

    // Need to find the delete button within the active session.
    // Since I added the delete button, I should target it specifically.
    // Assuming structure: .session-item.active .btn-delete-session

    const deleteBtnSelector = '.session-item.active .btn-delete-session';

    // If active session isn't found in sidebar (maybe created just now), we might need to reload sidebar.
    // But usually new chat redirects to new session.

    await ghost.click(deleteBtnSelector);

    // Wait for deletion confirming or UI update
    await ghost.wait(1000);

    // Step 3: Logout
    await ghost.click('.btn-logout');

    // End Demo
    sessionStorage.removeItem('demo_step');
    document.body.classList.remove('demo-active');
    alert('Demo Completed!');
}

async function waitForResponse() {
    // Wait until .typing-indicator is gone and bubbles increase
    // Simple implementation: wait fixed time + polling

    // Initial wait for request to start
    await new Promise(r => setTimeout(r, 1000));

    return new Promise(resolve => {
        const check = () => {
            // Check if any bubble has class 'ing' (active typing)
            const generating = document.querySelector('.bubble.ing');
            if (!generating) {
                resolve();
            } else {
                setTimeout(check, 500);
            }
        };
        check();
    });
}

// Initialize
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runDemo);
} else {
    runDemo();
}
