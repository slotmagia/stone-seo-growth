"""Publishing remains manual until OAuth/API authorization is configured."""
CAPABILITIES = {
    "website": "MANUAL_HANDOFF",  # CMS adapter not yet configured
    "baidu": "READ_ONLY_ANALYTICS",  # submission is not publication
    "google": "READ_ONLY_ANALYTICS",  # indexing != publishing
    "douyin": "MANUAL_HANDOFF",
    "domestic_shop": "MANUAL_HANDOFF",
    "alibaba_icbu": "MANUAL_HANDOFF",
    "geo": "READ_ONLY_ANALYTICS",
}

def publication_package(content):
    return {
        "content_id":content.id,
        "version":content.version,
        "channel":content.platform,
        "mode":CAPABILITIES.get(content.platform,"MANUAL_HANDOFF"),
        "requires_external_action": True,
        "message":"No external publishing was performed. Publish through an authorized account and confirm the URL manually.",
        "payload":{"title":content.title,"description":content.description,"body":content.body},
    }
