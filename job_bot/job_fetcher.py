from __future__ import annotations

import hashlib
import html
import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from job_bot.models import JobPosting


TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
JSONLD_SCRIPT_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
LOW_CONFIDENCE_TEXT_LENGTH = 200
ATS_URL_COMPANY_PATTERNS = [
    re.compile(r"^jobs\.ashbyhq\.com$"),
    re.compile(r"^(job-)?boards(\.eu)?\.greenhouse\.io$"),
    re.compile(r"^jobs\.lever\.co$"),
]
PERSONIO_SUBDOMAIN_RE = re.compile(r"^([a-z0-9-]+)\.jobs\.personio\.(de|com)$")


class ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self.parts.append(cleaned)


def fetch_job_from_url(url: str, timeout_seconds: int = 20) -> JobPosting:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 AppleWebKit/537.36 "
                "KHTML, like Gecko Chrome/120 Safari/537.36"
            )
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            content_type = response.headers.get("content-type", "")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not fetch job URL: {exc}") from exc

    charset = "utf-8"
    match = re.search(r"charset=([^;]+)", content_type, re.IGNORECASE)
    if match:
        charset = match.group(1).strip()

    page_html = raw.decode(charset, errors="replace")
    fallback_title = extract_title(page_html) or "Fetched Job Posting"

    jsonld_job = extract_jsonld_job_posting(page_html)
    if jsonld_job is not None:
        title = str(jsonld_job.get("title") or fallback_title)
        description_html = str(jsonld_job.get("description") or "")
        text = clean_text(HTMLTextOnly.strip_tags(description_html)) if description_html else ""
        if not text:
            text = extract_readable_text(page_html)
        company = extract_company_from_jsonld(jsonld_job) or infer_company(title)
        location = extract_location_from_jsonld(jsonld_job)
    else:
        title = fallback_title
        text = extract_readable_text(page_html)
        company = infer_company(title)
        location = ""

    company = company or infer_company_from_url(url) or "Unknown Company"

    return JobPosting(
        id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
        title=title,
        company=company,
        location=location,
        url=url,
        description=text[:12000],
        requirements=infer_requirements(text),
        description_confidence=(
            "low" if len(text.strip()) < LOW_CONFIDENCE_TEXT_LENGTH else "high"
        ),
    )


def extract_title(page_html: str) -> str:
    match = TITLE_RE.search(page_html)
    if not match:
        return ""
    return " ".join(HTMLTextOnly.strip_tags(match.group(1)).split())


def extract_readable_text(page_html: str) -> str:
    parser = ReadableHTMLParser()
    parser.feed(page_html)
    return "\n".join(parser.parts)


def extract_jsonld_job_posting(page_html: str) -> dict[str, Any] | None:
    for script_match in JSONLD_SCRIPT_RE.finditer(page_html):
        raw = script_match.group(1).strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        job_posting = find_job_posting(parsed)
        if job_posting is not None:
            return job_posting
    return None


def find_job_posting(node: Any) -> dict[str, Any] | None:
    if isinstance(node, dict):
        if node.get("@type") == "JobPosting":
            return node
        for value in node.values():
            found = find_job_posting(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find_job_posting(item)
            if found is not None:
                return found
    return None


def extract_company_from_jsonld(job_posting: dict[str, Any]) -> str:
    organization = job_posting.get("hiringOrganization")
    if isinstance(organization, dict):
        name = organization.get("name")
        if name:
            return str(name)
    return ""


def extract_location_from_jsonld(job_posting: dict[str, Any]) -> str:
    raw_locations = job_posting.get("jobLocation")
    locations = raw_locations if isinstance(raw_locations, list) else [raw_locations]
    parts: list[str] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address")
        if not isinstance(address, dict):
            continue
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            value = address.get(key)
            if value and str(value) not in parts:
                parts.append(str(value))
    return ", ".join(parts)


def clean_text(text: str) -> str:
    return " ".join(html.unescape(text).split())


def infer_company(title: str) -> str:
    for separator in [" | ", " - ", " – ", " — ", " @ ", " at "]:
        if separator in title:
            return title.split(separator)[-1].strip()
    return ""


def infer_company_from_url(url: str) -> str:
    """Last-resort company inference for known ATS URL shapes, used when
    JSON-LD's hiringOrganization is missing/empty (seen in the wild on some
    Personio boards) and the title has no usable separator. Ashby/Greenhouse/
    Lever put the company slug in the path; Personio puts it in the
    subdomain."""
    parsed = urlparse(url)
    host = parsed.netloc.casefold()

    personio_match = PERSONIO_SUBDOMAIN_RE.match(host)
    if personio_match:
        return slug_to_name(personio_match.group(1))

    if any(pattern.match(host) for pattern in ATS_URL_COMPANY_PATTERNS):
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments:
            return slug_to_name(segments[0])

    return ""


def slug_to_name(slug_value: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", slug_value) if part)


def infer_requirements(text: str) -> list[str]:
    requirements = []
    keywords = [
        "Python",
        "Java",
        "C++",
        "JavaScript",
        "SQL",
        "Machine Learning",
        "Deep Learning",
        "NLP",
        "Computer Vision",
        "Django",
        "Docker",
        "Git",
        "Power BI",
        "PostgreSQL",
        "MongoDB",
        "TensorFlow",
        "Keras",
        "Scikit-learn",
    ]
    folded = text.casefold()
    for keyword in keywords:
        if keyword.casefold() in folded:
            requirements.append(keyword)
    return requirements


class HTMLTextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    @classmethod
    def strip_tags(cls, page_html: str) -> str:
        parser = cls()
        parser.feed(page_html)
        return "".join(parser.parts)
