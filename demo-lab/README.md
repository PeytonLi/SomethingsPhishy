# Something's Phishy local demo lab

A standalone static scenario set for exercising the Something's Phishy MCP screen-capture and deterministic signal pipeline. Every merchant, mail provider, product, wallet, and identity shown here is fictional.

## Launch on Windows

For the reliable full-fidelity demo, run this once from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1
```

It starts the local fixture server on `8080`, restarts the MCP HTTP server on `8765` so code changes are loaded, launches a dedicated CDP-enabled Chrome profile on `9222`, verifies all three services, and opens the scenario home, SMCCCD OneLogin, Internet Archive, EXT, Logitech G checkout, and ElevenLabs subscription page as tabs. Active-document UI Automation and visible-CDP selection prevent inactive tab titles from entering the MCP verdict. Treat EXT as untrusted: do not sign in, install extensions, or open downloads while testing. To run only the static server instead:

```powershell
py -3 -m http.server 8080 --directory demo-lab
```

Open <http://127.0.0.1:8080/>. Keep the terminal open while testing.

## Chrome CDP is required

The capture pipeline reads page text, links, and iframe origins from Chrome DevTools Protocol at `127.0.0.1:9222`. Close ordinary Chrome windows first, then start a dedicated demo profile from Command Prompt:

```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%TEMP%\somethings-phishy-cdp"
```

If Chrome is installed elsewhere, use that installation's `chrome.exe`. Without CDP, capture falls back to UI Automation/OCR, but link destinations and Stripe iframe origins are not observable. A Stripe/card page therefore returns `CAUTION` with `PAYMENT_ORIGIN_UNVERIFIED`, never `SAFE`; the fake clone reaches `DANGER` only when CDP proves the Stripe iframe is absent. Make the scenario tab the foreground window before invoking an MCP tool.

## Expected MCP checks

Results below assume Chrome CDP is connected, the target tab is foreground, and no unrelated recent download or clipboard content adds findings. Humanized wording may vary; the verdict and finding codes are deterministic.

| Route | MCP command | Expected result |
| --- | --- | --- |
| `/` | `check_this_page()` | `SAFE` — launcher contains no threat signal. |
| `/safe-checkout.html` | `check_this_page()` | `SAFE` — CDP records `https://js.stripe.com` in `iframe_origins`, so the Stripe claim is backed by a Stripe-owned origin. The visible fields are inert. |
| `/fake-checkout.html` | `check_this_page()` | `DANGER` with `FAKE_PAYMENT_PROCESSOR`. Loopback HTTP is treated as a local test surface, while the page's Stripe claim and missing Stripe iframe remain observable through CDP. |
| `/email.html` | `check_this_page()` | `DANGER` with `LINK_TEXT_HREF_MISMATCH`; `URGENCY_PRESSURE` is also expected. CDP observes visible link text `secure.example.com` and href `https://example.net/review`. |
| `/ocr.html` | `check_this_page()` | `DANGER` with `TECH_SUPPORT_SCARE`. `document.body.innerText` is empty; capture should fall through to OCR and read the warning and painted demo ribbon from the canvas. |
| `/crypto.html` | `check_this_transaction()` | `CAUTION` with `DANGEROUS_APPROVAL` after observing `setApprovalForAll`. No wallet provider is accessed and no transaction is created. |
| `/download.html` | First click **Download invoice utility**, then invoke `check_this_download()` | `DANGER` with `DOUBLE_EXTENSION` for `invoice.pdf.exe`. The fixture is plain text. Chrome may show a download warning because the filename ends in `.exe`; retain it only if your isolated demo policy permits, and never open it. |

The MCP returns rendered verdict cards rather than JSON. Typical first lines are:

- `✅ No clear signs of a scam found.` for `SAFE`
- `⚠️ Something here needs a closer look.` for `CAUTION`
- `⛔ This looks dangerous.` for `DANGER`

## Scenario notes

### Safe checkout

`safe-checkout.html` is the one intentional network exception in this otherwise local asset set: its sandboxed, non-interactive iframe loads `https://js.stripe.com/v3/` solely so CDP can record a genuine Stripe-owned origin. It does not receive field values. The demo card controls are parent-page read-only inputs and are not Stripe Elements.

### Fake checkout

`fake-checkout.html` deliberately says “Powered by Stripe,” but has no Stripe iframe or Stripe script. Its raw-looking fields are read-only and all input, paste, drop, change, key, and submit events are blocked.

### Email

`email.html` uses a real anchor mismatch for inspection, but its click handler always prevents navigation. `example.net` is an IANA-reserved example domain.

### OCR warning

`ocr.html` paints the entire interface—including `SECURITY DEMO — NO REAL DATA`—into one canvas. There is no visible DOM text, link, form, or button. This is intentional so the OCR fallback is exercised.

### Crypto approval

`crypto.html` contains a fake recipient/operator address and static transaction language. It includes no wallet library, provider lookup, RPC endpoint, event request, or signing path.

### Download

`files/invoice.pdf.exe` is a plain-text fixture with no executable bytes or script. The double extension exists only to exercise filename detection. Do not rename it, execute it, or use it outside the demo lab.

## Safety guarantees

- A persistent yellow `SECURITY DEMO — NO REAL DATA` ribbon appears on every scenario. On the OCR route it is painted into the canvas by design.
- No form has an action. Shared JavaScript prevents submission and mutating input events.
- Payment controls are `readonly`, use `autocomplete="off"`, and accept no typed or pasted values.
- No entered data is stored in cookies, local/session storage, IndexedDB, files, or memory buffers.
- No analytics, telemetry, service workers, package dependencies, web fonts, remote images, or external CSS/JS are used.
- No email link navigates, no wallet connects, and no transaction is created.
- The only outbound request is the explicit Stripe-owned iframe on `safe-checkout.html`; it loads no user-entered data.
- Stop the local server with `Ctrl+C` when finished and delete the dedicated Chrome profile if desired.
