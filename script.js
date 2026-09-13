// ── Mobile nav toggle ────────────────────────────────────────────────
const toggle = document.getElementById("menuToggle");
const mobileMenu = document.getElementById("mobileMenu");

if (toggle && mobileMenu) {
  toggle.addEventListener("click", () => {
    mobileMenu.classList.toggle("show");
  });

  mobileMenu.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => mobileMenu.classList.remove("show"));
  });
}

// ── Nav scroll effect ────────────────────────────────────────────────
const nav = document.querySelector(".nav");
if (nav) {
  let lastScroll = 0;
  window.addEventListener("scroll", () => {
    const scrollY = window.scrollY;
    nav.classList.toggle("scrolled", scrollY > 40);
    lastScroll = scrollY;
  }, { passive: true });
}

// ── Scroll-reveal (IntersectionObserver) ─────────────────────────────
function initScrollReveal() {
  const revealEls = document.querySelectorAll(".reveal, .reveal-stagger");
  if (!revealEls.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );

  revealEls.forEach((el) => observer.observe(el));
}

// Auto-tag sections & cards for reveal
function autoTagRevealElements() {
  // Section headers
  document.querySelectorAll(".section__header").forEach((el) => {
    if (!el.classList.contains("reveal")) el.classList.add("reveal");
  });

  // Card grids get stagger
  document.querySelectorAll(".card-grid").forEach((el) => {
    if (!el.classList.contains("reveal-stagger")) el.classList.add("reveal-stagger");
  });

  // Planner & tip card
  document.querySelectorAll(".planner, .planner__grid, .cta, .footer__grid").forEach((el) => {
    if (!el.classList.contains("reveal")) el.classList.add("reveal");
  });
}

// ── Button ripple effect ─────────────────────────────────────────────
function initRippleButtons() {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn");
    if (!btn) return;

    const ripple = document.createElement("span");
    ripple.classList.add("ripple");
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    ripple.style.width = ripple.style.height = size + "px";
    ripple.style.left = e.clientX - rect.left - size / 2 + "px";
    ripple.style.top = e.clientY - rect.top - size / 2 + "px";
    btn.appendChild(ripple);

    ripple.addEventListener("animationend", () => ripple.remove());
  });
}

// ── Parallax-lite on hero ────────────────────────────────────────────
function initHeroParallax() {
  const hero = document.querySelector(".hero");
  if (!hero) return;

  window.addEventListener("scroll", () => {
    const scrollY = window.scrollY;
    if (scrollY < window.innerHeight) {
      hero.style.backgroundPositionY = `${50 + scrollY * 0.15}%`;
    }
  }, { passive: true });
}

// ── Counter animation for stat-like numbers ─────────────────────────
function animateCounters() {
  const counters = document.querySelectorAll("[data-count]");
  if (!counters.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const target = parseInt(el.dataset.count, 10);
          if (isNaN(target)) return;

          let current = 0;
          const step = Math.max(1, Math.ceil(target / 60));
          const interval = setInterval(() => {
            current += step;
            if (current >= target) {
              current = target;
              clearInterval(interval);
            }
            el.textContent = current.toLocaleString();
          }, 16);

          observer.unobserve(el);
        }
      });
    },
    { threshold: 0.5 }
  );

  counters.forEach((el) => observer.observe(el));
}

// ── Magnetic hover on cards (subtle tilt) ────────────────────────────
function initCardTilt() {
  document.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -3;
      const rotateY = ((x - centerX) / centerX) * 3;

      card.style.transform = `translateY(-8px) perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });

    card.addEventListener("mouseleave", () => {
      card.style.transform = "";
    });
  });
}

// ── Active nav link highlight on scroll ──────────────────────────────
function initActiveNavHighlight() {
  const sections = document.querySelectorAll("section[id]");
  const navLinks = document.querySelectorAll(".nav__links a[href^='#']");
  if (!sections.length || !navLinks.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          navLinks.forEach((link) => {
            link.style.color = "";
            link.style.fontWeight = "";
            if (link.getAttribute("href") === `#${id}`) {
              link.style.color = "var(--emerald-dark)";
              link.style.fontWeight = "700";
            }
          });
        }
      });
    },
    { threshold: 0.3, rootMargin: "-80px 0px -40% 0px" }
  );

  sections.forEach((s) => observer.observe(s));
}

// ── Smooth chip click & Hero Search Interaction ──────────────────────
function initHeroInteractions() {
  const searchInput = document.getElementById("heroSearchInput") || document.querySelector(".input-wrap input");
  const exploreBtn = document.getElementById("heroExploreBtn");
  const cabBtn = document.getElementById("heroBookCabBtn");

  // Chip click to quick-fill
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (searchInput) {
        searchInput.value = chip.textContent.trim();
        searchInput.focus();

        // Pulse the search card
        const searchCard = document.querySelector(".search-card");
        if (searchCard) {
          searchCard.style.transform = "scale(1.02)";
          setTimeout(() => {
            searchCard.style.transform = "";
          }, 200);
        }
      }
    });
  });

  const performSearch = () => {
    if (!searchInput) return;
    const val = searchInput.value.trim().toLowerCase();
    if (!val) {
      searchInput.focus();
      return;
    }
    
    // Default cities supported by the guide format
    const validCities = ['darjeeling', 'gangtok', 'kalimpong', 'dooars', 'mirik', 'lava'];
    const matchedCity = validCities.find(c => val.includes(c)) || validCities[0];
    
    // Open guide in new tab
    window.open(`/guide.html?city=${matchedCity}`, '_blank');
  };

  if (exploreBtn) exploreBtn.addEventListener("click", performSearch);
  
  if (searchInput) {
    searchInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") performSearch();
    });
  }

  // Phone numbers for different destinations
  const destinationPhones = {
    'darjeeling': '918617085139',
    'gangtok': '919800433516',
    'kalimpong': '916296239543'
  };

  // Book local cab jumps straight to WhatsApp
  if (cabBtn) {
    cabBtn.addEventListener("click", () => {
      const val = searchInput ? searchInput.value.trim().toLowerCase() : "";
      const destination = val || "cab";
      
      // Get phone number based on destination, default to first number if not found
      let phoneNumber = destinationPhones[destination] || '918617085139';
      
      console.log("Cab booking:", { searchValue: val, destination, phoneNumber });
      
      const text = val ? `Hi, I want to book a cab to ${val}` : `Hi, I want to book a cab`;
      window.open(`https://wa.me/${phoneNumber}?text=${encodeURIComponent(text)}`, '_blank');
    });
  }
}

// ── Typing effect for hero heading (subtle) ──────────────────────────
function initCursorBlink() {
  const heroH1 = document.querySelector(".hero h1");
  if (!heroH1) return;

  // Add a blinking cursor that fades away
  const cursor = document.createElement("span");
  cursor.textContent = "|";
  cursor.style.cssText = `
    display: inline-block;
    animation: cursorBlink 0.7s step-end infinite;
    color: var(--emerald);
    font-weight: 300;
    margin-left: 2px;
  `;

  // Add keyframes for cursor
  const style = document.createElement("style");
  style.textContent = `
    @keyframes cursorBlink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }
  `;
  document.head.appendChild(style);

  heroH1.appendChild(cursor);

  // Remove cursor after 3s
  setTimeout(() => {
    cursor.style.transition = "opacity 0.5s ease";
    cursor.style.opacity = "0";
    setTimeout(() => cursor.remove(), 500);
  }, 3000);
}

// ── Simple on-page AI-ish planner (rule-based) ───────────────────────
const input = document.getElementById("tripInput");
const btn = document.getElementById("generateBtn");
const quick = document.getElementById("quickGenerate");
const list = document.getElementById("itineraryList");
const title = document.getElementById("itineraryTitle");

function renderPlan(data) {
  const dest = data.destination || "your trip";
  title.textContent = data.title || `Suggested ${dest} plan`;
  list.innerHTML = "";

  // ── Highlights ribbon ──
  if (data.highlights && data.highlights.length) {
    const hlDiv = document.createElement("li");
    hlDiv.style.cssText = "background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(59,130,246,0.1)); border-radius: 12px; padding: 16px; margin-bottom: 16px;";
    const hlTitle = document.createElement("p");
    hlTitle.className = "eyebrow small";
    hlTitle.textContent = "Trip Highlights";
    hlTitle.style.color = "var(--emerald-dark)";
    hlDiv.appendChild(hlTitle);
    const hlList = document.createElement("div");
    hlList.style.cssText = "display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;";
    data.highlights.forEach(h => {
      if (!h) return;
      const chip = document.createElement("span");
      chip.textContent = h;
      chip.style.cssText = "background: var(--emerald); color: white; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 500;";
      hlList.appendChild(chip);
    });
    hlDiv.appendChild(hlList);
    list.appendChild(hlDiv);
  }

  // ── Budget breakdown ──
  if (data.budget_breakdown) {
    const bb = data.budget_breakdown;
    const bbLi = document.createElement("li");
    bbLi.style.cssText = "background: rgba(15,23,42,0.03); border-radius: 12px; padding: 16px; margin-bottom: 16px;";
    const bbTitle = document.createElement("p");
    bbTitle.className = "eyebrow small";
    bbTitle.textContent = `Budget Breakdown (Total: Rs ${data.total_budget || "N/A"})`;
    bbLi.appendChild(bbTitle);
    const bbGrid = document.createElement("div");
    bbGrid.style.cssText = "display:grid; grid-template-columns: repeat(auto-fit, minmax(120px,1fr)); gap:8px; margin-top:10px;";
    for (const [key, val] of Object.entries(bb)) {
      const cell = document.createElement("div");
      cell.style.cssText = "text-align:center; padding:8px; background:white; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.06);";
      cell.innerHTML = `<div style="font-size:18px;font-weight:700;color:var(--emerald-dark);">Rs ${val}</div><div style="font-size:11px;color:#64748b;text-transform:capitalize;">${key}</div>`;
      bbGrid.appendChild(cell);
    }
    bbLi.appendChild(bbGrid);
    list.appendChild(bbLi);
  }

  // ── Itinerary days ──
  const itinerary = data.itinerary || [];
  if (!itinerary.length) {
    list.innerHTML += "<li><p>No itinerary items found.</p></li>";
    return;
  }

  itinerary.forEach((item, index) => {
    const li = document.createElement("li");
    li.style.opacity = "0";
    li.style.transform = "translateY(12px)";

    const pLabel = document.createElement("p");
    pLabel.className = "eyebrow small";

    if (item.section) {
      pLabel.textContent = item.day ? `Day ${item.day}: ${item.section}` : item.section;
    } else {
      pLabel.textContent = item.label || "Activity";
    }
    li.appendChild(pLabel);

    if (item.activities && Array.isArray(item.activities)) {
      const ul = document.createElement("ul");
      ul.style.cssText = "list-style:none; padding:0; margin-top:8px;";

      item.activities.forEach(act => {
        const actLi = document.createElement("li");
        actLi.style.cssText = "margin-bottom:8px; padding: 8px 16px; border-left:3px solid var(--emerald-light); background:rgba(16,185,129,0.03); border-radius: 0 8px 8px 0; line-height:1.5;";

        // Highlight prices in the text
        const formatted = act.replace(/\((\d[\d,]*\s*INR)\)/g, '<strong style="color:var(--emerald-dark);">($1)</strong>')
                             .replace(/\((Free)\)/g, '<strong style="color:#22c55e;">($1)</strong>');
        actLi.innerHTML = formatted;
        ul.appendChild(actLi);
      });
      li.appendChild(ul);
    } else if (item.text) {
      const pText = document.createElement("p");
      pText.textContent = item.text;
      li.appendChild(pText);
    }

    list.appendChild(li);

    setTimeout(() => {
      li.style.transition = "opacity 0.4s ease, transform 0.4s ease";
      li.style.opacity = "1";
      li.style.transform = "translateY(0)";
    }, 100 * index);
  });

  // ── Pro tips ──
  if (data.pro_tips && data.pro_tips.length) {
    const tipLi = document.createElement("li");
    tipLi.style.cssText = "background: linear-gradient(135deg, rgba(251,191,36,0.08), rgba(251,146,60,0.08)); border-radius: 12px; padding: 16px; margin-top: 16px; border-left: 3px solid #f59e0b;";
    tipLi.style.opacity = "0";
    const tipTitle = document.createElement("p");
    tipTitle.className = "eyebrow small";
    tipTitle.textContent = "Pro Tips from NB Local";
    tipTitle.style.color = "#b45309";
    tipLi.appendChild(tipTitle);
    data.pro_tips.forEach(tip => {
      const p = document.createElement("p");
      p.style.cssText = "margin: 6px 0 0 0; font-size: 13px; color: #78350f;";
      p.textContent = `💡 ${tip}`;
      tipLi.appendChild(p);
    });
    list.appendChild(tipLi);
    setTimeout(() => {
      tipLi.style.transition = "opacity 0.5s ease";
      tipLi.style.opacity = "1";
    }, 100 * (itinerary.length + 1));
  }
}

function renderLoadingState() {
  title.textContent = "NB Local AI is crafting your perfect trip...";
  list.innerHTML = `
    <li style="text-align:center; padding: 32px;">
      <div style="display:inline-block; width:40px; height:40px; border:3px solid var(--emerald-light); border-top-color:var(--emerald-dark); border-radius:50%; animation: spin 0.8s linear infinite;"></div>
      <p style="margin-top:12px; color: var(--emerald-dark); font-weight:500;">Analyzing destinations, budgets & preferences...</p>
      <p style="font-size:13px; color:#64748b; margin-top:4px;">This usually takes 5-10 seconds</p>
    </li>
  `;
  // Add spinner keyframe
  if (!document.getElementById("spinnerStyle")) {
    const s = document.createElement("style");
    s.id = "spinnerStyle";
    s.textContent = "@keyframes spin { to { transform: rotate(360deg); } }";
    document.head.appendChild(s);
  }
}

async function generateAIPlan(text) {
  if (!text) return;

  renderLoadingState();

  try {
    const response = await fetch("/api/plan-trip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: text })
    });

    if (!response.ok) throw new Error("Failed to generate plan");

    const data = await response.json();
    renderPlan(data);

  } catch (err) {
    console.error("AI Planner error:", err);
    title.textContent = "Oops, something went wrong";
    list.innerHTML = `<li><p>Could not generate plan. Please check your connection and try again.</p></li>`;
  }
}


if (btn && input) {
  btn.addEventListener("click", () => generateAIPlan(input.value || input.placeholder));
}
if (quick && input) {
  quick.addEventListener("click", () => generateAIPlan(input.value || input.placeholder));
}

// ── Initialize everything ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  autoTagRevealElements();
  initScrollReveal();
  initRippleButtons();
  initHeroParallax();
  initCardTilt();
  initActiveNavHighlight();
  initHeroInteractions();
  initCursorBlink();
  animateCounters();
});
