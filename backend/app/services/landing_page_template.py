"""Landing page HTML template with placeholders for AI-generated copy."""

_LANDING_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0a0e1a;--surface:#111827;--text:#f1f5f9;--muted:#94a3b8;--primary:#0B4FD8;--accent:#22D3EE;--success:#10b981}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;overflow-x:hidden}
a{color:var(--accent);text-decoration:none}
@keyframes fadeInUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(11,79,216,.4)}50%{box-shadow:0 0 0 12px rgba(11,79,216,0)}}
.nav{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(10,14,26,.9);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.06)}
.nav-inner{max-width:1200px;margin:0 auto;padding:0 24px;height:60px;display:flex;align-items:center;justify-content:space-between}
.logo{font-size:20px;font-weight:700;color:var(--text);letter-spacing:-.5px}
.logo span{color:var(--primary)}
.nav-links{display:flex;gap:28px;list-style:none;align-items:center}
.nav-links a{color:var(--muted);font-size:14px;transition:color .2s}
.nav-links a:hover{color:var(--text)}
.nav-cta{background:var(--primary);color:#fff!important;padding:8px 18px;border-radius:8px;font-weight:500}
.hero{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:100px 24px 60px;text-align:center;background:radial-gradient(ellipse at 50% 100%,rgba(11,79,216,.15) 0%,transparent 60%)}
.hero-inner{max-width:800px;width:100%;animation:fadeInUp .8s ease both}
.badge{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:999px;background:rgba(11,79,216,.15);border:1px solid rgba(11,79,216,.25);color:var(--accent);font-size:13px;margin-bottom:24px}
.hero h1{font-size:clamp(36px,6vw,64px);font-weight:800;line-height:1.1;margin-bottom:20px;letter-spacing:-1.5px}
.hero h1 .gradient{background:linear-gradient(135deg,var(--primary),var(--accent));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{font-size:clamp(16px,2.5vw,20px);color:var(--muted);max-width:600px;margin:0 auto 32px}
.hero-form{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;max-width:540px;margin:0 auto 32px}
.hero-form input{flex:1 1 200px;padding:14px 18px;border-radius:10px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.05);color:var(--text);font-size:15px;outline:none;transition:border-color .2s}
.hero-form input:focus{border-color:var(--primary)}
.hero-form input::placeholder{color:var(--muted)}
.hero-form button{flex:0 0 auto;padding:14px 28px;border-radius:10px;border:none;background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;font-size:16px;font-weight:600;cursor:pointer;animation:pulse 2s infinite}
.hero-form button:hover{opacity:.9}
.stats{display:flex;justify-content:center;gap:48px;margin-top:40px;flex-wrap:wrap}
.stat-num{font-size:36px;font-weight:800;color:var(--text)}
.stat-label{font-size:14px;color:var(--muted)}
.section{padding:80px 24px;max-width:1200px;margin:0 auto}
.section-alt{background:radial-gradient(ellipse at 50% 0%,rgba(11,79,216,.06) 0%,transparent 60%)}
.section-header{text-align:center;margin-bottom:56px;animation:fadeInUp .8s ease both}
.section-header h2{font-size:clamp(28px,4vw,40px);font-weight:700;margin-bottom:12px}
.section-header p{color:var(--muted);font-size:18px;max-width:500px;margin:0 auto}
.features-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}
.feature-card{padding:32px;border-radius:16px;background:var(--surface);border:1px solid rgba(255,255,255,.06);transition:transform .2s,border-color .2s;animation:fadeInUp .6s ease both}
.feature-card:nth-child(2){animation-delay:.1s}
.feature-card:nth-child(3){animation-delay:.2s}
.feature-card:nth-child(4){animation-delay:.3s}
.feature-card:hover{transform:translateY(-4px);border-color:rgba(11,79,216,.3)}
.feature-icon{width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,var(--primary),var(--accent));display:flex;align-items:center;justify-content:center;font-size:22px;margin-bottom:16px}
.feature-card h3{font-size:18px;font-weight:600;margin-bottom:8px}
.feature-card p{color:var(--muted);font-size:15px;line-height:1.5}
.steps-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:32px;margin-top:40px}
.step-card{text-align:center;padding:32px;animation:fadeInUp .6s ease both}
.step-card:nth-child(2){animation-delay:.15s}
.step-card:nth-child(3){animation-delay:.3s}
.step-num{width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,var(--primary),var(--accent));display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;margin:0 auto 20px}
.step-card h3{font-size:20px;font-weight:600;margin-bottom:10px}
.step-card p{color:var(--muted);font-size:15px;line-height:1.6}
.reviews-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px;margin-top:40px}
.review-card{padding:28px;border-radius:16px;background:var(--surface);border:1px solid rgba(255,255,255,.06);animation:fadeInUp .6s ease both}
.review-card:nth-child(2){animation-delay:.15s}
.review-stars{color:#fbbf24;font-size:18px;margin-bottom:12px}
.review-card p{color:var(--muted);font-size:15px;line-height:1.6;margin-bottom:20px;font-style:italic}
.review-author{display:flex;align-items:center;gap:12px}
.review-avatar{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--primary),var(--accent));display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600}
.review-author div:last-child{font-size:14px;color:var(--muted)}
.review-author strong{color:var(--text);display:block}
.faq-list{max-width:800px;margin:40px auto 0}
.faq-item{border-bottom:1px solid rgba(255,255,255,.08)}
.faq-q{width:100%;display:flex;align-items:center;justify-content:space-between;padding:20px 0;background:none;border:none;color:var(--text);font-size:17px;font-weight:500;text-align:left;cursor:pointer}
.faq-q::after{content:'+';font-size:22px;color:var(--accent);transition:transform .3s}
.faq-item.active .faq-q::after{transform:rotate(45deg)}
.faq-a{max-height:0;overflow:hidden;transition:max-height .3s ease,padding .3s ease;color:var(--muted);font-size:15px;line-height:1.6}
.faq-item.active .faq-a{max-height:200px;padding-bottom:20px}
.footer{padding:60px 24px;text-align:center;border-top:1px solid rgba(255,255,255,.06)}
.footer h2{font-size:clamp(24px,3vw,32px);font-weight:700;margin-bottom:16px}
.footer p{color:var(--muted);margin-bottom:24px;max-width:500px;margin-left:auto;margin-right:auto}
.footer-btn{display:inline-block;padding:14px 32px;border-radius:10px;background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;font-size:16px;font-weight:600}
.footer-copy{margin-top:32px;font-size:14px;color:var(--muted)}
@media(max-width:640px){.nav-links{display:none}.hero{padding-top:80px}.stats{gap:24px}.features-grid,.steps-grid,.reviews-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<img src="/api/v1/landing-pages/track?lp_id={{LP_ID}}" width="1" height="1" style="position:absolute;visibility:hidden;" alt="">

<nav class="nav">
  <div class="nav-inner">
    <a href="#" class="logo">eko <span>AI</span></a>
    <ul class="nav-links">
      <li><a href="#benefits">Benefits</a></li>
      <li><a href="#how-it-works">How It Works</a></li>
      <li><a href="#reviews">Reviews</a></li>
      <li><a href="#faq">FAQ</a></li>
      <li><a href="#form" class="nav-cta">Get Started</a></li>
    </ul>
  </div>
</nav>

<section class="hero" id="form">
  <div class="hero-inner">
    <div class="badge">⚡ {{BADGE}}</div>
    <h1>{{HERO_TITLE}}</h1>
    <p>{{HERO_SUBTITLE}}</p>
    <form class="hero-form" action="/api/v1/leads/public?landing_page_id={{LP_ID}}" method="POST">
      <input type="text" name="first_name" placeholder="First Name" required>
      <input type="text" name="last_name" placeholder="Last Name" required>
      <input type="email" name="email" placeholder="Email" required>
      <input type="tel" name="phone" placeholder="Phone" required>
      <input type="url" name="website" placeholder="Website" required>
      <button type="submit">{{CTA_BUTTON}}</button>
    </form>
    <div class="stats">
      <div><div class="stat-num">{{STAT_1_NUM}}</div><div class="stat-label">{{STAT_1_LABEL}}</div></div>
      <div><div class="stat-num">{{STAT_2_NUM}}</div><div class="stat-label">{{STAT_2_LABEL}}</div></div>
      <div><div class="stat-num">{{STAT_3_NUM}}</div><div class="stat-label">{{STAT_3_LABEL}}</div></div>
    </div>
  </div>
</section>

<section class="section" id="benefits">
  <div class="section-header">
    <h2>{{BENEFITS_HEADLINE}}</h2>
    <p>{{BENEFITS_SUBHEADLINE}}</p>
  </div>
  <div class="features-grid">
    <div class="feature-card">
      <div class="feature-icon">{{BENEFIT_1_ICON}}</div>
      <h3>{{BENEFIT_1_TITLE}}</h3>
      <p>{{BENEFIT_1_DESC}}</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">{{BENEFIT_2_ICON}}</div>
      <h3>{{BENEFIT_2_TITLE}}</h3>
      <p>{{BENEFIT_2_DESC}}</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">{{BENEFIT_3_ICON}}</div>
      <h3>{{BENEFIT_3_TITLE}}</h3>
      <p>{{BENEFIT_3_DESC}}</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">{{BENEFIT_4_ICON}}</div>
      <h3>{{BENEFIT_4_TITLE}}</h3>
      <p>{{BENEFIT_4_DESC}}</p>
    </div>
  </div>
</section>

<section class="section section-alt" id="how-it-works">
  <div class="section-header">
    <h2>{{HOW_HEADLINE}}</h2>
    <p>{{HOW_SUBHEADLINE}}</p>
  </div>
  <div class="steps-grid">
    <div class="step-card">
      <div class="step-num">1</div>
      <h3>{{STEP_1_TITLE}}</h3>
      <p>{{STEP_1_DESC}}</p>
    </div>
    <div class="step-card">
      <div class="step-num">2</div>
      <h3>{{STEP_2_TITLE}}</h3>
      <p>{{STEP_2_DESC}}</p>
    </div>
    <div class="step-card">
      <div class="step-num">3</div>
      <h3>{{STEP_3_TITLE}}</h3>
      <p>{{STEP_3_DESC}}</p>
    </div>
  </div>
</section>

<section class="section" id="reviews">
  <div class="section-header">
    <h2>{{REVIEWS_HEADLINE}}</h2>
    <p>{{REVIEWS_SUBHEADLINE}}</p>
  </div>
  <div class="reviews-grid">
    <div class="review-card">
      <div class="review-stars">★★★★★</div>
      <p>"{{REVIEW_1_QUOTE}}"</p>
      <div class="review-author">
        <div class="review-avatar">{{REVIEW_1_INITIALS}}</div>
        <div><strong>{{REVIEW_1_NAME}}</strong>{{REVIEW_1_ROLE}}</div>
      </div>
    </div>
    <div class="review-card">
      <div class="review-stars">★★★★★</div>
      <p>"{{REVIEW_2_QUOTE}}"</p>
      <div class="review-author">
        <div class="review-avatar">{{REVIEW_2_INITIALS}}</div>
        <div><strong>{{REVIEW_2_NAME}}</strong>{{REVIEW_2_ROLE}}</div>
      </div>
    </div>
  </div>
</section>

<section class="section section-alt" id="faq">
  <div class="section-header">
    <h2>{{FAQ_HEADLINE}}</h2>
    <p>{{FAQ_SUBHEADLINE}}</p>
  </div>
  <div class="faq-list">
    <div class="faq-item active">
      <button class="faq-q" onclick="this.parentElement.classList.toggle('active')">{{FAQ_1_Q}}</button>
      <div class="faq-a">{{FAQ_1_A}}</div>
    </div>
    <div class="faq-item">
      <button class="faq-q" onclick="this.parentElement.classList.toggle('active')">{{FAQ_2_Q}}</button>
      <div class="faq-a">{{FAQ_2_A}}</div>
    </div>
    <div class="faq-item">
      <button class="faq-q" onclick="this.parentElement.classList.toggle('active')">{{FAQ_3_Q}}</button>
      <div class="faq-a">{{FAQ_3_A}}</div>
    </div>
    <div class="faq-item">
      <button class="faq-q" onclick="this.parentElement.classList.toggle('active')">{{FAQ_4_Q}}</button>
      <div class="faq-a">{{FAQ_4_A}}</div>
    </div>
  </div>
</section>

<footer class="footer">
  <h2>{{FOOTER_HEADLINE}}</h2>
  <p>{{FOOTER_SUBHEADLINE}}</p>
  <a href="#form" class="footer-btn">{{FOOTER_CTA}}</a>
  <div class="footer-copy">© {{YEAR}} Eko AI. contact@biz.ekoaiautomation.com</div>
</footer>

<script>
(function(){
  const form = document.querySelector('.hero-form');
  const msgDiv = document.createElement('div');
  msgDiv.style.cssText = 'flex:1 1 100%;text-align:center;padding:12px 18px;border-radius:10px;font-size:15px;font-weight:500;margin-top:8px;display:none;';
  form.insertBefore(msgDiv, form.querySelector('button').nextSibling);

  form.addEventListener('submit', function(e){
    e.preventDefault();
    msgDiv.style.display = 'none';
    const btn = form.querySelector('button');
    const originalText = btn.textContent;
    btn.textContent = 'Sending...';
    btn.disabled = true;

    const data = new URLSearchParams(new FormData(form));
    fetch(form.action, {
      method: 'POST',
      body: data,
      headers: {'Accept': 'application/json'}
    })
    .then(r => r.json().catch(() => ({})))
    .then(res => {
      if (res.status === 'created') {
        msgDiv.textContent = "Thanks! We'll send your AI analysis to your email within 24 hours.";
        msgDiv.style.background = 'rgba(16,185,129,0.15)';
        msgDiv.style.color = '#10b981';
        msgDiv.style.border = '1px solid rgba(16,185,129,0.3)';
        form.reset();
      } else if (res.status === 'existing') {
        msgDiv.textContent = "You're already on our list! We'll reach out to you soon.";
        msgDiv.style.background = 'rgba(251,191,36,0.15)';
        msgDiv.style.color = '#fbbf24';
        msgDiv.style.border = '1px solid rgba(251,191,36,0.3)';
        form.reset();
      } else {
        msgDiv.textContent = "Something went wrong. Please try again.";
        msgDiv.style.background = 'rgba(239,68,68,0.15)';
        msgDiv.style.color = '#ef4444';
        msgDiv.style.border = '1px solid rgba(239,68,68,0.3)';
      }
      msgDiv.style.display = 'block';
    })
    .catch(() => {
      msgDiv.textContent = "Something went wrong. Please try again.";
      msgDiv.style.background = 'rgba(239,68,68,0.15)';
      msgDiv.style.color = '#ef4444';
      msgDiv.style.border = '1px solid rgba(239,68,68,0.3)';
      msgDiv.style.display = 'block';
    })
    .finally(() => {
      btn.textContent = originalText;
      btn.disabled = false;
    });
  });
})();
</script>
</body>
</html>"""


# Default fallback values if AI fails to generate
_DEFAULT_COPY = {
    "TITLE": "Eko AI — Your 24/7 AI Agent",
    "BADGE": "AI-Powered Automation for Local Businesses",
    "HERO_TITLE": "Your Business Never Sleeps With <span class='gradient'>Eko AI</span>",
    "HERO_SUBTITLE": "Never miss a customer call again. Eko AI answers questions, books appointments, and follows up automatically—so you can focus on growing your business.",
    "CTA_BUTTON": "Get Your Free AI Analysis",
    "STAT_1_NUM": "24/7",
    "STAT_1_LABEL": "Always Available",
    "STAT_2_NUM": "500+",
    "STAT_2_LABEL": "Businesses Served",
    "STAT_3_NUM": "98%",
    "STAT_3_LABEL": "Customer Satisfaction",
    "BENEFITS_HEADLINE": "Why Business Owners Love Eko AI",
    "BENEFITS_SUBHEADLINE": "Everything you need to never miss a customer",
    "BENEFIT_1_ICON": "📞",
    "BENEFIT_1_TITLE": "Answer Calls 24/7",
    "BENEFIT_1_DESC": "Never miss a call again. Your AI answers, qualifies leads, and transfers when needed.",
    "BENEFIT_2_ICON": "💬",
    "BENEFIT_2_TITLE": "Respond on WhatsApp",
    "BENEFIT_2_DESC": "Instant replies to customer inquiries. Product questions, pricing, availability—all automatic.",
    "BENEFIT_3_ICON": "📅",
    "BENEFIT_3_TITLE": "Book Appointments",
    "BENEFIT_3_DESC": "Connects directly to your calendar. Customers book, reschedule, or cancel without human help.",
    "BENEFIT_4_ICON": "🤝",
    "BENEFIT_4_TITLE": "Follow Up Automatically",
    "BENEFIT_4_DESC": "No lead falls through the cracks. Automated follow-ups nurture prospects until they convert.",
    "HOW_HEADLINE": "How It Works",
    "HOW_SUBHEADLINE": "Get started in 3 simple steps",
    "STEP_1_TITLE": "Book Your Demo",
    "STEP_1_DESC": "15 minutes. We learn about your business and show you exactly how AI will work for you.",
    "STEP_2_TITLE": "We Configure Everything",
    "STEP_2_DESC": "Our team trains your AI agent with your business info, services, pricing, and brand voice.",
    "STEP_3_TITLE": "Go Live & Scale",
    "STEP_3_DESC": "Your AI starts working immediately. Answer calls, book appointments, follow up—24/7 from day one.",
    "REVIEWS_HEADLINE": "Loved by Business Owners",
    "REVIEWS_SUBHEADLINE": "See what our customers say",
    "REVIEW_1_QUOTE": "We went from missing 30% of calls to booking every single one. Eko AI paid for itself in the first week.",
    "REVIEW_1_INITIALS": "MR",
    "REVIEW_1_NAME": "Maria Rodriguez",
    "REVIEW_1_ROLE": "Spa Owner, Miami",
    "REVIEW_2_QUOTE": "Finally, an AI that actually sounds like me! Clients don't even know they're talking to a bot.",
    "REVIEW_2_INITIALS": "JC",
    "REVIEW_2_NAME": "James Chen",
    "REVIEW_2_ROLE": "Gym Owner, San Francisco",
    "FAQ_HEADLINE": "Frequently Asked Questions",
    "FAQ_SUBHEADLINE": "Everything you need to know",
    "FAQ_1_Q": "How quickly can Eko AI be set up?",
    "FAQ_1_A": "Most businesses are live within 48 hours of their demo. We handle all the configuration, training, and integration.",
    "FAQ_2_Q": "Does it work with my existing tools?",
    "FAQ_2_A": "Yes. Eko AI integrates with Google Calendar, Outlook, Cal.com, most CRMs, and popular business phone systems.",
    "FAQ_3_Q": "What if the AI can't answer a question?",
    "FAQ_3_A": "Your AI is trained specifically on your business. For edge cases, it can transfer to you or take a message with full context.",
    "FAQ_4_Q": "Can I cancel anytime?",
    "FAQ_4_A": "Yes. No long-term contracts, no cancellation fees. We earn your business every month.",
    "FOOTER_HEADLINE": "Ready to never miss a customer again?",
    "FOOTER_SUBHEADLINE": "Join 500+ businesses already using Eko AI to automate their customer interactions.",
    "FOOTER_CTA": "Get Your Free AI Analysis",
}


SYSTEM_PROMPT_TEMPLATE = """You are a conversion copywriter for local businesses. Generate landing page copy for Eko AI based on the user's instructions.

═══════════════════════════════════════════════════════════════════════════════
ABOUT EKO AI — THE FULL PLATFORM
═══════════════════════════════════════════════════════════════════════════════

Eko AI is a complete AI-powered business automation platform for local businesses.
It is NOT just a phone bot — it covers customer communication, content marketing,
sales funnels, and CRM in one integrated system.

CAPABILITY LIBRARY (pick the 4 most relevant for the BENEFIT cards, based on the
user's niche and prompt — do NOT default to the same 4 every time):

1. **24/7 AI Receptionist** — Answers phone calls, WhatsApp messages, and emails
   instantly in the business's voice. Never miss a customer again. Handles FAQs,
   quotes, hours, directions, multilingual (English + Spanish out of the box).

2. **Smart Appointment Booking** — Direct Cal.com / Google Calendar / Outlook
   integration. Customers book, reschedule, cancel without human help. Sends
   reminders + reduces no-shows. Handles waitlists automatically.

3. **AI Social Media Content Studio** — Auto-generates short-form (≈30s) and
   long-form (≈80s) videos with AI imagery (FLUX), Ken Burns motion, crossfade
   transitions, multilingual TTS, and yellow karaoke subtitles. Auto-publishes
   to Instagram, Facebook, TikTok, YouTube, and LinkedIn on peak-hour slots via
   Buffer integration. End-frame CTAs with the business's offer and contact.
   Owner just describes the business once — content runs on autopilot.

4. **Self-Service Landing Page Builder** — The business owner can generate
   unlimited niche-specific landing pages with AI from a simple prompt. Built-in
   A/B testing (Compare tab) with side-by-side analytics, random-pool rotation,
   SEO-friendly URLs, conversion tracking, lead-source attribution. Fully
   self-service — no developer needed.

5. **AI Email Reply Agent** — Auto-responds to inbound customer emails with
   contextual replies. Language detection (writes in customer's language).
   Keyword-based intent routing. Threads conversations by lead.

6. **Voice AI Outbound (VAPI)** — AI agent makes outbound calls for follow-ups,
   appointment confirmations, lead qualification, and re-activation campaigns.
   Sounds natural, hands off to humans on edge cases.

7. **AI Proposal Generator** — Auto-generates personalized sales proposals from
   lead data. Includes pricing, scope, terms — owner reviews and sends.

8. **Smart CRM with Lead Scoring** — Auto-enriches leads with website + social
   data, scores them 0-100 by fit and intent, prioritizes outreach. Tracks every
   interaction (call, email, WhatsApp, booking) in one unified timeline.

9. **Automated Nurture Sequences** — Multi-touch email + SMS campaigns that fire
   on schedule or behavior triggers. Drip campaigns, re-engagement flows,
   post-purchase follow-ups — all hands-off.

10. **Unified Inbox** — Every channel (phone transcripts, WhatsApp, email, web
    form) in one threaded view per customer. AI summarizes long threads,
    suggests replies, flags hot leads.

═══════════════════════════════════════════════════════════════════════════════
COPY GUIDELINES
═══════════════════════════════════════════════════════════════════════════════

- The 4 BENEFIT cards must feel niche-specific. A restaurant gets booking +
  WhatsApp + content + voice outbound. A real-estate broker gets CRM + proposals
  + email replies + voice outbound. A spa gets content + booking + landing
  pages + multilingual receptionist. Match capabilities to pain points the
  user described in the prompt.
- The 3 HOW-IT-WORKS steps should describe a realistic onboarding journey
  (demo → configuration → go-live) but mention which capabilities the business
  is activating.
- The 4 FAQs must address the niche's most common objections (integrations,
  setup time, cancellation, what happens to existing tools, multilingual, etc.).
- Reviews should sound like real local business owners — name + role + city.
- DO NOT mention a capability the user explicitly excluded.
- DO NOT use the literal phrase "Eko AI is just a phone bot" — that
  undersells the platform.

═══════════════════════════════════════════════════════════════════════════════

Return ONLY a JSON object with these exact keys. No markdown, no explanations outside the JSON.

Required JSON structure:
{
  "TITLE": "Page title (50 chars max)",
  "BADGE": "Short badge above headline (e.g., 'AI-Powered Automation for Salons')",
  "HERO_TITLE": "Main headline with HTML span: 'Your Salon Never Sleeps With <span class=\\'gradient\\'>Eko AI</span>'",
  "HERO_SUBTITLE": "One paragraph value prop (max 200 chars)",
  "CTA_BUTTON": "Button text (e.g., 'Get Your Free AI Analysis')",
  "STAT_1_NUM": "First stat number (e.g., '24/7')",
  "STAT_1_LABEL": "First stat label",
  "STAT_2_NUM": "Second stat number",
  "STAT_2_LABEL": "Second stat label",
  "STAT_3_NUM": "Third stat number",
  "STAT_3_LABEL": "Third stat label",
  "BENEFITS_HEADLINE": "Benefits section headline",
  "BENEFITS_SUBHEADLINE": "Benefits section subheadline",
  "BENEFIT_1_ICON": "Single emoji",
  "BENEFIT_1_TITLE": "Benefit 1 title (3-4 words)",
  "BENEFIT_1_DESC": "Benefit 1 description (max 120 chars)",
  "BENEFIT_2_ICON": "Single emoji",
  "BENEFIT_2_TITLE": "Benefit 2 title",
  "BENEFIT_2_DESC": "Benefit 2 description",
  "BENEFIT_3_ICON": "Single emoji",
  "BENEFIT_3_TITLE": "Benefit 3 title",
  "BENEFIT_3_DESC": "Benefit 3 description",
  "BENEFIT_4_ICON": "Single emoji",
  "BENEFIT_4_TITLE": "Benefit 4 title",
  "BENEFIT_4_DESC": "Benefit 4 description",
  "HOW_HEADLINE": "How It Works headline",
  "HOW_SUBHEADLINE": "How It Works subheadline",
  "STEP_1_TITLE": "Step 1 title (3-4 words)",
  "STEP_1_DESC": "Step 1 description (max 120 chars)",
  "STEP_2_TITLE": "Step 2 title",
  "STEP_2_DESC": "Step 2 description",
  "STEP_3_TITLE": "Step 3 title",
  "STEP_3_DESC": "Step 3 description",
  "REVIEWS_HEADLINE": "Reviews headline",
  "REVIEWS_SUBHEADLINE": "Reviews subheadline",
  "REVIEW_1_QUOTE": "First testimonial quote (max 150 chars)",
  "REVIEW_1_INITIALS": "2-letter initials (e.g., 'MR')",
  "REVIEW_1_NAME": "First person name",
  "REVIEW_1_ROLE": "First person role + location",
  "REVIEW_2_QUOTE": "Second testimonial quote",
  "REVIEW_2_INITIALS": "2-letter initials",
  "REVIEW_2_NAME": "Second person name",
  "REVIEW_2_ROLE": "Second person role + location",
  "FAQ_HEADLINE": "FAQ headline",
  "FAQ_SUBHEADLINE": "FAQ subheadline",
  "FAQ_1_Q": "FAQ question 1",
  "FAQ_1_A": "FAQ answer 1 (max 150 chars)",
  "FAQ_2_Q": "FAQ question 2",
  "FAQ_2_A": "FAQ answer 2",
  "FAQ_3_Q": "FAQ question 3",
  "FAQ_3_A": "FAQ answer 3",
  "FAQ_4_Q": "FAQ question 4",
  "FAQ_4_A": "FAQ answer 4",
  "FOOTER_HEADLINE": "Footer headline",
  "FOOTER_SUBHEADLINE": "Footer subheadline (max 120 chars)",
  "FOOTER_CTA": "Footer button text"
}

IMPORTANT: All copy MUST be written in English only. No Spanish, no other languages.

USER INSTRUCTIONS:
{custom_prompt}
"""


def render_template(copy: dict, landing_page_id: int, year: int) -> str:
    """Replace placeholders in template with generated copy."""
    html = _LANDING_PAGE_TEMPLATE
    data = {**_DEFAULT_COPY, **copy, "LP_ID": str(landing_page_id), "YEAR": str(year)}
    for key, value in data.items():
        placeholder = "{{" + key + "}}"
        html = html.replace(placeholder, str(value))
    return html
