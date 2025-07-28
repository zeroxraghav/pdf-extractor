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

This version is adapted for Docker execution as per the hackathon rules.
It reads all PDF files from an /app/input directory and writes a corresponding
JSON file for each to an /app/output directory.
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
    
    # --- 1. Extract all text blocks
    blocks = []
    style_counts = defaultdict(int)

    for page_num, page in enumerate(doc):
        page_blocks = page.get_text("blocks", sort=True)
        for i, b in enumerate(page_blocks):
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
            
            blocks.append({
                "text": text,
                "style_key": style_key,
                "size": span["size"],
                "is_bold": is_bold,
                "page": page_num, # Using 0-indexed pages
                "block_num": i,
                "y0": b[1]
            })

    if not blocks:
        return {"outline": []}

    # --- 2. Identify Body Text and Heading Styles ---
    if not style_counts:
        return {"outline": []}
        
    body_style_key = max(style_counts, key=style_counts.get)
    body_size, _ = body_style_key
    
    heading_styles = {}
    SIZE_THRESHOLD = 1.05
    for style, count in style_counts.items():
        size, is_bold = style
        if style != body_style_key:
            if size > (body_size * SIZE_THRESHOLD) or (abs(size - body_size) < 0.5 and is_bold):
                rank = size * 10 + (5 if is_bold else 0)
                heading_styles[style] = rank

    # --- 3. Identify Title FIRST
    title = None
    title = doc.metadata.get('title', '')
    if not title or len(title) < 5:
        # Look for title on page 0
        page0_blocks = [b for b in blocks if b['page'] == 0]
        page0_heading_styles = {k:v for k,v in heading_styles.items() if k in [b['style_key'] for b in page0_blocks]}
        
        if page0_heading_styles:
            top_style_rank = max(page0_heading_styles.values())
            top_style = next(k for k,v in page0_heading_styles.items() if v == top_style_rank)
            title_block = next((b for b in page0_blocks if b['style_key'] == top_style), None)
            if title_block:
                title = title_block['text']

    # --- 4. Hybrid Heading Identification ---
    candidates = {}
    
    # Pass 1: Style-based
    for block in blocks:
        if block['style_key'] in heading_styles:
            key = (block['page'], block['block_num'])
            candidates[key] = {'block': block, 'score': heading_styles[block['style_key']]}

    # Pass 2: Pattern-based
    for block in blocks:
        match = re.match(r'^(\d+(\.\d+)*)\s*(.*)', block['text'])
        if match:
            number_part = match.group(1)
            if len(number_part) == 4 and '.' not in number_part:
                continue

            level_num = len(number_part.split('.'))
            score_bonus = 200 - (level_num * 10)
            key = (block['page'], block['block_num'])
            
            modified_block = block.copy()
            cleaned_text = match.group(3).strip()
            if not cleaned_text: continue
            modified_block['text'] = cleaned_text

            if key in candidates:
                candidates[key]['score'] += score_bonus
                candidates[key]['block'] = modified_block
                candidates[key]['level_num'] = level_num # Add direct level
            else:
                candidates[key] = {'block': modified_block, 'score': score_bonus, 'level_num': level_num}

    if not candidates:
        return {"title": title, "outline": []} if title else {"outline": []}

    # --- 5. Rank and Build Final Outline ---
    sorted_candidates = sorted(candidates.values(), key=lambda x: x['score'], reverse=True)
    
    score_tiers = sorted(list(set(c['score'] for c in sorted_candidates)), reverse=True)
    level_map = {}
    if len(score_tiers) > 0: level_map[score_tiers[0]] = "H1"
    if len(score_tiers) > 1: level_map[score_tiers[1]] = "H2"
    if len(score_tiers) > 2: level_map[score_tiers[2]] = "H3"

    raw_outline = []
    for cand in sorted_candidates:
        score = cand['score']
        block = cand['block']
        level_num = cand.get('level_num')

        final_level = None
        if level_num:
            final_level = f"H{min(level_num, 6)}" # Prioritize direct mapping
        elif score in level_map:
            final_level = level_map[score] # Fallback to style-based mapping

        if final_level and block['text'] != title and not re.match(r'^\d+$', block["text"].strip()):
            raw_outline.append({
                "level": final_level, 
                "text": block["text"], 
                "page": block["page"],
                "y0": block["y0"]
            })

    outline = sorted(raw_outline, key=lambda x: (x['page'], x['y0']))
    for item in outline: del item['y0']

    doc.close()
    
    # --- 6. Construct Final Output ---
    final_output = {"outline": outline}
    if title:
        final_output = {"title": clean_text(title), **final_output}
    
    return final_output


if __name__ == '__main__':
     # Setup to allow running both locally and in Docker
    parser = argparse.ArgumentParser(description="Extract a structured outline from a PDF.")
    parser.add_argument('--input-dir', default='/app/input', help='The directory to read PDFs from.')
    parser.add_argument('--output-dir', default='/app/output', help='The directory to write JSON files to.')
    args = parser.parse_args()

    INPUT_DIR = args.input_dir
    OUTPUT_DIR = args.output_dir

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf')]

    for pdf_file in pdf_files:
        print(f"Processing {pdf_file}...")
        input_path = os.path.join(INPUT_DIR, pdf_file)
        
        start_time = time.time()
        result = analyze_pdf_structure(input_path)
        execution_time = time.time() - start_time

        output_filename = os.path.splitext(pdf_file)[0] + '.json'
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Finished processing {pdf_file} in {execution_time:.2f} seconds.")
        print(f"Output saved to {output_path}")