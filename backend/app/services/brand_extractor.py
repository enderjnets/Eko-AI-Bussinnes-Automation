import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Optional, Tuple


def extract_colors_from_css(css_text: str) -> list[str]:
    """Extract hex colors from CSS text."""
    # Match hex colors: #fff, #ffffff, #ffffff80
    hex_colors = re.findall(r'#(?:[0-9a-fA-F]{3}){1,2}(?:[0-9a-fA-F]{2})?', css_text)
    # Match rgb/rgba colors
    rgb_colors = re.findall(r'rgba?\([^)]+\)', css_text)
    return hex_colors + rgb_colors


def is_dark_color(hex_color: str) -> bool:
    """Determine if a hex color is dark (for contrast)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.5
    except (ValueError, IndexError):
        return False


def rank_colors(colors: list[str]) -> list[str]:
    """Rank colors by frequency and quality, removing near-duplicates."""
    from collections import Counter
    
    # Normalize colors
    normalized = []
    for c in colors:
        c = c.lower().strip()
        if c.startswith('#'):
            # Expand short hex
            if len(c) == 4:  # #rgb
                c = '#' + ''.join(x * 2 for x in c[1:])
            elif len(c) == 5:  # #rgba short
                c = '#' + ''.join(x * 2 for x in c[1:])
            elif len(c) == 7:  # #rrggbb
                pass
            elif len(c) == 9:  # #rrggbbaa
                c = c[:7]
        normalized.append(c)
    
    # Filter out common UI colors (white, black, gray variants)
    filtered = []
    for c in normalized:
        hex_part = c.lstrip('#')[:6]
        if len(hex_part) == 6:
            r = int(hex_part[0:2], 16)
            g = int(hex_part[2:4], 16)
            b = int(hex_part[4:6], 16)
            # Skip near-white, near-black, near-gray
            if r > 240 and g > 240 and b > 240:
                continue
            if r < 20 and g < 20 and b < 20:
                continue
            if abs(r - g) < 15 and abs(g - b) < 15 and abs(r - b) < 15:
                continue
        filtered.append(c)
    
    counts = Counter(filtered)
    # Sort by frequency, prefer colors that appear more than once
    ranked = [color for color, count in counts.most_common() if count >= 1]
    return ranked[:10]


def extract_brand_from_website(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract brand colors and logo from a website URL.
    Returns: (primary_color, secondary_color, logo_url)
    """
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        base_url = url
        
        all_colors = []
        
        # 1. Extract from inline styles
        for tag in soup.find_all(style=True):
            all_colors.extend(extract_colors_from_css(tag['style']))
        
        # 2. Extract from <style> tags
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                all_colors.extend(extract_colors_from_css(style_tag.string))
        
        # 3. Fetch and extract from linked CSS files
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if href:
                css_url = urljoin(base_url, href)
                try:
                    css_response = requests.get(css_url, headers=headers, timeout=10)
                    if css_response.status_code == 200:
                        all_colors.extend(extract_colors_from_css(css_response.text))
                except Exception:
                    pass
        
        # 4. Extract from meta theme-color
        theme_color = None
        meta_theme = soup.find('meta', attrs={'name': 'theme-color'})
        if meta_theme:
            theme_color = meta_theme.get('content')
        
        # Rank colors
        ranked = rank_colors(all_colors)
        
        primary_color = None
        secondary_color = None
        
        if theme_color:
            primary_color = theme_color.lower()
        elif ranked:
            primary_color = ranked[0]
        
        if len(ranked) > 1:
            # Pick secondary color that contrasts well with primary
            for c in ranked[1:]:
                if c != primary_color:
                    secondary_color = c
                    break
        
        # 5. Extract logo
        logo_url = None
        
        # Try favicon
        favicon = soup.find('link', rel=lambda x: x and 'icon' in x.lower())
        if favicon:
            logo_url = urljoin(base_url, favicon.get('href', ''))
        
        # Try og:image
        og_image = soup.find('meta', property='og:image')
        if og_image and not logo_url:
            logo_url = urljoin(base_url, og_image.get('content', ''))
        
        # Try logo in header/nav
        if not logo_url:
            for img in soup.find_all('img'):
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                if 'logo' in alt or 'logo' in src.lower():
                    logo_url = urljoin(base_url, src)
                    break
        
        return primary_color, secondary_color, logo_url
    
    except Exception as e:
        print(f"Brand extraction failed for {url}: {e}")
        return None, None, None
