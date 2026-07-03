// ── Raksha Fraud Network — Aurora Particle System v2 ──
// A smooth, premium particle network with aurora-inspired colors
(function () {
    const canvas = document.createElement('canvas');
    canvas.id = 'networkCanvas';
    document.body.prepend(canvas);
    const ctx = canvas.getContext('2d');

    let W, H, mouse = { x: -1000, y: -1000 };
    const PARTICLE_COUNT = 60; // Reduced count for a cleaner background
    const CONNECTION_DIST = 150;
    const MOUSE_RADIUS = 180;
    const particles = [];

    // Clean, unified premium color palette (soft indigo/gray)
    const COLOR = { r: 99, g: 102, b: 241 }; // Soft Indigo

    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = window.innerHeight;
    }

    class Particle {
        constructor() {
            this.reset();
        }
        reset() {
            this.x = Math.random() * W;
            this.y = Math.random() * H;
            this.vx = (Math.random() - 0.5) * 0.15; // Slower, more calming movement
            this.vy = (Math.random() - 0.5) * 0.15;
            this.radius = Math.random() * 2 + 1; // Slightly smaller
            this.color = COLOR;
            this.alpha = Math.random() * 0.25 + 0.15; // Lower alpha (15% to 40% max opacity)
            this.pulseSpeed = Math.random() * 0.015 + 0.005;
            this.pulseOffset = Math.random() * Math.PI * 2;
            this.isThreat = Math.random() < 0.05;
            if (this.isThreat) {
                this.color = { r: 212, g: 85, b: 106 }; // Soft tuned crimson for threat nodes
                this.radius = Math.random() * 1.5 + 1.5;
            }
        }
        update(time) {
            // Gentle floating motion
            this.x += this.vx;
            this.y += this.vy;

            // Mouse interaction
            const dx = this.x - mouse.x;
            const dy = this.y - mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < MOUSE_RADIUS && dist > 0) {
                const force = (MOUSE_RADIUS - dist) / MOUSE_RADIUS;
                const angle = Math.atan2(dy, dx);
                if (this.isThreat) {
                    // Threats scatter away
                    this.vx += Math.cos(angle) * force * 0.15;
                    this.vy += Math.sin(angle) * force * 0.15;
                } else {
                    // Normal particles gently attract
                    this.vx -= Math.cos(angle) * force * 0.03;
                    this.vy -= Math.sin(angle) * force * 0.03;
                }
            }

            // Damping
            this.vx *= 0.995;
            this.vy *= 0.995;

            // Wrap edges
            if (this.x < -20) this.x = W + 20;
            if (this.x > W + 20) this.x = -20;
            if (this.y < -20) this.y = H + 20;
            if (this.y > H + 20) this.y = -20;

            // Pulse alpha
            this.currentAlpha = this.alpha + Math.sin(time * this.pulseSpeed + this.pulseOffset) * 0.15;
        }
        draw() {
            const { r, g, b } = this.color;
            // Muted soft glow
            ctx.beginPath();
            const grad = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, this.radius * 4);
            grad.addColorStop(0, `rgba(${r},${g},${b},${this.currentAlpha * 0.3})`);
            grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
            ctx.fillStyle = grad;
            ctx.arc(this.x, this.y, this.radius * 4, 0, Math.PI * 2);
            ctx.fill();

            // Core dot
            ctx.beginPath();
            ctx.fillStyle = `rgba(${r},${g},${b},${this.currentAlpha})`;
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    function init() {
        resize();
        particles.length = 0;
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            particles.push(new Particle());
        }
    }

    function drawConnections() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const a = particles[i], b = particles[j];
                const dx = a.x - b.x;
                const dy = a.y - b.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < CONNECTION_DIST) {
                    const opacity = (1 - dist / CONNECTION_DIST) * 0.18; // Crisp but soft connection lines
                    // Blend colors of connected particles
                    const cr = Math.round((a.color.r + b.color.r) / 2);
                    const cg = Math.round((a.color.g + b.color.g) / 2);
                    const cb = Math.round((a.color.b + b.color.b) / 2);

                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(${cr},${cg},${cb},${opacity})`;
                    ctx.lineWidth = 0.5;
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            }
        }
    }

    let animFrame;
    function animate(time) {
        ctx.clearRect(0, 0, W, H);
        drawConnections();
        for (const p of particles) {
            p.update(time);
            p.draw();
        }
        animFrame = requestAnimationFrame(animate);
    }

    // Events
    window.addEventListener('resize', () => {
        resize();
        // Re-distribute particles after resize
        for (const p of particles) {
            if (p.x > W) p.x = Math.random() * W;
            if (p.y > H) p.y = Math.random() * H;
        }
    });

    document.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    document.addEventListener('mouseleave', () => {
        mouse.x = -1000;
        mouse.y = -1000;
    });

    init();
    animate(0);
})();
