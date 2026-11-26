import re
from collections import defaultdict

with open('F26_FYP1_Mid_Report_LaTeX_Complete/references/references.bib', 'r', encoding='utf-8') as f:
    text = f.read()

# Match each bib entry
entries = re.findall(r'@(\w+)\s*\{\s*([^,]+),(.*?)\n\}', text, re.DOTALL)

by_year = defaultdict(list)

for entry_type, key, body in entries:
    title_m = re.search(r'title\s*=\s*[\"{](.*?)[\"}],?', body)
    author_m = re.search(r'author\s*=\s*[\"{](.*?)[\"}],?', body)
    year_m = re.search(r'year\s*=\s*[\"{]?(\d{4})[\"}],?', body)
    venue_m = re.search(r'(?:journal|booktitle|publisher)\s*=\s*[\"{](.*?)[\"}],?', body)
    doi_m = re.search(r'doi\s*=\s*[\"{](.*?)[\"}],?', body)
    url_m = re.search(r'url\s*=\s*[\"{](.*?)[\"}],?', body)
    
    title = title_m.group(1).replace('{', '').replace('}', '') if title_m else 'N/A'
    author = author_m.group(1) if author_m else 'N/A'
    year = int(year_m.group(1)) if year_m else 0
    venue = venue_m.group(1).replace('{', '').replace('}', '') if venue_m else 'N/A'
    doi = doi_m.group(1) if doi_m else None
    url = url_m.group(1) if url_m else None
    
    by_year[year].append({
        'key': key,
        'type': entry_type,
        'author': author,
        'title': title,
        'venue': venue,
        'year': year,
        'doi': doi,
        'url': url
    })

total = sum(len(v) for v in by_year.values())
print(f"TOTAL REFERENCES: {total}\n")

for yr in sorted(by_year.keys(), reverse=True):
    print(f"### {yr} ({len(by_year[yr])} {'Paper' if len(by_year[yr])==1 else 'Papers'})")
    for item in by_year[yr]:
        link_str = f" [DOI/Link]({item['doi'] or item['url']})" if (item['doi'] or item['url']) else ""
        print(f"- **[{item['key']}]** {item['author']}. *\"{item['title']}\"*. **{item['venue']}**, {item['year']}.{link_str}")
    print()
