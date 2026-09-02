"use strict";

/* ============================================================
   CONTROLPLANE DASHBOARD
   ============================================================

   Frontend for:

       ControlPlane.ai
       AI Governance / Observability Dashboard

   Backend:

       http://127.0.0.1:8000/api

   Important:
   - Request IDs come from /observability/events
   - Never generate fake request IDs in the UI
   - Never hide request IDs
   - Dashboard refreshes every 15 seconds
   ============================================================ */


/* ============================================================
   CONFIGURATION
   ============================================================ */

const API_BASE = "/api";

const REFRESH_INTERVAL = 15000;

let refreshTimer = null;

let lastDashboardData = null;
let lastMetricsData = null;
let lastReviewsData = null;
let lastEvents = [];

let lastGeneratedRequestId = null;


/* ============================================================
   DOM HELPERS
   ============================================================ */

function $(id) {
    return document.getElementById(id);
}


function setText(id, value) {
    const element = $(id);

    if (!element) {
        return;
    }

    element.textContent =
        value === undefined ||
        value === null ||
        value === ""
            ? "—"
            : String(value);
}


function setHTML(id, html) {
    const element = $(id);

    if (!element) {
        return;
    }

    element.innerHTML = html;
}


/* ============================================================
   NUMBER HELPERS
   ============================================================ */

function safeNumber(value, fallback = 0) {
    const number = Number(value);

    return Number.isFinite(number)
        ? number
        : fallback;
}


function formatNumber(value, digits = 2) {
    return safeNumber(value)
        .toLocaleString(
            undefined,
            {
                minimumFractionDigits: digits,
                maximumFractionDigits: digits
            }
        );
}


function formatInteger(value) {
    return safeNumber(value)
        .toLocaleString();
}


function formatPercent(value) {
    return `${formatNumber(value, 1)}%`;
}


function formatCurrency(value) {
    return `$${safeNumber(value).toFixed(6)}`;
}


function formatMilliseconds(value) {
    return `${formatNumber(value, 1)} ms`;
}


function normalizeConfidence(value) {
    const number = safeNumber(value);

    if (number <= 1) {
        return number * 100;
    }

    return number;
}


/* ============================================================
   HTML ESCAPING
   ============================================================ */

function escapeHTML(value) {
    return String(
        value === undefined ||
        value === null
            ? ""
            : value
    )
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


/* ============================================================
   API
   ============================================================ */

async function apiFetch(path, options = {}) {

    const url = `${API_BASE}${path}`;

    console.log(
        "[ControlPlane API]",
        options.method || "GET",
        url
    );

    const response = await fetch(
        url,
        {
            cache: "no-store",

            ...options,

            headers: {
                "Accept": "application/json",

                ...(options.body
                    ? {
                        "Content-Type":
                            "application/json"
                    }
                    : {}),

                ...(options.headers || {})
            }
        }
    );


    if (!response.ok) {

        let detail = "";

        try {

            const errorData =
                await response.json();

            if (errorData?.detail) {
                detail =
                    ` - ${errorData.detail}`;
            }

        } catch (_) {
            /* Ignore invalid error body */
        }


        throw new Error(
            `API ${response.status}: ${response.statusText}${detail}`
        );
    }


    return response.json();
}


/* ============================================================
   ERROR HANDLING
   ============================================================ */

function showApiError(message) {

    console.error(
        "ControlPlane dashboard:",
        message
    );


    const status =
        $("system-status");

    if (status) {

        status.textContent =
            "DEGRADED";

        status.classList.add(
            "text-warning"
        );
    }


    const indicator =
        document.querySelector(
            ".live-indicator"
        );

    if (indicator) {
        indicator.classList.add(
            "offline"
        );
    }
}


/* ============================================================
   DYNAMIC DASHBOARD STYLING
   ============================================================

   This allows us to improve the visual appearance without
   replacing index.html or your existing CSS.
   ============================================================ */

function injectDashboardStyles() {

    if ($("controlplane-dashboard-enhancements")) {
        return;
    }


    const style =
        document.createElement("style");

    style.id =
        "controlplane-dashboard-enhancements";


    style.textContent = `

        /* ================================================
           GLOBAL
           ================================================ */

        :root {
            --cp-purple: #6c63ff;
            --cp-purple-light: #8b85ff;
            --cp-blue: #3bb8ff;
            --cp-green: #22c55e;
            --cp-red: #ff5f6d;
            --cp-yellow: #f6b73c;
            --cp-panel: rgba(15, 23, 42, 0.78);
            --cp-border: rgba(148, 163, 184, 0.12);
        }


        body {
            background:
                radial-gradient(
                    circle at 85% 10%,
                    rgba(108, 99, 255, 0.09),
                    transparent 30%
                ),
                radial-gradient(
                    circle at 55% 90%,
                    rgba(59, 184, 255, 0.055),
                    transparent 28%
                ),
                #05080f !important;
        }


        /* ================================================
           CARDS
           ================================================ */

        .metric-card,
        .stat-card,
        .panel,
        .card {

            border:
                1px solid
                rgba(148, 163, 184, 0.11);

            background:
                linear-gradient(
                    145deg,
                    rgba(18, 25, 39, 0.94),
                    rgba(10, 15, 25, 0.94)
                );

            box-shadow:
                0 18px 45px
                rgba(0, 0, 0, 0.18);

            transition:
                transform 180ms ease,
                border-color 180ms ease,
                box-shadow 180ms ease;
        }


        .metric-card:hover,
        .stat-card:hover,
        .panel:hover,
        .card:hover {

            transform:
                translateY(-2px);

            border-color:
                rgba(108, 99, 255, 0.30);

            box-shadow:
                0 22px 55px
                rgba(0, 0, 0, 0.28);
        }


        /* ================================================
           TABLES
           ================================================ */

        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
        }


        table thead th {

            background:
                rgba(15, 23, 42, 0.92);

            color:
                #71809a;

            font-size:
                10px;

            font-weight:
                700;

            letter-spacing:
                0.14em;

            text-transform:
                uppercase;

            padding:
                14px 16px;

            border-bottom:
                1px solid
                rgba(148, 163, 184, 0.10);
        }


        table tbody td {

            padding:
                15px 16px;

            border-bottom:
                1px solid
                rgba(148, 163, 184, 0.07);

            color:
                #d8deea;

            font-size:
                13px;
        }


        table tbody tr {

            transition:
                background 150ms ease;
        }


        table tbody tr:hover {

            background:
                rgba(108, 99, 255, 0.055);
        }


        /* ================================================
           REQUEST ID
           ================================================ */

        .cp-request-id {

            display:
                inline-flex;

            align-items:
                center;

            gap:
                8px;

            max-width:
                100%;

            font-family:
                ui-monospace,
                SFMono-Regular,
                Menlo,
                Monaco,
                Consolas,
                monospace;

            font-size:
                12px;

            color:
                #c7caff;

            background:
                rgba(108, 99, 255, 0.09);

            border:
                1px solid
                rgba(108, 99, 255, 0.20);

            border-radius:
                7px;

            padding:
                5px 8px;

            white-space:
                nowrap;
        }


        .cp-request-id-text {

            overflow:
                hidden;

            text-overflow:
                ellipsis;
        }


        .cp-copy-id {

            border:
                0;

            background:
                transparent;

            color:
                #8290aa;

            cursor:
                pointer;

            padding:
                2px 4px;

            border-radius:
                4px;
        }


        .cp-copy-id:hover {

            color:
                white;

            background:
                rgba(255,255,255,0.08);
        }


        /* ================================================
           DECISION BADGES
           ================================================ */

        .cp-decision {

            display:
                inline-flex;

            align-items:
                center;

            gap:
                6px;

            padding:
                5px 9px;

            border-radius:
                999px;

            font-size:
                10px;

            font-weight:
                800;

            letter-spacing:
                0.08em;
        }


        .cp-decision::before {

            content:
                "";

            width:
                6px;

            height:
                6px;

            border-radius:
                50%;

            background:
                currentColor;
        }


        .cp-allow {

            color:
                #4ade80;

            background:
                rgba(34,197,94,0.10);

            border:
                1px solid
                rgba(34,197,94,0.20);
        }


        .cp-review {

            color:
                #fbbf24;

            background:
                rgba(245,158,11,0.10);

            border:
                1px solid
                rgba(245,158,11,0.20);
        }


        .cp-block {

            color:
                #fb7185;

            background:
                rgba(244,63,94,0.10);

            border:
                1px solid
                rgba(244,63,94,0.20);
        }


        .cp-edit {

            color:
                #38bdf8;

            background:
                rgba(14,165,233,0.10);

            border:
                1px solid
                rgba(14,165,233,0.20);
        }


        .cp-unknown {

            color:
                #94a3b8;

            background:
                rgba(148,163,184,0.08);

            border:
                1px solid
                rgba(148,163,184,0.15);
        }


        /* ================================================
           RECENT ACTIVITY
           ================================================ */

        .recent-event {

            position:
                relative;

            display:
                grid;

            grid-template-columns:
                minmax(0, 1.4fr)
                minmax(160px, 1fr)
                minmax(100px, auto)
                minmax(90px, auto);

            align-items:
                center;

            gap:
                18px;

            padding:
                15px 18px;

            border-bottom:
                1px solid
                rgba(148,163,184,0.07);

            background:
                rgba(255,255,255,0.005);

            transition:
                background 150ms ease;
        }


        .recent-event:hover {

            background:
                rgba(108,99,255,0.045);
        }


        .recent-event-main {

            min-width:
                0;
        }


        .recent-event-title {

            display:
                flex;

            align-items:
                center;

            gap:
                10px;

            margin-bottom:
                6px;

            color:
                #eef2ff;

            font-size:
                13px;

            font-weight:
                700;
        }


        .recent-event-meta {

            color:
                #68758c;

            font-size:
                11px;
        }


        .recent-event-stat {

            color:
                #aab4c7;

            font-size:
                12px;
        }


        .recent-event-stat strong {

            display:
                block;

            color:
                #eef2ff;

            font-size:
                13px;

            margin-bottom:
                2px;
        }


        /* ================================================
           LATEST REQUEST
           ================================================ */

        .cp-latest-request {

            display:
                flex;

            align-items:
                center;

            justify-content:
                space-between;

            gap:
                16px;

            margin:
                0 0 22px 0;

            padding:
                12px 14px;

            border:
                1px solid
                rgba(108,99,255,0.18);

            border-radius:
                10px;

            background:
                linear-gradient(
                    90deg,
                    rgba(108,99,255,0.08),
                    rgba(59,184,255,0.035)
                );
        }


        .cp-latest-label {

            color:
                #73809a;

            font-size:
                10px;

            text-transform:
                uppercase;

            letter-spacing:
                0.13em;

            font-weight:
                700;
        }


        /* ================================================
           TOP BAR STATUS
           ================================================ */

        .live-indicator {

            display:
                inline-flex;

            align-items:
                center;

            gap:
                7px;

            transition:
                opacity 150ms ease;
        }


        .live-indicator > span {

            width:
                7px;

            height:
                7px;

            border-radius:
                50%;

            background:
                #22c55e;

            box-shadow:
                0 0 12px
                rgba(34,197,94,0.75);
        }


        .live-indicator.offline > span {

            background:
                #ef4444;

            box-shadow:
                0 0 12px
                rgba(239,68,68,0.65);
        }


        /* ================================================
           REFRESH BUTTON
           ================================================ */

        #refresh-button,
        #refresh-overview {

            transition:
                transform 150ms ease,
                opacity 150ms ease;
        }


        #refresh-button.loading {

            opacity:
                0.55;

            cursor:
                wait;
        }


        #refresh-button.loading {

            animation:
                cp-spin 0.9s linear infinite;
        }


        @keyframes cp-spin {

            from {
                transform:
                    rotate(0deg);
            }

            to {
                transform:
                    rotate(360deg);
            }
        }


        /* ================================================
           EMPTY STATE
           ================================================ */

        .empty-state {

            padding:
                35px 20px !important;

            text-align:
                center;

            color:
                #59667d !important;

            font-size:
                13px;
        }


        /* ================================================
           HOW IT WORKS INTERACTION
           ================================================ */

        .cp-architecture-focus {

            transform:
                translateY(-2px);

            box-shadow:
                0 12px 35px
                rgba(108,99,255,0.10);
        }


        /* ================================================
           RESPONSIVE
           ================================================ */

        @media (max-width: 1100px) {

            .recent-event {

                grid-template-columns:
                    1fr 1fr;
            }
        }


        @media (max-width: 700px) {

            .recent-event {

                grid-template-columns:
                    1fr;
            }

            .cp-latest-request {

                align-items:
                    flex-start;

                flex-direction:
                    column;
            }

            .cp-request-id {

                max-width:
                    100%;
            }
        }

    `;


    document.head.appendChild(style);
}


/* ============================================================
   NAVIGATION
   ============================================================ */

function initializeNavigation() {

    const navItems =
        document.querySelectorAll(
            "[data-page]"
        );

    const pages =
        document.querySelectorAll(
            ".page"
        );

    const pageTitle =
        $("page-title");


    async function switchPage(target) {

        if (!target) {
            return;
        }


        pages.forEach(
            page => {

                page.classList.toggle(
                    "active",
                    page.id ===
                        `page-${target}`
                );
            }
        );


        navItems.forEach(
            item => {

                item.classList.toggle(
                    "active",
                    item.dataset.page ===
                        target
                );
            }
        );


        const activePage =
            document.querySelector(
                `#page-${target}`
            );


        if (
            activePage &&
            pageTitle
        ) {

            const heading =
                activePage.querySelector(
                    "h1"
                );

            pageTitle.textContent =
                heading
                    ? heading.textContent
                    : target;
        }


        if (target === "reviews") {
            await loadReviews();
        }


        if (target === "metrics") {
            await loadMetrics();
        }


        if (target === "factuality") {
            await loadFactuality();
        }


        if (
            target === "audit" ||
            target === "requests"
        ) {

            await loadAuditView();
        }
    }


    navItems.forEach(
        item => {

            item.addEventListener(
                "click",
                event => {

                    event.preventDefault();

                    switchPage(
                        item.dataset.page
                    );
                }
            );
        }
    );


    const pageTargetButtons =
        document.querySelectorAll(
            "[data-page-target]"
        );


    pageTargetButtons.forEach(
        button => {

            button.addEventListener(
                "click",
                event => {

                    event.preventDefault();

                    switchPage(
                        button.dataset.pageTarget
                    );
                }
            );
        }
    );
}


/* ============================================================
   HOW CONTROLPLANE WORKS
   ============================================================

   The current dashboard already contains a dedicated
   "How It Works" page in index.html.

   This initializer is intentionally additive: it does not
   replace the existing architecture markup, navigation,
   generate flow, governance logic, factuality logic, review
   workflow, metrics, audit log, or auto-refresh behavior.

   It simply makes the architecture page robust when the
   dashboard is loaded from a slightly older HTML file and
   adds lightweight interaction to the existing flow cards.
   ============================================================ */

function initializeHowItWorks() {

    const page =
        $("page-how-it-works");


    if (!page) {

        console.log(
            "[ControlPlane] How It Works page not present in current HTML."
        );

        return;
    }


    if (
        page.dataset.cpHowItWorksInitialized ===
        "true"
    ) {

        return;
    }


    page.dataset.cpHowItWorksInitialized =
        "true";


    /*
     * Add a small visual state to the architecture flow
     * without changing any existing application behavior.
     * Cards remain normal buttons/content and all existing
     * data-page-target navigation continues to be handled by
     * initializeNavigation().
     */

    const interactiveCards =
        page.querySelectorAll(
            ".flow-step, .agent-card, .decision-gate, .outcome-card"
        );


    interactiveCards.forEach(
        card => {

            card.addEventListener(
                "mouseenter",
                () => {
                    card.classList.add(
                        "cp-architecture-focus"
                    );
                }
            );


            card.addEventListener(
                "mouseleave",
                () => {
                    card.classList.remove(
                        "cp-architecture-focus"
                    );
                }
            );
        }
    );


    /*
     * Keep the page title synchronized if the page is opened
     * directly through an architecture navigation card.
     */

    const pageTitle =
        $("page-title");


    if (
        pageTitle &&
        !pageTitle.textContent.trim()
    ) {

        pageTitle.textContent =
            "How It Works";
    }


    console.log(
        "[ControlPlane] How It Works architecture initialized."
    );
}


/* ============================================================
   DASHBOARD API
   ============================================================ */

async function loadDashboard() {

    try {

        const data =
            await apiFetch(
                "/metrics/dashboard"
            );

        lastDashboardData =
            data;

        renderDashboard(
            data
        );

        return data;

    } catch (error) {

        showApiError(
            error.message
        );

        return null;
    }
}


/* ============================================================
   FULL METRICS
   ============================================================ */

async function loadMetrics() {

    try {

        const data =
            await apiFetch(
                "/metrics"
            );

        lastMetricsData =
            data;

        renderMetrics(
            data
        );

        return data;

    } catch (error) {

        showApiError(
            error.message
        );

        return null;
    }
}


/* ============================================================
   REVIEWS
   ============================================================ */

async function loadReviews() {

    try {

        const data =
            await apiFetch(
                "/reviews"
            );

        lastReviewsData =
            data;

        renderReviews(
            data
        );

        return data;

    } catch (error) {

        console.error(
            "Reviews failed:",
            error
        );

        renderReviews({
            reviews: []
        });

        return null;
    }
}


/* ============================================================
   HEALTH
   ============================================================ */

async function checkHealth() {

    try {

        const health =
            await apiFetch(
                "/health"
            );


        const status =
            health.status === "healthy"
                ? "ACTIVE"
                : "DEGRADED";


        setText(
            "system-status",
            status
        );


        const indicator =
            document.querySelector(
                ".live-indicator"
            );


        if (indicator) {

            indicator.classList.toggle(
                "offline",
                status !== "ACTIVE"
            );
        }


        return true;

    } catch (error) {

        console.error(
            "Health check failed:",
            error
        );


        setText(
            "system-status",
            "OFFLINE"
        );


        const indicator =
            document.querySelector(
                ".live-indicator"
            );


        if (indicator) {

            indicator.classList.add(
                "offline"
            );
        }


        return false;
    }
}


/* ============================================================
   EVENTS
   ============================================================

   IMPORTANT FIX:

   We use:

       /observability/events

   because the backend explicitly returns:

       request_id
       decision
       risk_score
       latency_ms
       estimated_cost
       review_id
       review_status
       metadata

   This is the reliable source for Recent Activity.
   ============================================================ */

async function loadEvents() {

    try {

        const data =
            await apiFetch(
                "/observability/events"
            );

        const events =
            extractEvents(data);

        lastEvents =
            events;

        return {
            events
        };

    } catch (error) {

        console.error(
            "Observability events failed:",
            error
        );


        /*
         * Fallback to /metrics/events.
         */
        try {

            const fallback =
                await apiFetch(
                    "/metrics/events"
                );

            const events =
                extractEvents(
                    fallback
                );

            lastEvents =
                events;

            return {
                events
            };

        } catch (fallbackError) {

            console.error(
                "Metrics events fallback failed:",
                fallbackError
            );

            return {
                events: []
            };
        }
    }
}


/* ============================================================
   EVENT EXTRACTION
   ============================================================ */

function extractEvents(data) {

    if (!data) {
        return [];
    }


    if (Array.isArray(data)) {
        return data;
    }


    if (
        Array.isArray(
            data.events
        )
    ) {
        return data.events;
    }


    if (
        Array.isArray(
            data.audit
        )
    ) {
        return data.audit;
    }


    if (
        Array.isArray(
            data.recent_events
        )
    ) {
        return data.recent_events;
    }


    if (
        Array.isArray(
            data.recent_requests
        )
    ) {
        return data.recent_requests;
    }


    if (
        Array.isArray(
            data.requests
        )
    ) {
        return data.requests;
    }


    return [];
}


/* ============================================================
   NORMALIZE EVENT
   ============================================================ */

function normalizeEvent(event) {

    if (!event || typeof event !== "object") {
        return {
            request_id: "—",
            decision: "UNKNOWN",
            risk_score: 0,
            confidence: null,
            latency_ms: 0,
            estimated_cost: 0,
            timestamp: null,
            prompt: "",
            review_id: null,
            review_status: null
        };
    }


    const metadata =
        event.metadata || {};


    /*
     * Request ID priority:
     *
     * 1. event.request_id
     * 2. event.metadata.request_id
     * 3. event.id
     *
     * We NEVER create a fake ID.
     */

    const requestId =
        event.request_id ||
        metadata.request_id ||
        event.id ||
        "—";


    const decision =
        String(
            event.decision ||
            event.action ||
            event.policy_decision ||
            "UNKNOWN"
        ).toUpperCase();


    return {

        ...event,

        request_id:
            requestId,

        decision,

        risk_score:
            event.risk_score ??
            event.risk ??
            0,

        confidence:
            event.confidence ??
            null,

        latency_ms:
            event.latency_ms ??
            event.latency ??
            0,

        estimated_cost:
            event.estimated_cost ??
            event.cost ??
            0,

        timestamp:
            event.timestamp ||
            event.time ||
            event.created_at ||
            null,

        prompt:
            event.prompt ||
            metadata.prompt ||
            "",

        review_id:
            event.review_id ||
            null,

        review_status:
            event.review_status ||
            null
    };
}


/* ============================================================
   DECISION CLASS
   ============================================================ */

function decisionClass(decision) {

    switch (
        String(decision)
            .toUpperCase()
    ) {

        case "ALLOW":
            return "cp-allow";

        case "REVIEW":
            return "cp-review";

        case "BLOCK":
            return "cp-block";

        case "EDIT":
            return "cp-edit";

        default:
            return "cp-unknown";
    }
}


/* ============================================================
   DECISION BADGE
   ============================================================ */

function decisionBadge(decision) {

    const normalized =
        String(
            decision || "UNKNOWN"
        ).toUpperCase();


    return `
        <span class="
            cp-decision
            ${decisionClass(normalized)}
        ">
            ${escapeHTML(normalized)}
        </span>
    `;
}


/* ============================================================
   REQUEST ID HTML
   ============================================================ */

function requestIdHTML(requestId) {

    const safeId =
        escapeHTML(
            requestId || "—"
        );


    if (
        !requestId ||
        requestId === "—"
    ) {

        return `
            <span class="cp-request-id">
                <span class="cp-request-id-text">
                    —
                </span>
            </span>
        `;
    }


    return `
        <span
            class="cp-request-id"
            title="${safeId}"
        >

            <span
                class="cp-request-id-text"
            >
                ${safeId}
            </span>

            <button
                type="button"
                class="cp-copy-id"
                data-request-id="${safeId}"
                title="Copy request ID"
            >
                ⧉
            </button>

        </span>
    `;
}


/* ============================================================
   COPY REQUEST ID
   ============================================================ */

function initializeRequestIdCopy() {

    document.addEventListener(
        "click",
        async event => {

            const button =
                event.target.closest(
                    ".cp-copy-id"
                );


            if (!button) {
                return;
            }


            event.preventDefault();


            const requestId =
                button.dataset.requestId;


            if (!requestId) {
                return;
            }


            try {

                await navigator.clipboard.writeText(
                    requestId
                );


                const oldText =
                    button.textContent;

                button.textContent =
                    "✓";


                setTimeout(
                    () => {
                        button.textContent =
                            oldText;
                    },
                    1000
                );

            } catch (error) {

                console.error(
                    "Could not copy request ID:",
                    error
                );
            }
        }
    );
}


/* ============================================================
   DASHBOARD RENDERER
   ============================================================ */

function renderDashboard(data) {

    if (!data) {
        return;
    }


    const system =
        data.system || {};

    const governance =
        data.governance || {};

    const risk =
        data.risk || {};

    const performance =
        data.performance || {};

    const cost =
        data.cost || {};

    const reviews =
        data.human_review || {};

    const decisions =
        data.decisions || {};


    /* ========================================================
       TOP METRICS
       ======================================================== */

    setText(
        "metric-requests",
        formatInteger(
            system.requests || 0
        )
    );


    setText(
        "system-status",
        system.status || "READY"
    );


    setText(
        "metric-allow-rate",
        formatPercent(
            governance.allow_rate || 0
        )
    );


    setText(
        "metric-reviews",
        formatInteger(
            reviews.pending ??
            reviews.pending_reviews ??
            reviews.total_pending ??
            0
        )
    );


    setText(
        "metric-risk",
        formatNumber(
            risk.average || 0,
            3
        )
    );


    setText(
        "metric-latency",
        formatMilliseconds(
            performance.average_ms || 0
        )
    );


    setText(
        "metric-model-latency",
        formatMilliseconds(
            performance.model_average_ms ||
            performance.model_latency_ms ||
            performance.model_ms ||
            0
        )
    );


    setText(
        "metric-cost",
        formatCurrency(
            cost.total ||
            cost.estimated_total ||
            cost.average ||
            0
        )
    );


    /* ========================================================
       GOVERNANCE SUMMARY
       ======================================================== */

    setText(
        "governance-request",
        governance.request_decision ||
        governance.request ||
        "—"
    );


    setText(
        "governance-response",
        governance.response_decision ||
        governance.response ||
        "—"
    );


    const confidence =
        governance.confidence;


    if (
        confidence !== undefined &&
        confidence !== null
    ) {

        setText(
            "governance-confidence",
            formatPercent(
                normalizeConfidence(
                    confidence
                )
            )
        );

    } else {

        setText(
            "governance-confidence",
            "—"
        );
    }


    /* ========================================================
       DECISIONS
       ======================================================== */

    renderDecisionDistribution(
        decisions
    );


    /* ========================================================
       RISK
       ======================================================== */

    renderRiskValues(
        risk
    );


    /* ========================================================
       FACTUALITY
       ======================================================== */

    loadFactuality();
}


/* ============================================================
   DECISION DISTRIBUTION
   ============================================================ */

function renderDecisionDistribution(
    decisions
) {

    decisions =
        decisions || {};


    const allow =
        safeNumber(
            decisions.ALLOW ??
            decisions.allow ??
            0
        );


    const review =
        safeNumber(
            decisions.REVIEW ??
            decisions.review ??
            0
        );


    const block =
        safeNumber(
            decisions.BLOCK ??
            decisions.block ??
            0
        );


    const edit =
        safeNumber(
            decisions.EDIT ??
            decisions.edit ??
            0
        );


    const unknown =
        safeNumber(
            decisions.UNKNOWN ??
            decisions.unknown ??
            0
        );


    setText(
        "allow-count",
        formatInteger(allow)
    );


    setText(
        "review-count",
        formatInteger(review)
    );


    setText(
        "block-count",
        formatInteger(block)
    );


    setText(
        "edit-count",
        formatInteger(edit)
    );


    setText(
        "decision-allow",
        formatInteger(allow)
    );


    setText(
        "decision-review",
        formatInteger(review)
    );


    setText(
        "decision-block",
        formatInteger(block)
    );


    setText(
        "decision-edit",
        formatInteger(edit)
    );


    setText(
        "decision-unknown",
        formatInteger(unknown)
    );


    const total =
        allow +
        review +
        block +
        edit +
        unknown;


    const donut =
        document.querySelector(
            "#governance-donut"
        );


    const chart =
        document.querySelector(
            ".governance-donut"
        );


    if (
        !donut &&
        !chart
    ) {
        return;
    }


    const target =
        donut || chart;


    if (total <= 0) {

        target.style.background =
            "conic-gradient(#263148 0% 100%)";

        return;
    }


    const allowPercent =
        (allow / total) * 100;


    const reviewPercent =
        (review / total) * 100;


    const blockPercent =
        (block / total) * 100;


    const editPercent =
        (edit / total) * 100;


    const reviewEnd =
        allowPercent +
        reviewPercent;


    const blockEnd =
        reviewEnd +
        blockPercent;


    const editEnd =
        blockEnd +
        editPercent;


    target.style.background =
        `conic-gradient(
            #6c63ff 0% ${allowPercent}%,
            #3bb8ff ${allowPercent}% ${reviewEnd}%,
            #ff5f6d ${reviewEnd}% ${blockEnd}%,
            #f6b73c ${blockEnd}% ${editEnd}%,
            #475569 ${editEnd}% 100%
        )`;
}


/* ============================================================
   RISK VALUES
   ============================================================ */

function renderRiskValues(risk) {

    risk = risk || {};

    const values = {

        security:
            risk.security ??
            risk.security_risk ??
            risk.security_score,

        privacy:
            risk.privacy ??
            risk.privacy_risk ??
            risk.privacy_score,

        bias:
            risk.bias ??
            risk.bias_risk ??
            risk.bias_score,

        factuality:
            risk.factuality ??
            risk.factuality_risk ??
            risk.factuality_score,

        cost:
            risk.cost ??
            risk.cost_risk ??
            risk.cost_score
    };


    Object.entries(values).forEach(
        ([name, value]) => {

            const id =
                `${name}-risk`;

            const element =
                $(id);

            if (!element) {
                return;
            }


            if (
                value === undefined ||
                value === null ||
                value === ""
            ) {

                element.textContent =
                    "—";

                return;
            }


            const numeric =
                Math.max(
                    0,
                    Math.min(
                        1,
                        safeNumber(value)
                    )
                );


            element.textContent =
                formatNumber(
                    numeric,
                    3
                );


            const row =
                element.closest(
                    ".risk-row"
                );


            if (!row) {
                return;
            }


            row.style.setProperty(
                "--risk-value",
                `${numeric * 100}%`
            );


            row.classList.remove(
                "risk-low",
                "risk-medium",
                "risk-high"
            );


            if (numeric >= 0.70) {

                row.classList.add(
                    "risk-high"
                );

            } else if (numeric >= 0.40) {

                row.classList.add(
                    "risk-medium"
                );

            } else {

                row.classList.add(
                    "risk-low"
                );
            }
        }
    );
}


/* ============================================================
   METRICS PAGE
   ============================================================ */

function renderMetrics(data) {

    if (!data) {
        return;
    }


    const snapshot =
        data.snapshot ||
        data;


    const latency =
        snapshot.latency ||
        data.latency ||
        {};


    const modelLatency =
        snapshot.model_latency ||
        data.model_latency ||
        {};


    const performance =
        snapshot.performance ||
        data.performance ||
        {};


    const cost =
        snapshot.cost ||
        data.cost ||
        {};


    const risk =
        snapshot.risk ||
        data.risk ||
        {};


    setText(
        "metric-latency",
        formatMilliseconds(
            latency.average_ms ??
            latency.average ??
            performance.average_ms ??
            0
        )
    );


    setText(
        "metric-model-latency",
        formatMilliseconds(
            modelLatency.average_ms ??
            performance.model_average_ms ??
            performance.model_latency_ms ??
            0
        )
    );


    setText(
        "metric-cost",
        formatCurrency(
            cost.total ??
            cost.average ??
            0
        )
    );


    setText(
        "metric-risk",
        formatNumber(
            risk.average ?? 0,
            3
        )
    );
}


/* ============================================================
   REVIEWS
   ============================================================ */

function renderReviews(data) {

    const reviews =
        Array.isArray(data)
            ? data
            : Array.isArray(data?.reviews)
                ? data.reviews
                : [];


    /*
     * The actual dashboard/index.html uses:
     *
     *     <div id="reviews-container"
     *          class="review-list">
     *
     * The previous implementation incorrectly looked
     * for "reviews-table", which does not exist.
     */

    const container =
        $("reviews-container");


    if (!container) {

        console.warn(
            "[ControlPlane] reviews-container not found."
        );

        return;
    }


    /*
     * No pending reviews.
     */

    if (!reviews.length) {

        container.innerHTML = `
            <div class="empty-state">
                No pending reviews.
            </div>
        `;

        return;
    }


    /*
     * Render every pending review.
     */

    container.innerHTML =
        reviews
            .map(
                review => {

                    const reviewId =
                        escapeHTML(
                            review.review_id ||
                            review.id ||
                            ""
                        );


                    const requestId =
                        escapeHTML(
                            review.request_id ||
                            review.metadata?.request_id ||
                            "—"
                        );


                    const prompt =
                        escapeHTML(
                            review.prompt ||
                            "No prompt available."
                        );


                    const modelResponse =
                        escapeHTML(
                            review.model_response ||
                            review.response ||
                            "No model response available."
                        );


                    const decision =
                        String(
                            review.decision ||
                            review.action ||
                            "REVIEW"
                        ).toUpperCase();


                    const riskScore =
                        safeNumber(
                            review.risk_score,
                            0
                        );


                    const reason =
                        escapeHTML(
                            review.reason ||
                            review.comment ||
                            "Governance pipeline requires human review."
                        );


                    const createdAt =
                        escapeHTML(
                            review.created_at ||
                            review.timestamp ||
                            "—"
                        );


                    return `
                        <div
                            class="review-item"
                            data-review-id="${reviewId}"
                        >

                            <div
                                style="
                                    display:flex;
                                    justify-content:space-between;
                                    align-items:flex-start;
                                    gap:16px;
                                "
                            >

                                <div
                                    style="
                                        min-width:0;
                                        flex:1;
                                    "
                                >

                                    <h3>
                                        HUMAN REVIEW
                                    </h3>

                                    <p
                                        style="
                                            margin-top:8px;
                                            color:#dce2ec;
                                            font-size:13px;
                                            line-height:1.6;
                                        "
                                    >
                                        ${prompt}
                                    </p>

                                </div>


                                <div>
                                                 decision
                                    )}
                                </div>

                            </div>


                            <div
                                style="
                                    margin-top:14px;
                                    padding:12px;
                                    border-radius:8px;
                                    background:rgba(255,255,255,.025);
                                    border:1px solid rgba(255,255,255,.05);
                                "
                            >

                                <div
                                    style="
                                        color:#71809a;
                                        font-size:9px;
                                        font-weight:700;
                                        letter-spacing:.12em;
                                        text-transform:uppercase;
                                    "
                                >
                                    MODEL RESPONSE
                                </div>


                                <div
                                    style="
                                        margin-top:7px;
                                        color:#cfd6e4;
                                        font-size:12px;
                                        line-height:1.6;
                                        white-space:pre-wrap;
                                    "
                                >
                                    ${modelResponse}
                                </div>

                            </div>


                            <div
                                style="
                                    display:grid;
                                    grid-template-columns:
                                        minmax(0,1fr)
                                        minmax(0,1fr);
                                    gap:10px;
                                    margin-top:12px;
                                "
                            >

                                <div
                                    style="
                                        padding:10px;
                                        border-radius:8px;
                                        background:rgba(255,255,255,.018);
                                    "
                                >

                                    <div
                                        style="
                                            color:#71809a;
                                            font-size:9px;
                                            font-weight:700;
                                            letter-spacing:.1em;
                                        "
                                    >
                                        RISK SCORE
                                    </div>

                                    <div
                                        style="
                                            margin-top:5px;
                                            color:#f6b73c;
                                            font-size:14px;
                                            font-weight:700;
                                        "
                                    >
                                        ${riskScore.toFixed(3)}
                                    </div>

                                </div>


                                <div
                                    style="
                                        padding:10px;
                                        border-radius:8px;
                                        background:rgba(255,255,255,.018);
                                    "
                                >

                                    <div
                                        style="
                                            color:#71809a;
                                            font-size:9px;
                                            font-weight:700;
                                            letter-spacing:.1em;
                                        "
                                    >
                                        STATUS
                                    </div>

                                    <div
                                        style="
                                            margin-top:5px;
                                            color:#f6b73c;
                                            font-size:14px;
                                            font-weight:700;
                                        "
                                    >
                                        ${escapeHTML(
                                            review.status ||
                                            "PENDING"
                                        )}
                                    </div>

                                </div>

                            </div>


                            <div
                                style="
                                    margin-top:12px;
                                    padding:10px 12px;
                                    border-left:
                                        2px solid
                                        rgba(246,183,60,.55);
                                    background:
                                        rgba(246,183,60,.035);
                                "
                            >

                                <div
                                    style="
                                        color:#71809a;
                                        font-size:9px;
                                        font-weight:700;
                                        letter-spacing:.1em;
                                        text-transform:uppercase;
                                    "
                                >
                                    REASON
                                </div>

                                <div
                                    style="
                                        margin-top:5px;
                                        color:#aeb8c9;
                                        font-size:11px;
                                        line-height:1.5;
                                    "
                                >
                                    ${reason}
                                </div>

                            </div>


                            <div
                                style="
                                    margin-top:12px;
                                    display:flex;
                                    align-items:center;
                                    justify-content:space-between;
                                    gap:12px;
                                    flex-wrap:wrap;
                                "
                            >

                                <div
                                    class="cp-request-id"
                                >
                                    ${requestIdHTML(
                                        requestId
                                    )}
                                </div>


                                <div
                                    style="
                                        color:#59657a;
                                        font-size:10px;
                                    "
                                >
                                    ${createdAt}
                                </div>

                            </div>


                            <div
                                style="
                                    margin-top:14px;
                                    padding-top:12px;
                                    border-top:
                                        1px solid
                                        rgba(255,255,255,.055);
                                    display:flex;
                                    gap:8px;
                                    flex-wrap:wrap;
                                "
                            >

                                <button
                                    type="button"
                                    class="cp-review-action"
                                    data-review-id="${reviewId}"
                                    data-final-decision="ALLOW"
                                    style="
                                        border:1px solid
                                            rgba(34,197,94,.30);
                                        background:
                                            rgba(34,197,94,.08);
                                        color:#4ade80;
                                        padding:8px 14px;
                                        border-radius:7px;
                                        cursor:pointer;
                                        font-size:11px;
                                        font-weight:700;
                                    "
                                >
                                    APPROVE
                                </button>


                                <button
                                    type="button"
                                    class="cp-review-action"
                                    data-review-id="${reviewId}"
                                    data-final-decision="REJECT"
                                    style="
                                        border:1px solid
                                            rgba(255,95,109,.30);
                                        background:
                                            rgba(255,95,109,.08);
                                        color:#ff7b87;
                                        padding:8px 14px;
                                        border-radius:7px;
                                        cursor:pointer;
                                        font-size:11px;
                                        font-weight:700;
                                    "
                                >
                                    REJECT
                                </button>

                            </div>

                        </div>
                    `;
                }
            )
            .join("");


    /*
     * Attach human-review resolution handlers.
     */

    container
        .querySelectorAll(
            ".cp-review-action"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    async () => {

                        const reviewId =
                            button.dataset.reviewId;


                        const finalDecision =
                            button.dataset.finalDecision;


                        if (!reviewId) {

                            console.error(
                                "[ControlPlane] Missing review ID."
                            );

                            return;
                        }


                        /*
                         * Disable both actions while
                         * the resolution is submitted.
                         */

                        const reviewItem =
                            button.closest(
                                ".review-item"
                            );


                        const actionButtons =
                            reviewItem
                                ? reviewItem.querySelectorAll(
                                    ".cp-review-action"
                                )
                                : [];


                        actionButtons.forEach(
                            actionButton => {

                                actionButton.disabled =
                                    true;

                                actionButton.style.opacity =
                                    "0.55";

                                actionButton.style.cursor =
                                    "not-allowed";
                            }
                        );


                        /*
                         * Reviewer identity.
                         *
                         * This is intentionally a simple
                         * dashboard identity for the prototype.
                         */

                        const reviewer =
                            "ControlPlane Admin";


                        try {

                            await apiFetch(
                                `/reviews/${encodeURIComponent(
                                    reviewId
                                )}/resolve`,
                                {
                                    method: "POST",

                                    body: JSON.stringify(
                                        {
                                            final_decision:
                                                finalDecision,

                                            reviewer:
                                                reviewer,

                                            comment:
                                                `Human review resolved as ${finalDecision}.`
                                        }
                                    )
                                }
                            );


                            /*
                             * Reload reviews immediately.
                             */

                            await loadReviews();


                            /*
                             * Refresh metrics so the
                             * dashboard reflects the
                             * resolution.
                             */

                            await loadMetrics();


                            /*
                             * Refresh events/audit data.
                             */

                            await loadEvents();


                            console.log(
                                "[ControlPlane] Review resolved:",
                                reviewId,
                                finalDecision
                            );


                        } catch (error) {

                            console.error(
                                "[ControlPlane] Review resolution failed:",
                                error
                            );


                            showApiError(
                                error.message
                            );


                            /*
                             * Re-enable buttons if
                             * resolution failed.
                             */

                            actionButtons.forEach(
                                actionButton => {

                                    actionButton.disabled =
                                        false;

                                    actionButton.style.opacity =
                                        "1";

                                    actionButton.style.cursor =
                                        "pointer";
                                }
                            );
                        }
                    }
                );
            }
        );
}


/* ============================================================
   FACTUALITY
   ============================================================ */

async function loadFactuality() {

    try {

        /*
         * Always fetch the authoritative metrics snapshot.
         *
         * /metrics already returns:
         * factuality.requests_checked
         * factuality.claims
         * factuality.verified
         * factuality.failed
         * factuality.unknown
         */

        const data =
            await apiFetch(
                "/metrics"
            );


        /*
         * Keep the global cache synchronized.
         * This does not change any existing dashboard logic.
         */

        lastMetricsData =
            data;


        const factuality =
            data?.factuality ||
            {};


        /*
         * No factuality data yet.
         *
         * Use 0 because the backend has a valid factuality
         * snapshot even when no claims have been extracted.
         */

        setText(
            "factuality-verified",
            formatInteger(
                factuality.verified ??
                factuality.verified_count ??
                0
            )
        );


        setText(
            "factuality-failed",
            formatInteger(
                factuality.failed ??
                factuality.failed_count ??
                0
            )
        );


        setText(
            "factuality-unknown",
            formatInteger(
                factuality.unknown ??
                factuality.unknown_count ??
                0
            )
        );


        setText(
            "factuality-claims",
            formatInteger(
                factuality.claims ??
                factuality.total_claims ??
                0
            )
        );


    } catch (error) {

        console.error(
            "Factuality metrics failed:",
            error
        );


        /*
         * Do not overwrite valid existing values
         * if the refresh request temporarily fails.
         */

        if (!lastMetricsData?.factuality) {

            setText(
                "factuality-verified",
                "—"
            );

            setText(
                "factuality-failed",
                "—"
            );

            setText(
                "factuality-unknown",
                "—"
            );

            setText(
                "factuality-claims",
                "—"
            );
        }
    }
}


/* ============================================================
   REQUESTS TABLE
   ============================================================ */

function renderRequests(data) {

    const rows =
        Array.isArray(data)
            ? data
            : Array.isArray(
                data?.requests
            )
                ? data.requests
                : Array.isArray(
                    data?.events
                )
                    ? data.events
                    : Array.isArray(
                        data?.recent_requests
                    )
                        ? data.recent_requests
                        : [];


    const table =
        $("requests-table");


    if (!table) {
        return;
    }


    if (!rows.length) {

        table.innerHTML = `
            <tr>
                <td
                    colspan="5"
                    class="empty-state"
                >
                    No requests available.
                </td>
            </tr>
        `;

        return;
    }


    const normalizedRows =
        rows
            .map(normalizeEvent)
            .slice()
            .reverse();


    table.innerHTML =
        normalizedRows
            .map(
                request => {

                    const requestId =
                        request.request_id;


                    const confidence =
                        request.confidence;


                    return `
                        <tr>

                            <td>
                                ${requestIdHTML(
                                    requestId
                                )}
                            </td>

                            <td>
                                ${decisionBadge(
                                    request.decision
                                )}
                            </td>

                            <td>
                                ${formatNumber(
                                    request.risk_score,
                                    3
                                )}
                            </td>

                            <td>
                                ${
                                    confidence === null
                                        ? "—"
                                        : formatPercent(
                                            normalizeConfidence(
                                                confidence
                                            )
                                        )
                                }
                            </td>

                            <td>
                                ${formatMilliseconds(
                                    request.latency_ms
                                )}
                            </td>

                        </tr>
                    `;
                }
            )
            .join("");
}


/* ============================================================
   AUDIT TABLE
   ============================================================ */

function renderAuditTable(events) {

    const table =
        $("audit-table");


    if (!table) {
        return;
    }


    if (!events.length) {

        table.innerHTML = `
            <tr>
                <td
                    colspan="5"
                    class="empty-state"
                >
                    No audit events available.
                </td>
            </tr>
        `;

        return;
    }


    table.innerHTML =
        events
            .map(normalizeEvent)
            .slice()
            .reverse()
            .map(
                event => {

                    const timestamp =
                        escapeHTML(
                            event.timestamp ||
                            "—"
                        );


                    return `
                        <tr>

                            <td>
                                ${timestamp}
                            </td>

                            <td>
                                ${requestIdHTML(
                                    event.request_id
                                )}
                            </td>

                            <td>
                                ${decisionBadge(
                                    event.decision
                                )}
                            </td>

                            <td>
                                ${formatNumber(
                                    event.risk_score,
                                    3
                                )}
                            </td>

                            <td>
                                ${
                                    event.confidence === null
                                        ? "—"
                                        : formatPercent(
                                            normalizeConfidence(
                                                event.confidence
                                            )
                                        )
                                }
                            </td>

                        </tr>
                    `;
                }
            )
            .join("");
}


/* ============================================================
   RECENT ACTIVITY
   ============================================================ */

function renderRecentEvents(events) {

    const container =
        $("recent-events");


    if (!container) {
        return;
    }


    if (
        !events ||
        !events.length
    ) {

        container.innerHTML = `
            <tr>
                <td
                    colspan="6"
                    class="empty-state"
                >
                    No recent activity.
                </td>
            </tr>
        `;

        return;
    }


    const normalized =
        events
            .map(normalizeEvent)
            .slice()
            .reverse()
            .slice(0, 10);


    container.innerHTML =
        normalized
            .map(
                event => {

                    const requestId =
                        event.request_id ||
                        "—";


                    const factuality =
                        event.factuality_status ||
                        event.factuality ||
                        event.metadata?.factuality_status ||
                        "—";


                    let timestamp =
                        "Recent";


                    if (
                        event.timestamp
                    ) {

                        try {

                            timestamp =
                                new Date(
                                    event.timestamp
                                ).toLocaleTimeString(
                                    [],
                                    {
                                        hour:
                                            "2-digit",

                                        minute:
                                            "2-digit",

                                        second:
                                            "2-digit"
                                    }
                                );

                        } catch (_) {

                            timestamp =
                                String(
                                    event.timestamp
                                );
                        }
                    }


                    return `
                        <tr
                            class="recent-table-row"
                        >

                            <td>

                                ${decisionBadge(
                                    event.decision
                                )}

                                <div
                                    class="recent-event-meta"
                                >
                                    Governed AI request
                                </div>

                            </td>


                            <td>

                                ${requestIdHTML(
                                    requestId
                                )}

                            </td>


                            <td>

                                <strong>
                                    ${formatNumber(
                                        event.risk_score,
                                        3
                                    )}
                                </strong>

                            </td>


                            <td>

                                <span
                                    class="factuality-status"
                                >
                                    ${escapeHTML(
                                        factuality
                                    )}
                                </span>

                            </td>


                            <td>

                                <strong>
                                    ${formatMilliseconds(
                                        event.latency_ms
                                    )}
                                </strong>

                            </td>


                            <td>

                                <span
                                    class="recent-event-time"
                                >
                                    ${escapeHTML(
                                        timestamp
                                    )}
                                </span>

                            </td>

                        </tr>
                    `;
                }
            )
            .join("");
}


/* ============================================================
   LATEST REQUEST STRIP
   ============================================================ */

function renderLatestRequest(event) {

    if (!event) {
        return;
    }


    const normalized =
        normalizeEvent(event);


    /*
     * Try existing element first.
     */
    let container =
        $("latest-request");


    /*
     * If it doesn't exist, create one inside
     * the active page header.
     */

    if (!container) {

        const overview =
            $("page-overview");


        if (!overview) {
            return;
        }


        const header =
            overview.querySelector(
                ".page-header"
            );


        if (!header) {
            return;
        }


        container =
            document.createElement(
                "div"
            );


        container.id =
            "latest-request";


        container.className =
            "cp-latest-request";


        header.after(
            container
        );
    }


    container.innerHTML = `

        <div>

            <div
                class="cp-latest-label"
            >
                Latest governed request
            </div>

            <div
                style="
                    margin-top:6px;
                    font-size:12px;
                    color:#dce2f0;
                "
            >
                ${decisionBadge(
                    normalized.decision
                )}
            </div>

        </div>


        <div>

            ${requestIdHTML(
                normalized.request_id
            )}

        </div>

    `;
}


/* ============================================================
   AUDIT / REQUEST VIEW
   ============================================================ */

async function loadAuditView() {

    try {

        const response =
            await loadEvents();


        const events =
            extractEvents(
                response
            );


        lastEvents =
            events;


        renderAuditTable(
            events
        );


        renderRecentEvents(
            events
        );


        renderRequests(
            events
        );


        if (events.length) {

            renderLatestRequest(
                events[events.length - 1]
            );
        }


    } catch (error) {

        console.error(
            "Audit view failed:",
            error
        );


        renderAuditTable([]);

        renderRecentEvents([]);

        renderRequests([]);
    }
}


/* ============================================================
   GENERATE REQUEST
   ============================================================ */

async function generateRequest(
    prompt,
    metadata = null
) {

    if (
        !prompt ||
        !String(prompt).trim()
    ) {

        throw new Error(
            "Prompt cannot be empty."
        );
    }


    const payload = {

        prompt:
            String(prompt).trim()
    };


    if (metadata) {

        payload.metadata =
            metadata;
    }


    console.log(
        "[ControlPlane] Generating request..."
    );


    const result =
        await apiFetch(
            "/generate",
            {
                method: "POST",

                body:
                    JSON.stringify(
                        payload
                    )
            }
        );


    console.log(
        "[ControlPlane] Generate response:",
        result
    );


    /*
     * CRITICAL:
     *
     * Your generate response contains:
     *
     * metadata:
     * {
     *     request_id: "req-..."
     * }
     *
     * Therefore capture it immediately.
     */

    const requestId =
        result?.metadata?.request_id ||
        result?.request_id ||
        result?.id ||
        null;


    lastGeneratedRequestId =
        requestId;


    if (requestId) {

        console.log(
            "[ControlPlane] Request ID:",
            requestId
        );
    }


    /*
     * Populate response fields.
     */

    setText(
        "response-output",
        result.output ||
        result.raw_output ||
        "—"
    );


    setText(
        "decision-output",
        result.decision ||
        result.action ||
        result.policy_decision ||
        "—"
    );


    setText(
        "risk-output",
        result.risk_score !== undefined
            ? formatNumber(
                result.risk_score,
                3
            )
            : "—"
    );


    setText(
        "confidence-output",
        result.confidence !== undefined
            ? formatPercent(
                normalizeConfidence(
                    result.confidence
                )
            )
            : "—"
    );


    setText(
        "latency-output",
        result.latency_ms !== undefined
            ? formatMilliseconds(
                result.latency_ms
            )
            : "—"
    );


    /*
     * If HTML has a request-id-output field,
     * populate it.
     */

    setText(
        "request-id-output",
        requestId || "—"
    );


    /*
     * Create a request ID display near the response
     * if the existing HTML doesn't have one.
     */

    renderGeneratedRequestId(
        requestId
    );


    /*
     * Refresh all monitoring data after generation.
     */

    await refreshDashboard();


    /*
     * Fetch events once more after refresh so the new
     * request is immediately visible.
     */

    try {

        const eventsResponse =
            await loadEvents();


        const events =
            extractEvents(
                eventsResponse
            );


        lastEvents =
            events;


        renderRecentEvents(
            events
        );


        renderRequests(
            events
        );


        renderAuditTable(
            events
        );


        if (events.length) {

            renderLatestRequest(
                events[
                    events.length - 1
                ]
            );
        }

    } catch (error) {

        console.warn(
            "Could not refresh request activity:",
            error
        );
    }


    return result;
}


/* ============================================================
   GENERATED REQUEST ID
   ============================================================ */

function renderGeneratedRequestId(
    requestId
) {

    if (!requestId) {
        return;
    }


    /*
     * If an explicit element exists,
     * it is enough.
     */

    if ($("request-id-output")) {
        return;
    }


    /*
     * Find response area.
     */

    const response =
        $("response-output");


    if (!response) {
        return;
    }


    const parent =
        response.parentElement;


    if (!parent) {
        return;
    }


    /*
     * Avoid duplicates.
     */

    if (
        parent.querySelector(
            ".cp-generated-request-id"
        )
    ) {
        return;
    }


    const wrapper =
        document.createElement(
            "div"
        );


    wrapper.className =
        "cp-generated-request-id";


    wrapper.style.cssText = `
        margin-top:12px;
        padding-top:10px;
        border-top:1px solid
            rgba(148,163,184,0.10);
    `;


    wrapper.innerHTML = `

        <div
            style="
                color:#6f7c93;
                font-size:10px;
                font-weight:700;
                letter-spacing:.12em;
                text-transform:uppercase;
                margin-bottom:6px;
            "
        >
            Request ID
        </div>

        ${requestIdHTML(
            requestId
        )}

    `;


    parent.appendChild(
        wrapper
    );
}


/* ============================================================
   GENERATE FORM
   ============================================================ */

function initializeGenerateForm() {

    const possibleForms = [
        "generate-form",
        "prompt-form",
        "request-form"
    ];


    let form = null;


    for (
        const id of possibleForms
    ) {

        const element =
            $(id);


        if (element) {

            form =
                element;

            break;
        }
    }


    if (!form) {

        console.log(
            "[ControlPlane] No generate form detected."
        );

        return;
    }


    /* ========================================================
       PROMPT INPUT
       ======================================================== */

    let promptInput =
        $("prompt");


    if (!promptInput) {

        promptInput =
            $("prompt-input");
    }


    if (!promptInput) {

        promptInput =
            form.querySelector(
                "textarea[name='prompt']"
            );
    }


    if (!promptInput) {

        promptInput =
            form.querySelector(
                "input[name='prompt']"
            );
    }


    if (!promptInput) {

        console.warn(
            "[ControlPlane] Generate form found, but prompt input was not found."
        );

        return;
    }


    /* ========================================================
       PREVENT DUPLICATE INITIALIZATION
       ======================================================== */

    if (
        form.dataset.cpInitialized ===
        "true"
    ) {

        return;
    }


    form.dataset.cpInitialized =
        "true";


    /* ========================================================
       GOVERNANCE PROFILE
       ========================================================

       The backend supports:

       1. customer_support
       2. internal_copilot
       3. regulated_decision

       The selector is created dynamically so we do not need
       to modify index.html.

       Default:
           Customer Support — Balanced safety & latency

       The selected profile is sent to /generate as:

           metadata: {
               use_case: "...",
               governance_profile: "..."
           }

       This keeps the existing generate flow intact.
       ======================================================== */


    let governanceProfile =
        $("governance-profile");


    /*
     * If the selector already exists in HTML,
     * make sure it is visible and usable.
     */

    if (governanceProfile) {

        governanceProfile.style.display =
            "block";

    } else {

        /*
         * Create the Governance Profile section.
         */

        const profileWrapper =
            document.createElement(
                "div"
            );


        profileWrapper.id =
            "governance-profile-wrapper";


        profileWrapper.style.cssText = `
            margin-top:24px;
            margin-bottom:18px;
        `;


        profileWrapper.innerHTML = `

            <div
                style="
                    color:#8b9ab5;
                    font-size:12px;
                    font-weight:700;
                    letter-spacing:.12em;
                    text-transform:uppercase;
                    margin-bottom:9px;
                "
            >
                GOVERNANCE PROFILE
            </div>


            <div
                style="
                    position:relative;
                "
            >

                <select
                    id="governance-profile"
                    name="governance_profile"
                    style="
                        width:100%;
                        box-sizing:border-box;
                        appearance:none;
                        -webkit-appearance:none;
                        color-scheme:dark;
                        background:
                            linear-gradient(
                                145deg,
                                rgba(15,23,42,.96),
                                rgba(8,13,23,.96)
                            );
                        color:#e7ebf5;
                        border:
                            1px solid
                            rgba(148,163,184,.18);
                        border-radius:9px;
                        padding:
                            15px 44px 15px 16px;
                        font-size:14px;
                        font-family:inherit;
                        outline:none;
                        cursor:pointer;
                        transition:
                            border-color 160ms ease,
                            box-shadow 160ms ease,
                            background 160ms ease;
                    "
                >

                    <option
                        value="customer_support"
                    >
                        Customer Support — Balanced safety & latency
                    </option>


                    <option
                        value="internal_copilot"
                    >
                        Internal Copilot — Productivity focused
                    </option>


                    <option
                        value="regulated_decision"
                    >
                        Regulated Decision — High safety & strict controls
                    </option>

                </select>


                <span
                    style="
                        position:absolute;
                        right:16px;
                        top:50%;
                        transform:translateY(-50%);
                        color:#8491aa;
                        pointer-events:none;
                        font-size:12px;
                    "
                >
                    ▼
                </span>

            </div>


            <div
                id="governance-profile-description"
                style="
                    margin-top:8px;
                    color:#687892;
                    font-size:11px;
                    line-height:1.5;
                "
            >
                Balanced controls for customer-facing AI.
            </div>

        `;


        /*
         * Insert the selector immediately before
         * the Generate Response button area.
         *
         * First try to locate the submit button.
         */

        const submitButton =
            form.querySelector(
                "button[type='submit']"
            );


        if (submitButton) {

            /*
             * The button may be inside a wrapper.
             * Insert before the closest sensible block.
             */

            const buttonParent =
                submitButton.parentElement;


            if (
                buttonParent &&
                buttonParent !== form
            ) {

                buttonParent.before(
                    profileWrapper
                );

            } else {

                submitButton.before(
                    profileWrapper
                );
            }

        } else {

            /*
             * Fallback:
             * Put the selector after the prompt.
             */

            promptInput.after(
                profileWrapper
            );
        }


        governanceProfile =
            $("governance-profile");
    }


    /* ========================================================
       GOVERNANCE PROFILE DESCRIPTIONS
       ======================================================== */

    const governanceDescriptions = {

        customer_support:
            "Balanced controls for customer-facing AI.",

        internal_copilot:
            "Moderate risk controls with stronger productivity and latency flexibility.",

        regulated_decision:
            "Strict controls for high-risk or regulated decision-support workflows."
    };


    /*
     * Default profile.
     *
     * This matches the profile shown in your previous
     * working screenshot.
     */

    if (governanceProfile) {

        governanceProfile.value =
            governanceProfile.value ||
            "customer_support";


        const description =
            $("governance-profile-description");


        if (description) {

            description.textContent =
                governanceDescriptions[
                    governanceProfile.value
                ] ||
                governanceDescriptions.customer_support;
        }


        /*
         * Update description whenever the user changes
         * the governance profile.
         */

        governanceProfile.addEventListener(
            "change",
            () => {

                const selectedProfile =
                    governanceProfile.value;


                if (description) {

                    description.textContent =
                        governanceDescriptions[
                            selectedProfile
                        ] ||
                        "";
                }


                console.log(
                    "[ControlPlane] Governance profile changed:",
                    selectedProfile
                );
            }
        );


        /*
         * Focus styling.
         */

        governanceProfile.addEventListener(
            "focus",
            () => {

                governanceProfile.style.borderColor =
                    "rgba(108,99,255,.65)";

                governanceProfile.style.boxShadow =
                    "0 0 0 3px rgba(108,99,255,.10)";
            }
        );


        governanceProfile.addEventListener(
            "blur",
            () => {

                governanceProfile.style.borderColor =
                    "rgba(148,163,184,.18)";

                governanceProfile.style.boxShadow =
                    "none";
            }
        );
    }


    /* ========================================================
       SUBMIT
       ======================================================== */

    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const prompt =
                promptInput.value;


            /*
             * Read the selected governance profile.
             *
             * Always fall back to customer_support so the
             * existing behaviour remains unchanged if the
             * selector is unavailable.
             */

            const selectedGovernanceProfile =
                governanceProfile?.value ||
                "customer_support";


            const submitButton =
                form.querySelector(
                    "button[type='submit']"
                );


            if (submitButton) {

                submitButton.disabled =
                    true;

                submitButton.classList.add(
                    "loading"
                );
            }


            try {

                /*
                 * Send the selected governance profile
                 * through metadata.
                 *
                 * Existing metadata behaviour is preserved.
                 */

                const metadata = {

                    use_case:
                        selectedGovernanceProfile,

                    governance_profile:
                        selectedGovernanceProfile
                };


                console.log(
                    "[ControlPlane] Generating with governance profile:",
                    selectedGovernanceProfile
                );


                const result =
                    await generateRequest(
                        prompt,
                        metadata
                    );


                if (
                    result &&
                    result.output
                ) {

                    setText(
                        "response-output",
                        result.output
                    );
                }


                /*
                 * Clear input only after success.
                 */

                promptInput.value = "";


            } catch (error) {

                console.error(
                    "Generate request failed:",
                    error
                );


                showApiError(
                    error.message
                );


            } finally {

                if (submitButton) {

                    submitButton.disabled =
                        false;

                    submitButton.classList.remove(
                        "loading"
                    );
                }
            }
        }
    );
}


/* ============================================================
   REFRESH EVERYTHING
   ============================================================ */

async function refreshDashboard() {

    const refreshButton =
        $("refresh-button");


    if (refreshButton) {

        refreshButton.classList.add(
            "loading"
        );

        refreshButton.disabled =
            true;
    }


    try {

        /*
         * Load all independent dashboard sources in parallel.
         */

        const results =
            await Promise.allSettled(
                [
                    loadDashboard(),
                    loadMetrics(),
                    loadReviews(),
                    checkHealth(),
                    loadEvents()
                ]
            );


        const dashboardResult =
            results[0];


        const metricsResult =
            results[1];


        const reviewsResult =
            results[2];


        const eventsResult =
            results[4];


        /*
         * Store dashboard data.
         */

        if (
            dashboardResult.status ===
                "fulfilled" &&
            dashboardResult.value
        ) {

            lastDashboardData =
                dashboardResult.value;
        }


        /*
         * Store FULL metrics data.
         *
         * This contains the factuality counters.
         */

        if (
            metricsResult.status ===
                "fulfilled" &&
            metricsResult.value
        ) {

            lastMetricsData =
                metricsResult.value;
        }


        /*
         * Store reviews.
         */

        if (
            reviewsResult.status ===
                "fulfilled" &&
            reviewsResult.value
        ) {

            lastReviewsData =
                reviewsResult.value;
        }


        /*
         * IMPORTANT:
         *
         * loadDashboard() renders immediately while the other
         * parallel requests are still running.
         *
         * Therefore render again AFTER /metrics has completed.
         */

        if (lastDashboardData) {

            renderDashboard(
                lastDashboardData
            );
        }


        /*
         * Explicitly render factuality AFTER metrics have
         * been stored.
         */

        await loadFactuality();


        /*
         * Events are the reliable source for:
         *
         * - Request IDs
         * - Recent Activity
         * - Requests
         * - Audit
         */

        if (
            eventsResult.status ===
                "fulfilled" &&
            eventsResult.value
        ) {

            const events =
                extractEvents(
                    eventsResult.value
                );


            lastEvents =
                events;


            renderRecentEvents(
                events
            );


            renderAuditTable(
                events
            );


            renderRequests(
                events
            );


            if (events.length) {

                renderLatestRequest(
                    events[
                        events.length - 1
                    ]
                );
            }
        }


        /*
         * Keep Reviews page fresh.
         */

        const activePage =
            document.querySelector(
                ".page.active"
            );


        if (activePage) {

            if (
                activePage.id ===
                "page-reviews"
            ) {

                renderReviews(
                    lastReviewsData
                );
            }


            if (
                activePage.id ===
                "page-factuality"
            ) {

                await loadFactuality();
            }
        }


        console.log(
            "[ControlPlane] Dashboard refreshed:",
            new Date().toLocaleTimeString()
        );


    } catch (error) {

        console.error(
            "Dashboard refresh failed:",
            error
        );


    } finally {

        if (refreshButton) {

            refreshButton.classList.remove(
                "loading"
            );

            refreshButton.disabled =
                false;
        }
    }
}


/* ============================================================
   REFRESH BUTTONS
   ============================================================ */

function initializeRefreshButton() {

    const button =
        $("refresh-button");


    if (button) {

        button.addEventListener(
            "click",
            () => {
                refreshDashboard();
            }
        );
    }


    const overviewButton =
        $("refresh-overview");


    if (overviewButton) {

        overviewButton.addEventListener(
            "click",
            () => {
                refreshDashboard();
            }
        );
    }
}


/* ============================================================
   AUTO REFRESH
   ============================================================ */

function startAutoRefresh() {

    if (refreshTimer) {

        clearInterval(
            refreshTimer
        );
    }


    refreshTimer =
        setInterval(
            () => {

                refreshDashboard();

            },
            REFRESH_INTERVAL
        );


    console.log(
        `[ControlPlane] Auto-refresh enabled: every ${REFRESH_INTERVAL / 1000}s`
    );
}


function stopAutoRefresh() {

    if (refreshTimer) {

        clearInterval(
            refreshTimer
        );

        refreshTimer =
            null;
    }
}


/* ============================================================
   KEYBOARD SHORTCUT
   ============================================================ */

function initializeKeyboardShortcuts() {

    document.addEventListener(
        "keydown",
        event => {

            /*
             * Shift + R
             * = dashboard refresh
             */

            if (
                event.shiftKey &&
                event.key.toLowerCase() ===
                    "r"
            ) {

                event.preventDefault();

                refreshDashboard();
            }
        }
    );
}


/* ============================================================
   INITIAL STATE
   ============================================================ */

function initializeEmptyState() {

    const defaults = {

        "metric-requests":
            "—",

        "metric-allow-rate":
            "—",

        "metric-reviews":
            "—",

        "metric-risk":
            "—",

        "metric-latency":
            "—",

        "metric-model-latency":
            "—",

        "metric-cost":
            "—",


        "governance-request":
            "—",

        "governance-response":
            "—",

        "governance-confidence":
            "—",


        "security-risk":
            "—",

        "privacy-risk":
            "—",

        "bias-risk":
            "—",

        "factuality-risk":
            "—",

        "cost-risk":
            "—",


        "factuality-verified":
            "—",

        "factuality-failed":
            "—",

        "factuality-unknown":
            "—",

        "factuality-claims":
            "—",


        "allow-count":
            "0",

        "review-count":
            "0",

        "block-count":
            "0",

        "edit-count":
            "0",


        "decision-allow":
            "0",

        "decision-review":
            "0",

        "decision-block":
            "0",

        "decision-edit":
            "0",

        "decision-unknown":
            "0"
    };


    Object.entries(
        defaults
    ).forEach(
        ([id, value]) => {

            setText(
                id,
                value
            );
        }
    );
}


/* ============================================================
   INITIALIZATION
   ============================================================ */

async function initializeDashboard() {

    console.log(
        "=========================================="
    );

    console.log(
        "ControlPlane dashboard starting..."
    );

    console.log(
        "API:",
        API_BASE
    );

    console.log(
        "=========================================="
    );


    /*
     * Inject visual enhancements first.
     */

    injectDashboardStyles();


    initializeEmptyState();

    initializeHowItWorks();

    initializeNavigation();

    initializeRefreshButton();

    initializeKeyboardShortcuts();

    initializeRequestIdCopy();

    initializeGenerateForm();


    /*
     * Initial data load.
     */

    await refreshDashboard();


    /*
     * Continuous monitoring.
     */

    startAutoRefresh();
}


/* ============================================================
   PAGE READY
   ============================================================ */

if (
    document.readyState ===
    "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initializeDashboard
    );

} else {

    initializeDashboard();
}


/* ============================================================
   GLOBAL API
   ============================================================ */

window.generateRequest =
    generateRequest;


window.ControlPlaneDashboard = {

    refresh:
        refreshDashboard,

    loadDashboard:
        loadDashboard,

    loadMetrics:
        loadMetrics,

    loadReviews:
        loadReviews,

    loadEvents:
        loadEvents,

    loadAudit:
        loadAuditView,

    generate:
        generateRequest,

    checkHealth:
        checkHealth,

    startAutoRefresh:
        startAutoRefresh,

    stopAutoRefresh:
        stopAutoRefresh
};
                           