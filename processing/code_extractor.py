import re
# PS Store voucher codes are generally 12 alphanumeric characters.
# Accept separators commonly inserted by OCR/transcription.
TOKEN = re.compile(r'(?<![A-Z0-9])([A-Z0-9]{4})[\s\-]?([A-Z0-9]{4})[\s\-]?([A-Z0-9]{4})(?![A-Z0-9])', re.I)
DIGIT_WORDS = {
    "zero":"0","oh":"0","o":"0","one":"1","two":"2","to":"2","too":"2",
    "three":"3","four":"4","for":"4","five":"5","six":"6","seven":"7",
    "eight":"8","ate":"8","nine":"9"
}
def normalize_spoken(text):
    words = text.lower().replace(",", " ").replace(".", " ").split()
    out = []
    for word in words:
        clean = re.sub(r'[^a-z0-9]', '', word)
        out.append(DIGIT_WORDS.get(clean, clean.upper()))
    return " ".join(out)

def extract_codes(text, source=""):
    candidates = []
    for match in TOKEN.finditer(text.upper()):
        code = "".join(match.groups())
        # Require at least one digit to avoid flagging ordinary 12-letter words.
        if len(code) == 12 and any(c.isdigit() for c in code):
            candidates.append((f"{code[:4]}-{code[4:8]}-{code[8:]}", 0.95 if "OCR" in source else 0.90))
    if "Audio" in source:
        normalized = normalize_spoken(text)
        for match in TOKEN.finditer(normalized):
            code = "".join(match.groups())
            if len(code) == 12 and any(c.isdigit() for c in code):
                candidates.append((f"{code[:4]}-{code[4:8]}-{code[8:]}", 0.78))
    # unique within this text
    return list(dict((c, conf) for c, conf in candidates).items())
