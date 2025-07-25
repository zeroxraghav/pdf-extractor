# import fitz  # PyMuPDF
# import json
# import re
# from collections import defaultdict
# import time
# import argparse
# import sys

# """
# This script implements a sophisticated heuristic-based model for extracting a 
# structured outline (Title, H1, H2, H3) from a PDF document.

# V2 Changes:
# - Smarter Heading Identification: The logic now considers font weight (boldness)
#   as a key factor, not just size. This helps distinguish headings that are the
#   same size as body text but are bolded.
# - More Robust Style Analysis: Instead of just finding one body text style, it
#   analyzes the distribution of all font styles to better isolate headings as

#   statistical outliers.
# - Duplicate Title Removal: Automatically removes the first H1 if it's identical
#   to the document's main title, cleaning up the output.
# """

# def clean_text(text):
#     """Removes common artifacts and extra whitespace from extracted text."""
#     text = text.strip()
#     text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
#     text = re.sub(r'\s+', ' ', text)
#     return text

# def analyze_pdf_structure(pdf_path):
#     """
#     Main function to analyze a PDF and extract its structure.
#     """
#     try:
#         doc = fitz.open(pdf_path)
#     except Exception as e:
#         return {"error": f"Failed to open or process PDF: {e}"}

#     if doc.page_count > 50:
#         return {"error": "PDF exceeds the 50-page limit."}

#     # --- 1. Extract all text blocks with detailed style information ---
#     blocks = []
#     style_counts = defaultdict(int)

#     for page_num, page in enumerate(doc):
#         page_blocks = page.get_text("dict").get("blocks", [])
#         for block in page_blocks:
#             if "lines" in block:
#                 for line in block["lines"]:
#                     for span in line["spans"]:
#                         text = clean_text(span["text"])
#                         if not text:
#                             continue
                        
#                         # Use a more detailed style key: size and boldness
#                         is_bold = "bold" in span["font"].lower()
#                         style_key = (span["size"], is_bold)
#                         style_counts[style_key] += len(text)
                        
#                         blocks.append({
#                             "text": text,
#                             "style_key": style_key,
#                             "size": span["size"],
#                             "is_bold": is_bold,
#                             "font": span["font"],
#                             "page": page_num + 1
#                         })

#     if not blocks:
#         return {"title": "Empty or Image-Only PDF", "outline": []}

#     # --- 2. Identify the primary body text style ---
#     if not style_counts:
#         return {"title": "No text found in PDF", "outline": []}
        
#     body_style_key = max(style_counts, key=style_counts.get)
#     body_size, body_is_bold = body_style_key

#     # --- 3. Identify and Rank Heading Styles ---
#     heading_candidates = []
#     for style, count in style_counts.items():
#         size, is_bold = style
#         # A style is a heading candidate if it's NOT the body style AND
#         # it's either larger, or the same size but bold (if body isn't).
#         if style != body_style_key:
#             if size > body_size or (size == body_size and is_bold and not body_is_bold):
#                  # Rank styles: size is primary, boldness is a secondary factor.
#                 rank_score = size * 10 + (5 if is_bold else 0)
#                 heading_candidates.append({'style': style, 'rank': rank_score})
    
#     # Sort candidates by their rank score, highest first
#     sorted_headings = sorted(heading_candidates, key=lambda x: x['rank'], reverse=True)
    
#     # --- 4. Map top ranked styles to H1, H2, H3 ---
#     level_map = {}
#     if len(sorted_headings) > 0:
#         level_map[sorted_headings[0]['style']] = "H1"
#     if len(sorted_headings) > 1:
#         level_map[sorted_headings[1]['style']] = "H2"
#     if len(sorted_headings) > 2:
#         level_map[sorted_headings[2]['style']] = "H3"

#     # --- 5. Extract Title ---
#     title = doc.metadata.get('title', '')
#     if not title or len(title) < 4:
#         # Find the text block with the highest rank on the first page
#         first_page_blocks = sorted(
#             [b for b in blocks if b["page"] == 1 and b['style_key'] in level_map],
#             key=lambda b: level_map.get(b['style_key'], 'H9'), # Sort by H1, H2, etc.
#             reverse=False # H1 comes first
#         )
#         if first_page_blocks:
#             title = first_page_blocks[0]['text']
#         else: # Fallback to just the largest text on page 1
#             first_page_largest = sorted([b for b in blocks if b["page"] == 1], key=lambda x: x['size'], reverse=True)
#             if first_page_largest:
#                 title = first_page_largest[0]['text']
#             else:
#                 title = "Untitled Document"

#     # --- 6. Build the final outline ---
#     outline = []
#     for block in blocks:
#         if block["style_key"] in level_map:
#             # Filter out page numbers or simple numeric/dot patterns
#             if not re.match(r'^[\d\.\s]+$', block["text"]):
#                  outline.append({
#                     "level": level_map[block["style_key"]],
#                     "text": block["text"],
#                     "page": block["page"]
#                 })
    
#     # --- 7. Clean up: Remove duplicate title from outline ---
#     if outline and outline[0]['level'] == 'H1' and outline[0]['text'] == title:
#         outline.pop(0)

#     doc.close()
    
#     return {
#         "title": clean_text(title),
#         "outline": outline
#     }


# if __name__ == '__main__':
#     parser = argparse.ArgumentParser(description="Extract a structured outline from a PDF.")
#     parser.add_argument("pdf_path", type=str, help="The full path to the PDF file.")
#     args = parser.parse_args()

#     start_time = time.time()
#     result = analyze_pdf_structure(args.pdf_path)
#     execution_time = time.time() - start_time

#     if "error" in result:
#         print(json.dumps(result, indent=2))
#     else:
#         print(json.dumps(result, indent=2))
#         print(f"\n--- Performance ---", file=sys.stderr)
#         print(f"Execution Time: {execution_time:.4f} seconds", file=sys.stderr)
