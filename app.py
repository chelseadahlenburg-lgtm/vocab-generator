import os
import io
import base64
import fitz
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

st.set_page_config(page_title="Fixed Template Vocab Generator", layout="wide")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TEMPLATE_PATH = "templates/master_template.pdf"
OUTPUT_DPI = 200

# Adjust these once only if needed
TITLE_BOX = (80, 35, 1150, 115)
WORD_BOXES = [
    (75, 420, 310, 455), (75, 625, 310, 660), (75, 830, 310, 865),
    (75, 1035, 310, 1070), (75, 1240, 310, 1275), (75, 1445, 310, 1480),
]
IMAGE_BOXES = [
    (90, 460, 295, 610), (90, 665, 295, 815), (90, 870, 295, 1020),
    (90, 1075, 295, 1225), (90, 1280, 295, 1430), (90, 1485, 295, 1635),
]

DEFAULT_WORDS = {
    "australian cropping": [
        "Crop", "Grain", "Wheat", "Soil", "Sowing", "Germination",
        "Irrigation", "Fertiliser", "Weed", "Pest", "Harvest", "Yield"
    ],
    "steer selection and marketing": [
        "Steer", "Conformation", "Muscling", "Fat Cover", "Liveweight", "Growth Rate",
        "Feed Efficiency", "Carcase", "Yield", "Market Specifications", "Profitability", "Marketing"
    ],
}

def load_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def render_pdf_pages():
    doc = fitz.open(TEMPLATE_PATH)
    pages = []
    zoom = OUTPUT_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        pages.append(img)
    return pages

def choose_words(topic):
    key = topic.strip().lower()
    if key in DEFAULT_WORDS:
        return DEFAULT_WORDS[key]

    prompt = f"""
Choose the 12 most important vocabulary words for a school agriculture vocabulary pre-assessment.
Topic: {topic}
Return only the 12 words, one per line. No definitions.
"""
    response = client.responses.create(
        model="gpt-5.5",
        input=prompt,
    )
    words = [w.strip("-• 1234567890. ") for w in response.output_text.splitlines() if w.strip()]
    return words[:12]

def generate_image_for_word(word, topic):
    prompt = f"""
Photorealistic educational image for the vocabulary word "{word}".
Topic: {topic}.
Clear, realistic, age-appropriate school worksheet image.
No text, no labels, no cartoons, no icons.
"""
    result = client.images.generate(
        model="gpt-image-2",
        prompt=prompt,
        size="1024x1024"
    )
    b64 = result.data[0].b64_json
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")

def fit_image(img, box):
    x1, y1, x2, y2 = box
    target_w = x2 - x1
    target_h = y2 - y1
    img.thumbnail((target_w, target_h))
    canvas = Image.new("RGB", (target_w, target_h), "white")
    px = (target_w - img.width) // 2
    py = (target_h - img.height) // 2
    canvas.paste(img, (px, py))
    return canvas

def cover(draw, box, fill="white"):
    draw.rectangle(box, fill=fill)

def write_center(draw, text, box, font, fill="black"):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2), text, font=font, fill=fill)

def populate_page(template_img, year, topic, words, images, page_num):
    img = template_img.copy()
    draw = ImageDraw.Draw(img)

    title_font = load_font(36, bold=True)
    word_font = load_font(24, bold=True)

    title = f"PRE ASSESSMENT for Year {year} {topic}"

    # Cover and replace title
    cover(draw, TITLE_BOX)
    write_center(draw, title, TITLE_BOX, title_font, fill=(90, 40, 120))

    for i, word in enumerate(words):
        cover(draw, WORD_BOXES[i])
        write_center(draw, word, WORD_BOXES[i], word_font)

        cover(draw, IMAGE_BOXES[i])
        fitted = fit_image(images[i], IMAGE_BOXES[i])
        img.paste(fitted, IMAGE_BOXES[i][:2])

    return img

def make_pdf(pages):
    pdf_bytes = io.BytesIO()
    pages[0].save(
        pdf_bytes,
        format="PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=OUTPUT_DPI
    )
    pdf_bytes.seek(0)
    return pdf_bytes

st.title("Fixed Gardening Template Vocabulary Generator")

st.warning("Template is locked. Only title, vocab words, and images are replaced.")

year = st.text_input("Year level", "8")
topic = st.text_input("Subject/topic", "Australian Cropping")
word_mode = st.radio("Words", ["You choose 12", "I will enter 12 words"])

manual_words = ""
if word_mode == "I will enter 12 words":
    manual_words = st.text_area("Enter 12 words, one per line")

if st.button("Generate worksheet"):
    if not os.path.exists(TEMPLATE_PATH):
        st.error("Missing templates/master_template.pdf")
        st.stop()

    with st.spinner("Preparing words..."):
        if word_mode == "You choose 12":
            words = choose_words(topic)
        else:
            words = [w.strip() for w in manual_words.splitlines() if w.strip()][:12]

    if len(words) != 12:
        st.error("Exactly 12 words are needed.")
        st.stop()

    st.write("Using words:", ", ".join(words))

    with st.spinner("Rendering locked template..."):
        template_pages = render_pdf_pages()

    with st.spinner("Generating images..."):
        generated_images = [generate_image_for_word(word, topic) for word in words]

    page1_words = words[:6]
    page2_words = words[6:]
    page1_images = generated_images[:6]
    page2_images = generated_images[6:]

    with st.spinner("Populating fixed template..."):
        page1 = populate_page(template_pages[0], year, topic, page1_words, page1_images, 1)
        page2 = populate_page(template_pages[1], year, topic, page2_words, page2_images, 2)
        pdf = make_pdf([page1, page2])

    st.success("Done.")

    col1, col2 = st.columns(2)
    with col1:
        st.image(page1, caption="Page 1", use_container_width=True)
    with col2:
        st.image(page2, caption="Page 2", use_container_width=True)

    p1 = io.BytesIO()
    p2 = io.BytesIO()
    page1.save(p1, format="PNG")
    page2.save(p2, format="PNG")

    st.download_button("Download Page 1 PNG", p1.getvalue(), "page_1.png", "image/png")
    st.download_button("Download Page 2 PNG", p2.getvalue(), "page_2.png", "image/png")
    st.download_button("Download Combined PDF", pdf.getvalue(), "vocab_pre_assessment.pdf", "application/pdf")
