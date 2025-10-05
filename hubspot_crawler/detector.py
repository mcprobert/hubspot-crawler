
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

# Load patterns at import time
import importlib.resources as pkg_resources
from . import patterns as _patterns_pkg

_PATTERNS_RAW = json.loads(pkg_resources.files(_patterns_pkg).joinpath("hubspot_patterns.json").read_text())
RX: Dict[str, re.Pattern] = {
    k: re.compile(v, re.IGNORECASE | re.MULTILINE)
    for k, v in _PATTERNS_RAW["patterns"].items()
}

Evidence = Dict[str, Any]

def _push(evid: List[Evidence], category: str, pattern_id: str, match: str,
          source: str, hubid: Optional[int] = None, confidence: str = "strong", context: Optional[str] = None):
    evid.append({
        "category": category,
        "patternId": pattern_id,
        "match": match[:300],
        "source": source,
        "hubId": hubid,
        "confidence": confidence,
        "context": context
    })

def detect_html(html: str) -> List[Evidence]:
    ev: List[Evidence] = []
    m_loader = RX["tracking_loader_script"].search(html)
    if m_loader:
        # Extract Hub ID from the pattern's capture group
        hubid = int(m_loader.group(1)) if m_loader.group(1) else None
        _push(ev, "tracking", "tracking_loader_script", m_loader.group(0), "html", hubid, "definitive")
    else:
        # Fallback: any reference to hs-scripts.com (catches cases without id attribute)
        m_script_any = RX["tracking_script_any"].search(html)
        if m_script_any:
            hubid = int(m_script_any.group(1)) if m_script_any.group(1) else None
            _push(ev, "tracking", "tracking_script_any", m_script_any.group(0), "html", hubid, "strong")

    m_analytics = RX["analytics_core"].search(html)
    if m_analytics:
        hubid = int(m_analytics.group(1)) if m_analytics.group(1) else None
        _push(ev, "tracking", "analytics_core", m_analytics.group(0), "html", hubid, "strong")

    # _hsq analytics queue presence (common tracking indicator)
    m_hsq = RX["_hsq_presence"].search(html)
    if m_hsq:
        _push(ev, "tracking", "_hsq_presence", m_hsq.group(0), "html", None, "strong")

    # Banner helper tracking
    m_banner = RX["banner_helper"].search(html)
    if m_banner:
        _push(ev, "tracking", "banner_helper", m_banner.group(0), "html", None, "strong")

    # URL tracking parameters (email/campaign tracking)
    m_url_params = RX["url_params_hs"].search(html)
    if m_url_params:
        _push(ev, "tracking", "url_params_hs", m_url_params.group(0), "html", None, "moderate")

    # Cookies mentioned in code (weak)
    for ck in RX["cookie_any"].finditer(html):
        _push(ev, "cookies", "cookie_any", ck.group(0), "html", None, "moderate")

    # Forms - spec requires BOTH loader and create call for definitive
    m_forms_loader = RX["forms_v2_loader"].search(html)
    m_forms_create = RX["forms_create_call"].search(html)
    if m_forms_loader:
        _push(ev, "forms", "forms_v2_loader", m_forms_loader.group(0), "html", None, "definitive" if m_forms_create else "strong")
    if m_forms_create:
        _push(ev, "forms", "forms_create_call", m_forms_create.group(0), "html", None, "definitive")

    m_forms_context = RX["forms_hidden_hs_context"].search(html)
    if m_forms_context:
        _push(ev, "forms", "forms_hidden_hs_context", m_forms_context.group(0), "html", None, "strong")

    # Chat
    m_chat_js = RX["chat_usemessages_js"].search(html)
    if m_chat_js:
        _push(ev, "chat", "chat_usemessages_js", m_chat_js.group(0), "html", None, "definitive")

    m_chat_api = RX["chat_usemessages_api"].search(html)
    if m_chat_api:
        _push(ev, "chat", "chat_usemessages_api", m_chat_api.group(0), "html", None, "definitive")

    m_chat_cookie = RX["cookie_messagesUtk"].search(html)
    if m_chat_cookie:
        _push(ev, "chat", "cookie_messagesUtk", m_chat_cookie.group(0), "html", None, "strong")

    # CTAs - spec requires BOTH loader and load call for definitive
    m_cta_loader = RX["cta_loader_legacy"].search(html)
    m_cta_call = RX["cta_load_call"].search(html)
    if m_cta_loader:
        _push(ev, "ctas", "cta_loader_legacy", m_cta_loader.group(0), "html", None, "definitive" if m_cta_call else "strong")
    if m_cta_call:
        _push(ev, "ctas", "cta_load_call", m_cta_call.group(0), "html", None, "definitive")

    m_cta_redirect = RX["cta_redirect_link"].search(html)
    if m_cta_redirect:
        _push(ev, "ctas", "cta_redirect_link", m_cta_redirect.group(0), "html", None, "definitive")

    # Meetings
    m_meetings_js = RX["meetings_embed_js"].search(html)
    if m_meetings_js:
        _push(ev, "meetings", "meetings_embed_js", m_meetings_js.group(0), "html", None, "strong")

    m_meetings_iframe = RX["meetings_iframe"].search(html)
    if m_meetings_iframe:
        _push(ev, "meetings", "meetings_iframe", m_meetings_iframe.group(0), "html", None, "strong")

    # CMS / files
    # CMS hosting requires: meta generator=HubSpot OR (hs_cos_wrapper class AND /_hcms/ path)
    m_meta_gen = RX["cms_meta_generator"].search(html)
    if m_meta_gen:
        _push(ev, "cms", "cms_meta_generator", m_meta_gen.group(0), "html", None, "strong")

    m_wrapper = RX["cms_wrapper_class"].search(html)
    if m_wrapper and RX["cms_internal_paths"].search(html):
        # Both wrapper class AND /_hcms/ path required for strong CMS confidence
        _push(ev, "cms", "cms_wrapper_with_hcms", m_wrapper.group(0), "html", None, "strong")

    # CMS hosting via hs-sites.com domain
    m_hs_sites = RX["cms_host_hs_sites"].search(html)
    if m_hs_sites:
        _push(ev, "cms", "cms_host_hs_sites", m_hs_sites.group(0), "html", None, "strong")

    # Files CDN - moderate confidence (files hosted ≠ CMS)
    m_files = RX["cms_files_hubspotusercontent"].search(html)
    if m_files:
        _push(ev, "files", "cms_files_hubspotusercontent", m_files.group(0), "html", None, "moderate")

    m_hubfs = RX["cms_files_hubfs_path"].search(html)
    if m_hubfs:
        _push(ev, "files", "cms_files_hubfs_path", m_hubfs.group(0), "html", None, "moderate")

    # Video
    m_video = RX["video_hubspotvideo"].search(html)
    if m_video:
        _push(ev, "video", "video_hubspotvideo", m_video.group(0), "html", None, "strong")

    # Email indicators embedded in HTML
    m_email_marketing = RX["email_hubspot_marketing_click"].search(html)
    if m_email_marketing:
        _push(ev, "email", "email_hubspot_marketing_click", m_email_marketing.group(0), "html", None, "strong")

    m_email_links = RX["email_hubspotlinks"].search(html)
    if m_email_links:
        _push(ev, "email", "email_hubspotlinks", m_email_links.group(0), "html", None, "moderate")

    return ev

def detect_network(lines: str) -> List[Evidence]:
    ev: List[Evidence] = []
    for u in [ln.strip() for ln in (lines or "").splitlines() if ln.strip()]:
        # Tracking patterns - network evidence is "definitive" (actual requests)
        for key in ("tracking_loader_script","analytics_core","beacon_ptq"):
            r = RX.get(key)
            if r:
                m = r.search(u)
                if m:
                    hubid = None
                    # Try to extract Hub ID from capture groups or URL pattern
                    if m.lastindex and m.lastindex >= 1:
                        try:
                            hubid = int(m.group(1))
                        except (ValueError, IndexError):
                            pass
                    # Fallback Hub ID extraction for URLs
                    if not hubid:
                        id_match = re.search(r"(?:hs-scripts\.com|hs-analytics\.net)/(?:analytics/\d+/)?(\d+)\.js", u, re.I)
                        if id_match:
                            hubid = int(id_match.group(1))
                    _push(ev, "tracking", key, u, "url", hubid, "definitive")
        # Other patterns - use actual URL as match text
        table = [
            ("forms_v2_loader","forms","definitive"),  # Network = actual request = definitive
            ("forms_submit_v2","forms","definitive"),
            ("forms_submit_v3","forms","definitive"),
            ("chat_usemessages_api","chat","definitive"),
            ("chat_usemessages_js","chat","definitive"),
            ("cta_loader_legacy","ctas","definitive"),  # Network = definitive
            ("cta_redirect_link","ctas","definitive"),
            ("meetings_embed_js","meetings","definitive"),  # Network = definitive
            ("meetings_iframe","meetings","strong"),
            ("cms_host_hs_sites","cms","strong"),
            ("cms_files_hubspotusercontent","files","moderate"),
            ("video_hubspotvideo","video","strong"),
            ("email_hubspot_marketing_click","email","strong"),
            ("email_hubspot_sales_click","email","strong"),
            ("email_hubspotlinks","email","moderate")
        ]
        for key, cat, conf in table:
            r = RX.get(key)
            if r:
                m = r.search(u)
                if m:
                    _push(ev, cat, key, u, "url", None, conf)
    return ev

def summarise(evidence: List[Evidence]) -> dict:
    def has(cat: str) -> bool:
        return any(e["category"] == cat for e in evidence)

    tracking = has("tracking") or any(e["category"]=="cookies" and "hubspotutk" in e["match"].lower() for e in evidence)
    cms_hosting = any(e["category"]=="cms" and e["confidence"] in ("strong","definitive") for e in evidence)
    features = {
        "forms": has("forms"),
        "chat": has("chat"),
        "ctasLegacy": has("ctas"),
        "meetings": has("meetings"),
        "video": has("video"),
        "emailTrackingIndicators": any(e["category"]=="email" for e in evidence),
    }

    # Determine overall confidence level
    if not evidence:
        confidence = "weak"
    elif tracking and any(e.get("patternId")=="tracking_loader_script" and e.get("confidence")=="definitive" for e in evidence):
        confidence = "definitive"
    elif tracking:
        confidence = "strong"
    elif any(e.get("confidence") in ("strong", "definitive") for e in evidence):
        confidence = "moderate"
    else:
        confidence = "weak"

    return {
        "tracking": tracking,
        "cmsHosting": cms_hosting,
        "features": features,
        "confidence": confidence
    }

def make_result(url: str, evidence: List[Evidence], headers: Optional[dict] = None,
                http_status: Optional[int] = None, page_metadata: Optional[dict] = None) -> dict:
    hub_ids = []
    for e in evidence:
        hid = e.get("hubId")
        if isinstance(hid, int) and hid not in hub_ids:
            hub_ids.append(hid)
    summary = summarise(evidence)

    # Calculate hubspot_detected flag
    hubspot_detected = (
        summary.get("tracking", False) or
        summary.get("cmsHosting", False) or
        any(summary.get("features", {}).values())
    )

    result = {
        "url": url,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hubspot_detected": hubspot_detected,
        "hubIds": hub_ids,
        "summary": summary,
        "evidence": evidence,
        "headers": headers or {}
    }

    # Add optional fields if provided
    if http_status is not None:
        result["http_status"] = http_status
    if page_metadata is not None:
        result["page_metadata"] = page_metadata

    return result
