# P0 control failure for Track C

`control-amazon-order-esp` empirically reproduces the assigned
`LINK_TEXT_HREF_MISMATCH` false positive:

```text
anchor: Track package at amazon.com
href snapshot: https://aax-us-east.amazon-adsystem.com/s/snapshot
actual: DANGER — LINK_TEXT_HREF_MISMATCH
expected: SAFE — zero findings
```

This is a legitimate Amazon Ads/ESP tracking redirect pattern from the Amazon
order-confirmation control. The second real ESP control (`click.e.alerts.chase.com`)
passes because its anchor does not claim a domain. Track C should include the
Amazon tracking host in its ESP handling and rerun `py -m eval.run` after merge.

Baseline before Track C fix: **1/8 controls false-positive (12.5%); 45/60
Nazario phishing snapshots detected (75.0%)**.
