"""Split the policy docs into one chunk per '## ' section (for RAG)."""

from pathlib import Path


def chunk_docs(docs_dir: str = "docs") -> list[dict]:
    """Split each .md file in docs_dir into one chunk per '## ' section.

    Each chunk looks like:
      {"id": "returns#2", "doc": "returns", "heading": "Items that can't be returned",
       "text": "<doc title> > <heading>\n<section body>"}
    """
    chunks = []

    for path in sorted(Path(docs_dir).glob("*.md")):
        doc = path.stem
        title = None
        current_heading = None
        current_lines = []

        def save():
            body = "\n".join(current_lines).strip()
            if current_heading is None or not body:
                return
            n = sum(1 for c in chunks if c["doc"] == doc) + 1
            chunks.append({
                "id": f"{doc}#{n}",
                "doc": doc,
                "heading": current_heading,
                "text": f"{title} > {current_heading}\n{body}",
            })

        for line in path.read_text().splitlines():
            if line.startswith("# ") and title is None:
                title = line[2:].strip()
            elif line.startswith("## "):
                save()
                current_heading = line[3:].strip()
                current_lines = []
            elif current_heading is not None:
                current_lines.append(line)

        save()  # last section: no '## ' after it to trigger the save

    return chunks


if __name__ == "__main__":
    chunks = chunk_docs()
    print(len(chunks))
    print(chunks[0])
