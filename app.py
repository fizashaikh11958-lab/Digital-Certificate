"""
Certificate System (Streamlit)
Create certificates, make many at once, and verify them with a certificate ID.

Run locally:  streamlit run app.py
"""
import io
import os
import re
import zipfile
from datetime import date, datetime

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

try:
    import qrcode
except ImportError:  # the app still works without QR codes
    qrcode = None

REGISTRY = "certificates.csv"
REG_COLUMNS = ["cert_id", "name", "course", "cert_date", "issuer", "signer", "issued_on"]
W, H = 1754, 1240  # A4 landscape

THEMES = {
    "Royal Blue": {"main": (25, 55, 120), "accent": (190, 150, 60), "bg": (253, 251, 244)},
    "Forest Green": {"main": (25, 90, 60), "accent": (180, 140, 50), "bg": (251, 253, 246)},
    "Maroon": {"main": (120, 25, 40), "accent": (190, 150, 60), "bg": (254, 250, 246)},
}

FONT_PATHS = {
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"],
    "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"],
    "italic": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"],
}


# ---------------------------------------------------------------------------
# Certificate drawing
# ---------------------------------------------------------------------------
def get_font(kind, size):
    for p in FONT_PATHS[kind]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def centered(draw, text, y, kind, size, color, max_width=None):
    font = get_font(kind, size)
    while max_width and size > 20 and draw.textbbox((0, 0), text, font=font)[2] > max_width:
        size -= 4
        font = get_font(kind, size)
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((W - (box[2] - box[0])) / 2, y), text, font=font, fill=color)


def make_certificate(name, course, cert_date, issuer, signer, cert_id,
                     cert_title="Certificate of Completion", theme="Royal Blue"):
    t = THEMES[theme]
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)

    # Borders
    d.rectangle([30, 30, W - 30, H - 30], outline=t["main"], width=14)
    d.rectangle([62, 62, W - 62, H - 62], outline=t["accent"], width=4)
    for x, y in [(90, 90), (W - 90, 90), (90, H - 90), (W - 90, H - 90)]:
        d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=t["accent"])

    # Title
    line1, _, line2 = cert_title.upper().partition(" OF ")
    centered(d, line1, 150, "bold", 110, t["main"], 1300)
    if line2:
        centered(d, "OF " + line2, 290, "bold", 46, t["accent"], 1300)
    d.line([W / 2 - 250, 370, W / 2 + 250, 370], fill=t["accent"], width=4)

    # Body
    centered(d, "This certificate is proudly presented to", 430, "italic", 38, (70, 70, 70))
    centered(d, name, 510, "bold", 120, t["main"], 1350)
    d.line([W / 2 - 480, 665, W / 2 + 480, 665], fill=t["accent"], width=3)
    centered(d, "for successfully completing", 710, "italic", 38, (70, 70, 70))
    centered(d, course, 780, "bold", 66, (40, 40, 40), 1400)
    centered(d, f"Date: {cert_date}", 920, "regular", 36, (70, 70, 70))
    centered(d, f"Issued by {issuer}", 975, "regular", 32, (70, 70, 70), 1200)

    # Signature (left)
    d.line([200, 1030, 620, 1030], fill=(60, 60, 60), width=3)
    d.text((200, 1042), signer, font=get_font("bold", 34), fill=(40, 40, 40))
    d.text((200, 1090), "Authorized Signatory", font=get_font("italic", 26), fill=(100, 100, 100))

    # QR code + ID (right)
    if qrcode is not None:
        qr = qrcode.QRCode(box_size=5, border=1)
        qr.add_data(cert_id)
        qr.make(fit=True)
        q = qr.make_image(fill_color="black", back_color="white")
        q = getattr(q, "get_image", lambda: q)().convert("RGB").resize((170, 170))
        img.paste(q, (W - 200 - 170, 925))
    d.text((W - 400 - 170 / 2 - 95, 1105), cert_id, font=get_font("regular", 26), fill=(60, 60, 60))
    return img


def to_png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def to_pdf(img):
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=150)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Registry (saved in a CSV file)
# ---------------------------------------------------------------------------
def load_registry():
    if os.path.exists(REGISTRY):
        return pd.read_csv(REGISTRY, dtype=str).fillna("")
    return pd.DataFrame(columns=REG_COLUMNS)


def next_id(reg):
    year = datetime.now().year
    nums = [int(m.group(1)) for c in reg["cert_id"]
            if (m := re.match(rf"CERT-{year}-(\d+)$", str(c)))]
    return f"CERT-{year}-{(max(nums) if nums else 0) + 1:04d}"


def add_record(rec):
    reg = load_registry()
    reg = pd.concat([reg, pd.DataFrame([rec])], ignore_index=True)
    reg.to_csv(REGISTRY, index=False)


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_") or "certificate"


def issue(name, course, cert_date, issuer, signer, cert_title, theme):
    """Create a certificate, save its record and return (id, image)."""
    reg = load_registry()
    cid = next_id(reg)
    img = make_certificate(name, course, cert_date, issuer, signer, cid, cert_title, theme)
    add_record({"cert_id": cid, "name": name, "course": course, "cert_date": cert_date,
                "issuer": issuer, "signer": signer,
                "issued_on": datetime.now().strftime("%Y-%m-%d %H:%M")})
    return cid, img


# ===== UI starts here =====================================================
st.set_page_config(page_title="Certificate System", page_icon="🎓", layout="wide")
st.title("🎓 Certificate System")
st.caption("Create certificates, generate many at once, and verify them with a certificate ID.")

with st.sidebar:
    st.header("Certificate settings")
    cert_title = st.selectbox("Certificate type", [
        "Certificate of Completion", "Certificate of Achievement",
        "Certificate of Participation", "Certificate of Appreciation",
        "Certificate of Excellence"])
    theme = st.selectbox("Colour theme", list(THEMES))
    issuer = st.text_input("Organisation / College", "Your College Name")
    signer = st.text_input("Signatory name", "Head of Department")
    cert_date = st.date_input("Certificate date", date.today()).strftime("%d %B %Y")

tab1, tab2, tab3, tab4 = st.tabs(["🖊️ Create", "📦 Bulk create", "🔍 Verify", "📋 All certificates"])

# ---- Single certificate ----
with tab1:
    c1, c2 = st.columns(2)
    name = c1.text_input("Recipient name", "Student Name")
    course = c2.text_input("Course / Event / Achievement", "Python Programming Workshop")
    if st.button("✨ Generate certificate", type="primary"):
        if not name.strip() or not course.strip():
            st.error("Please enter the recipient name and the course.")
        else:
            cid, img = issue(name.strip(), course.strip(), cert_date, issuer, signer, cert_title, theme)
            st.session_state.cert = {"id": cid, "name": name.strip(),
                                     "png": to_png(img), "pdf": to_pdf(img)}
    cert = st.session_state.get("cert")
    if cert:
        st.success(f"Certificate created. ID: **{cert['id']}**")
        st.image(cert["png"])
        d1, d2 = st.columns(2)
        base = f"{cert['id']}_{safe_name(cert['name'])}"
        d1.download_button("⬇️ Download PNG", cert["png"], f"{base}.png", "image/png")
        d2.download_button("⬇️ Download PDF", cert["pdf"], f"{base}.pdf", "application/pdf")

# ---- Bulk ----
with tab2:
    st.write("Make many certificates at once (maximum 100). Use the same course for all.")
    course_b = st.text_input("Course / Event / Achievement", "Python Programming Workshop", key="course_b")
    src = st.radio("Names from", ["Type names", "Upload CSV (column: name)"], horizontal=True)
    names = []
    if src.startswith("Type"):
        text = st.text_area("One name per line", "Student One\nStudent Two\nStudent Three", height=150)
        names = [n.strip() for n in text.splitlines() if n.strip()]
    else:
        up = st.file_uploader("CSV file with a 'name' column", type="csv")
        if up is not None:
            df = pd.read_csv(up)
            col = next((c for c in df.columns if c.strip().lower() == "name"), None)
            if col is None:
                st.error("The CSV needs a column called 'name'.")
            else:
                names = [str(n).strip() for n in df[col].dropna() if str(n).strip()]
    st.write(f"**{len(names)}** name(s) ready.")
    fmt = st.radio("File format", ["PNG", "PDF"], horizontal=True)
    if st.button("📦 Generate all", type="primary", disabled=not names):
        names = names[:100]
        zbuf = io.BytesIO()
        bar = st.progress(0)
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
            for i, n in enumerate(names):
                cid, img = issue(n, course_b, cert_date, issuer, signer, cert_title, theme)
                z.writestr(f"{cid}_{safe_name(n)}.{fmt.lower()}",
                           to_png(img) if fmt == "PNG" else to_pdf(img))
                bar.progress((i + 1) / len(names))
        st.session_state.zip = zbuf.getvalue()
        st.session_state.zip_count = len(names)
    if st.session_state.get("zip"):
        st.success(f"{st.session_state.zip_count} certificates created.")
        st.download_button("⬇️ Download ZIP", st.session_state.zip, "certificates.zip", "application/zip")

# ---- Verify ----
with tab3:
    st.write("Enter the certificate ID (printed on the certificate, also inside the QR code).")
    vid = st.text_input("Certificate ID", placeholder="CERT-2026-0001").strip().upper()
    if st.button("🔍 Verify"):
        reg = load_registry()
        hit = reg[reg["cert_id"].str.upper() == vid] if vid else reg.iloc[0:0]
        if len(hit):
            r = hit.iloc[0]
            st.success("✅ Valid certificate")
            st.write(f"**Name:** {r['name']}")
            st.write(f"**Course:** {r['course']}")
            st.write(f"**Date:** {r['cert_date']}")
            st.write(f"**Issued by:** {r['issuer']}")
        else:
            st.error("❌ Certificate not found. It may be fake or the ID is wrong.")

# ---- All records ----
with tab4:
    reg = load_registry()
    st.metric("Certificates issued", len(reg))
    if len(reg):
        search = st.text_input("Search by name or ID")
        view = reg
        if search:
            mask = reg.apply(lambda c: c.str.contains(search, case=False, regex=False)).any(axis=1)
            view = reg[mask]
        st.dataframe(view, hide_index=True)
        st.download_button("⬇️ Download records (CSV)", reg.to_csv(index=False).encode(),
                           "certificates.csv", "text/csv")
    else:
        st.info("No certificates yet.")
    restore = st.file_uploader("Restore records from a saved CSV (after the app restarts)", type="csv")
    if restore is not None and st.button("Restore records"):
        old = pd.read_csv(restore, dtype=str).fillna("")
        if all(c in old.columns for c in REG_COLUMNS):
            old[REG_COLUMNS].to_csv(REGISTRY, index=False)
            st.success("Records restored.")
        else:
            st.error("This CSV does not look like a records file.")
    st.caption("On free hosting, records are cleared when the app restarts, so download the CSV "
               "regularly and restore it later.")
