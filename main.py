import fitz  # PyMuPDF
import json
import re
from collections import defaultdict
import time
import argparse
import sys
import os

"""
This script implements a sophisticated heuristic-based model for extracting a 
structured outline (Title, H1, H2, H3) from a PDF document.

V6.1 Changes:
- Added layout analysis to detect tabular and form-like structures.
- The script now intelligently ignores text within these structures when
  identifying headings, preventing table headers and form labels from being
  incorrectly added to the outline.
- Improved title detection to ignore file metadata that looks like a filename.
"""

def clean_text(text):
    """Removes common artifacts and extra whitespace from extracted text."""
    text = text.strip()
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    text = re.sub(r'\s+', ' ', text)
    return text

def is_page_tabular(page_blocks, y_tolerance=5, x_tolerance=10):
    """
    Analyzes block positions to detect if a page has a table or form-like structure.
    Returns True if a significant number of blocks are aligned in rows or columns.
    """
    if len(page_blocks) < 5: # Not enough blocks to be a complex table/form
        return False

    y_alignments = defaultdict(int)
    x_alignments = defaultdict(int)

    for block in page_blocks:
        # Group blocks by their vertical and horizontal positions
        y_alignments[round(block['y0'] / y_tolerance)] += 1
        x_alignments[round(block['bbox'][0] / x_tolerance)] += 1
    
    # Heuristic: If there are multiple rows with more than 2 items, it's likely a table/form.
    rows_with_multiple_items = sum(1 for count in y_alignments.values() if count > 2)
    if rows_with_multiple_items > 2:
        return True
        
    # Heuristic: If there are multiple columns with more than 2 items, it's likely a table/form.
    cols_with_multiple_items = sum(1 for count in x_alignments.values() if count > 2)
    if cols_with_multiple_items > 2:
        return True

    return False

def analyze_pdf_structure(pdf_path):
    """
    Main function to analyze a PDF and extract its structure.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {"error": f"Failed to open or process PDF: {e}"}
    
    # --- 1. Extract all text blocks
    blocks = []
    style_counts = defaultdict(int)
    page_map = defaultdict(list) # To store blocks per page for layout analysis

    for page_num, page in enumerate(doc):
        page_raw_blocks = page.get_text("blocks", sort=True)
        for i, b in enumerate(page_raw_blocks):
            text = clean_text(b[4])
            if not text or len(text) < 1:
                continue

            block_dict = page.get_text("dict", clip=b[:4])
            if not block_dict.get('blocks') or not block_dict['blocks'][0].get('lines') or not block_dict['blocks'][0]['lines'][0].get('spans'):
                continue
            
            span = block_dict['blocks'][0]['lines'][0]['spans'][0]
            
            is_bold = "bold" in span["font"].lower()
            style_key = (round(span["size"], 1), is_bold)
            style_counts[style_key] += len(text)
            
            block_info = {
                "text": text,
                "style_key": style_key,
                "page": page_num, # 0-indexed
                "y0": b[1],
                "bbox": b[:4] # Bounding box for layout analysis
            }
            blocks.append(block_info)
            page_map[page_num].append(block_info)

    if not blocks:
        return {"outline": []}

    # --- 2. Identify Body Text and Rank Heading Styles ---
    if not style_counts:
        return {"outline": []}
        
    body_style_key = max(style_counts, key=style_counts.get)
    
    heading_styles = []
    for style, count in style_counts.items():
        if style != body_style_key:
            size, is_bold = style
            rank = size * 10 + (5 if is_bold else 0)
            heading_styles.append({'style': style, 'rank': rank})
    
    sorted_heading_styles = sorted(heading_styles, key=lambda x: x['rank'], reverse=True)

    # --- 3. Identify Title ---
    title = None
    title_style = None
    if sorted_heading_styles:
        page0_blocks = [b for b in blocks if b['page'] == 0]
        for h_style in sorted_heading_styles:
            if any(b['style_key'] == h_style['style'] for b in page0_blocks):
                title_style = h_style['style']
                break
    
    if title_style:
        title_blocks = [b['text'] for b in page0_blocks if b['style_key'] == title_style]
        if title_blocks:
            title = " ".join(title_blocks)

    # --- 4. Hybrid Heading Identification (with table/form skipping) ---
    tabular_pages = {pn for pn, p_blocks in page_map.items() if is_page_tabular(p_blocks)}
    
    raw_outline = []
    style_level_map = {}
    if len(sorted_heading_styles) > 0: style_level_map[sorted_heading_styles[0]['style']] = "H1"
    if len(sorted_heading_styles) > 1: style_level_map[sorted_heading_styles[1]['style']] = "H2"
    if len(sorted_heading_styles) > 2: style_level_map[sorted_heading_styles[2]['style']] = "H3"

    for block in blocks:
        # Skip heading detection entirely for pages identified as tabular
        if block['page'] in tabular_pages:
            continue

        text = block['text']
        style = block['style_key']
        level = None

        match = re.match(r'^(\d+(\.\d+)*)\s+.+', text)
        if match:
            level_num = len(match.group(1).split('.'))
            level = f"H{min(level_num, 3)}"
        elif style in style_level_map:
            level = style_level_map[style]
        elif style == body_style_key and len(text.split()) < 6 and text.istitle() and not text.endswith('.'):
             level = "H1"

        if level and (not title or text not in title):
            raw_outline.append({
                "level": level,
                "text": text,
                "page": block["page"],
                "y0": block["y0"]
            })
            
    outline = sorted(raw_outline, key=lambda x: (x['page'], x['y0']))
    for item in outline:
        del item['y0']

    doc.close()
    
    # --- 5. Construct Final Output ---
    final_output = {"outline": outline}
    if title:
        final_output = {"title": clean_text(title), **final_output}
    
    return final_output


if __name__ == '__main__':
    BASE_DIR = "sample_dataset"
    INPUT_DIR = os.path.join(BASE_DIR, "pdfs")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if not os.path.exists(INPUT_DIR):
        print(f"Error: Input directory not found at {INPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf')]

    for pdf_file in pdf_files:
        print(f"Processing {pdf_file}...")
        input_path = os.path.join(INPUT_DIR, pdf_file)
        
        start_time = time.time()
        result = analyze_pdf_structure(input_path)
        execution_time = time.time() - start_time

        output_filename = os.path.splitext(pdf_file)[0] + '.json'
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        
        print(f"Finished processing {pdf_file} in {execution_time:.2f} seconds.")
        print(f"Output saved to {output_path}")
