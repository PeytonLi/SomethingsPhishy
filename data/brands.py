"""Precision-first brand and email-service-provider domain data."""

# Domains a brand genuinely owns and routes its own mail/links through. Only
# add a domain here after confirming the brand actually controls it — every
# entry is a hole punched in LINK_TEXT_HREF_MISMATCH, which is CRITICAL and
# DECISIVE, so a wrong entry silently disarms the strongest email check.
ESP_TRACKING_DOMAINS = {
    "amazon.com": {
        "amazon.com",
        "awstrack.me",
        "amazon-adsystem.com",   # ad/click tracking on order + marketing mail
        "media-amazon.com",
        "ssl-images-amazon.com",
    },
    "paypal.com": {
        "paypal-communication.com",
        "paypalobjects.com",
    },
}

# Shared ESP click-trackers. Any brand may legitimately route through these.
GENERIC_ESP_TRACKING_DOMAINS = {
    "sendgrid.net",
    "list-manage.com",
    "exacttarget.com",
    "amazonses.com",
    "mailgun.org",
    "mandrillapp.com",
    "sparkpostmail.com",
    "hubspotlinks.com",
}
