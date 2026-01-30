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

        // Hide real cursor and focus rings, add active simulation styles
        const style = document.createElement('style');
        style.innerHTML = `
            body.demo-active { cursor: none !important; } 
            body.demo-active * { cursor: none !important; }
            body.demo-active *:focus { outline: none !important; }
            
            /* Visual feedback for clicks */
            .click-ripple {
                position: fixed;
                border-radius: 50%;
                background: rgba(37, 99, 235, 0.4);
                transform: translate(-50%, -50%);
                pointer-events: none;
                z-index: 9998;
                animation: ripple-effect 0.4s ease-out forwards;
            }
            @keyframes ripple-effect {
                0% { width: 0; height: 0; opacity: 0.8; }
                100% { width: 40px; height: 40px; opacity: 0; }
            }
            
            /* Simulated active state for buttons/inputs */
            .active-simulated {
                transform: scale(0.98) !important;
                opacity: 0.8 !important;
                background-color: rgba(0, 0, 0, 0.05) !important;
            }
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
        let element = document.querySelector(selector);

        // Retry logic for dynamic elements
        if (!element) {
            for (let i = 0; i < 5; i++) {
                await this.wait(200);
                element = document.querySelector(selector);
                if (element) break;
            }
        }

        if (!element) {
            console.warn(`Element not found: ${selector}`);
            return;
        }

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

    createRipple(x, y) {
        const ripple = document.createElement('div');
        ripple.className = 'click-ripple';
        ripple.style.left = `${x}px`;
        ripple.style.top = `${y}px`;
        document.body.appendChild(ripple);
        setTimeout(() => ripple.remove(), 400);
    }

    async click(selector) {
        await this.moveTo(selector, 800);

        // 1. Visual Cursor Click Animation
        this.cursor.style.transform = `translate(${this.x}px, ${this.y}px) scale(0.8)`;

        // 2. Create Ripple Effect
        this.createRipple(this.x, this.y);

        await new Promise(r => setTimeout(r, 100));
        this.cursor.style.transform = `translate(${this.x}px, ${this.y}px) scale(1)`;

        const element = document.querySelector(selector);
        if (element) {
            // 3. Simulate Active State on Element
            element.classList.add('active-simulated');
            setTimeout(() => element.classList.remove('active-simulated'), 150);

            // 4. Dispatch Events
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
    console.log("Initializing Demo Script...");

    // Check if demo is requested (e.g. via URL param ?demo=true)
    const urlParams = new URLSearchParams(window.location.search);
    const isDemo = urlParams.has('demo') || sessionStorage.getItem('demo_active') === 'true';

    if (!isDemo) {
        return;
    }

    console.log("Demo mode active!");
    // Persist demo state across reloads/redirects
    sessionStorage.setItem('demo_active', 'true');

    // Wait for load to be sure
    if (document.readyState !== 'complete') {
        await new Promise(r => window.addEventListener('load', r));
    }
    await new Promise(r => setTimeout(r, 200));

    const ghost = new GhostCursor();
    const path = window.location.pathname;

    // Logout Confirmation Page Check
    if (path.includes('/logout')) {
        await runLogoutConfirmStep(ghost);
        return;
    }

    if (path.includes('/signup')) {
        // await runSignupStep(ghost);
        console.log("Signup step skipped by user request. Redirecting to login...");
        window.location.href = '/accounts/login/?demo=true';
    } else if (path.includes('/login')) {
        await runLoginStep(ghost);
    } else if (path === '/' || path === '' || path.includes('home')) {
        await runHomeStep(ghost);
    } else if (path.includes('/chat')) {
        await runChatStep(ghost);
    } else {
        console.log("Unrecognized path for demo, checking for generic checks...");
        if (document.querySelector('form[action*="login"]')) await runLoginStep(ghost);
        else if (document.querySelector('form[action*="signup"]')) {
            // await runSignupStep(ghost);
            window.location.href = '/accounts/login/?demo=true';
        }
        else if (document.querySelector('.start-btn')) await runHomeStep(ghost);
        else if (document.body.innerText.includes('로그아웃') && document.querySelector('form button')) {
            await runLogoutConfirmStep(ghost);
        }
    }
}

async function runHomeStep(ghost) {
    console.log("Starting Home Step");
    await ghost.wait(500);

    const startBtn = document.querySelector('.start-btn');
    if (startBtn) {
        await ghost.click('.start-btn');
    } else {
        console.warn("Start button not found on home page");
        window.location.href = '/chat/';
    }
}

async function runSignupStep(ghost) {
    console.log("Starting Signup Step - SKIPPED");
    /*
    await ghost.wait(500);
    
    let emailField = document.querySelector('input[name="email"]') || document.querySelector('#id_email');
    if (emailField) {
        const randomId = Math.floor(Math.random() * 1000);
        await ghost.type(emailField.id ? '#' + emailField.id : 'input[name="email"]', `demo${randomId}@example.com`);
    }
    
    await ghost.wait(300);

    let pass1 = document.querySelector('input[name="password1"]') || document.querySelector('#id_password1');
    if (pass1) await ghost.type(pass1.id ? '#' + pass1.id : 'input[name="password1"]', 'DemoPass123!');
    
    await ghost.wait(300);
    
    let pass2 = document.querySelector('input[name="password2"]') || document.querySelector('#id_password2');
    if (pass2) {
        await ghost.type(pass2.id ? '#' + pass2.id : 'input[name="password2"]', 'DemoPass123!');
    }
    
    await ghost.wait(500);
    await ghost.click('button[type="submit"]');
    */
}

async function runLoginStep(ghost) {
    console.log("Starting Login Step");
    await ghost.wait(500);

    // User requested credentials:
    // Email: testuser@example.com
    // Password: ComplexPass123!

    let emailField = document.querySelector('input[name="login"]');
    if (emailField) {
        // Always clear and type for demo visual
        await ghost.type('input[name="login"]', 'testuser@example.com');
    }

    await ghost.wait(300);

    let passField = document.querySelector('input[name="password"]');
    if (passField) {
        await ghost.type('input[name="password"]', 'ComplexPass123!');
    }

    await ghost.wait(500);
    await ghost.click('button[type="submit"]');
}

async function runChatStep(ghost) {
    const step = parseInt(sessionStorage.getItem('demo_step') || '0');
    console.log(`Starting Chat Demo Step: ${step}`);

    if (step === 0) {
        // Step 0: Initial Load (Just Arrived) -> Send Q1
        await ghost.wait(1000);

        // 1. Send Question
        const question = "퇴직금 지급 기준이 어떻게 되나요?";

        if (document.querySelector('#messageInput')) {
            await ghost.type('#messageInput', question);
            await ghost.wait(500);
            await ghost.click('#sendBtn');
            await waitForResponse();

            // Move to next step
            sessionStorage.setItem('demo_step', '1');

            await ghost.wait(2000); // Give time to read answer
            runChatStep(ghost); // Re-invoke to proceed to step 1 logic
        }
        return;
    }

    if (step === 1) {
        // Step 1: Click New Chat
        console.log("Step 1: Clicking New Chat");
        await ghost.wait(1000); // Wait a bit after answer

        const newChatBtn = document.querySelector('.btn-new-chat');
        if (newChatBtn) {
            await ghost.click('.btn-new-chat');
            // This will reload the page
            sessionStorage.setItem('demo_step', '2');
        }
        return;
    }

    if (step === 2) {
        // Step 2: Delete Chat (Previous or Current)
        console.log("Step 2: Deleting Chat");
        await ghost.wait(1500); // Wait for reload

        // Try to find the second session item (Previous), fallback to first (Current)
        const sessionItems = document.querySelectorAll('.session-item');
        let targetSession = null;
        let targetIndex = 0;

        if (sessionItems.length >= 2) {
            targetSession = sessionItems[1]; // Prefer 2nd item
            targetIndex = 2; // for nth-child
        } else if (sessionItems.length === 1) {
            targetSession = sessionItems[0]; // Fallback to 1st
            targetIndex = 1; // for nth-child
        }

        if (targetSession) {
            // Move to hover it to show delete button
            const itemSelector = `.session-list .session-item:nth-child(${targetIndex})`;
            await ghost.moveTo(itemSelector);

            // Trigger simulated hover to reveal delete button
            targetSession.classList.add('hover-simulated');
            await ghost.wait(800); // Wait for render/visibility

            // Click delete button inside it
            await ghost.click(`${itemSelector} .delete-btn`);

            // Wait for Modal
            await ghost.wait(800);
            const confirmBtn = document.querySelector('#btnConfirm');
            if (confirmBtn) {
                await ghost.click('#btnConfirm');

                // Wait for deletion effect
                await ghost.wait(1500);

                // Move to Step 3
                sessionStorage.setItem('demo_step', '3');
                runChatStep(ghost);
            }
        } else {
            console.warn("No sessions found to delete! Skipping...");
            // Fallback
            sessionStorage.setItem('demo_step', '3');
            runChatStep(ghost);
        }
        return;
    }

    if (step === 3) {
        // Step 3: Logout
        console.log("Step 3: Logging Out");
        await ghost.wait(1000);

        const logoutBtn = document.querySelector('.btn-logout');
        if (logoutBtn) {
            await ghost.click('.btn-logout');
        } else {
            // Try searching for a link with logout text
            const links = Array.from(document.querySelectorAll('a'));
            const logoutLink = links.find(el => el.textContent.includes('로그아웃'));
            if (logoutLink) {
                await ghost.click('a[href*="logout"]');
            }
        }
    }
}

async function runLogoutConfirmStep(ghost) {
    console.log("Confirming Logout");
    await ghost.wait(800);
    const confirmBtn = document.querySelector('form button') || document.querySelector('button[type="submit"]');
    if (confirmBtn) {
        await ghost.click('button[type="submit"]');
    }

    // Cleanup
    sessionStorage.removeItem('demo_step');
    sessionStorage.removeItem('demo_active');
    document.body.classList.remove('demo-active');
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

// Initialize - robust loading
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(runDemo, 500));
} else {
    setTimeout(runDemo, 500);
}
