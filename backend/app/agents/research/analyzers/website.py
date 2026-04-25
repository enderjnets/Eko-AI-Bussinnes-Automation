import re
from typing import Optional, Dict

import httpx
from bs4 import BeautifulSoup

import logging

logger = logging.getLogger(__name__)


class WebsiteAnalyzer:
    """Analyze a business website to extract insights."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )

    async def analyze(self, url: str) -> Dict:
        """
        Fetch and analyze a website.

        Returns:
            Dict with: title, description, technologies_detected, has_chatbot,
            has_booking, has_contact_form, social_links, email_found,
            services, pricing_info, hours, about_text, team_names,
            has_ecommerce, has_blog, has_newsletter
        """
        if not url.startswith("http"):
            url = f"https://{url}"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return {"error": str(e), "url": url}

        soup = BeautifulSoup(response.text, "html.parser")
        html_text = response.text.lower()

        # Extract basic info
        title = soup.title.string.strip() if soup.title else ""

        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc["content"] if meta_desc else ""

        if not description:
            og_desc = soup.find("meta", attrs={"property": "og:description"})
            description = og_desc["content"] if og_desc else ""

        # Detect technologies
        technologies = []
        tech_indicators = {
            "WordPress": "wp-content",
            "Shopify": "myshopify",
            "Squarespace": "squarespace",
            "Wix": "wix",
            "React": "react",
            "Vue": "vue",
            "Angular": "angular",
            "Stripe": "stripe",
            "PayPal": "paypal",
            "Calendly": "calendly",
            "HubSpot": "hubspot",
            "Mailchimp": "mailchimp",
            "Google Analytics": "google-analytics",
            "Facebook Pixel": "fbevents",
            "Intercom": "intercom",
            "Zendesk": "zendesk",
            "Drift": "drift",
            "Tidio": "tidio",
            "Tawk.to": "tawk",
            "Crisp": "crisp",
            "LiveChat": "livechat",
            "OpenTable": "opentable",
            "Square": "squareup",
            "Toast": "toasttab",
            "MindBody": "mindbodyonline",
        }

        for tech, indicator in tech_indicators.items():
            if indicator in html_text:
                technologies.append(tech)

        # Detect features
        has_chatbot = any(
            indicator in html_text
            for indicator in ["chatbot", "livechat", "intercom", "drift", "tawk", "crisp", "tidio"]
        )

        has_booking = any(
            indicator in html_text
            for indicator in ["book now", "schedule", "appointment", "reservation", "calendly"]
        )

        has_contact_form = bool(soup.find("form")) or "contact" in html_text

        # Extract social links
        social_links = {}
        social_domains = {
            "facebook": "facebook.com",
            "instagram": "instagram.com",
            "twitter": "twitter.com",
            "linkedin": "linkedin.com",
            "youtube": "youtube.com",
            "tiktok": "tiktok.com",
        }

        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            for platform, domain in social_domains.items():
                if domain in href and platform not in social_links:
                    social_links[platform] = a["href"]

        # Try to find email on page
        email_found = self._extract_emails(response.text, soup)

        # If no email found, try contact page
        if not email_found:
            email_found = await self._try_contact_page(url)

        # Extract services offered
        services = self._extract_services(soup)

        # Extract pricing mentions
        pricing_info = self._extract_pricing(soup, html_text)

        # Extract business hours
        hours = self._extract_hours(soup, html_text)

        # Extract about text
        about_text = self._extract_about(soup)

        # Extract team/owner names
        team_names = self._extract_team(soup)

        # Detect additional features
        has_ecommerce = any(
            indicator in html_text
            for indicator in ["cart", "checkout", "shop", "product", "buy now", "add to cart"]
        )
        has_blog = any(
            indicator in html_text
            for indicator in ["/blog", "blog.", "latest posts", "articles"]
        )
        has_newsletter = any(
            indicator in html_text
            for indicator in ["newsletter", "subscribe", "join our list", "email list"]
        )

        # Check for online ordering / delivery
        has_online_ordering = any(
            indicator in html_text
            for indicator in ["order online", "online ordering", "delivery", "pickup"]
        )

        return {
            "url": url,
            "title": title,
            "description": description,
            "technologies_detected": technologies,
            "has_chatbot": has_chatbot,
            "has_booking": has_booking,
            "has_contact_form": has_contact_form,
            "social_links": social_links,
            "email_found": email_found,
            "services": services,
            "pricing_info": pricing_info,
            "hours": hours,
            "about_text": about_text,
            "team_names": team_names,
            "has_ecommerce": has_ecommerce,
            "has_blog": has_blog,
            "has_newsletter": has_newsletter,
            "has_online_ordering": has_online_ordering,
        }

    def _extract_emails(self, text: str, soup: BeautifulSoup = None) -> Optional[str]:
        """Extract the most likely business email from page text, mailto links, and schema.org."""
        all_emails = []

        # 1. Regex from raw HTML
        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        all_emails.extend(email_pattern.findall(text))

        # 2. mailto: links
        if soup:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    if email and "@" in email:
                        all_emails.append(email)

            # 3. Schema.org JSON-LD
            import json as _json
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = _json.loads(script.string or "{}")
                    def find_emails(obj):
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if k == "email" and isinstance(v, str) and "@" in v:
                                    all_emails.append(v)
                                elif isinstance(v, (dict, list)):
                                    find_emails(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                find_emails(item)
                    find_emails(data)
                except Exception:
                    pass

        if all_emails:
            # Filter out platform / fake emails
            blocked_domains = [
                "example.com", "test.com", "domain.com", "email.com",
                "sentry.io", "sentry.com", "sentry-next.wixpress.com",
                "wixpress.com", "wix.com", "editorx.com",
                "squarespace.com", "squarespace-mail.com",
                "shopify.com", "myshopify.com",
                "weebly.com", "webflow.io", "webflow.com",
                "wordpress.com", "wp.com", "wpengine.com",
                "godaddy.com", "hostgator.com", "bluehost.com",
                "google.com", "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
                "facebook.com", "instagram.com", "twitter.com", "x.com",
                "linkedin.com", "youtube.com", "tiktok.com",
            ]
            blocked_patterns = [
                "noreply", "no-reply", "donotreply", "do-not-reply",
                "support@shopify", "support@wix", "admin@wordpress",
                "info@wordpress", "help@wordpress", "test@",
                "example@", "user@", "admin@", "postmaster@",
                "abuse@", "webmaster@", "hostmaster@",
            ]

            filtered = []
            for e in all_emails:
                e_lower = e.lower()
                if e.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
                    continue
                if any(bd in e_lower for bd in blocked_domains):
                    continue
                if any(bp in e_lower for bp in blocked_patterns):
                    continue
                filtered.append(e)

            if filtered:
                preferred_prefixes = ["info@", "contact@", "hello@", "admin@", "support@", "sales@", "booking@", "appointments@"]
                preferred = [e for e in filtered if any(e.lower().startswith(p) for p in preferred_prefixes)]
                return preferred[0] if preferred else filtered[0]
        return None

    async def _try_contact_page(self, base_url: str) -> Optional[str]:
        """Try to find email on /contact or /about pages."""
        for path in ["/contact", "/contact-us", "/about", "/about-us"]:
            try:
                url = base_url.rstrip("/") + path
                resp = await self.client.get(url, timeout=10.0)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    email = self._extract_emails(resp.text, soup)
                    if email:
                        return email
            except Exception:
                continue
        return None

    def _extract_services(self, soup: BeautifulSoup) -> list:
        """Try to extract list of services from common sections."""
        services = []
        # Common section headings for services
        service_keywords = ["services", "what we offer", "our services", "treatments", "menu", "pricing", "specialties"]

        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = heading.get_text(strip=True).lower()
            if any(kw in text for kw in service_keywords):
                # Look at next sibling lists or paragraphs
                next_elem = heading.find_next_sibling()
                for _ in range(5):  # Check next 5 siblings
                    if next_elem is None:
                        break
                    if next_elem.name in ["ul", "ol"]:
                        for li in next_elem.find_all("li"):
                            svc = li.get_text(strip=True)
                            if svc and len(svc) > 2:
                                services.append(svc)
                    elif next_elem.name == "div":
                        # Maybe a grid of services
                        for item in next_elem.find_all(["h3", "h4", "p", "span"]):
                            svc = item.get_text(strip=True)
                            if svc and len(svc) > 2 and len(svc) < 100:
                                services.append(svc)
                    next_elem = next_elem.find_next_sibling()

        # Deduplicate and limit
        seen = set()
        unique = []
        for s in services:
            key = s.lower()
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique[:15]

    def _extract_pricing(self, soup: BeautifulSoup, html_text: str) -> Optional[str]:
        """Extract pricing mentions."""
        price_indicators = ["$", "price", "pricing", "cost", "rate", "from ", "starting at"]
        # Look for pricing sections
        for heading in soup.find_all(["h1", "h2", "h3"]):
            text = heading.get_text(strip=True).lower()
            if "price" in text or "menu" in text or "rates" in text:
                section_text = ""
                next_elem = heading.find_next_sibling()
                for _ in range(3):
                    if next_elem is None:
                        break
                    section_text += next_elem.get_text(separator=" ", strip=True) + " "
                    next_elem = next_elem.find_next_sibling()
                if section_text:
                    return section_text[:500].strip()
        return None

    def _extract_hours(self, soup: BeautifulSoup, html_text: str) -> Optional[str]:
        """Extract business hours if available."""
        for heading in soup.find_all(["h2", "h3", "h4", "strong", "b"]):
            text = heading.get_text(strip=True).lower()
            if "hours" in text or "open" in text or "schedule" in text:
                next_elem = heading.find_next_sibling()
                if next_elem:
                    hours_text = next_elem.get_text(separator=" ", strip=True)
                    if hours_text and len(hours_text) > 5:
                        return hours_text[:300]
        # Also check for schema.org OpeningHoursSpecification
        hours_meta = soup.find("div", class_=re.compile(r"hours|open", re.I))
        if hours_meta:
            return hours_meta.get_text(separator=" ", strip=True)[:300]
        return None

    def _extract_about(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract about us / story text."""
        for heading in soup.find_all(["h1", "h2", "h3"]):
            text = heading.get_text(strip=True).lower()
            if any(kw in text for kw in ["about us", "our story", "who we are", "about", "meet the team"]):
                section_text = ""
                next_elem = heading.find_next_sibling()
                for _ in range(4):
                    if next_elem is None:
                        break
                    section_text += next_elem.get_text(separator=" ", strip=True) + " "
                    next_elem = next_elem.find_next_sibling()
                if section_text:
                    return section_text[:800].strip()
        return None

    def _extract_team(self, soup: BeautifulSoup) -> list:
        """Extract team member or owner names."""
        names = []
        for heading in soup.find_all(["h2", "h3", "h4"]):
            text = heading.get_text(strip=True).lower()
            if any(kw in text for kw in ["team", "staff", "our people", "meet", "owner", "founder"]):
                next_elem = heading.find_next_sibling()
                for _ in range(5):
                    if next_elem is None:
                        break
                    # Look for strong/b tags with names
                    for name_tag in next_elem.find_all(["strong", "b", "h3", "h4"]):
                        name = name_tag.get_text(strip=True)
                        if name and 2 < len(name) < 40 and not any(x in name.lower() for x in ["team", "staff", "meet", "our"]):
                            names.append(name)
                    next_elem = next_elem.find_next_sibling()
        # Deduplicate
        seen = set()
        unique = []
        for n in names:
            key = n.lower()
            if key not in seen:
                seen.add(key)
                unique.append(n)
        return unique[:5]

    async def close(self):
        await self.client.aclose()
