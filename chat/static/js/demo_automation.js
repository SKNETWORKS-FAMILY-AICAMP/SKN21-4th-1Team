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
        if (element) {
            // Dispatch typical events for robustness
            element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            element.click();
            element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
        }
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
    const isDemo = urlParams.has('demo') || sessionStorage.getItem('demo_active') === 'true';

    if (!isDemo) return;

    // Persist demo state across reloads/redirects
    sessionStorage.setItem('demo_active', 'true');

    // Wait for load
    await new Promise(r => setTimeout(r, 1000));

    const ghost = new GhostCursor();

    // Check current path to decide action
    const path = window.location.pathname;

    if (path.includes('/signup')) {
        await runSignupStep(ghost);
    } else if (path.includes('/login')) {
        await runLoginStep(ghost);
    } else if (path.includes('/chat') || path === '/' || path === '') {
        await runChatStep(ghost);
    }
}

async function runSignupStep(ghost) {
    console.log("Starting Signup Step");
    await ghost.wait(500);

    // Input Email
    // Try to find email field (generic or id)
    let emailField = document.querySelector('input[name="email"]') || document.querySelector('#id_email');
    if (emailField) {
        // Generate random email to avoid duplicate error during repeated demos
        const randomId = Math.floor(Math.random() * 1000);
        await ghost.type(emailField.id ? '#' + emailField.id : 'input[name="email"]', `demo${randomId}@example.com`);
    }

    await ghost.wait(300);

    // Password 1
    let pass1 = document.querySelector('input[name="password1"]') || document.querySelector('#id_password1');
    if (pass1) await ghost.type(pass1.id ? '#' + pass1.id : 'input[name="password1"]', 'DemoPass123!');

    await ghost.wait(300);

    // Password 2
    let pass2 = document.querySelector('input[name="password2"]') || document.querySelector('#id_password2');
    if (pass2) {
        await ghost.type(pass2.id ? '#' + pass2.id : 'input[name="password2"]', 'DemoPass123!');
    }

    await ghost.wait(500);

    // Click Signup Button
    await ghost.click('button[type="submit"]');
}

async function runLoginStep(ghost) {
    console.log("Starting Login Step");
    await ghost.wait(500);

    // Check if we need to type (auto-fill might not happen in demo)
    let emailField = document.querySelector('input[name="login"]');
    // If not filled, type generic or hope user typed. 
    // Since signup redirects to login usually without auto-login in some configs, 
    // we might need credentials. But we used random email in signup...
    // Issue: Login step needs to know the email used in Signup.
    // Solution: Just type a fixed demo email for now, OR assume signup logs in automatically.
    // If signup logs in automatically, we won't land here. 
    // If we land here, we need credentials.
    // Let's type a standard demo email. User might need to have this account ready if signup isn't used.
    // Or if signup WAS used, we are stuck.
    // Let's assume for this demo, the user starts at Signup, and Signup logic handles login or redirects.
    // If redirects to Login, we type fixed credentials.

    if (emailField && !emailField.value) {
        await ghost.type('input[name="login"]', 'demo_user@example.com');
    }

    await ghost.wait(300);

    let passField = document.querySelector('input[name="password"]');
    if (passField && !passField.value) {
        await ghost.type('input[name="password"]', 'DemoPass123!');
    }

    await ghost.wait(500);

    // Click Login
    await ghost.click('button[type="submit"]');
}

async function runChatStep(ghost) {
    const step = parseInt(sessionStorage.getItem('demo_step') || '0');
    console.log(`Starting Chat Demo Step: ${step}`);

    if (step === 0) {
        // Step 0: Initial Load -> Click New Chat
        // Just to show activity, move around a bit
        await ghost.moveTo('.nav-brand', 1000);
        await ghost.wait(500);
        await ghost.click('.btn-new-chat');
        sessionStorage.setItem('demo_step', '1');
        return;
    }

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

        sessionStorage.setItem('demo_step', '2');
        runDeleteStep(ghost);
    } else if (step === 2) {
        runDeleteStep(ghost);
    }
}

async function runDeleteStep(ghost) {
    await ghost.wait(1000);
    const deleteBtnSelector = '.session-item.active .delete-btn';
    await ghost.click(deleteBtnSelector);
    await ghost.wait(1000);

    // Step 3: Logout
    await ghost.click('.btn-logout');

    // End Demo
    sessionStorage.removeItem('demo_step');
    sessionStorage.removeItem('demo_active');
    document.body.classList.remove('demo-active');
    // alert('Demo Completed!');
}

async function waitForResponse() {
    await new Promise(r => setTimeout(r, 1000));
    return new Promise(resolve => {
        const check = () => {
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
