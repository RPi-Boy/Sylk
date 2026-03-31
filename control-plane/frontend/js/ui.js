// ui.js - Global Stylized Animations & Interactions for Sylk

document.addEventListener("DOMContentLoaded", () => {
    injectGlobalStyles();
    initStaggerBoot();
    initCountUp();
    // Defer canvas init by one rAF to ensure layout is committed
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            initMeshHover();
        });
    });
});

function injectGlobalStyles() {
    const style = document.createElement("style");
    style.id = "sylk-dynamic-ui";
    style.innerHTML = `
        /* Staggered Boot Sequence */
        .stagger-boot {
            opacity: 0;
            transform: translateY(20px);
            animation: staggerBootAnim 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes staggerBootAnim {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Mesh Web Canvas Engine */
        .mesh-glass {
            position: relative;
            overflow: hidden !important;
        }

        /* The canvas sits on top of the card content but doesn't block pointer events */
        .mesh-glass .web-canvas {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
            opacity: 0;
            transition: opacity 0.4s ease;
        }

        .mesh-glass:hover .web-canvas {
            opacity: 1;
        }

        /* Enforce z-index on content so the canvas stays underneath */
        .mesh-glass > *:not(.web-canvas) {
            position: relative;
            z-index: 1;
        }
    `;
    document.head.appendChild(style);
}

// 1. Staggered Boot Sequence
function initStaggerBoot() {
    const elements = document.querySelectorAll('.stagger-boot');
    elements.forEach((el, index) => {
        el.style.animationDelay = `${index * 75}ms`;
    });
}

// 2. Canvas Spider Web hover effect
function initMeshHover() {
    const cards = document.querySelectorAll('.mesh-glass');
    console.log(`[Sylk UI] initMeshHover found ${cards.length} .mesh-glass card(s).`);
    if (!cards.length) return;

    cards.forEach(card => {
        // Parse the contextual color from --mesh-color CSS var (fallback to purple)
        const computedColor = card.style.getPropertyValue('--mesh-color') || 'rgba(210,187,255,0.8)';

        // Create the canvas layer
        const canvas = document.createElement('canvas');
        canvas.classList.add('web-canvas');
        card.insertBefore(canvas, card.firstChild);
        const ctx = canvas.getContext('2d');

        // Grid of "node" points spaced 40px apart
        const GRID_SPACING = 40;
        // Max distance from cursor to draw a line to a node
        const REACH = 130;
        // Mouse state
        let mouseX = -999, mouseY = -999;
        let animFrame = null;
        let sized = false;

        // Robust canvas sizing — offsetWidth can be 0 during stagger animation
        function sizeCanvas() {
            const w = card.offsetWidth || card.getBoundingClientRect().width || 300;
            const h = card.offsetHeight || card.getBoundingClientRect().height || 200;
            if (w > 0 && h > 0) {
                canvas.width = w;
                canvas.height = h;
                sized = true;
            }
        }
        sizeCanvas();
        new ResizeObserver(sizeCanvas).observe(card);

        // Parse rgba color string to get RGB components
        function parseColor(colorStr) {
            // Works for rgba(...) and rgb(...)
            const m = colorStr.match(/[\d.]+/g);
            if (m && m.length >= 3) return { r: +m[0], g: +m[1], b: +m[2] };
            return { r: 210, g: 187, b: 255 };
        }
        const { r, g, b } = parseColor(computedColor);

        function drawWeb() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const cols = Math.ceil(canvas.width / GRID_SPACING) + 1;
            const rows = Math.ceil(canvas.height / GRID_SPACING) + 1;

            // Build list of nodes
            const nodes = [];
            for (let row = 0; row < rows; row++) {
                for (let col = 0; col < cols; col++) {
                    nodes.push({ x: col * GRID_SPACING, y: row * GRID_SPACING });
                }
            }

            // Draw lines from cursor to each nearby node
            nodes.forEach(node => {
                const dx = node.x - mouseX;
                const dy = node.y - mouseY;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < REACH) {
                    const strength = 1 - dist / REACH; // 1 near, 0 at edge

                    // Line from cursor to node
                    ctx.beginPath();
                    ctx.moveTo(mouseX, mouseY);
                    ctx.lineTo(node.x, node.y);
                    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${strength * 0.6})`;
                    ctx.lineWidth = strength * 1.2;
                    ctx.stroke();

                    // Node dot — brighter the closer
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, strength * 2.5, 0, Math.PI * 2);
                    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${strength * 0.9})`;
                    ctx.fill();
                }
            });

            // Draw lines between nearby nodes that are BOTH within reach
            for (let i = 0; i < nodes.length; i++) {
                const a = nodes[i];
                const distA = Math.hypot(a.x - mouseX, a.y - mouseY);
                if (distA >= REACH) continue;

                for (let j = i + 1; j < nodes.length; j++) {
                    const bNode = nodes[j];
                    const distB = Math.hypot(bNode.x - mouseX, bNode.y - mouseY);
                    if (distB >= REACH) continue;

                    // Only connect adjacent nodes (not diagonals across several cells)
                    const edgeDist = Math.hypot(a.x - bNode.x, a.y - bNode.y);
                    if (edgeDist > GRID_SPACING * 1.5) continue;

                    const combinedStrength = (1 - distA / REACH) * (1 - distB / REACH) * 0.4;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(bNode.x, bNode.y);
                    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${combinedStrength})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }

            // Cursor center dot
            ctx.beginPath();
            ctx.arc(mouseX, mouseY, 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.9)`;
            ctx.fill();
        }

        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            // Re-size lazily on first mouse contact in case card was zero-width at boot
            if (!sized || canvas.width !== rect.width) {
                canvas.width = rect.width;
                canvas.height = rect.height;
                sized = true;
            }
            mouseX = e.clientX - rect.left;
            mouseY = e.clientY - rect.top;
            if (animFrame) cancelAnimationFrame(animFrame);
            animFrame = requestAnimationFrame(drawWeb);
        });

        card.addEventListener('mouseleave', () => {
            mouseX = -999;
            mouseY = -999;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        });
    });

    console.log(`[Sylk UI] Mesh web initialized on ${cards.length} card(s).`);
}

// 3. Count-Up on scroll-into-view
function initCountUp() {
    const metrics = document.querySelectorAll('.count-up-metric');
    if (!metrics.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const targetValue = el.getAttribute('data-val');
                if (targetValue) {
                    window.animateCountUp(el, targetValue);
                }
                // Only fire once per element
                observer.unobserve(el);
            }
        });
    }, { threshold: 0.1 });

    metrics.forEach(el => observer.observe(el));
}

// Re-usable scramble/count engine
window.animateCountUp = function(element, targetString, duration = 800) {
    // Separate numeric value from suffix (e.g. "4.2TB/s" -> number=4.2, suffix="TB/s")
    const match = String(targetString).match(/([0-9.]+)(.*)/);
    if (!match) {
        element.textContent = targetString;
        return;
    }

    const endValue = parseFloat(match[1]);
    const rawSuffix = match[2] || "";
    // Preserve the space separator if it existed (e.g. "1.2 GB/s")
    const suffix = rawSuffix;
    const hasDecimal = match[1].includes(".");
    
    let startTime = null;
    
    function step(timestamp) {
        if (!startTime) startTime = timestamp;
        const progress = Math.min((timestamp - startTime) / duration, 1);
        
        // Use easeOutQuart for extremely fast start, slow finish
        const easeProgress = 1 - Math.pow(1 - progress, 4);
        
        const currentValue = endValue * easeProgress;
        
        // Scramble effect: rapidly generate gibberish until the final 20%
        if (progress < 0.8 && Math.random() > 0.5) {
            element.textContent = (Math.random() * endValue * 1.5).toFixed(hasDecimal ? 1 : 0) + suffix;
        } else {
            element.textContent = currentValue.toFixed(hasDecimal ? 1 : 0) + suffix;
        }

        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            // Guarantee precise landing
            element.textContent = endValue.toFixed(hasDecimal ? 1 : 0) + suffix;
        }
    }
    window.requestAnimationFrame(step);
};
