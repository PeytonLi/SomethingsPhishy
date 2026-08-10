# Phishing and Scam Landscape

> Research brief for README use. Source check completed August 9, 2026. The most recent datasets covered here are calendar year 2025 for FBI reporting, calendar year 2024 for the latest cited FTC nationwide total, and Q1 2026 for APWG observations. Dollar figures are U.S. dollars.

## README-ready summary

Phishing and scams operate at enormous scale, but no single statistic captures the whole problem. In 2025, the FBI Internet Crime Complaint Center received **1,008,597 complaints** and recorded **$20.877 billion in reported losses**, up **26% from 2024**. Phishing/spoofing accounted for **72,984 complaints**.[^1] Separately, the FTC's latest cited nationwide annual total covers 2024: fraud reports from **2.6 million consumers** described **more than $12.5 billion** in losses, up **25% from 2023**; investment scams led FTC loss categories at **$5.7 billion**, followed by imposter scams at **$2.95 billion**.[^2] Older adults bear especially severe losses: people age 60 and older filed **201,266 IC3 complaints** reporting **$7.748 billion lost** in 2025.[^1] The threat is not limited to conventional email links. It spans calls, texts, QR codes, malicious attachments and downloads, fake verification prompts, and social engineering that convinces legitimate users to grant access or run attacker-supplied actions.[^3][^5][^6][^7]

## Key findings

### Scale and reported losses

- **FBI IC3, calendar year 2025:** **1,008,597 complaints**, **$20.877 billion in losses**, and an average loss of **$20,699** across all complaints. Reported losses increased **26% from 2024**.[^1]
- **Phishing/spoofing remained a major IC3 category:** **72,984 complaints** and **$215,843,126** assigned directly to that category. IC3 defines it as unsolicited email, text messages, and telephone calls that impersonate legitimate companies to request personal, financial, or login credentials.[^1]
- **FTC Consumer Sentinel, calendar year 2024:** fraud reports came from **2.6 million consumers**, almost unchanged from 2023, while reported fraud losses rose **25%** to **more than $12.5 billion**. The share of fraud reports indicating a monetary loss rose from **27% in 2023** to **38% in 2024**.[^2]
- **Observed phishing infrastructure remains high-volume:** APWG observed **971,181 phishing attacks in Q1 2026**, up **13.8%** from **853,244 in Q4 2025**. Telecom represented 33% of the Q1 2026 sector breakdown, while SaaS/webmail represented 20%; APWG also reported telephone-based fraud rising 15% quarter over quarter.[^3]

These measurements answer different questions. IC3 and FTC count reports or complaints, while APWG counts attacks, campaigns, and sites observed through its reporting network. None is a count of everyone exposed or harmed.

### Older adults

- In the FBI 2025 data, people **age 60 and older** submitted more complaints and reported more loss than any other age group: **201,266 complaints** and **$7.748 billion lost**. Those figures were up **37% in complaints** and **59% in losses** from 2024.[^1]
- The FTC reported that adults **age 60 and older** disclosed **more than $1.9 billion** in fraud losses in calendar year 2023. Because most fraud is not reported, the FTC estimated actual annual losses to older consumers could have been as high as **$61.5 billion**.[^4]
- Older adults were less likely than people age 18–59 to report losing money, but losses were more severe when they did. Median reported loss was **$804 for ages 70–79** and **$1,450 for age 80 and older**. Reports of losses of **$100,000 or more** had increased more than threefold since 2020.[^4]
- Compared with ages 18–59, adults 60 and older were **more than five times as likely** to report losing money to tech-support scams, **nearly three times as likely** to report a loss to prize, lottery, or sweepstakes scams, and **53% more likely** to report a loss to friend or family impersonation scams.[^4]

### Social engineering is multichannel

CISA defines social engineering as using human interaction to obtain or compromise information, and phishing as social engineering that impersonates a trusted organization through email or malicious websites. Its February 1, 2021 guidance distinguishes voice phishing, or vishing, from SMS phishing, or smishing, and identifies unsolicited attachments as a common malware-delivery mechanism.[^5] The page is now archived, so its definitions remain useful while its defensive advice should be checked against current guidance.

The FTC contact data shows the same multichannel reality: in 2024, **email was the most commonly reported contact method** for the second consecutive year, followed by **phone calls** and **text messages**.[^2]

A June 4, 2025 Google Threat Intelligence case study shows why this matters inside organizations. Google tracked UNC6040 operators impersonating IT support over voice calls and persuading users to authorize malicious connected applications or disclose credentials and MFA codes. Google states that every observed case manipulated end users rather than exploiting a Salesforce vulnerability; the resulting access enabled large-scale data theft and later extortion.[^6] Social engineering can therefore bypass technical controls by inducing a legitimate user to perform an authorized-looking action.

### ClickFix, QR codes, and malicious downloads

Microsoft reported on August 21, 2025 that the ClickFix social-engineering technique had grown since early 2024 and was targeting **thousands of enterprise and end-user devices globally every day**. ClickFix uses fake technical errors, human-verification prompts, or CAPTCHA checks to persuade users to copy, paste, and run attacker-supplied commands. Arrival paths include phishing, malicious advertising, and compromised or malicious websites; execution can download infostealers, remote-access tools, loaders, or rootkits on Windows and macOS.[^7]

Microsoft observed **tens of thousands of emails** in a May 2024 campaign and **thousands of phishing emails** in a March 2025 campaign. In early 2025, it also observed **thousands of devices per month** on which users executed ClickFix commands even with endpoint detection and response enabled. A single day of malicious-advertising redirects could send **tens or hundreds of thousands of unique visitors** to scam pages.[^7] These are Microsoft telemetry figures, not global prevalence estimates.

QR codes create another bridge from a benign-looking message to a phishing page or malware download. APWG member Mimecast detected **more than 1.7 million unique malicious QR codes** from **October 1, 2024 through March 31, 2025** and saw an average **2.7 million emails with QR-code attachments per day**. The codes led to phishing pages, brand-impersonation pages, scam sites, or malware.[^3] These figures describe Mimecast telemetry included in the APWG report, not the entire email ecosystem.

### Cryptocurrency scams

- IC3 tagged **149,686 complaints** with a cryptocurrency nexus in 2024, associated with **$9,322,335,911 in reported losses**. Losses increased **66% from 2023**.[^8]
- People age 60 and older represented the largest age group in this 2024 cryptocurrency-nexus data: **33,369 complaints** and **$2,839,333,197 lost**.[^8]
- Within the narrower **cryptocurrency investment** category in 2024, IC3 recorded **41,557 complaints** and **$5,819,531,069 lost**, up **29% in complaints** and **47% in losses** from 2023. People over 60 accounted for **8,043 complaints** and **$1,600,353,509 lost**.[^8]
- In the separate FTC taxonomy, investment scams produced **$5.7 billion** in reported 2024 losses. The FTC also found that losses paid by **bank transfer or cryptocurrency together exceeded losses through all other payment methods combined**.[^2]

The FBI's 2024 release described investment fraud, specifically cases involving cryptocurrency, as producing more than $6.5 billion in loss. The detailed 2024 IC3 report distinguishes **all investment loss** at **$6,570,639,864** from the narrower **cryptocurrency-investment nexus** at **$5,819,531,069**. This brief uses the detailed table labels rather than treating those figures as interchangeable.[^8]

## Interpretation and citation cautions

1. **Reported loss is not total loss.** IC3 and FTC figures depend on complaints and reports; underreporting is substantial. The FTC estimate for older adults illustrates the possible gap.
2. **Do not add FBI and FTC totals.** The systems have different intake channels, contributors, definitions, and overlapping scope, so summing them would double-count unknown portions of the same harm.
3. **A complaint is not necessarily one unique victim.** Reports can omit age or loss, and one event can generate more than one record or category relationship.
4. **Taxonomies differ.** Phishing, fraud, investment scams, and cryptocurrency nexus are not interchangeable labels. Phishing can be an entry technique for a loss ultimately categorized as investment fraud, tech support, identity theft, or another crime type; the **$70,013,036** in the IC3 phishing row is therefore not a complete estimate of downstream harm enabled by phishing.
5. **APWG attacks are not victim counts.** APWG presents observed attacks, sites, or campaigns as a general measure of phishing volume.
6. **Vendor telemetry has a visibility boundary.** Microsoft, Google, and Mimecast findings reflect their products, customers, investigations, and detection coverage. They establish real techniques and scale within those environments, not population-wide prevalence.

## Primary sources

[^1]: Federal Bureau of Investigation, Internet Crime Complaint Center, [2025 IC3 Annual Report](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf). See the 2025 complaint highlights, crime-type table, and elder-fraud sections.
[^2]: Federal Trade Commission, [New FTC Data Show a Big Jump in Reported Losses to Fraud to $12.5 Billion in 2024](https://www.ftc.gov/news-events/news/press-releases/2025/03/new-ftc-data-show-big-jump-reported-losses-fraud-125-billion-2024), **March 10, 2025**.
[^3]: Anti-Phishing Working Group, [Phishing Activity Trends Report, 1st Quarter 2026](https://docs.apwg.org/reports/apwg_trends_report_q1_2026.pdf), reporting period **January 1–March 31, 2026**, pp. 3–5.
[^4]: Federal Trade Commission, [FTC Issues Annual Report to Congress on Agency’s Actions to Protect Older Adults](https://www.ftc.gov/news-events/news/press-releases/2024/10/ftc-issues-annual-report-congress-agencys-actions-protect-older-adults), **October 18, 2024**, summarizing calendar-year 2023 data from *Protecting Older Consumers 2023–2024*.
[^5]: Cybersecurity and Infrastructure Security Agency, [Avoiding Social Engineering and Phishing Attacks](https://www.cisa.gov/news-events/news/avoiding-social-engineering-and-phishing-attacks), **February 1, 2021**; currently marked archived.
[^6]: Google Threat Intelligence Group, [The Cost of a Call: From Voice Phishing to Data Extortion](https://cloud.google.com/blog/topics/threat-intelligence/voice-phishing-data-extortion), **June 4, 2025**.
[^7]: Microsoft Threat Intelligence and Microsoft Defender Experts, [Think before you Click(Fix): Analyzing the ClickFix social engineering technique](https://www.microsoft.com/en-us/security/blog/2025/08/21/think-before-you-clickfix-analyzing-the-clickfix-social-engineering-technique/), **August 21, 2025**.
[^8]: Federal Bureau of Investigation, Internet Crime Complaint Center, [2024 IC3 Annual Report](https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf), released April 23, 2025.
