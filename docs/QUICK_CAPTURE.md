# Quick Capture

`/capture/` is a zero-backend capture surface for the existing owner GitHub source intake.

## Why it exists

Source intake should be cheap enough to use during normal browsing. The capture page does not create a second database or expose a GitHub credential. It only normalizes the URL, infers a likely source type and opens a pre-filled GitHub issue that is handled by the existing queue workflow.

## Browser flow

1. Open `/capture/`.
2. Paste a source URL, or open the page with `?url=<encoded-url>`.
3. Confirm the inferred source type and optionally add focus/context.
4. Choose **Open source intake**.
5. GitHub opens the normal `[source]` issue with the fields already populated.

The existing issue workflow remains responsible for owner authorization, canonical URL normalization and deduplication.

## One-click desktop capture

The capture page exposes a bookmarklet. Drag **Capture to Signal to Insight** to the bookmarks bar. Clicking it on any webpage opens the capture page with the current URL prefilled.

No token is stored in the bookmarklet.

## Mobile flow

The minimal portable flow is deliberately backend-free:

1. use the browser/app Share or Copy Link action;
2. open the capture page;
3. paste the URL;
4. open the GitHub intake.

A native share-target/PWA is not required until repeated dogfood shows that these extra taps materially reduce capture usage.

## Normalization

`capture.js` removes common tracking parameters and YouTube timestamp/share parameters before preparing the issue. The canonical repository intake performs normalization again, so capture-side cleanup is convenience rather than the authoritative deduplication layer.

## Safety boundary

- no GitHub credential is embedded in client code;
- capture does not publish anything;
- the source still enters the normal `queued → research → review` lifecycle;
- the page is `noindex,nofollow` because it is an owner utility, not a discovery surface.

## Checks

```bash
node --check capture.js
node capture.js --self-test
```
