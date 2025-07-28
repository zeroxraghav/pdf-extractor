# Adobe Hackathon: Round 1A - Document Outline Extractor

This project is a solution for Round 1A of the Adobe Hackathon, "Connecting the Dots." It provides a high-performance, offline system for extracting a structured outline (Title, H1, H2, H3) from PDF documents and conforms to the specified directory structure and output schema.

## Our Approach

The core of this solution is a sophisticated **heuristic-based model** built in Python. Instead of relying on large, pre-trained AI models, this approach uses a set of intelligent rules to analyze the visual and structural properties of a PDF, mimicking how a human would identify its structure. This makes the solution extremely fast, lightweight, and fully compliant with the hackathon's offline and resource constraints.

The logic works in several key stages:

1.  **Style Analysis:** It first analyzes the entire document to identify all unique font styles (combinations of size and boldness) and determines the most common style, which is assumed to be the main body text.
2.  **Title Identification:** It robustly identifies the document's title by looking for the most visually prominent text on the first page, separate from the main outline.
3.  **Hybrid Heading Detection:** It uses a powerful two-pass system to find headings:
    - **Style-Based Pass:** It identifies text that is visually distinct from the body text (e.g., larger or bolder).
    - **Pattern-Based Pass:** It gives a high priority to text that follows a numbered list format (e.g., "1. Introduction", "2.1 Key Players"), which is a strong structural signal. It also intelligently strips these numbers from the final output.
4.  **Ranking and Output:** It ranks all heading candidates and maps them to H1, H2, and H3 levels, finally generating a clean JSON output that conforms to the provided schema.

This approach is designed to be highly resilient, handling a wide variety of document types, including academic papers, plain-text documents, and creative layouts.

## Libraries Used

- **PyMuPDF:** A high-performance Python library for accessing and extracting content from PDF documents. It was chosen for its speed, low memory footprint, and detailed style information.

## How to Build and Run

The solution is containerized using Docker

### Build the Docker Image

From the root directory (where the `Dockerfile` is located), run the following command:

```bash
docker build --platform linux/amd64 -t challenge_1a .

Run the Solution
The following command will run the container. It mounts the sample_dataset directory into the container, allowing the script to read from pdfs/ and write to outputs/.

docker run --rm -v "$(pwd)/sample_dataset:/app/sample_dataset" --network none challenge_1a
```
