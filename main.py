import fitz  # PyMuPDF
import json
import re
from collections import defaultdict
import time
import argparse
import sys

"""
This script implements a sophisticated heuristic-based model for extracting a 
structured outline (Title, H1, H2, H3) from a PDF document.

V2.3 Changes:
- Stricter Heading Detection: A style is now only considered a heading if it is
  at least 10% larger than the body text, or if it's bold. This prevents minor,
  unintentional font variations from being misclassified as headings.
- More Reliable Title Logic: A title is only sought if the document has a
  clear structure with headings.
"""

def clean_text(text):
    """Removes common artifacts and extra whitespace from extracted text."""
    text = text.strip()
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    text = re.sub(r'\s+', ' ', text)
    return text

def analyze_pdf_structure(pdf_path):
    """
    Main function to analyze a PDF and extract its structure.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {"error": f"Failed to open or process PDF: {e}"}

    if doc.page_count > 50:
        return {"error": "PDF exceeds the 50-page limit."}

    # --- 1. Extract all text blocks with detailed style information ---
    blocks = []
    style_counts = defaultdict(int)

    for page_num, page in enumerate(doc):
        page_blocks = page.get_text("dict").get("blocks", [])
        for block in page_blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = clean_text(span["text"])
                        if not text:
                            continue
                        
                        is_bold = "bold" in span["font"].lower()
                        # Round size to 1 decimal place to group similar sizes
                        style_key = (round(span["size"], 1), is_bold)
                        style_counts[style_key] += len(text)
                        
                        blocks.append({
                            "text": text,
                            "style_key": style_key,
                            "size": span["size"],
                            "is_bold": is_bold,
                            "font": span["font"],
                            "page": page_num + 1
                        })

    if not blocks:
        return {"outline": []}

    # --- 2. Identify the primary body text style ---
    if not style_counts:
        return {"outline": []}
        
    body_style_key = max(style_counts, key=style_counts.get)
    body_size, body_is_bold = body_style_key

    # --- 3. Identify Heading Candidates with Stricter Criteria ---
    heading_candidates = []
    # A heading must be noticeably larger (e.g., >10%) or bold.
    SIZE_THRESHOLD = 1.1 
    for style, count in style_counts.items():
        size, is_bold = style
        if style != body_style_key:
            # Condition: Is the font size at least 10% larger?
            is_significantly_larger = size > (body_size * SIZE_THRESHOLD)
            # Condition: Is the font size similar, but bold (while body is not)?
            is_same_size_but_bold = (abs(size - body_size) < 0.5 and is_bold and not body_is_bold)

            if is_significantly_larger or is_same_size_but_bold:
                rank_score = size * 10 + (5 if is_bold else 0)
                heading_candidates.append({'style': style, 'rank': rank_score})
    
    title = None
    outline = []

    # --- 4. LOGIC BRANCH: Decide based on whether headings were found ---
    if heading_candidates:
        # --- Structured Document Logic ---
        sorted_headings = sorted(heading_candidates, key=lambda x: x['rank'], reverse=True)
        
        level_map = {}
        if len(sorted_headings) > 0:
            level_map[sorted_headings[0]['style']] = "H1"
        if len(sorted_headings) > 1:
            level_map[sorted_headings[1]['style']] = "H2"
        if len(sorted_headings) > 2:
            level_map[sorted_headings[2]['style']] = "H3"

        # Extract Title from potential headings
        title = doc.metadata.get('title', '')
        if not title or len(title) < 4:
            first_page_blocks = sorted(
                [b for b in blocks if b["page"] == 1 and b['style_key'] in level_map],
                key=lambda b: level_map.get(b['style_key'], 'H9'),
                reverse=False
            )
            if first_page_blocks:
                title = first_page_blocks[0]['text']
            else: 
                title = None # No reliable title found
        
        # Build outline from headings
        for block in blocks:
            if block["style_key"] in level_map:
                if not re.match(r'^[\d\.\s]+$', block["text"]):
                     outline.append({
                        "level": level_map[block["style_key"]],
                        "text": block["text"],
                        "page": block["page"]
                    })
        
        # Clean up duplicate title
        if title and outline and outline[0]['level'] == 'H1' and outline[0]['text'] == title:
            outline.pop(0)
    else:
        # --- Plain Text Document Logic ---
        # No headings found, so the outline is empty and there is no title.
        pass

    doc.close()
    
    # --- 5. Construct Final Output ---
    final_output = {"outline": outline}
    if title:
        final_output = {"title": clean_text(title), **final_output}
    
    return final_output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extract a structured outline from a PDF.")
    parser.add_argument("pdf_path", type=str, help="The full path to the PDF file.")
    args = parser.parse_args()

    start_time = time.time()
    result = analyze_pdf_structure(args.pdf_path)
    execution_time = time.time() - start_time

    if "error" in result:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
        print(f"\n--- Performance ---", file=sys.stderr)
        print(f"Execution Time: {execution_time:.4f} seconds", file=sys.stderr)
