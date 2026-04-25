(function() {
    'use strict';

    const VERSION = '1.0.0';
    console.log(`[Enhancements v${VERSION}] 初始化中...`);

    function loadCSS(href) {
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        document.head.appendChild(link);
    }

    try { loadCSS('enhancements.css'); } catch(e) {}

    var Utils = {
        rand: function(min, max) { return Math.random() * (max - min) + min; },
        randInt: function(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; },
        clamp: function(v, min, max) { return Math.max(min, Math.min(max, v)); },
        lerp: function(a, b, t) { return a + (b - a) * t; },
        qs: function(s) { return document.querySelector(s); },
        qsa: function(s) { return document.querySelectorAll(s); },
        on: function(el, event, fn) { if (el) el.addEventListener(event, fn); }
    };

    /* ============================================
       1. 角色渲染增强系统
       ============================================ */
    var CharacterEnhance = {
        sprite: null,
        currentMood: 'normal',
        moodTimer: null,
        equipment: { hat: null, collar: null },

        init: function() {
            this.sprite = Utils.qs('#catSprite');
            if (!this.sprite) return;
            this.addBreathing();
            this.addBlinking();
            this.addTailWag();
            this.addClickEffect();
            this.startMoodSystem();
            this.sprite.classList.add('breathing', 'blink', 'wagging');
            console.log('[Character] 角色动画系统已启动');
        },

        addBreathing: function() {
            var body = Utils.qs('#catBody');
            if (!body) return;
            body.style.transformOrigin = 'center bottom';
        },

        addBlinking: function() {
            var leftEye = Utils.qs('#leftEye');
            var rightEye = Utils.qs('#rightEye');
            if (!leftEye || !rightEye) return;
            leftEye.style.transformOrigin = 'center';
            rightEye.style.transformOrigin = 'center';
        },

        addTailWag: function() {
            var tail = Utils.qs('#tail');
            if (!tail) return;
            tail.style.transformOrigin = '145px 140px';
        },

        addClickEffect: function() {
            var self = this;
            Utils.on(this.sprite, 'click', function(e) {
                self.sprite.classList.remove('clicked');
                void self.sprite.offsetWidth;
                self.sprite.classList.add('clicked');
                setTimeout(function() { self.sprite.classList.remove('clicked'); }, 400);
                self.spawnHeart(e);
                self.setMood('happy', 3000);
            });
        },

        spawnHeart: function(e) {
            var hearts = ['❤️', '💕', '💖', '🧡', '💗'];
            var heart = document.createElement('span');
            heart.className = 'click-heart';
            heart.textContent = hearts[Utils.randInt(0, hearts.length - 1)];
            var rect = this.sprite.getBoundingClientRect();
            heart.style.left = (Utils.rand(20, rect.width - 30)) + 'px';
            heart.style.top = (Utils.rand(20, rect.height * 0.5)) + 'px';
            this.sprite.appendChild(heart);
            setTimeout(function() { if (heart.parentNode) heart.remove(); }, 1000);
        },

        setMood: function(mood, duration) {
            var self = this;
            var moods = ['normal', 'happy', 'sad', 'tired', 'excited'];
            moods.forEach(function(m) { if (self.sprite) self.sprite.classList.remove(m); });
            this.currentMood = mood;
            if (mood !== 'normal' && this.sprite) this.sprite.classList.add(mood);

            if (this.moodTimer) clearTimeout(this.moodTimer);
            if (duration) {
                this.moodTimer = setTimeout(function() {
                    self.setMood('normal');
                }, duration);
            }
        },

        startMoodSystem: function() {
            var self = this;
            setInterval(function() {
                if (self.currentMood === 'normal' && typeof cat !== 'undefined') {
                    var hpRatio = cat.hp / cat.maxHp;
                    var hunger = cat.hunger || 50;
                    var happy = cat.happiness || 50;

                    if (hpRatio < 0.3) self.setMood('sad', 4000);
                    else if (hunger < 20 || happy < 20) self.setMood('tired', 4000);
                    else if (happy > 80 && Utils.randInt(1, 10) > 7) self.setMood('excited', 2000);
                    else if (Utils.randInt(1, 15) > 13) self.setMood('happy', 2000);
                }
            }, 8000);
        },

        showEquipment: function(type, emoji) {
            var group = Utils.qs('#outfitGroup');
            if (!group) return;
            var badge = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            badge.setAttribute('x', type === 'hat' ? '92' : '88');
            badge.setAttribute('y', type === 'hat' ? '28' : '108');
            badge.setAttribute('font-size', '18');
            badge.setAttribute('text-anchor', 'middle');
            badge.textContent = emoji;
            group.appendChild(badge);
            this.equipment[type] = badge;
        },

        hideEquipment: function(type) {
            if (this.equipment[type]) {
                this.equipment[type].remove();
                this.equipment[type] = null;
            }
        },

        playEvolutionGlow: function() {
            var glow = document.createElement('div');
            glow.className = 'evolution-glow';
            var sprite = Utils.qs('#catSprite');
            if (sprite) {
                sprite.style.position = 'relative';
                sprite.appendChild(glow);
                setTimeout(function() { if (glow.parentNode) glow.remove(); }, 5000);
            }
        }
    };

    /* ============================================
       2. 场景深度感系统
       ============================================ */
    var SceneDepth = {
        layers: [],
        mouseX: 0,
        mouseY: 0,

        init: function() {
            this.createParallaxLayers();
            this.createCloudLayer();
            this.createGlowOverlay();
            this.createFogLayer();
            this.createDayNightIndicator();
            this.bindMouseEvents();
            console.log('[SceneDepth] 场景深度系统已启动');
        },

        createParallaxLayers: function() {
            var container = document.createElement('div');
            container.className = 'parallax-container';
            var configs = [
                { cls: 'bg-far', speed: 0.02 },
                { cls: 'bg-mid', speed: 0.05 },
                { cls: 'bg-near', speed: 0.1 }
            ];
            var self = this;
            configs.forEach(function(cfg) {
                var layer = document.createElement('div');
                layer.className = 'parallax-layer ' + cfg.cls;
                container.appendChild(layer);
                self.layers.push({ el: layer, speed: cfg.speed });
            });
            document.body.insertBefore(container, document.body.firstChild);
        },

        createCloudLayer: function() {
            var layer = document.createElement('div');
            layer.className = 'cloud-layer';
            for (var i = 1; i <= 4; i++) {
                var cloud = document.createElement('div');
                cloud.className = 'cloud cloud-' + i;
                cloud.style.top = Utils.rand(2, 25) + '%';
                cloud.style.animationDuration = Utils.rand(40, 90) + 's';
                cloud.style.animationDelay = (-Utils.rand(0, 60)) + 's';
                cloud.style.width = Utils.rand(120, 350) + 'px';
                cloud.style.height = Utils.rand(40, 90) + 'px';
                layer.appendChild(cloud);
            }
            document.body.appendChild(layer);
        },

        createGlowOverlay: function() {
            var overlay = document.createElement('div');
            overlay.className = 'glow-overlay';
            document.body.appendChild(overlay);
        },

        createFogLayer: function() {
            var fog = document.createElement('div');
            fog.className = 'fog-layer';
            document.body.appendChild(fog);
        },

        createDayNightIndicator: function() {
            var indicator = document.createElement('div');
            indicator.className = 'day-night-indicator';
            indicator.id = 'dayNightIndicator';
            this.updateIndicator(indicator);
            document.body.appendChild(indicator);
            var self = this;
            setInterval(function() { self.updateIndicator(indicator); }, 60000);
        },

        updateIndicator: function(el) {
            if (!el) return;
            var hour = new Date().getHours();
            var icon, text;
            if (hour >= 6 && hour < 12) { icon = '☀️'; text = '上午'; }
            else if (hour >= 12 && hour < 18) { icon = '🌤️'; text = '下午'; }
            else if (hour >= 18 && hour < 21) { icon = '🌅'; text = '傍晚'; }
            else { icon = '🌙'; text = '夜晚'; }
            el.textContent = icon + ' ' + text;
            el.title = text;
        },

        bindMouseEvents: function() {
            var self = this;
            document.addEventListener('mousemove', function(e) {
                self.mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
                self.mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
            });

            function updateParallax() {
                self.layers.forEach(function(layer) {
                    var x = self.mouseX * layer.speed * 80;
                    var y = self.mouseY * layer.speed * 40;
                    layer.el.style.transform = 'translate(' + x + 'px, ' + y + 'px)';
                });
                requestAnimationFrame(updateParallax);
            }
            updateParallax();
        }
    };

    /* ============================================
       3. 战斗画面增强
       ============================================ */
    var BattleEnhance = {
        active: false,
        effectsContainer: null,
        particlePool: [],
        originalAttackFn: null,
        originalUseSkillFn: null,

        init: function() {
            var screen = Utils.qs('#battleScreen');
            if (!screen) return;
            screen.classList.add('enhanced');
            this.effectsContainer = Utils.qs('#battleEffects');
            this.hookBattleEvents();
            console.log('[BattleEnhance] 战斗增强系统已启动');
        },

        hookBattleEvents: function() {
            var self = this;
            if (typeof startBattle === 'function') {
                var origStart = window.startBattle;
                window.startBattle = function(enemy) {
                    self.active = true;
                    self.showBattleIntro(enemy.name || enemy);
                    if (origStart) origStart.apply(null, arguments);
                    setTimeout(function() { self.setBattleBgScene(); }, 100);
                };
            }

            if (typeof attackEnemy === 'function') {
                var origAttack = window.attackEnemy;
                window.attackEnemy = function() {
                    if (self.active) {
                        self.playCatAttackAnimation();
                        setTimeout(function() {
                            if (origAttack) origAttack.apply(null, arguments);
                        }, 250);
                    } else {
                        if (origAttack) origAttack.apply(null, arguments);
                    }
                };
            }

            if (typeof useSkill === 'function') {
                var origUseSkill = window.useSkill;
                window.useSkill = function(skillId) {
                    if (self.active && typeof skills === 'object' && skills[skillId]) {
                        var skill = skills[skillId];
                        self.playSkillEffect(skill.type || skillId, skill.name || skillId);
                    }
                    if (origUseSkill) origUseSkill.apply(null, arguments);
                };
            }

            var origClose = window.closeBattle;
            if (origClose) {
                window.closeBattle = function() {
                    self.active = false;
                    self.clearEffects();
                    origClose.apply(null, arguments);
                };
            }
        },

        showBattleIntro: function(enemyName) {
            var arena = Utils.qs('.battle-arena');
            if (!arena) return;
            var overlay = document.createElement('div');
            overlay.className = 'battle-intro-overlay';
            overlay.innerHTML = '<span class="battle-intro-text">⚔️ ' + (enemyName || '') + '</span>';
            arena.appendChild(overlay);
            setTimeout(function() { if (overlay.parentNode) overlay.remove(); }, 800);
        },

        setBattleBgScene: function() {
            var arena = Utils.qs('.battle-arena');
            if (!arena) return;
            var existing = arena.querySelector('.battle-bg-scene');
            if (existing) existing.remove();

            var scenes = ['forest', 'cave', 'castle'];
            var sceneType = scenes[Utils.randInt(0, scenes.length - 1)];

            var bg = document.createElement('div');
            bg.className = 'battle-bg-scene ' + sceneType;
            arena.insertBefore(bg, arena.firstChild);
        },

        playCatAttackAnimation: function() {
            var catSprite = Utils.qs('#battleCatSprite');
            if (catSprite) {
                catSprite.classList.remove('enhanced-attack');
                void catSprite.offsetWidth;
                catSprite.classList.add('enhanced-attack');
                setTimeout(function() { catSprite.classList.remove('enhanced-attack'); }, 500);
            }
        },

        playEnemyHit: function() {
            var enemy = Utils.qs('#battleEnemy');
            var sprite = Utils.qs('#enemySprite');
            if (enemy) {
                enemy.classList.remove('hit-shake');
                void enemy.offsetWidth;
                enemy.classList.add('hit-shake');
                setTimeout(function() { enemy.classList.remove('hit-shake'); }, 400);
            }
            if (sprite) {
                sprite.classList.remove('hit-flash');
                void sprite.offsetWidth;
                sprite.classList.add('hit-flash');
                setTimeout(function() { sprite.classList.remove('hit-flash'); }, 600);
            }
        },

        playSkillEffect: function(skillType, skillName) {
            var container = Utils.qs('.battle-arena');
            if (!container) return;

            this.showSkillNameToast(skillType, skillName);
            this.spawnSkillParticles(container, skillType);
        },

        spawnSkillParticles: function(container, type) {
            var colors = {
                fire: '#ff6b35', ice: '#74b9ff', lightning: '#ffd93d',
                heal: '#6bcb77', dark: '#636e72', holy: '#ffeaa7'
            };
            var color = colors[type] || '#ff6b9d';

            var rect = container.getBoundingClientRect();
            var cx = rect.width / 2;
            var cy = rect.height * 0.35;

            for (var i = 0; i < 20; i++) {
                var p = document.createElement('div');
                p.className = 'skill-particle ' + type;
                var angle = (Math.PI * 2 / 20) * i + Utils.rand(-0.3, 0.3);
                var speed = Utils.rand(3, 8);
                var dist = Utils.rand(40, 120);
                p.style.left = cx + 'px';
                p.style.top = cy + 'px';
                p.style.setProperty('--tx', (Math.cos(angle) * dist) + 'px');
                p.style.setProperty('--ty', (Math.sin(angle) * dist) + 'px');

                p.animate([
                    { transform: 'translate(-50%, -50%) scale(0)', opacity: 1 },
                    { transform: 'translate(calc(-50% + ' + (Math.cos(angle) * dist) + 'px), calc(-50% + ' + (Math.sin(angle) * dist) + 'px)) scale(1)', opacity: 1, offset: 0.4 },
                    { transform: 'translate(calc(-50% + ' + (Math.cos(angle) * dist * 1.5) + 'px), calc(-50% + ' + (Math.sin(angle) * dist * 1.5) + 'px)) scale(0)', opacity: 0 }
                ], { duration: Utils.rand(600, 1000), easing: 'ease-out' });

                container.appendChild(p);
                setTimeout(function() { if (p.parentNode) p.remove(); }, 1100);
            }
        },

        showDamagePopup: function(damage, isCritical, isHeal, isMiss) {
            var enemy = Utils.qs('#battleEnemy');
            if (!enemy) return;

            var popup = document.createElement('div');
            var cls = 'damage-popup ';
            if (isMiss) cls += 'miss';
            else if (isHeal) cls += 'heal';
            else if (isCritical) cls += 'critical';
            else cls += 'normal';

            popup.className = cls;
            popup.textContent = isMiss ? 'MISS' : (isHeal ? '+' + damage : '-' + damage);

            var rect = enemy.getBoundingClientRect();
            var parentRect = enemy.offsetParent ? enemy.offsetParent.getBoundingClientRect() : { left: 0, top: 0 };
            popup.style.left = (rect.width / 2) + 'px';
            popup.style.top = (rect.height * 0.3) + 'px';

            enemy.appendChild(popup);
            setTimeout(function() { if (popup.parentNode) popup.remove(); }, 1300);
        },

        showSkillNameToast: function(type, name) {
            var arena = Utils.qs('.battle-arena');
            if (!arena) return;
            var toast = document.createElement('div');
            toast.className = 'skill-name-toast ' + (type || '');
            toast.textContent = name || '';
            arena.appendChild(toast);
            setTimeout(function() { if (toast.parentNode) toast.remove(); }, 1600);
        },

        clearEffects: function() {
            var effects = Utils.qsa('.battle-arena .skill-particle, .battle-arena .damage-popup, .battle-arena .skill-name-toast');
            effects.forEach(function(e) { e.remove(); });
        }
    };

    /* ============================================
       4. UI 微交互系统
       ============================================ */
    var UIEffects = {
        init: function() {
            this.addButtonRipple();
            this.addNumberAnimations();
            this.addShopItemHover();
            this.hookUpdateUI();
            console.log('[UIEffects] UI微交互系统已启动');
        },

        addButtonRipple: function() {
            var buttons = '.action-btn, .battle-skill-btn, .shop-item, .top-btn, .music-btn, .voice-btn';
            Utils.on(document, 'click', function(e) {
                var btn = e.target.closest(buttons);
                if (!btn) return;

                var ripple = document.createElement('span');
                ripple.className = 'ripple-effect';
                var rect = btn.getBoundingClientRect();
                var size = Math.max(rect.width, rect.height);
                ripple.style.width = ripple.style.height = size + 'px';
                ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
                ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';

                btn.style.position = btn.style.position || 'relative';
                btn.style.overflow = 'hidden';
                btn.appendChild(ripple);
                setTimeout(function() { if (ripple.parentNode) ripple.remove(); }, 650);
            });
        },

        addNumberAnimations: function() {
            var targets = ['#coins', '#gems', '#level', '#exp', '#battleCatHp', '#enemyHp',
                           '#battleCatMp', '#hungerVal', '#happyVal', '#energyVal'];

            targets.forEach(function(sel) {
                var el = Utils.qs(sel);
                if (el) {
                    el.classList.add('number-pop');
                    var observer = new MutationObserver(function(mutations) {
                        mutations.forEach(function(m) {
                            if (m.type === 'childList' || m.type === 'characterData') {
                                el.classList.remove('bump');
                                void el.offsetWidth;
                                el.classList.add('bump');
                                setTimeout(function() { el.classList.remove('bump'); }, 280);
                            }
                        });
                    });
                    observer.observe(el, { childList: true, subtree: true, characterData: true });
                }
            });
        },

        addShopItemHover: function() {
            var items = Utils.qsa('.shop-item');
            items.forEach(function(item) {
                item.style.transition = 'transform 0.25s ease, box-shadow 0.25s ease';
            });
        },

        hookUpdateUI: function() {
            var self = this;
            if (typeof updateUI === 'function') {
                var origUpdate = window.updateUI;
                window.updateUI = function() {
                    if (origUpdate) origUpdate.apply(null, arguments);
                    self.onUIUpdated();
                };
            }
        },

        onUIUpdated: function() {},
        showAchievementUnlock: function(title, desc) {
            var el = document.createElement('div');
            el.className = 'achievement-unlock';
            el.innerHTML = '<h3>🏆 成就解锁</h3><p>' + title + '</p>';
            if (desc) el.innerHTML += '<small style="color:var(--text-dim);font-size:12px">' + desc + '</small>';

            for (var i = 0; i < 12; i++) {
                var s = document.createElement('div');
                s.className = 'achievement-sparkle';
                s.style.left = Utils.rand(10, 90) + '%';
                s.style.top = Utils.rand(10, 90) + '%';
                s.style.setProperty('--sx', Utils.rand(-80, 80) + 'px');
                s.style.setProperty('--sy', Utils.rand(-80, 80) + 'px');
                el.appendChild(s);
            }

            document.body.appendChild(el);
            setTimeout(function() { if (el.parentNode) el.remove(); }, 2600);
        },

        showLevelUpBurst: function() {
            var sprite = Utils.qs('#catSprite');
            if (!sprite) return;
            var burst = document.createElement('div');
            burst.className = 'level-up-burst';

            var ring = document.createElement('div');
            ring.className = 'level-up-ring';
            burst.appendChild(ring);

            var stars = ['⭐', '✨', '🌟', '💫', '⭐'];
            for (var i = 0; i < 8; i++) {
                var star = document.createElement('div');
                star.className = 'level-up-star';
                star.textContent = stars[i % stars.length];
                var angle = (Math.PI * 2 / 8) * i;
                star.style.setProperty('--tx', (Math.cos(angle) * 70) + 'px');
                star.style.setProperty('--ty', (Math.sin(angle) * 70) + 'px');
                star.style.setProperty('--tx2', (Math.cos(angle) * 140) + 'px');
                star.style.setProperty('--ty2', (Math.sin(angle) * 140) + 'px');
                star.style.setProperty('--rot', (angle * 180 / Math.PI) + 'deg');
                star.style.setProperty('--rot2', ((angle + 0.5) * 180 / Math.PI) + 'deg');
                burst.appendChild(star);
            }

            sprite.style.position = 'relative';
            sprite.appendChild(burst);
            setTimeout(function() { if (burst.parentNode) burst.remove(); }, 1200);
        },

        flyCoins: function(fromX, fromY, count) {
            var coinEl = Utils.qs('.coin-display') || Utils.qs('#coins');
            if (!coinEl) return;
            var targetRect = coinEl.getBoundingClientRect();

            for (var i = 0; i < (count || 5); i++) {
                (function(i) {
                    setTimeout(function() {
                        var coin = document.createElement('span');
                        coin.className = 'coin-fly';
                        coin.textContent = '💰';
                        coin.style.left = fromX + 'px';
                        coin.style.top = fromY + 'px';
                        document.body.appendChild(coin);

                        coin.animate([
                            { transform: 'translate(0, 0) scale(1)', opacity: 1 },
                            { transform: 'translate(' + ((targetRect.left - fromX) * 0.5) + 'px, ' + ((targetRect.top - fromY) * 0.3) + 'px) scale(1.3)', opacity: 1, offset: 0.6 },
                            { transform: 'translate(' + (targetRect.left - fromX) + 'px, ' + (targetRect.top - fromY) + 'px) scale(0.5)', opacity: 0 }
                        ], { duration: 700, easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)' });

                        setTimeout(function() { if (coin.parentNode) coin.remove(); }, 750);
                    }, i * 80);
                })(i);
            }
        }
    };

    /* ============================================
       5. Canvas 粒子引擎
       ============================================ */
    var ParticleEngine = {
        canvas: null,
        ctx: null,
        particles: [],
        mouseParticles: [],
        sceneParticles: [],
        running: false,
        maxParticles: 150,
        mouseX: -1000,
        mouseY: -1000,

        init: function() {
            this.createCanvas();
            this.bindMouseEvents();
            this.running = true;
            this.loop();
            this.spawnAmbientParticles();
            console.log('[ParticleEngine] 粒子系统已启动');
        },

        createCanvas: function() {
            this.canvas = document.createElement('canvas');
            this.canvas.id = 'particleCanvas';
            this.canvas.width = window.innerWidth;
            this.canvas.height = window.innerHeight;
            document.body.appendChild(this.canvas);
            this.ctx = this.canvas.getContext('2d');
            var self = this;
            window.addEventListener('resize', function() {
                self.canvas.width = window.innerWidth;
                self.canvas.height = window.innerHeight;
            });
        },

        bindMouseEvents: function() {
            var self = this;
            document.addEventListener('mousemove', function(e) {
                self.mouseX = e.clientX;
                self.mouseY = e.clientY;
                if (Utils.randInt(1, 3) > 1) self.addMouseTrail(e.clientX, e.clientY);
            });
            document.addEventListener('mouseleave', function() {
                self.mouseX = -1000;
                self.mouseY = -1000;
            });
        },

        loop: function() {
            var self = this;
            function run() {
                if (!self.running) return;
                self.update();
                self.render();
                requestAnimationFrame(run);
            }
            run();
        },

        update: function() {
            this.particles = this.particles.filter(function(p) { return p.life > 0; });
            this.mouseParticles = this.mouseParticles.filter(function(p) { return p.life > 0; });

            var self = this;
            this.particles.forEach(function(p) {
                p.x += p.vx;
                p.y += p.vy;
                p.vy += p.gravity || 0;
                p.vx *= p.friction || 0.99;
                p.vy *= p.friction || 0.99;
                p.life -= p.decay;
                p.size *= p.shrink || 0.98;
                if (p.rotation !== undefined) p.rotation += p.rotSpeed || 0.05;
            });

            this.mouseParticles.forEach(function(p) {
                p.x += p.vx;
                p.y += p.vy;
                p.life -= p.decay;
                p.size *= 0.95;
            });
        },

        render: function() {
            var ctx = this.ctx;
            ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

            var allParticles = this.particles.concat(this.mouseParticles);
            var self = this;
            allParticles.forEach(function(p) {
                ctx.save();
                ctx.globalAlpha = Utils.clamp(p.life, 0, 1);
                ctx.fillStyle = p.color;

                if (p.shape === 'star') {
                    self.drawStar(ctx, p.x, p.y, p.size, p.points || 5);
                } else if (p.shape === 'rect') {
                    ctx.translate(p.x, p.y);
                    if (p.rotation) ctx.rotate(p.rotation);
                    ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
                } else {
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, Math.max(p.size, 0.5), 0, Math.PI * 2);
                    ctx.fill();
                }

                if (p.glow) {
                    ctx.shadowColor = p.color;
                    ctx.shadowBlur = p.glow;
                    ctx.fill();
                    ctx.shadowBlur = 0;
                }
                ctx.restore();
            });
        },

        drawStar: function(ctx, x, y, r, points) {
            ctx.beginPath();
            for (var i = 0; i < points * 2; i++) {
                var angle = (Math.PI / points) * i - Math.PI / 2;
                var radius = i % 2 === 0 ? r : r * 0.4;
                var px = x + Math.cos(angle) * radius;
                var py = y + Math.sin(angle) * radius;
                if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
            }
            ctx.closePath();
            ctx.fill();
        },

        addParticle: function(x, y, opts) {
            if (this.particles.length >= this.maxParticles) return;
            this.particles.push({
                x: x, y: y,
                vx: opts.vx || (Math.random() - 0.5) * 4,
                vy: opts.vy || (Math.random() - 0.5) * 4,
                size: opts.size || Math.random() * 5 + 2,
                color: opts.color || '#ff6b9d',
                life: opts.life || 1,
                decay: opts.decay || 0.015,
                gravity: opts.gravity || 0,
                shrink: opts.shrink || 0.97,
                friction: opts.friction || 0.99,
                shape: opts.shape || 'circle',
                glow: opts.glow || 0,
                rotation: 0,
                rotSpeed: (Math.random() - 0.5) * 0.1,
                points: opts.points
            });
        },

        addExplosion: function(x, y, color, count) {
            count = count || 25;
            for (var i = 0; i < count; i++) {
                var angle = (Math.PI * 2 / count) * i + Math.random() * 0.3;
                var speed = Math.random() * 6 + 2;
                this.addParticle(x, y, {
                    vx: Math.cos(angle) * speed,
                    vy: Math.sin(angle) * speed,
                    color: color,
                    size: Math.random() * 6 + 2,
                    life: 1,
                    decay: 0.02 + Math.random() * 0.01,
                    gravity: 0.08,
                    glow: 8,
                    shape: Math.random() > 0.5 ? 'circle' : 'star',
                    points: Math.floor(Math.random() * 3) + 4
                });
            }
        },

        addMouseTrail: function(x, y) {
            if (this.mouseParticles.length > 20) return;
            var hue = Date.now() % 360;
            this.mouseParticles.push({
                x: x, y: y,
                vx: (Math.random() - 0.5) * 1.5,
                vy: (Math.random() - 0.5) * 1.5 - 0.5,
                size: Math.random() * 4 + 2,
                color: 'hsla(' + hue + ', 80%, 65%, ',
                life: 0.8,
                decay: 0.03,
                gravity: -0.03,
                shrink: 0.96,
                glow: 6
            });
        },

        spawnAmbientParticles: function() {
            var self = this;
            setInterval(function() {
                if (document.hidden) return;
                var bodyClass = document.body.className;

                if (bodyClass.indexOf('snow') !== -1) {
                    self.addParticle(
                        Math.random() * self.canvas.width,
                        -10,
                        { vy: Utils.rand(1, 3), vx: Utils.rand(-0.5, 0.5),
                          size: Utils.rand(2, 5), color: 'rgba(255,255,255,',
                          life: 1, decay: 0.004, gravity: 0.02, shrink: 0.995,
                          shape: 'rect', rotation: Math.random() * Math.PI, rotSpeed: 0.02 }
                    );
                } else if (bodyClass.indexOf('night') !== -1) {
                    if (Math.random() > 0.85) {
                        self.addParticle(
                            Math.random() * self.canvas.width,
                            Math.random() * self.canvas.height * 0.7,
                            { vx: Utils.rand(-0.3, 0.3), vy: Utils.rand(-0.5, 0.1),
                              size: Utils.rand(2, 4), color: 'rgba(255,217,61,',
                              life: 1, decay: 0.008, gravity: -0.02, glow: 10 }
                        );
                    }
                } else if (bodyClass.indexOf('sunny') !== -1) {
                    if (Math.random() > 0.9) {
                        self.addParticle(
                            Math.random() * self.canvas.width,
                            self.canvas.height + 10,
                            { vy: Utils.rand(-1.5, -0.5), vx: Utils.rand(-0.3, 0.3),
                              size: Utils.rand(1, 3), color: 'rgba(255,217,61,',
                              life: 0.8, decay: 0.006, gravity: -0.04, shrink: 0.98 }
                        );
                    }
                }
            }, 200);
        },

        clear: function() {
            this.particles = [];
            this.mouseParticles = [];
        }
    };

    /* ============================================
       场景粒子（DOM-based，用于落叶等）
       ============================================ */
    var SceneParticles = {
        container: null,
        particles: [],

        init: function() {
            this.container = document.createElement('div');
            this.container.className = 'scene-particles';
            document.body.appendChild(this.container);
            this.watchWeatherChanges();
            console.log('[SceneParticles] 场景粒子系统已启动');
        },

        watchWeatherChanges: function() {
            var self = this;
            var observer = new MutationObserver(function() {
                self.onWeatherChange(document.body.className);
            });
            observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
            this.onWeatherChange(document.body.className);
        },

        onWeatherChange: function(className) {
            this.clearAll();

            if (className.indexOf('sunny') !== -1 || className.indexOf('beach') !== -1) {
                this.spawnLeaves(8);
            }
            if (className.indexOf('night') !== -1) {
                this.spawnFireflies(12);
            }
            if (className.indexOf('snow') !== -1) {
                this.spawnSnowflakes(20);
            }
        },

        clearAll: function() {
            var self = this;
            this.particles.forEach(function(p) { if (p.parentNode) p.remove(); });
            this.particles = [];
        },

        spawnLeaves: function(count) {
            for (var i = 0; i < count; i++) {
                var leaf = document.createElement('div');
                leaf.className = 'scene-particle leaf';
                leaf.style.left = Utils.rand(0, 100) + '%';
                leaf.style.animationDuration = Utils.rand(8, 16) + 's';
                leaf.style.animationDelay = (-Utils.rand(0, 15)) + 's';
                leaf.style.opacity = Utils.rand(0.4, 0.8);
                this.container.appendChild(leaf);
                this.particles.push(leaf);
            }
        },

        spawnFireflies: function(count) {
            for (var i = 0; i < count; i++) {
                var ff = document.createElement('div');
                ff.className = 'scene-particle firefly';
                ff.style.left = Utils.rand(5, 95) + '%';
                ff.style.top = Utils.rand(10, 80) + '%';
                ff.style.animationDelay = (-Utils.rand(0, 3000)) + 'ms';
                this.container.appendChild(ff);
                this.particles.push(ff);

                (function(el) {
                    setInterval(function() {
                        el.style.left = Utils.rand(5, 95) + '%';
                        el.style.top = Utils.rand(10, 80) + '%';
                    }, Utils.rand(3000, 7000));
                })(ff);
            }
        },

        spawnSnowflakes: function(count) {
            var flakes = ['❄', '❅', '❆', '•'];
            for (var i = 0; i < count; i++) {
                var sf = document.createElement('div');
                sf.className = 'scene-particle snowflake';
                sf.textContent = flakes[Utils.randInt(0, flakes.length - 1)];
                sf.style.left = Utils.rand(0, 100) + '%';
                sf.style.animationDuration = Utils.rand(5, 14) + 's';
                sf.style.animationDelay = (-Utils.rand(0, 12)) + 's';
                sf.style.fontSize = Utils.rand(8, 18) + 'px';
                this.container.appendChild(sf);
                this.particles.push(sf);
            }
        }
    };

    /* ============================================
       全局事件桥接
       ============================================ */
    var EventBridge = {
        init: function() {
            var self = this;
            this.hookLogAdd();
            this.hookLevelUp();
            this.hookAchievements();
            this.hookShopBuy();
            this.hookEquipment();
            console.log('[EventBridge] 事件桥接已建立');
        },

        hookLogAdd: function() {
            var self = this;
            if (typeof addBattleLog === 'function') {
                var orig = window.addBattleLog;
                window.addBattleLog = function(msg, type) {
                    if (orig) orig.apply(null, arguments);
                    if (type === 'damage' || type === 'critical') {
                        var dmgMatch = msg.match(/(\d+)/);
                        if (dmgMatch) {
                            var dmg = parseInt(dmgMatch[1]);
                            setTimeout(function() {
                                BattleEnhance.showDamagePopup(dmg, type === 'critical', false, false);
                                BattleEnhance.playEnemyHit();
                                ParticleEngine.addExplosion(
                                    (window.innerWidth / 2) + Utils.rand(-30, 30),
                                    (window.innerHeight * 0.35) + Utils.rand(-20, 20),
                                    type === 'critical' ? '#ffd93d' : '#ff6b6b',
                                    type === 'critical' ? 15 : 8
                                );
                            }, 200);
                        }
                    } else if (type === 'heal') {
                        var healMatch = msg.match(/(\d+)/);
                        if (healMatch) {
                            setTimeout(function() {
                                BattleEnhance.showDamagePopup(parseInt(healMatch[1]), false, true, false);
                                ParticleEngine.addExplosion(
                                    (window.innerWidth / 2) + Utils.rand(-20, 20),
                                    (window.innerHeight * 0.35) + Utils.rand(-10, 10),
                                    '#6bcb77', 10
                                );
                            }, 200);
                        }
                    }
                };
            }
        },

        hookLevelUp: function() {
            var origCheck = window.checkLevelUp;
            if (origCheck) {
                window.checkLevelUp = function() {
                    var prevLevel = typeof cat !== 'undefined' ? cat.level : 0;
                    origCheck.apply(null, arguments);
                    if (typeof cat !== 'undefined' && cat.level > prevLevel) {
                        UIEffects.showLevelUpBurst();
                        CharacterEnhance.setMood('excited', 4000);
                        CharacterEnhance.playEvolutionGlow();
                        ParticleEngine.addExplosion(window.innerWidth / 2, window.innerHeight / 2, '#ffd93d', 40);
                    }
                };
            }
        },

        hookAchievements: function() {
            if (typeof unlockAchievement === 'function') {
                var orig = window.unlockAchievement;
                window.unlockAchievement = function(id) {
                    if (orig) orig.apply(null, arguments);
                    var achNames = {
                        firstWin: '初次胜利', winStreak3: '三连胜', winStreak10: '十连胜',
                        level5: '成长之路', level10: '冒险新星', level20: '资深战士',
                        richCat: '小富翁', collector: '收藏家', explorer: '探险家'
                    };
                    UIEffects.showAchievementUnlock(achNames[id] || id, '');
                    ParticleEngine.addExplosion(window.innerWidth / 2, window.innerHeight * 0.3, '#ffd93d', 30);
                };
            }
        },

        hookShopBuy: function() {
            if (typeof buyItem === 'function') {
                var orig = window.buyItem;
                window.buyItem = function(item, price) {
                    if (orig) {
                        var result = orig.apply(null, arguments);
                        if (result !== false) {
                            var btn = document.querySelector('[onclick*="buyItem(\'' + item + '\'"]');
                            if (btn) {
                                var rect = btn.getBoundingClientRect();
                                UIEffects.flyCoins(rect.left + rect.width / 2, rect.top, 3);
                            }
                            ParticleEngine.addExplosion(
                                rect ? rect.left + rect.width / 2 : window.innerWidth / 2,
                                rect ? rect.top : window.innerHeight / 2,
                                '#ffd93d', 8
                            );
                        }
                        return result;
                    }
                };
            }
        },

        hookEquipment: function() {
            if (typeof equipItem === 'function') {
                var orig = window.equipItem;
                window.equipItem = function(itemId) {
                    if (orig) orig.apply(null, arguments);
                    var itemMap = {
                        wizardHat: { type: 'hat', emoji: '🎩' },
                        partyHat: { type: 'hat', emoji: '🎉' },
                        crown: { type: 'hat', emoji: '👑' },
                        ribbon: { type: 'collar', emoji: '🎀' },
                        bellCollar: { type: 'collar', emoji: '🔔' }
                    };
                    var info = itemMap[itemId];
                    if (info) {
                        CharacterEnhance.showEquipment(info.type, info.emoji);
                    }
                };
            }
        }
    };

    /* ============================================
       启动入口
       ============================================ */
    function boot() {
        try {
            CharacterEnhance.init();
            SceneDepth.init();
            SceneParticles.init();
            ParticleEngine.init();
            BattleEnhance.init();
            UIEffects.init();
            EventBridge.init();
            console.log('[Enhancements v' + VERSION + '] 所有增强模块加载完成 ✓');
        } catch(err) {
            console.error('[Enhancements] 初始化错误:', err);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

    window.__enhancements = {
        version: VERSION,
        CharacterEnhance: CharacterEnhance,
        SceneDepth: SceneDepth,
        BattleEnhance: BattleEnhance,
        UIEffects: UIEffects,
        ParticleEngine: ParticleEngine,
        SceneParticles: SceneParticles
    };

})();
