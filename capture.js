(function () {
  "use strict";

  const REPO_ISSUE_URL = "https://github.com/dkharlanau/signal-to-insight/issues/new";
  const TRACKING_PARAMS = new Set([
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src"
  ]);

  function cleanUrl(raw) {
    if (!raw) return "";
    const url = new URL(raw.trim());
    for (const key of Array.from(url.searchParams.keys())) {
      if (TRACKING_PARAMS.has(key.toLowerCase())) url.searchParams.delete(key);
    }
    if (/(^|\.)youtube\.com$/i.test(url.hostname) || /^youtu\.be$/i.test(url.hostname)) {
      for (const key of ["t", "start", "time_continue", "si", "feature"]) url.searchParams.delete(key);
    }
    url.hash = "";
    return url.toString();
  }

  function inferType(raw) {
    const url = new URL(raw);
    const host = url.hostname.toLowerCase();
    const path = url.pathname.toLowerCase();
    if (host.includes("youtube.com") || host === "youtu.be" || host.includes("vimeo.com")) return "video";
    if (host === "github.com" && path.split("/").filter(Boolean).length >= 2) return "repository";
    if (path.endsWith(".pdf") || host.includes("arxiv.org")) return "paper";
    if (host.includes("podcasts.apple.com") || host.includes("spotify.com") && path.includes("episode")) return "podcast";
    if (host.includes("docs.") || path.includes("/docs/") || path.includes("/documentation/")) return "documentation";
    if (path.endsWith(".ppt") || path.endsWith(".pptx") || host.includes("slideshare.net")) return "presentation";
    return "article";
  }

  function issueBody(values) {
    return [
      "### Source URL", "", values.url,
      "", "### Source type", "", values.type,
      "", "### Focus", "", values.focus || "_No response_",
      "", "### Note", "", values.note || "_No response_"
    ].join("\n");
  }

  function buildIssueUrl(values) {
    const clean = cleanUrl(values.url);
    const parsed = new URL(clean);
    const params = new URLSearchParams({
      title: `[source] ${parsed.hostname}`,
      body: issueBody({ ...values, url: clean })
    });
    return `${REPO_ISSUE_URL}?${params.toString()}`;
  }

  function bookmarklet() {
    const capture = "https://dkharlanau.github.io/signal-to-insight/capture/";
    return `javascript:location.href='${capture}?url='+encodeURIComponent(location.href)`;
  }

  function bindPage() {
    const form = document.querySelector("[data-capture-form]");
    if (!form) return;
    const urlInput = form.querySelector("[name=url]");
    const typeInput = form.querySelector("[name=type]");
    const query = new URLSearchParams(location.search);
    if (query.get("url")) {
      try {
        urlInput.value = cleanUrl(query.get("url"));
        typeInput.value = inferType(urlInput.value);
      } catch (_) {
        urlInput.value = query.get("url");
      }
    }
    urlInput.addEventListener("change", () => {
      try {
        urlInput.value = cleanUrl(urlInput.value);
        typeInput.value = inferType(urlInput.value);
      } catch (_) {}
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form).entries());
      try {
        location.href = buildIssueUrl(values);
      } catch (error) {
        const target = document.querySelector("[data-error]");
        if (target) target.textContent = `Enter a valid http(s) URL. ${error.message}`;
      }
    });
    const bookmarkTarget = document.querySelector("[data-bookmarklet]");
    if (bookmarkTarget) bookmarkTarget.href = bookmarklet();
  }

  function selfTest() {
    const cleaned = cleanUrl("https://www.youtube.com/watch?v=abc&t=30&utm_source=x&si=z");
    if (cleaned.includes("utm_source") || cleaned.includes("&t=") || cleaned.includes("&si=")) throw new Error("tracking cleanup failed");
    if (inferType("https://github.com/open-policy-agent/opa") !== "repository") throw new Error("repository inference failed");
    if (inferType("https://arxiv.org/abs/2210.03629") !== "paper") throw new Error("paper inference failed");
    const issue = buildIssueUrl({ url: "https://example.com/a?utm_source=x", type: "article", focus: "why", note: "note" });
    const issueUrl = new URL(issue);
    if (!issue.includes("issues/new") || !(issueUrl.searchParams.get("body") || "").includes("### Source URL")) throw new Error("issue prefill failed");
    console.log("capture self-test passed; URL cleanup, type inference and GitHub issue prefill work.");
  }

  const api = { cleanUrl, inferType, issueBody, buildIssueUrl, bookmarklet };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") {
    window.SignalToInsightCapture = api;
    window.addEventListener("DOMContentLoaded", bindPage);
  }
  if (typeof process !== "undefined" && process.argv && process.argv.includes("--self-test")) selfTest();
})();
